"""Railway entry point for the existing London product runtime.

The backend has no public domain. Only the project's frontend can reach it over
Railway private networking, and the wrapper adapts the runtime's loopback-only
Host/Origin checks after validating the private-network request boundary.
"""

import json
import os
import shutil
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("LONDON_PRODUCT_DATA_DIR", "/persist"))


def bootstrap() -> None:
    seed = ROOT / "seed-data"
    DATA.mkdir(parents=True, exist_ok=True)
    if not (DATA / "market.sqlite3").exists():
        if not (seed / "market.sqlite3").is_file():
            raise RuntimeError("Production market snapshot is missing")
        shutil.copytree(seed, DATA, dirs_exist_ok=True)

    config = {
        "provider": "OpenAI-compatible relay (upstream identity not independently verified)",
        "base_url": os.environ.get("LONDON_MODEL_BASE_URL", ""),
        "model": os.environ.get("LONDON_MODEL_ID", ""),
        "api_key": os.environ.get("LONDON_MODEL_API_KEY", ""),
    }
    if not all(config[k] for k in ("base_url", "model", "api_key")):
        raise RuntimeError("Model configuration is incomplete")
    secret_dir = ROOT / "secrets"
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    target = secret_dir / "model.json"
    target.write_text(json.dumps(config), encoding="utf-8")
    target.chmod(0o600)


class RailwayPrivateBoundary:
    def __init__(self, app, expected_host: str, frontend_origin: str):
        self.app = app
        self.expected_host = expected_host.lower()
        self.frontend_origin = frontend_origin.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        from starlette.responses import JSONResponse

        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"").decode("latin1").split(":")[0].lower()
        if host not in {self.expected_host, "127.0.0.1", "localhost"}:
            return await JSONResponse({"detail": "Private backend only"}, status_code=403)(scope, receive, send)
        origin = headers.get(b"origin", b"").decode("latin1")
        if origin and origin != self.frontend_origin:
            return await JSONResponse({"detail": "Untrusted origin"}, status_code=403)(scope, receive, send)
        adapted = dict(scope)
        adapted["headers"] = [
            (key, value) for key, value in scope.get("headers", [])
            if key.lower() not in {b"host", b"origin"}
        ] + [(b"host", b"127.0.0.1")]
        return await self.app(adapted, receive, send)


def main() -> None:
    bootstrap()
    from london_product.runtime import create_app

    port = int(os.environ.get("PORT", "8080"))
    app = create_app(directory=DATA, seed=False, scheduler=True, api_port=port)
    app = RailwayPrivateBoundary(
        app,
        expected_host=os.environ.get("LONDON_PRIVATE_HOST", "lite-backend.railway.internal"),
        frontend_origin=os.environ["LONDON_FRONTEND_ORIGIN"],
    )
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, proxy_headers=False)


if __name__ == "__main__":
    main()
