"""Execute the frozen existing startup, adding a read-only HTTP boundary."""
import hashlib
import json
import runpy
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'docs/delivery/real-ai-frozen-20261019'
manifest = json.loads((OUT / 'SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
candidate = Path(manifest['candidate'])
assert all(hashlib.sha256((candidate / p).read_bytes()).hexdigest() == h for p, h in manifest['source_files'].items())
sys.argv = ['run-isolated-product.py', '--directory', manifest['runtime'], '--port', '7785', '--frontend-port', '3105']
namespace = runpy.run_path(str(candidate / 'app/scripts/run-isolated-product.py'), run_name='frozen_preview')
app = namespace['app']
from fastapi.responses import JSONResponse
@app.middleware('http')
async def read_only(request, call_next):
    if request.method not in ['GET', 'HEAD', 'OPTIONS']:
        return JSONResponse({'detail': 'Frozen report preview is read-only; model execution and mutations disabled'}, status_code=409)
    return await call_next(request)
identity = namespace['identity']
identity.update(source_root=str(candidate), runtime_module_path=sys.modules['london_product.runtime'].__file__,
    source_manifest_sha256=hashlib.sha256((OUT / 'SOURCE_MANIFEST.json').read_bytes()).hexdigest(),
    read_only=True, model_configuration='dummy_localhost_endpoint',
    module_paths={name: module.__file__ for name, module in list(sys.modules.items())
        if name.startswith(('london_product', 'london_data')) and getattr(module, '__file__', None)})
(OUT / 'RUNTIME_IDENTITY.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=7785)
