"""Read-only measurements; routing disagreement is never a quality label."""
from collections import Counter
import json
import math
from pathlib import Path

from .jev_shadow import INTENTS


def read_receipts(path):
    rows, invalid = [], 0
    with Path(path).open(encoding='utf-8') as handle:
        for line in handle:
            try:
                if len(line) > 65536:
                    raise ValueError('Oversized receipt')
                row = json.loads(line)
                if (not isinstance(row, dict) or row.get('status') not in
                        ('ok', 'timeout', 'http_error', 'network_error', 'invalid_response', 'internal_error')
                        or type(row.get('elapsed_ms')) not in (float, int)
                        or not math.isfinite(row['elapsed_ms']) or row['elapsed_ms'] < 0):
                    raise ValueError('Invalid receipt')
                if row['status'] == 'ok':
                    if (not isinstance(row.get('submission_id'), str)
                            or row['suggestion']['intent'] not in INTENTS
                            or type(row['suggestion']['low_confidence']) is not bool):
                        raise ValueError('Invalid success receipt')
                rows.append(row)
            except (ValueError, TypeError, KeyError, OverflowError):
                invalid += 1
    return rows, invalid


def summarize(rows, labels=None):
    labels = labels or {}
    if not isinstance(labels, dict) or any(value not in INTENTS for value in labels.values()):
        raise ValueError('Labels must map submission IDs to known intent names')
    rows = list(rows)
    successes = [row for row in rows if row.get('status') == 'ok']
    latencies = sorted(row['elapsed_ms'] for row in successes)
    def percentile(q):
        return latencies[max(0, math.ceil(q*len(latencies))-1)] if latencies else None
    labeled = [row for row in successes if row.get('submission_id') in labels]
    return dict(observations=len(rows), successes=len(successes),
                statuses=dict(Counter(row.get('status', 'unknown') for row in rows)),
                latency_ms=dict(p50=percentile(.5), p95=percentile(.95)),
                coarse_disagreements=sum(row.get('coarse_disagreement') is True for row in successes),
                low_confidence=sum(row['suggestion'].get('low_confidence') is True for row in successes),
                labeled_count=len(labeled),
                accuracy=(sum(row['suggestion']['intent'] == labels[row['submission_id']] for row in labeled)/len(labeled)
                          if labeled else None),
                note='Latency is provider observation wall time for successful calls. Disagreement is diagnostic, not error rate. '
                     'Drop/write counters live on the running status endpoint; receipts alone do not prove full request coverage.')
