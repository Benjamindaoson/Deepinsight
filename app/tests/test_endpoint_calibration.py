"""Synthetic usage receipts test validation only; no provider calls."""
import hashlib,json
from pathlib import Path
import pytest
from london_product.qa_context import estimate_payload,character_units


def calibration_files(tmp_path,monkeypatch):
    import london_product.qa_context as context
    monkeypatch.setattr(context,'CALIBRATION_ROOT',tmp_path,raising=False)
    request=dict(model='fixture-model',messages=[dict(role='user',content='SYNTHETIC offline fixture')],max_tokens=64)
    receipt=dict(endpoint='https://provider.example/v1',model='fixture-model',request=request,
        response=dict(id='SYNTHETIC',model='fixture-model',usage=dict(prompt_tokens=20,completion_tokens=2)))
    proof=tmp_path/'usage.json';proof.write_text(json.dumps(receipt),encoding='utf-8')
    config=dict(model='fixture-model',endpoint=receipt['endpoint'],multiplier=3,safety_margin=1.25,
        samples=[dict(evidence_path=str(proof),evidence_sha256=hashlib.sha256(proof.read_bytes()).hexdigest())],
        limitation='Synthetic fixture, never a real calibration result')
    path=tmp_path/'calibration.json';path.write_text(json.dumps(config),encoding='utf-8')
    monkeypatch.setenv('LONDON_TOKEN_CALIBRATION_PATH',str(path))
    return request,receipt,proof,config,path


def test_explicit_isolated_calibration_accepts_matching_hashed_usage(tmp_path,monkeypatch):
    request,receipt,proof,config,path=calibration_files(tmp_path,monkeypatch)
    estimate=estimate_payload(request,config['endpoint'])
    assert estimate['calibration_samples']==1 and estimate['multiplier']==3
    with pytest.raises(ValueError,match='TOKEN_ESTIMATOR_UNCALIBRATED'):estimate_payload(request,'https://different.example/v1')


@pytest.mark.parametrize('fault',['hash','endpoint','usage','multiplier','empty_samples','nan_cap','infinite_cap','boolean_cap','fractional_cap'])
def test_override_cannot_relabel_unproven_or_under_reserved_usage(tmp_path,monkeypatch,fault):
    request,receipt,proof,config,path=calibration_files(tmp_path,monkeypatch)
    if fault=='hash':proof.write_text('{}',encoding='utf-8')
    if fault=='endpoint':config['endpoint']='https://different.example/v1'
    if fault=='usage':
        receipt['response'].pop('usage');proof.write_text(json.dumps(receipt),encoding='utf-8')
        config['samples'][0]['evidence_sha256']=hashlib.sha256(proof.read_bytes()).hexdigest()
    if fault=='multiplier':config['multiplier']=1.25
    if fault=='empty_samples':config['samples']=[]
    if fault.endswith('_cap'):
        receipt['request']['max_tokens']={'nan_cap':float('nan'),'infinite_cap':float('inf'),'boolean_cap':True,'fractional_cap':64.5}[fault]
        if fault=='boolean_cap':receipt['response']['usage']['completion_tokens']=0
        proof.write_text(json.dumps(receipt),encoding='utf-8')
        config['samples'][0]['evidence_sha256']=hashlib.sha256(proof.read_bytes()).hexdigest()
    path.write_text(json.dumps(config),encoding='utf-8')
    with pytest.raises(ValueError,match='TOKEN_ESTIMATOR_UNCALIBRATED'):estimate_payload(request,config['endpoint'])
