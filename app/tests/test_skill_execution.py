"""Offline adapter acceptance against real Agno loaders and canonical business Skills."""
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from agno.skills import LocalSkills, Skills


SKILL_ROOT = Path(__file__).parents[1] / 'product_skills'


def adapter(tmp_path, *, skill_root=SKILL_ROOT):
    # Deliberately use the installed SDK and real on-disk Skill packages.
    from london_product.skill_execution import AuditedSkillLoader
    native = Skills(loaders=[LocalSkills(str(skill_root))])
    return AuditedSkillLoader(native, tmp_path / 'skill-ledgers', skill_root=skill_root), native


def receipts(tmp_path):
    return [json.loads(path.read_text(encoding='utf-8'))
            for path in (tmp_path / 'skill-ledgers').glob('*.json')]


def test_selected_business_guidance_and_policy_gate_are_loaded_via_real_sdk(tmp_path):
    loader, native = adapter(tmp_path)
    result = loader.load(['analysis', 'comparison'], run_id='real-run', session_id='real-session')
    assert result['status'] == 'loaded'
    assert result['requested_skills'] == ['analysis', 'comparison']
    assert result['policy_added_skills'] == ['verification']
    assert [item['name'] for item in result['skills']] == ['analysis', 'comparison', 'verification']
    for item in result['skills']:
        full = json.loads(native._get_skill_instructions(item['name']))['instructions']
        for heading in ['Input', 'Workflow', 'Output', 'Safety Mechanisms']:
            start = full.index('## ' + heading + '\n')
            end = full.find('\n## ', start + 1)
            section = full[start:end if end != -1 else len(full)].strip()
            assert section in item['instructions']
        assert '## Quick Start' not in item['instructions']
        assert '## Examples' not in item['instructions']
    assert result['runtime_contract'].count('## Evidence and publication') == 1
    assert '## Input and output precedence' in result['runtime_contract']
    assert '## Budget, failure and delivery' in result['runtime_contract']
    assert 'Real interfaces and side effects' not in result['runtime_contract']
    receipt, = receipts(tmp_path)
    assert receipt['run_id'] == 'real-run'
    assert receipt['session_id'] == 'real-session'
    assert receipt['requested_skills'] == ['analysis', 'comparison']
    assert receipt['policy_added_skills'] == ['verification']
    assert len(receipt['sdk_calls']) == 6
    for source in receipt['sources']:
        folder = SKILL_ROOT / source['name']
        assert source['source_path'] == str((folder / 'SKILL.md').resolve())
        assert source['source_sha256'] == hashlib.sha256((folder / 'SKILL.md').read_bytes()).hexdigest()
        assert source['reference_sha256'] == hashlib.sha256((folder / 'references/runtime-contract.md').read_bytes()).hexdigest()
        instructions = json.loads(native._get_skill_instructions(source['name']))['instructions']
        assert source['instructions_sha256'] == hashlib.sha256(instructions.encode()).hexdigest()
    projection = {key: value for key, value in result.items() if key not in {'audit_id', 'projection_sha256'}}
    encoded = json.dumps(projection, ensure_ascii=False, separators=(',', ':')).encode()
    assert result['projection_sha256'] == hashlib.sha256(encoded).hexdigest()
    assert receipt['projection_sha256'] == result['projection_sha256']


def test_maximum_domain_selection_is_compact_complete_and_not_all_skills(tmp_path):
    loader, _ = adapter(tmp_path)
    result = loader.load(['fact-extraction', 'alerting', 'reporting'])
    assert result['status'] == 'loaded'
    assert len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) <= 14336
    assert len(result['skills']) == 4
    assert '## Workflow' in result['skills'][-1]['instructions']


def test_explicit_verification_remains_model_requested_not_policy_claimed(tmp_path):
    loader, _ = adapter(tmp_path)
    result = loader.load(['analysis', 'verification'])
    assert result['requested_skills'] == ['analysis', 'verification']
    assert result['policy_added_skills'] == []
    assert [item['name'] for item in result['skills']].count('verification') == 1


@pytest.mark.parametrize('selection', [[], ['../analysis'], ['Analysis'], ['not-a-skill'],
                                       ['analysis', 'analysis'], 'analysis',
                                       ['analysis', 'comparison', 'reporting', 'alerting']])
def test_invalid_or_excessive_model_selection_fails_closed_without_sdk_access(tmp_path, selection):
    loader, _ = adapter(tmp_path)
    result = loader.load(selection, run_id='../../outside')
    assert result['status'] == 'blocked'
    assert 'skills' not in result
    receipt, = receipts(tmp_path)
    assert receipt['sdk_calls'] == []
    assert len(list((tmp_path / 'skill-ledgers').glob('*.json'))) == 1
    assert not (tmp_path / 'outside').exists()


def test_missing_reference_fails_closed_and_preserves_actual_sdk_error_attempt(tmp_path):
    root = tmp_path / 'packages'
    for name in ['analysis', 'verification']:
        shutil.copytree(SKILL_ROOT / name, root / name)
    (root / 'analysis/references/runtime-contract.md').unlink()
    loader, _ = adapter(tmp_path, skill_root=root)
    result = loader.load(['analysis'])
    assert result['status'] == 'blocked'
    assert 'skills' not in result
    receipt, = receipts(tmp_path)
    assert any(call['method'] == '_get_skill_reference' and call['status'] == 'error'
               for call in receipt['sdk_calls'])


def test_stale_sdk_cache_cannot_be_audited_as_current_source(tmp_path):
    root = tmp_path / 'packages'
    for name in ['analysis', 'verification']:
        shutil.copytree(SKILL_ROOT / name, root / name)
    loader, _ = adapter(tmp_path, skill_root=root)
    path = root / 'analysis/SKILL.md'
    path.write_text(path.read_text(encoding='utf-8').replace('## Workflow', '## Stale Workflow'), encoding='utf-8')
    result = loader.load(['analysis'])
    assert result['status'] == 'blocked'
    assert result['error_code'] == 'source_instructions_mismatch'


def test_divergent_selected_runtime_contracts_are_not_silently_deduplicated(tmp_path):
    root = tmp_path / 'packages'
    for name in ['analysis', 'verification']:
        shutil.copytree(SKILL_ROOT / name, root / name)
    reference = root / 'analysis/references/runtime-contract.md'
    reference.write_text(reference.read_text(encoding='utf-8').replace(
        '## Evidence and publication\n', '## Evidence and publication\n\nChanged gate.\n'), encoding='utf-8')
    loader, _ = adapter(tmp_path, skill_root=root)
    result = loader.load(['analysis'])
    assert result['status'] == 'blocked'
    assert result['error_code'] == 'shared_contract_mismatch'
    assert 'skills' not in result


def test_oversized_operative_section_blocks_instead_of_truncating_guidance(tmp_path):
    root = tmp_path / 'packages'
    for name in ['analysis', 'verification']:
        shutil.copytree(SKILL_ROOT / name, root / name)
    source = root / 'analysis/SKILL.md'
    source.write_text(source.read_text(encoding='utf-8').replace(
        '## Workflow\n', '## Workflow\n\n' + ('Complete important instruction. ' * 600) + '\n'), encoding='utf-8')
    loader, _ = adapter(tmp_path, skill_root=root)
    result = loader.load(['analysis'])
    assert result['status'] == 'blocked'
    assert result['error_code'] == 'guidance_exceeds_context_budget'
    assert 'skills' not in result


@pytest.mark.parametrize('name', [path.name for path in SKILL_ROOT.iterdir() if (path / 'SKILL.md').exists()])
def test_every_canonical_business_package_can_be_loaded_on_demand(tmp_path, name):
    loader, _ = adapter(tmp_path)
    result = loader.load([name])
    assert result['status'] == 'loaded'
    assert result['skills'][0]['name'] == name
    assert result['policy_added_skills'] == ([] if name == 'verification' else ['verification'])


def test_concurrent_calls_have_distinct_atomic_receipts_and_run_ids(tmp_path):
    loader, _ = adapter(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda index: loader.load(['comparison'], run_id=f'run-{index}'), range(8)))
    assert all(result['status'] == 'loaded' for result in results)
    assert len({result['audit_id'] for result in results}) == 8
    records = receipts(tmp_path)
    assert {record['run_id'] for record in records} == {f'run-{index}' for index in range(8)}
    assert not list((tmp_path / 'skill-ledgers').glob('*.tmp'))


def test_audit_write_failure_never_releases_guidance(tmp_path):
    from london_product.skill_execution import AuditedSkillLoader, SkillAuditError
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('file', encoding='utf-8')
    native = Skills(loaders=[LocalSkills(str(SKILL_ROOT))])
    loader = AuditedSkillLoader(native, blocked)
    with pytest.raises(SkillAuditError):
        loader.load(['analysis'])


def test_query_agent_exposes_only_load_and_evidence_business_operations(tmp_path):
    # A compare operation offered before loading evidence could write arbitrary
    # IDs despite the provider's forced tool choice. The report builder already
    # calculates bounded comparisons within the evidence operation.
    from types import SimpleNamespace
    from london_product.intelligence import query_agent
    service = SimpleNamespace(store=SimpleNamespace(root=tmp_path))
    agent = query_agent(service, None)
    assert {function.name for function in agent.tools} == {'load_market_skills', 'search_market_evidence'}
    assert agent.tool_call_limit == 2


def test_provider_must_complete_actual_skill_load_and_evidence_chain():
    from london_product.skill_execution import validate_skill_tool_chain
    import json, pytest
    loaded=dict(tool_name='load_market_skills',result=json.dumps(dict(status='loaded',audit_id='real-audit',projection_sha256='source-hash')))
    evidence=dict(tool_name='search_market_evidence',result='{}')
    validate_skill_tool_chain([loaded,evidence])
    for tools in [[],[evidence],[loaded],[evidence,loaded],[dict(tool_name='get_skill_instructions'),evidence],
                  [dict(loaded,result='{}'),evidence]]:
        with pytest.raises(ValueError,match='SKILL_EXECUTION_INCOMPLETE'):validate_skill_tool_chain(tools)


def test_real_agno_post_hook_propagates_invalid_execution_guard(tmp_path):
    import asyncio, pytest
    from types import SimpleNamespace
    from agno.agent._hooks import aexecute_post_hooks
    from agno.exceptions import OutputCheckError
    from agno.run import RunContext
    from london_product.intelligence import query_agent
    agent=query_agent(SimpleNamespace(store=SimpleNamespace(root=tmp_path)),None)
    async def execute():
        async for _ in aexecute_post_hooks(agent,agent.post_hooks,
            SimpleNamespace(tools=[],run_id='offline-invalid'),None,RunContext(run_id='offline-invalid',session_id='offline')):
            pass
    with pytest.raises(OutputCheckError,match='SKILL_EXECUTION_INCOMPLETE'):
        asyncio.run(execute())
