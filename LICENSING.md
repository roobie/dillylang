---
id: dillylang::licensing
description: Per-path license mapping for the dual-licensed dillylang repository
tags: [licensing, meta, governance]
created: 2026-05-11
status: active
---

# Licensing

Dillylang is dual-licensed. Code is under **Apache License 2.0**; written
documentation (the spec, ADRs, references, top-level guides) is under
**Creative Commons Attribution 4.0 International** (CC BY 4.0).

The full text of each licenses lives in [`LICENSE.apache20.txt`](LICENSE.apache20.txt) and
[`LICENSE.ccby40.txt`](LICENSE.ccby40.txt) respectively.

## Per-path mapping

| Path                                                          | License    | SPDX         |
|---------------------------------------------------------------|------------|--------------|
| `src/`                                                        | Apache-2.0 | `Apache-2.0` |
| `tests/`                                                      | Apache-2.0 | `Apache-2.0` |
| `skills/`                                                     | Apache-2.0 | `Apache-2.0` |
| `scripts/`                                                    | Apache-2.0 | `Apache-2.0` |
| `pyproject.toml`, `uv.lock`, `skills-lock.json`, `.gitignore` | Apache-2.0 | `Apache-2.0` |
| `spec/`                                                       | CC BY 4.0  | `CC-BY-4.0`  |
| `docs/`                                                       | CC BY 4.0  | `CC-BY-4.0`  |
| `README.md`, `AGENTS.md`, `CLAUDE.md`                         | CC BY 4.0  | `CC-BY-4.0`  |

When a file is ambiguous, the directory-level rule above governs. The
`skills/` directory is treated as code (functional inputs to a runtime),
not prose, even though its files are markdown.

## Why two licenses

- **Code** under Apache-2.0 to maximize adoption: corporate legal teams
  approve it without friction, the explicit patent grant covers
  contributors, and it's compatible with the broadest range of downstream
  use.
- **Docs and spec** under CC BY 4.0 because Apache-2.0 is awkwardly worded
  for prose. CC BY 4.0 is the standard choice for technical documentation
  (Python docs, React docs, libuv docs, Linux kernel docs in part) and
  permits any reuse with attribution.

## Per-file SPDX headers (optional)

Files may carry an inline SPDX identifier as the first non-shebang line.
This is purely informational — the directory rule above is authoritative.

```python
# SPDX-License-Identifier: Apache-2.0
```

```markdown
<!-- SPDX-License-Identifier: CC-BY-4.0 -->
```

## Contributions

By submitting a contribution, you agree to license it under the same terms
as the file(s) you modify (Apache-2.0 for code, CC BY 4.0 for docs). No
separate CLA is required.
