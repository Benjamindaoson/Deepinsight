"""Small, redacted JSON timing receipts for local route and answer phases."""

import hashlib
import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


_WRITE_LOCK = threading.Lock()
_ALLOWED = {'routing', 'acquisition', 'database', 'evidence', 'validation', 'report_render', 'model', 'verification', 'publication', 'complete'}


class PhaseTrace:
    def __init__(self, root, kind, question, route='unknown'):
        self.root = Path(root)
        self.kind = kind
        self.route = route
        self.question_sha256 = hashlib.sha256(question.encode('utf-8')).hexdigest()
        self.started = time.perf_counter()
        self.last = self.started
        self.phases = {}
        self.observed_at = datetime.now(timezone.utc).isoformat()
        self.finished = False

    def mark(self, phase):
        if phase not in _ALLOWED:
            raise ValueError('Unknown phase')
        current = time.perf_counter()
        self.phases[phase] = round((current-self.last)*1000, 3)
        self.last = current

    def finish(self, status, *, model_requests=0):
        if self.finished:
            raise ValueError('Trace already finished')
        self.mark('complete')
        self.finished = True
        receipt = dict(schema_version=1, observed_at=self.observed_at, kind=self.kind,
                       route=self.route, question_sha256=self.question_sha256,
                       status=status, phases_ms=self.phases,
                       total_ms=round((self.last-self.started)*1000, 3),
                       model_requests=int(model_requests))
        path = self.root/'traces'/'phases.jsonl'
        try:
            with _WRITE_LOCK:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(receipt, ensure_ascii=False, allow_nan=False)+'\n')
        except OSError:
            # Telemetry must never turn an otherwise valid saved answer into a failure.
            receipt['persisted'] = False
        return receipt


def summarize(root, *, kind=None, route=None, limit=1000):
    path = Path(root)/'traces'/'phases.jsonl'
    if not path.exists():
        return dict(count=0,p50_ms=None,p95_ms=None,basis='observed_local_runs')
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines()[-limit:]:
        try:
            row = json.loads(line)
            if (kind is None or row.get('kind') == kind) and (route is None or row.get('route') == route):
                if isinstance(row.get('total_ms'), (int,float)) and math.isfinite(row['total_ms']):
                    rows.append(row['total_ms'])
        except (ValueError, TypeError):
            continue
    rows.sort()
    def percentile(p):
        return rows[max(0, math.ceil(len(rows)*p)-1)] if rows else None
    return dict(count=len(rows),p50_ms=percentile(.5),p95_ms=percentile(.95),
                basis='observed_local_runs')
