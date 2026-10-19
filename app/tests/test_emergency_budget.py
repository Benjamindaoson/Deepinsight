import pytest
from london_product.qa_context import estimate_payload,compact


@pytest.mark.parametrize('model',['deepseek-chat','deepseek-reasoner','deepseek-flash'])
def test_official_deepseek_budget_is_explicit_conservative_not_fake_calibration(model):
    payload={'model':model,'messages':[{'role':'user','content':'London £95'}],'tools':[{'type':'function'}]}
    result=estimate_payload(payload,'https://api.deepseek.com/v1')
    assert result['method']=='utf8-bytes-plus-framing-v1'
    assert result['calibration_samples']==0
    assert result['estimated_input_tokens']==len(compact(payload).encode('utf-8'))+4096
    assert result['components']['tools']>0
    with pytest.raises(ValueError,match='TOKEN_ESTIMATOR_UNCALIBRATED'):
        estimate_payload(payload,'https://unapproved.invalid/v1')


def test_explicit_model_profile_is_used_by_extraction_identity(tmp_path,monkeypatch):
    import json
    from london_data.extraction import configured_model,config_version
    profile=tmp_path/'model.json'
    profile.write_text(json.dumps(dict(model='deepseek-chat',base_url='https://api.deepseek.com/v1',api_key='not-a-real-key')))
    monkeypatch.setenv('LONDON_MODEL_CONFIG',str(profile))
    assert configured_model().id=='deepseek-chat'
    first=config_version()
    profile.write_text(json.dumps(dict(model='deepseek-reasoner',base_url='https://api.deepseek.com/v1',api_key='not-a-real-key')))
    assert config_version()!=first
