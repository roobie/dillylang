"""Skill directory ingestion boundary adapter.

Deterministic: parse, don't validate. Reads a Claude Code skill directory
and produces a typed SkillSourceBundle Artifact. No LLM calls, no budget
consumption.

Enforces ingestion limits per D-12: 50KB total content, 20 files max.
Truncation is always visible in the output, never silent.
If SKILL.md is missing or exceeds limits, ingestion fails.
"""

from __future__ import annotations

import re
from pathlib import Path

from dillylang.vocab.schemas import SkillFile, SkillSourceBundle, TruncationInfo
from dillylang.vocab.types import Artifact, ArtifactStatus

# Ingestion limits per D-12
MAX_TOTAL_BYTES = 50_000  # 50KB total content budget
MAX_FILES = 20  # Maximum files to ingest

# Tool invocation patterns (Claude Code built-in tools)
_TOOL_PATTERNS = re.compile(
    r"\b(Read|Write|Edit|Bash|MultiTool|TodoRead|TodoWrite|WebFetch|Glob|Grep|LS)\b"
)

# Control flow patterns indicating branching/looping/parallelism
_CONTROL_FLOW_PATTERNS = re.compile(
    r"\b(if|else|elif|for|while|loop|branch|parallel|subagent|spawn|delegate)\b",
    re.IGNORECASE,
)

# File kind priority for ingestion ordering (higher = read first)
_KIND_PRIORITY: dict[str, int] = {
    "skill_md": 100,
    "readme": 90,
    "claude_md": 80,
    "prompt": 70,
    "script": 60,
    "config": 50,
    "other": 40,
}


def _classify_file(relative_path: str) -> str:
    """Classify a file's role within a skill directory.

    Returns one of: skill_md, readme, claude_md, script, prompt, config, other.
    """
    name = Path(relative_path).name.lower()
    parts = Path(relative_path).parts

    # Exact filename matches (case-insensitive)
    if name == "skill.md":
        return "skill_md"
    if name == "readme.md":
        return "readme"
    if name == "claude.md":
        return "claude_md"

    # Directory-based classification
    lower_parts = [p.lower() for p in parts[:-1]]  # exclude filename

    if "scripts" in lower_parts:
        return "script"
    if "prompts" in lower_parts:
        return "prompt"

    # Extension-based classification
    suffix = Path(relative_path).suffix.lower()
    if suffix in {".sh", ".lua", ".py", ".bash", ".zsh"}:
        return "script"
    if suffix in {".prompt", ".txt"}:
        # .txt in prompts/ dir handled above; standalone .txt is ambiguous
        # but leans toward prompt in a skill context
        return "prompt"
    if suffix in {".toml", ".yaml", ".yml", ".json", ".cfg", ".ini"}:
        return "config"

    return "other"


def _detect_entrypoints(skill_md_content: str) -> list[dict[str, str]]:
    """Extract command entrypoints from SKILL.md content.

    Looks for /command-name patterns and ## Commands sections.
    """
    entrypoints: list[dict[str, str]] = []
    # Match /command-name patterns (slash-prefixed identifiers)
    for match in re.finditer(r"(?:^|\s)(/[\w-]+)", skill_md_content):
        cmd = match.group(1)
        if cmd not in [e["command"] for e in entrypoints]:
            entrypoints.append({"command": cmd, "declared_in": "SKILL.md"})
    return entrypoints


def _detect_tools(contents: list[str]) -> list[str]:
    """Detect tool invocations across all file contents."""
    tools: set[str] = set()
    for content in contents:
        tools.update(_TOOL_PATTERNS.findall(content))
    return sorted(tools)


def _detect_control_flow(contents: list[str]) -> list[str]:
    """Detect control flow patterns across all file contents."""
    patterns: set[str] = set()
    for content in contents:
        patterns.update(m.lower() for m in _CONTROL_FLOW_PATTERNS.findall(content))
    return sorted(patterns)


def ingest_skill_directory(path: str | Path) -> Artifact:
    """Parse a Claude Code skill directory into a SkillSourceBundle Artifact.

    Deterministic boundary adapter: reads filesystem, classifies files,
    enforces size/count limits, returns typed Artifact.

    Args:
        path: Path to the skill directory (absolute or relative).

    Returns:
        Artifact wrapping a SkillSourceBundle in its data field.

    Raises:
        ValueError: If path does not exist or is not a directory.
    """
    resolved_path = Path(path).resolve()
    if not resolved_path.exists():
        raise ValueError(f"Directory does not exist: {resolved_path}")
    if not resolved_path.is_dir():
        raise ValueError(f"Path is not a directory: {resolved_path}")

    # Step 1: Find SKILL.md (case-insensitive)
    skill_md_path: Path | None = None
    for item in resolved_path.iterdir():
        if item.is_file() and item.name.lower() == "skill.md":
            skill_md_path = item
            break

    if skill_md_path is None:
        # SKILL.md missing => ingestion fails
        bundle = SkillSourceBundle(
            path=str(resolved_path),
            files=[],
            ingestion_status="failed",
            truncation=TruncationInfo(
                occurred=True,
                reason="SKILL.md not found in directory",
            ),
        )
        return Artifact(
            id="ingest_0",
            operator="ingest_skill_directory",
            step_index=0,
            data=bundle.model_dump(),
            status=ArtifactStatus.FAILED,
        )

    # Step 2: Read SKILL.md first (priority per D-12, Pitfall 5)
    skill_md_content = skill_md_path.read_text(encoding="utf-8", errors="replace")
    skill_md_bytes = len(skill_md_content.encode("utf-8"))

    if skill_md_bytes > MAX_TOTAL_BYTES:
        # SKILL.md itself exceeds limit => fail
        bundle = SkillSourceBundle(
            path=str(resolved_path),
            files=[],
            ingestion_status="failed",
            truncation=TruncationInfo(
                occurred=True,
                bytes_dropped=skill_md_bytes - MAX_TOTAL_BYTES,
                reason="SKILL.md exceeds ingestion limit",
            ),
        )
        return Artifact(
            id="ingest_0",
            operator="ingest_skill_directory",
            step_index=0,
            data=bundle.model_dump(),
            status=ArtifactStatus.FAILED,
        )

    # Step 3: Discover all files (non-recursive first level + recursive subdirs)
    all_files: list[tuple[Path, str]] = []  # (absolute_path, relative_path_str)
    for item in sorted(resolved_path.rglob("*")):
        if item.is_file():
            rel = str(item.relative_to(resolved_path))
            all_files.append((item, rel))

    # Step 4: Classify and sort by priority (SKILL.md already read)
    classified: list[tuple[Path, str, str]] = []  # (abs_path, rel_path, kind)
    for abs_path, rel_path in all_files:
        kind = _classify_file(rel_path)
        classified.append((abs_path, rel_path, kind))

    # Sort by kind priority (descending), SKILL.md first
    classified.sort(key=lambda x: (-_KIND_PRIORITY.get(x[2], 0), x[1]))

    # Step 5: Read files respecting limits
    skill_files: list[SkillFile] = []
    cumulative_bytes = skill_md_bytes
    files_dropped: list[str] = []
    bytes_dropped = 0
    ingestion_status = "success"

    # Add SKILL.md first
    skill_md_rel = str(skill_md_path.relative_to(resolved_path))
    skill_files.append(
        SkillFile(path=skill_md_rel, kind="skill_md", content=skill_md_content)
    )

    for abs_path, rel_path, kind in classified:
        # Skip SKILL.md (already added)
        if kind == "skill_md":
            continue

        # File count limit
        if len(skill_files) >= MAX_FILES:
            try:
                file_bytes = abs_path.stat().st_size
            except OSError:
                file_bytes = 0
            files_dropped.append(rel_path)
            bytes_dropped += file_bytes
            ingestion_status = "partial"
            continue

        # Read file content
        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            files_dropped.append(rel_path)
            ingestion_status = "partial"
            continue

        file_bytes = len(content.encode("utf-8"))

        # Byte limit check
        if cumulative_bytes + file_bytes > MAX_TOTAL_BYTES:
            files_dropped.append(rel_path)
            bytes_dropped += file_bytes
            ingestion_status = "partial"
            continue

        cumulative_bytes += file_bytes
        skill_files.append(SkillFile(path=rel_path, kind=kind, content=content))

    # Remaining unprocessed files also count as dropped
    # (already handled in the loop above)

    # Step 6: Detect entrypoints from SKILL.md
    entrypoints = _detect_entrypoints(skill_md_content)

    # Step 7: Detect scripts, prompts, tools, control flow
    detected_scripts = [f.path for f in skill_files if f.kind == "script"]
    detected_prompts = [f.path for f in skill_files if f.kind == "prompt"]
    all_contents = [f.content for f in skill_files]
    detected_tools = _detect_tools(all_contents)
    detected_control_flow = _detect_control_flow(all_contents)

    # Step 8: Build truncation info
    truncation = TruncationInfo(
        occurred=bool(files_dropped),
        files_dropped=files_dropped,
        bytes_dropped=bytes_dropped,
        reason="exceeded 50KB/20-file ingestion limit" if files_dropped else "",
    )

    # Step 9: Construct bundle and artifact
    bundle = SkillSourceBundle(
        path=str(resolved_path),
        files=skill_files,
        entrypoints=entrypoints,
        detected_scripts=detected_scripts,
        detected_prompts=detected_prompts,
        detected_tools=detected_tools,
        detected_control_flow=detected_control_flow,
        ingestion_status=ingestion_status,
        truncation=truncation,
    )

    artifact_status = (
        ArtifactStatus.SUCCESS
        if ingestion_status == "success"
        else ArtifactStatus.PARTIAL
    )

    return Artifact(
        id="ingest_0",
        operator="ingest_skill_directory",
        step_index=0,
        data=bundle.model_dump(),
        status=artifact_status,
    )
