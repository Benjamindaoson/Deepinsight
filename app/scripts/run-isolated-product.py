"""Run the existing product against an explicit isolated directory, no scheduler."""
import argparse
import os
import json
import hashlib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'app'))
parser=argparse.ArgumentParser()
parser.add_argument('--directory',type=Path,required=True)
parser.add_argument('--port',type=int,default=7782)
parser.add_argument('--frontend-port',type=int,default=3102)
parser.add_argument('--allow-paid',action='store_true',help='Only after explicit operator authorization')
args=parser.parse_args()
directory=args.directory.resolve()
if directory == (ROOT/'app/data/product').resolve() or not directory.is_relative_to(ROOT/'docs/delivery'):
    parser.error('Use a directory under docs/delivery, never formal product data')
os.environ.pop('LONDON_NOTIFICATION_URL',None)
os.environ['LONDON_TAVILY_ENABLED']='0'
from london_product.runtime import create_app
from fastapi.responses import JSONResponse
app=create_app(directory,seed=False,scheduler=False,frontend_port=args.frontend_port)
identity=dict(pid=os.getpid(),directory=str(directory),scheduler=False,notifications=False,paid_allowed=args.allow_paid,
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'app/london_product').glob('*.py')})
@app.get('/api/market/runtime-identity')
def runtime_identity():return identity
@app.middleware('http')
async def paid_boundary(request,call_next):
    if not args.allow_paid and request.method=='POST':
        path=request.url.path
        if '/extract' in path or ('/agents/' in path and '/runs' in path) or ('/workflows/' in path and '/runs' in path):
            return JSONResponse({'detail':'Paid/native execution disabled in isolated acceptance server'},status_code=409)
        if path in ['/api/market/ask','/api/market/reports']:
            payload=await request.json()
            from london_product.query_router import DEEP
            saved_research=(path=='/api/market/ask' and payload.get('mode')=='auto'
                and isinstance(payload.get('message'),str) and bool(DEEP.search(payload['message']))
                and not payload.get('refresh_sources'))
            if (payload.get('mode') in ['agent','auto'] and not saved_research) or payload.get('include_analysis'):
                return JSONResponse({'detail':'Paid AI validation awaits explicit authorization; select Saved evidence mode'},status_code=409)
    return await call_next(request)
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=args.port)
