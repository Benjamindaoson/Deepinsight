"""Offline startup configuration tests; no real credentials or network."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

LOADER = Path(__file__).parents[1] / 'scripts/load-tavily-config.ps1'


@pytest.mark.parametrize('enabled', [True, False])
def test_project_config_overrides_stale_key_without_printing_it(tmp_path, enabled):
    shell = shutil.which('powershell')
    if not shell:
        pytest.skip('Windows launcher verification')
    config = tmp_path / 'tavily.json'
    config.write_text(json.dumps({'api_key': 'offline-fixture-only', 'enabled': enabled}))
    script = f"""$env:LONDON_TAVILY_API_KEY='stale'
. '{LOADER}' -ConfigPath '{config}'
if ($env:LONDON_TAVILY_API_KEY -ne 'offline-fixture-only') {{ exit 1 }}
if ($env:LONDON_TAVILY_ENABLED -ne '{int(enabled)}') {{ exit 2 }}
Write-Output 'PASS'
"""
    result = subprocess.run([shell, '-NoProfile', '-Command', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'PASS'


def test_malformed_local_config_fails_closed_without_secret_output(tmp_path):
    shell = shutil.which('powershell')
    if not shell:
        pytest.skip('Windows launcher verification')
    config = tmp_path / 'tavily.json'
    config.write_text('{"api_key":"offline-sensitive", "enabled":"yes"}')
    result = subprocess.run([shell, '-NoProfile', '-Command', f". '{LOADER}' -ConfigPath '{config}'"], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'offline-sensitive' not in result.stdout + result.stderr
