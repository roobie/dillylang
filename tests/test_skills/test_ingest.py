"""Tests for skill directory ingestion boundary adapter."""

from __future__ import annotations

import pytest

from dillylang.skills.ingest import ingest_skill_directory
from dillylang.vocab.types import ArtifactStatus


def test_ingest_valid_skill_directory(tmp_path):
    """Complete skill directory with SKILL.md, script, and prompt."""
    (tmp_path / "SKILL.md").write_text("# My Skill\n\nDoes stuff.\n/my-command\n")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "run.sh").write_text("#!/bin/bash\necho hello\n")
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "main.prompt").write_text("You are a helpful assistant.\n")

    result = ingest_skill_directory(tmp_path)

    assert result.status == ArtifactStatus.SUCCESS
    assert result.data["ingestion_status"] == "success"
    assert len(result.data["files"]) == 3
    # SKILL.md should be first (highest priority)
    assert result.data["files"][0]["kind"] == "skill_md"
    assert result.operator == "ingest_skill_directory"


def test_ingest_missing_skill_md(tmp_path):
    """Directory without SKILL.md results in failed ingestion."""
    (tmp_path / "README.md").write_text("# Some Readme\n")
    (tmp_path / "script.py").write_text("print('hello')\n")

    result = ingest_skill_directory(tmp_path)

    assert result.status == ArtifactStatus.FAILED
    assert result.data["ingestion_status"] == "failed"
    assert "SKILL.md" in result.data["truncation"]["reason"]


def test_ingest_truncation_visible(tmp_path):
    """Exceeding 50KB with multiple files triggers visible truncation."""
    # Small SKILL.md
    (tmp_path / "SKILL.md").write_text("# Skill\nBasic skill.\n")
    # Create enough large files to exceed 50KB
    for i in range(10):
        (tmp_path / f"large_{i}.py").write_text("x = 1\n" * 2000)  # ~12KB each

    result = ingest_skill_directory(tmp_path)

    assert result.status == ArtifactStatus.PARTIAL
    assert result.data["ingestion_status"] == "partial"
    assert result.data["truncation"]["occurred"] is True
    assert len(result.data["truncation"]["files_dropped"]) > 0


def test_ingest_skill_md_too_large(tmp_path):
    """SKILL.md exceeding 50KB causes ingestion failure."""
    # Create a SKILL.md larger than 50KB
    large_content = "# Huge Skill\n" + "x" * 60_000
    (tmp_path / "SKILL.md").write_text(large_content)

    result = ingest_skill_directory(tmp_path)

    assert result.status == ArtifactStatus.FAILED
    assert result.data["ingestion_status"] == "failed"
    assert "SKILL.md" in result.data["truncation"]["reason"]


def test_ingest_file_classification(tmp_path):
    """Each file type gets the correct kind classification."""
    (tmp_path / "SKILL.md").write_text("# Skill\n")
    (tmp_path / "README.md").write_text("# Readme\n")
    (tmp_path / "script.py").write_text("print('hi')\n")
    (tmp_path / "config.toml").write_text("[tool]\n")
    (tmp_path / "random.xyz").write_text("whatever\n")

    result = ingest_skill_directory(tmp_path)

    assert result.status == ArtifactStatus.SUCCESS
    files_by_path = {f["path"]: f["kind"] for f in result.data["files"]}
    assert files_by_path["SKILL.md"] == "skill_md"
    assert files_by_path["README.md"] == "readme"
    assert files_by_path["script.py"] == "script"
    assert files_by_path["config.toml"] == "config"
    assert files_by_path["random.xyz"] == "other"


def test_ingest_nonexistent_directory():
    """Nonexistent path raises ValueError."""
    with pytest.raises(ValueError, match="does not exist"):
        ingest_skill_directory("/nonexistent/path/to/skill")


def test_ingest_entrypoint_detection(tmp_path):
    """Commands in SKILL.md content are detected as entrypoints."""
    skill_content = """\
# My Tool Skill

This skill provides /my-command and /another-tool for processing.

## Commands

- /my-command: does the thing
- /another-tool: does another thing
"""
    (tmp_path / "SKILL.md").write_text(skill_content)

    result = ingest_skill_directory(tmp_path)

    assert result.status == ArtifactStatus.SUCCESS
    entrypoints = result.data["entrypoints"]
    commands = [e["command"] for e in entrypoints]
    assert "/my-command" in commands
    assert "/another-tool" in commands
    # All entrypoints declared in SKILL.md
    for ep in entrypoints:
        assert ep["declared_in"] == "SKILL.md"
