"""Authoring and runnable-package checks; never perform paid model evaluation."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'product_skills'
HELPER = SKILLS / 'scripts' / 'skill_helper.py'
REQUIRED = ['Capabilities','Input','Workflow','Quick Start','Output','Examples',
            'Safety Mechanisms','Dependencies','Runtime Integration']


@pytest.mark.parametrize('path', sorted(SKILLS.glob('*/SKILL.md')), ids=lambda p:p.parent.name)
def test_canonical_skill_has_a_usable_documented_contract(path):
    text = path.read_text(encoding='utf-8')
    missing = [title for title in REQUIRED if '\n## '+title+'\n' not in text]
    assert not missing, f'{path.parent.name}: missing {missing}'
    assert 'references/runtime-contract.md' in text
    header = text.split('---',2)[1]
    assert 'Use when' in header or 'Triggered when' in header


def helper_module():
    spec = importlib.util.spec_from_file_location('skill_helper', HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_lists_and_checks_the_real_packages():
    for args in [['list'],['check']]:
        run = subprocess.run([sys.executable,str(HELPER),*args],capture_output=True,text=True,encoding='utf-8')
        assert run.returncode == 0, run.stdout+run.stderr
        result = json.loads(run.stdout)
        assert result['count'] == len(list(SKILLS.glob('*/SKILL.md')))
    run = subprocess.run([sys.executable,str(HELPER),'show','comparison'],capture_output=True,text=True,encoding='utf-8')
    assert run.returncode == 0 and '# comparison' in run.stdout
    run = subprocess.run([sys.executable,str(HELPER),'show','../../secrets'],capture_output=True,text=True,encoding='utf-8')
    assert run.returncode != 0 and 'unknown skill' in run.stderr.lower()


def test_validator_rejects_missing_contract_and_broken_links(tmp_path):
    folder = tmp_path/'example';folder.mkdir()
    text='---\nname: example\ndescription: "Use when inspecting examples."\n---\n\n# example\n'
    (folder/'SKILL.md').write_text(text,encoding='utf-8')
    first=helper_module().inspect_registry(tmp_path)
    assert not first['valid']
    assert any('missing section' in x for x in first['skills'][0]['issues'])
    complete=text+'\n'.join('\n## '+title+'\n\nActual instructions.\n' for title in REQUIRED)
    complete+='\n[reference](missing.md)\n'
    (folder/'SKILL.md').write_text(complete,encoding='utf-8')
    second=helper_module().inspect_registry(tmp_path)
    assert any('missing local reference' in x for x in second['skills'][0]['issues'])


def test_real_agno_can_read_every_skills_runtime_reference():
    from london_product.intelligence import native_skills
    loaded = native_skills()
    for skill in loaded.get_all_skills():
        assert 'runtime-contract.md' in skill.references, skill.name
        result = json.loads(loaded._get_skill_reference(skill.name, 'runtime-contract.md'))
        assert 'error' not in result, result
        assert 'Input and output precedence' in result['content']
        assert 'Evidence and publication' in result['content']
