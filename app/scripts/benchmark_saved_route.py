"""Measure the local deterministic ask path without calling a model or source API."""
import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100:
        raise ValueError('Samples must be 1–100')
    timings = []
    with httpx.Client(base_url='http://127.0.0.1:7780', timeout=10, trust_env=False) as client:
        for _ in range(args.samples):
            started = time.perf_counter()
            first = None
            done = None
            with client.stream('POST', '/api/market/ask',
                               json={'message': '查看伦敦就业数据', 'mode': 'auto'}) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith('data: '):
                        continue
                    payload = json.loads(line[6:])
                    if payload.get('type') == 'token' and first is None:
                        first = time.perf_counter() - started
                    if payload.get('type') == 'done':
                        done = payload
            total = time.perf_counter() - started
            if (first is None or done is None or
                    done['metrics']['route']['mode'] != 'saved' or
                    done['metrics']['model_requests'] != 0):
                raise RuntimeError('Saved route did not complete without a model')
            timings.append(dict(first_token_ms=round(first * 1000, 1),
                                complete_ms=round(total * 1000, 1)))
    ordered = sorted(sample['complete_ms'] for sample in timings)
    result = dict(captured_at=datetime.now(timezone.utc).isoformat(),
                  question='查看伦敦就业数据', route='saved', model_requests=0,
                  samples=timings, p50_complete_ms=statistics.median(ordered),
                  p95_complete_ms=ordered[math.ceil(.95 * len(ordered)) - 1],
                  note='Local loopback observations; not a network or production SLA. AI interpretation latency excluded.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('p50_complete_ms', 'p95_complete_ms', 'model_requests')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
