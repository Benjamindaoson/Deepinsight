"""Discover the canonical, project-local business Skill registry.

The registry deliberately reads the files used by Agno's ``LocalSkills``
loader.  API metadata therefore cannot drift into a second hand-maintained
list of Skills.
"""

from __future__ import annotations

from pathlib import Path


APP = Path(__file__).resolve().parents[1]
SKILLS_ROOT = APP / "product_skills"


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Skill lacks YAML frontmatter: {path}")
    try:
        header = text.split("---\n", 2)[1]
    except IndexError as exc:
        raise ValueError(f"Skill has incomplete YAML frontmatter: {path}") from exc
    metadata: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    if not metadata.get("name") or not metadata.get("description"):
        raise ValueError(f"Skill requires name and description: {path}")
    return metadata


def discover_skills() -> list[dict]:
    """Return contracts for every Skill the runtime can actually load."""
    contracts = []
    for path in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        metadata = _frontmatter(path)
        contracts.append({
            "name": metadata["name"],
            "description": metadata["description"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "minLength": 1},
                    "context": {"type": "object"},
                },
                "required": ["question"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"enum": ["available", "insufficient", "error"]},
                    "data": {},
                    "sources": {"type": "array"},
                    "as_of": {"type": ["string", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "disclaimer": {"type": "string"},
                },
                "required": ["status", "sources", "as_of", "disclaimer"],
            },
            "file": path.relative_to(APP.parent).as_posix(),
        })
    return contracts


def validate_registry() -> list[dict]:
    skills = discover_skills()
    names = [item["name"] for item in skills]
    if not skills:
        raise ValueError("No Skills found in canonical registry")
    if len(names) != len(set(names)):
        raise ValueError("Duplicate Skill names in canonical registry")
    return skills
