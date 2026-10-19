"""Local offline demo of the existing product API on a separate port."""

import argparse
import sqlite3
from pathlib import Path

import uvicorn

from .runtime import ROOT, create_app


def saved_snapshot_directory() -> Path | None:
    """Freeze the existing business database without writing to the source.

    The source's original files remain in their registered locations and are
    checked again against their hashes before any evidence is displayed.
    Never replace an earlier offline snapshot or its report/alert history.
    """
    source = ROOT / "app/data/product/market.sqlite3"
    if not source.is_file():
        return None
    target = ROOT / "app/data/product/offline-saved-snapshot"
    database = target / "market.sqlite3"
    if database.exists():
        return target
    target.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        with sqlite3.connect(database) as destination:
            connection.backup(destination)
    finally:
        connection.close()
    return target


def main():
    parser = argparse.ArgumentParser(description="Run saved-evidence product without API keys")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=3101)
    args = parser.parse_args()
    snapshot = saved_snapshot_directory()
    app = create_app(snapshot or ROOT / "app/data/product/offline-demo",
                      seed=snapshot is None, scheduler=False,
                      frontend_port=args.frontend_port, offline=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
