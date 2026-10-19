"""Run the existing AgentOS product on the final isolated delivery store."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'app'))
os.environ['LONDON_TAVILY_ENABLED']='0'
os.environ['LONDON_JEV_ROUTING_ENABLED']='0'
os.environ['LONDON_JEV_SHADOW_ENABLED']='0'
os.environ.pop('LONDON_NOTIFICATION_URL',None)
from london_product.runtime import create_app
directory=ROOT/'docs/delivery/final-delivery-20261019/demo-runtime'
if not (directory/'market.sqlite3').exists():raise SystemExit('Final delivery store missing; see delivery RUNBOOK.md')
app=create_app(directory,seed=False,scheduler=True,frontend_port=3106)
app.state.agent_os._scheduler_base_url='http://127.0.0.1:7786'
@app.get('/api/market/delivery-identity')
def delivery_identity():
    return dict(pid=os.getpid(),directory=str(directory),scheduler=True,external_notifications=False,paid_search=False)
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=7786)
