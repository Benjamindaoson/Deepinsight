from fastapi.testclient import TestClient
from london_product.runtime import create_app


def test_saved_api_and_safe_report(tmp_path):
    with TestClient(create_app(tmp_path,seed=False,scheduler=False)) as client:
        response=client.post('/api/market/ask',json={'message':'Show gaps','mode':'saved'})
        assert response.status_code==200 and '"type": "done"' in response.text
        assert '"model_requests": 0' in response.text
        report=client.post('/api/market/reports',json={'period':'daily'}).json()
        assert report['analysis_status']=='no_data' and report['workflow_run_id']
        assert client.get('/api/market/reports/'+report['id']).status_code==200
        assert client.post('/api/market/notifications',json={'report_id':report['id']}).json()['status']=='configuration_missing'
        assert client.post('/api/market/refresh',headers={'Origin':'https://evil.example'}).status_code==403
        assert client.get('/api/market/facts',headers={'Host':'evil.example'}).status_code==403
        assert client.put('/api/market/settings',json={'secret_file':'outside'}).status_code==422
