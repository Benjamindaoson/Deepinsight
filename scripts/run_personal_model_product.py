"""Run the actual product with user model settings and notifications/scheduler disabled.

Uses the existing formal product database. Backups are created before launch.
No model generation occurs at startup. Provider calls require a chat submission.
"""
import os
import sys
from pathlib import Path
from release_manifest import resolve_release

PROJECT=Path(__file__).resolve().parents[1]
release=resolve_release(PROJECT,os.environ.get('LONDON_RELEASE_POINTER'))
os.environ['LONDON_RELEASE_MANIFEST']=release['manifest_path']
sys.dont_write_bytecode=True
sys.path.insert(0,release['backend_app'])
from london_product.release_identity import bind_verified_release
bind_verified_release(release)
from london_product.runtime import create_app
import uvicorn

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    directory = Path(os.environ.get('LONDON_PERSONAL_RUNTIME', str(root / 'app/data/product')))
    api_port = int(os.environ.get('LONDON_PERSONAL_API_PORT', '7788'))
    frontend_port = int(os.environ.get('LONDON_PERSONAL_FRONTEND_PORT', '3105'))
    if not os.environ.get('LONDON_MODEL_CONFIG'):
        os.environ['LONDON_MODEL_CONFIG']=str(root/'secrets/model.deepseek-acceptance-20261019.json')
    for key in ['LONDON_TAVILY_ENABLED','LONDON_JEV_ROUTING_ENABLED','LONDON_JEV_SHADOW_ENABLED']:os.environ[key]='0'
    os.environ.pop('LONDON_NOTIFICATION_URL',None)
    app = create_app(directory, seed=False, scheduler=False, frontend_port=frontend_port, api_port=api_port, extra_frontend_port=3107)
    app.state.market.save_settings(dict(monitoring_enabled=False,notifications_enabled=False,monitor_analysis_enabled=False))
    uvicorn.run(app, host='127.0.0.1', port=api_port)
