"""Audited, bounded projections of real Agno business Skill instructions.

This adapter reads documentation through the injected native Skills instance. It
does not dispatch business operations, approve evidence, or call a model.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


_OPERATIVE = ('Input', 'Workflow', 'Output', 'Safety Mechanisms')
_CONTRACT = ('Input and output precedence', 'Evidence and publication', 'Budget, failure and delivery')
_REFERENCE = 'runtime-contract.md'
_MAX_OUTPUT_BYTES = 14336
_MAX_RECEIPT_BYTES = 65536
_MAX_SOURCE_BYTES = 131072


class SkillAuditError(RuntimeError):
    """No guidance may be released when its audit receipt cannot be saved."""


def validate_skill_tool_chain(tools: list[dict]) -> None:
    """Provider tool_choice is advisory; verify completed execution before publishing."""
    if [item.get('tool_name') for item in tools] != ['load_market_skills', 'search_market_evidence']:
        raise ValueError('SKILL_EXECUTION_INCOMPLETE')
    if any(item.get('tool_call_error') for item in tools):
        raise ValueError('TOOL_ERROR')
    try:
        loaded = json.loads(tools[0].get('result') or '{}')
    except (ValueError, TypeError):
        raise ValueError('SKILL_EXECUTION_INCOMPLETE') from None
    if loaded.get('status') != 'loaded' or not loaded.get('audit_id') or not loaded.get('projection_sha256'):
        raise ValueError('SKILL_EXECUTION_INCOMPLETE')


class _LoadBlocked(Exception):
    pass


def _encode(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sections(text: str, headings: tuple[str, ...]) -> str:
    """Select complete verbatim H2 sections, never shortening a section."""
    matches = list(re.finditer(r'^## ([^\n]+)\n', text, re.MULTILINE))
    selected = {}
    for index, match in enumerate(matches):
        heading = match.group(1)
        if heading in headings:
            if heading in selected:
                raise _LoadBlocked('duplicate_operative_section')
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            selected[heading] = text[match.start():end].strip()
    if set(selected) != set(headings):
        raise _LoadBlocked('missing_operative_section')
    return '\n\n'.join(selected[heading] for heading in headings)


class AuditedSkillLoader:
    """Load at most three selected domain Skills plus the verification gate.

    ``native`` must be the actual ``native_skills()`` object. ``ledger_root`` is
    supplied by the caller (normally ``service.store.root / 'skill-ledgers'``).
    Each invocation saves a bounded, independent JSON receipt before returning.
    The optional source root permits isolated copies of the canonical packages
    in offline tests; production uses app/product_skills.
    """

    def __init__(self, native, ledger_root: str | Path, *, skill_root: str | Path | None = None):
        self.native = native
        self.ledger_root = Path(ledger_root).resolve()
        self.skill_root = Path(skill_root or Path(__file__).parents[1] / 'product_skills').resolve()

    def load(self, skill_names: list[str], *, run_id: str | None = None,
             session_id: str | None = None) -> dict:
        """Return operative source guidance, or an audited blocked result.

        Audit identity is generated locally, never derived from model/user path
        input. No tool/context object or arbitrary exception text is persisted.
        ``SkillAuditError`` is raised if the atomic receipt write fails.
        """
        audit_id = uuid4().hex
        receipt = dict(audit_id=audit_id, created_at=datetime.now(timezone.utc).isoformat(),
                       run_id=str(run_id)[:256] if run_id is not None else None,
                       session_id=str(session_id)[:256] if session_id is not None else None,
                       requested_skills=[], policy_added_skills=[], sources=[], sdk_calls=[])
        try:
            available = set(self.native.get_skill_names())
            # Retain valid canonical requests even when another argument is bad;
            # never log arbitrary model input (which could contain credentials).
            if isinstance(skill_names, list):
                receipt['requested_skills'] = [name for name in skill_names[:4]
                                               if isinstance(name, str) and name in available]
            if (not isinstance(skill_names, list) or not skill_names or len(skill_names) > 4
                    or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name)
                           or name not in available for name in skill_names)
                    or len(set(skill_names)) != len(skill_names)
                    or len([name for name in skill_names if name != 'verification']) > 3):
                raise _LoadBlocked('invalid_skill_selection')
            receipt['requested_skills'] = list(skill_names)
            receipt['policy_added_skills'] = [] if 'verification' in skill_names else ['verification']
            selected = skill_names + receipt['policy_added_skills']
            instructions = []
            common_contract = None
            for name in selected:
                item, contract = self._read_skill(name, receipt)
                instructions.append(item)
                if common_contract is not None and common_contract != contract:
                    raise _LoadBlocked('shared_contract_mismatch')
                common_contract = contract
            projection = dict(status='loaded', requested_skills=list(skill_names),
                              policy_added_skills=receipt['policy_added_skills'],
                              skills=instructions, runtime_contract=common_contract)
            if len(_encode(projection)) + 170 > _MAX_OUTPUT_BYTES:
                raise _LoadBlocked('guidance_exceeds_context_budget')
        except _LoadBlocked as error:
            projection = dict(status='blocked', error_code=str(error),
                              requested_skills=receipt['requested_skills'],
                              policy_added_skills=receipt['policy_added_skills'])
        except (OSError, ValueError, TypeError, AttributeError):
            projection = dict(status='blocked', error_code='skill_resource_unavailable',
                              requested_skills=receipt['requested_skills'],
                              policy_added_skills=receipt['policy_added_skills'])
        digest = _sha(_encode(projection))
        receipt.update(status=projection['status'], projection_sha256=digest,
                       projection_bytes=len(_encode(projection)))
        if 'error_code' in projection:
            receipt['error_code'] = projection['error_code']
        self._persist(receipt)
        return {**projection, 'audit_id': audit_id, 'projection_sha256': digest}

    def _sdk(self, name: str, method: str, receipt: dict) -> dict:
        call = dict(name=name, method=method, status='error')
        receipt['sdk_calls'].append(call)
        try:
            function = getattr(self.native, method)
            raw = function(name, _REFERENCE) if method == '_get_skill_reference' else function(name)
            if not isinstance(raw, str) or len(raw.encode()) > _MAX_SOURCE_BYTES:
                raise _LoadBlocked('invalid_sdk_response')
            call['returned_sha256'] = _sha(raw.encode())
            payload = json.loads(raw)
            if not isinstance(payload, dict) or 'error' in payload or payload.get('skill_name') != name:
                raise _LoadBlocked('sdk_resource_error')
            if method == '_get_skill_instructions':
                if (not isinstance(payload.get('instructions'), str)
                        or not isinstance(payload.get('available_references'), list)):
                    raise _LoadBlocked('invalid_sdk_response')
            elif payload.get('reference_path') != _REFERENCE or not isinstance(payload.get('content'), str):
                raise _LoadBlocked('invalid_sdk_response')
            call['status'] = 'loaded'
            return payload
        except _LoadBlocked:
            raise
        except Exception:
            # Never persist SDK error strings, document contents or credentials.
            raise _LoadBlocked('sdk_resource_error') from None

    def _read_skill(self, name: str, receipt: dict) -> tuple[dict, str]:
        skill = self.native.get_skill(name)
        if skill is None:
            raise _LoadBlocked('missing_policy_skill')
        folder = (self.skill_root / name).resolve()
        if (folder.parent != self.skill_root or Path(skill.source_path).resolve() != folder):
            raise _LoadBlocked('noncanonical_skill_source')
        source_path = (folder / 'SKILL.md').resolve()
        reference_path = (folder / 'references' / _REFERENCE).resolve()
        if not source_path.is_relative_to(folder) or not reference_path.is_relative_to(folder):
            raise _LoadBlocked('noncanonical_skill_source')
        source_receipt = dict(name=name, source_path=str(source_path), reference_path=str(reference_path))
        receipt['sources'].append(source_receipt)
        loaded = self._sdk(name, '_get_skill_instructions', receipt)
        source_bytes = self._read_bytes(source_path)
        source_receipt.update(source_sha256=_sha(source_bytes),
                              instructions_sha256=_sha(loaded['instructions'].encode()))
        source = source_bytes.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
        frontmatter = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', source, re.DOTALL)
        body = frontmatter.group(2).strip() if frontmatter else source
        if body != loaded['instructions']:
            raise _LoadBlocked('source_instructions_mismatch')
        reference = self._sdk(name, '_get_skill_reference', receipt)
        reference_bytes = self._read_bytes(reference_path)
        source_receipt.update(reference_sha256=_sha(reference_bytes),
                              reference_content_sha256=_sha(reference['content'].encode()))
        reference_text = reference_bytes.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n')
        if reference_text != reference['content']:
            raise _LoadBlocked('source_reference_mismatch')
        return (dict(name=name, instructions=_sections(loaded['instructions'], _OPERATIVE)),
                _sections(reference['content'], _CONTRACT))

    @staticmethod
    def _read_bytes(path: Path) -> bytes:
        with path.open('rb') as stream:
            value = stream.read(_MAX_SOURCE_BYTES + 1)
        if len(value) > _MAX_SOURCE_BYTES:
            raise _LoadBlocked('skill_source_exceeds_limit')
        return value

    def _persist(self, receipt: dict) -> None:
        payload = _encode(receipt)
        if len(payload) > _MAX_RECEIPT_BYTES:
            raise SkillAuditError('Skill audit receipt exceeds its size limit')
        temporary = None
        try:
            self.ledger_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.tmp', prefix='skill-',
                                             dir=self.ledger_root, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.ledger_root / (receipt['audit_id'] + '.json'))
        except OSError:
            raise SkillAuditError('Skill audit receipt could not be saved') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
