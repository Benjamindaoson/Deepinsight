"""Measure the isolated, explicit Saved route without invoking a model."""

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered)*fraction)-1)] if ordered else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:7791')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--runs', type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        parser.error('--runs must be between 1 and 100')
    measures = {'search': [], 'saved_ask': []}
    report_ids = []
    with httpx.Client(timeout=30) as client:
        for _ in range(args.runs):
            start = time.perf_counter()
            search = client.get(args.base+'/api/market/search', params={'q':'vacancy', 'limit':3})
            search.raise_for_status()
            assert search.json()['model_requests'] == 0
            measures['search'].append(round((time.perf_counter()-start)*1000,3))
            start = time.perf_counter()
            answer = client.post(args.base+'/api/market/ask', json={
                'message':'Show City vacancy for 2026 Q2', 'mode':'saved', 'refresh_sources':False})
            answer.raise_for_status()
            events = [json.loads(line[6:]) for line in answer.text.splitlines() if line.startswith('data: ')]
            done = [event for event in events if event.get('type')=='done']
            assert len(done) == 1 and done[0]['metrics']['model_requests'] == 0
            assert not any(event.get('type')=='error' for event in events)
            report_ids.append(done[0]['report_id'])
            measures['saved_ask'].append(round((time.perf_counter()-start)*1000,3))
    receipt = dict(observed_at=datetime.now(timezone.utc).isoformat(),
        environment='isolated local API on loopback',runs=args.runs,
        paid_model_requests=0,question='Show City vacancy for 2026 Q2',
        measurements={name:dict(p50_ms=percentile(values,.5),p95_ms=percentile(values,.95),
                                min_ms=min(values),max_ms=max(values),samples_ms=values)
                      for name, values in measures.items()},report_ids=report_ids,
        limitation='Local loopback timings are not a production SLA or browser measurement.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({name:{key:value for key,value in row.items() if key!='samples_ms'}
        for name,row in receipt['measurements'].items()},indent=2))


if __name__ == '__main__':
    main()
