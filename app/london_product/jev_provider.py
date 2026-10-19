"""Private killable HTTP child; no application startup, database or scheduler."""
import json
import sys

from .jev_shadow import JevShadowObserver, ShadowConfig


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read(65536))
        config = ShadowConfig(api_key=payload['api_key'], model=payload['model'],
            timeout_seconds=payload['timeout_seconds'], confidence_threshold=payload['confidence_threshold'])
        # enabled=False avoids creating an executor in this HTTP-only process.
        observer = JevShadowObserver('.', config)
        result = observer._evaluate(payload['question'])
    except Exception:
        result = dict(status='internal_error')
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True, allow_nan=False).encode())


if __name__ == '__main__':
    main()
