"""Quota errors are actionable without leaking raw provider responses."""
import pytest
from london_product.qa_context import classify_error


@pytest.mark.parametrize('message', [
    "Error code: 403 - {'error': {'code': 'insufficient_user_quota'}}",
    '账户余额或套餐额度不足。请充值或切换套餐后重试。',
    'PROVIDER_QUOTA_EXHAUSTED',
])
def test_explicit_quota_errors_survive_nested_classification(message):
    assert classify_error(classify_error(message)) == 'PROVIDER_QUOTA_EXHAUSTED'


@pytest.mark.parametrize('message', ['403 Forbidden', 'invalid_api_key', 'insufficient permissions'])
def test_other_provider_errors_are_not_mislabelled_as_quota(message):
    expected='MODEL_AUTHENTICATION_FAILED' if message=='invalid_api_key' else 'PROVIDER_ERROR'
    assert classify_error(message) == expected
    assert classify_error(message) != 'PROVIDER_QUOTA_EXHAUSTED'
