"""One-shot authenticated SSE acceptance against the deployed Lite frontend."""

import argparse
import base64
import json
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen


URL = 'https://lite-frontend-production.up.railway.app/api/market/ask'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--question', required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--password-file', type=Path, required=True)
    parser.add_argument('--mode', choices=['agent', 'saved'], default='agent')
    args = parser.parse_args()
    password = args.password_file.read_text(encoding='utf-8').strip()
    auth = base64.b64encode(('reviewer:' + password).encode()).decode()
    body = json.dumps(dict(message=args.question, session_id=args.session_id,
                           mode=args.mode, refresh_sources=False)).encode()
    req = Request(URL, data=body, method='POST', headers={
        'Authorization': 'Basic ' + auth,
        'Content-Type': 'application/json',
        'Idempotency-Key': str(uuid.uuid4()),
        'Accept': 'text/event-stream',
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    events = []
    try:
        with urlopen(req, timeout=240) as response:
            status = response.status
            lines = []
            for line in response:
                decoded = line.decode('utf-8', errors='replace')
                lines.append(decoded)
                if decoded.startswith('data: '):
                    try:
                        item = json.loads(decoded[6:])
                    except ValueError:
                        continue
                    events.append(dict(elapsed_seconds=round(time.monotonic()-started, 3),
                                       type=item.get('type'), payload=item))
        args.output.write_text(''.join(lines), encoding='utf-8')
    except Exception as exc:
        print(json.dumps(dict(status='request_failed', error_type=type(exc).__name__,
                              elapsed_seconds=round(time.monotonic()-started, 3))))
        raise
    summary = dict(http_status=status, elapsed_seconds=round(time.monotonic()-started, 3),
                   event_types=[e['type'] for e in events],
                   first_visible_seconds=next((e['elapsed_seconds'] for e in events
                                               if e['type'] in {'token', 'report'}), None),
                   done=next((e['payload'] for e in reversed(events) if e['type']=='done'), None),
                   error=next((e['payload'] for e in reversed(events) if e['type']=='error'), None),
                   output_file=str(args.output))
    args.output.with_suffix('.summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    printable = {k:v for k,v in summary.items() if k not in {'done','error'}}
    printable['done'] = bool(summary['done'])
    printable['error'] = ({k: summary['error'].get(k) for k in ('code','message','run_id','stage','submission_id')}
                          if summary['error'] else None)
    print(json.dumps(printable, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
