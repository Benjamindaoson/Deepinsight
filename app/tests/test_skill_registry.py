from pathlib import Path

from london_product.intelligence import APP, native_skills
from london_product.skill_registry import SKILLS_ROOT, validate_registry


def test_runtime_has_one_canonical_skill_root():
    assert SKILLS_ROOT == APP / "product_skills"
    assert not (APP / "skills").exists()
    assert not (APP.parent / "skills" / "market_skills.py").exists()


def test_every_canonical_skill_has_machine_readable_contract():
    skills = validate_registry()
    disk_files = sorted(SKILLS_ROOT.glob("*/SKILL.md"))
    assert len(skills) == len(disk_files) >= 10
    for skill in skills:
        assert skill["input_schema"]["required"] == ["question"]
        assert "sources" in skill["output_schema"]["required"]
        assert Path(APP.parent / skill["file"]).is_file()


def test_agno_loader_sees_every_canonical_skill_and_instructions():
    registry_names = {item["name"] for item in validate_registry()}
    loaded = native_skills()
    assert set(loaded.get_skill_names()) == registry_names
    assert len(loaded.get_all_skills()) == len(registry_names)
    prompt = loaded.get_system_prompt_snippet()
    assert "alerting" in prompt
    assert "verification" in prompt
