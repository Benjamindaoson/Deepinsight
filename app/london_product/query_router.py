"""Rules-first query classification and Python-owned execution policy."""
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
from uuid import uuid4

from .jev_shadow import JevShadowObserver, ShadowConfig
from .routing import ANALYSIS, route_question

QUERY_ROUTE = ContextVar('market_query_route', default=None)
FRESH = re.compile(r'\b(latest|newest|recent|today|live|current)\b|最新|实时|今天|当前', re.I)
DEEP = re.compile(r'deep.?research|in.depth|investigat|cross.source|深入研究|深度研究|调查', re.I)
EXPLAIN = re.compile(r'\b(explain|understand|drivers?|synthesi\w*|comprehensive)\b|解释|研判|综合', re.I)
REPORT = re.compile(r'\breport\b|报告', re.I)
COMPARE = re.compile(r'compar|比较|对比', re.I)


def load_query_config(path=None):
    """Only dedicated project configuration; error text never contains values."""
    path = Path(path) if path is not None else Path(__file__).resolve().parents[2]/'secrets'/'jev.json'
    try:
        config = ShadowConfig(enabled=True, api_key=os.getenv('LONDON_JEV_API_KEY', '').strip(),
            model=os.getenv('LONDON_JEV_MODEL', 'jev-1.13.0'),
            timeout_seconds=float(os.getenv('LONDON_JEV_TIMEOUT_SECONDS', '2')),
            max_pending=int(os.getenv('LONDON_JEV_MAX_PENDING', '4')),
            max_calls=int(os.getenv('LONDON_JEV_MAX_CALLS', '100')))
        if path.exists():
            values = json.loads(path.read_text(encoding='utf-8-sig'))
            allowed = {'api_key', 'enabled', 'model', 'timeout_seconds', 'max_pending', 'max_calls', 'confidence_threshold'}
            if not isinstance(values, dict) or set(values)-allowed:
                raise ValueError('Invalid configuration')
            if any(k in values and not isinstance(values[k], str) for k in ('api_key', 'model')):
                raise ValueError('Invalid configuration')
            if 'enabled' in values and type(values['enabled']) is not bool:
                raise ValueError('Invalid configuration')
            if any(k in values and type(values[k]) not in (int, float) for k in ('timeout_seconds', 'confidence_threshold')):
                raise ValueError('Invalid configuration')
            config = replace(config, **values)
        flag = os.getenv('LONDON_JEV_ROUTING_ENABLED')
        if flag is not None:
            if flag not in ('0', '1'):
                raise ValueError('Invalid configuration')
            config = replace(config, enabled=flag == '1')
        return config
    except (OSError, ValueError, TypeError, OverflowError):
        return ShadowConfig(enabled=True, config_error=True)


def requires_analysis(question):
    return bool(ANALYSIS.search(question) or EXPLAIN.search(question) or REPORT.search(question) or DEEP.search(question))


def baseline_route(question):
    route = route_question(question)
    if requires_analysis(question):
        route = dict(mode='agent', reason='interpretation_requested')
    return route


def node_guidance(route):
    """Compact, safe context for evidence tools; never includes credentials."""
    return {k: route[k] for k in ('intent', 'mode', 'classifier', 'classification_status', 'limitations',
                                  'requires_latest_data', 'refresh_sources') if k in route}


class QueryRouter:
    def __init__(self, root, config=None, *, transport=None):
        self.config = config or load_query_config()
        self.path = Path(root)/'routing'/'decisions.jsonl'
        self._client = JevShadowObserver(root, replace(self.config, enabled=False), transport=transport)
        self._transport = transport
        self._lock = threading.RLock()
        self._receipts = queue.Queue(maxsize=128)
        self._writer = None
        self._writer_stop = threading.Event()
        self._counts = Counter()
        self._futures = set()
        self._closed = False
        self._pool = (ThreadPoolExecutor(max_workers=self.config.max_pending, thread_name_prefix='jev-classifier')
                      if self.config.state == 'ready' else None)

    def status(self):
        with self._lock:
            state = 'closed' if self._closed else self.config.state
            return dict(state=state, node_integrated=True, enabled=self.config.enabled,
                        controls_auto_execution=state == 'ready', native_node_guidance=True,
                        model=self.config.model if state != 'invalid_configuration' else None,
                        max_calls=self.config.max_calls if state != 'invalid_configuration' else None,
                        max_pending=self.config.max_pending if state != 'invalid_configuration' else None,
                        accepted=self._counts['accepted'], in_flight=len(self._futures),
                        write_failures=self._counts['write_failures'],
                        receipt_dropped=self._counts['receipt_dropped'], receipt_backlog=self._receipts.qsize(),
                        outcomes={k[8:]:v for k,v in self._counts.items() if k.startswith('outcome:')})

    def _finished(self, future):
        with self._lock:
            self._futures.discard(future)

    def _admit(self, question):
        with self._lock:
            if self._closed:
                return None, 'closed'
            if self._pool is None:
                return None, self.config.state
            if len(self._futures) >= self.config.max_pending:
                return None, 'capacity_exhausted'
            if self._counts['accepted'] >= self.config.max_calls:
                return None, 'budget_exhausted'
            operation = self._client._evaluate if self._transport is not None else self._client._isolated_evaluate
            future = self._pool.submit(operation, question)
            self._futures.add(future)
            self._counts['accepted'] += 1
            future.add_done_callback(self._finished)
            return future, None

    def _record(self, question, route, identity):
        with self._lock:
            self._counts['outcome:'+route['classification_status']] += 1
        # These dedicated operational receipts never write business tables.
        row = dict(schema_version=1, observed_at=datetime.now(timezone.utc).isoformat(), identity=identity or route['decision_id'],
                   question_sha256=hashlib.sha256(question.encode()).hexdigest(), question_length=len(question), decision=route)
        with self._lock:
            if self._closed:
                self._counts['receipt_dropped'] += 1
                return
            if self._writer is None:
                self._writer = threading.Thread(target=self._write_loop, name='jev-routing-receipts', daemon=True)
                try:
                    self._writer.start()
                except RuntimeError:
                    self._writer = None
                    self._counts['write_failures'] += 1
                    self._counts['receipt_dropped'] += 1
                    return
            try:
                self._receipts.put_nowait(row)
            except queue.Full:
                self._counts['receipt_dropped'] += 1

    def _write_loop(self):
        while not self._writer_stop.is_set() or not self._receipts.empty():
            try:
                row = self._receipts.get(timeout=.05)
            except queue.Empty:
                continue
            try:
                self._write_receipt(row)
            finally:
                self._receipts.task_done()

    def _write_receipt(self, row):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
        except Exception:
            with self._lock:
                self._counts['write_failures'] += 1

    async def classify(self, question, requested_mode='auto', identity=None, *, allow_research=False):
        started = time.perf_counter()
        if requested_mode not in ('auto', 'saved', 'agent'):
            raise ValueError('Invalid execution mode')
        if not isinstance(question, str) or not 1 <= len(question) <= 4000:
            return dict(mode='agent', reason='unsupported_query', classifier='fallback',
                        classification_status='unsupported_query', jev_attempted=False, limitations=[])
        baseline = baseline_route(question) if self.config.enabled else route_question(question)
        latest = bool(FRESH.search(question))
        limitations = ['LIVE_RESEARCH_UNAVAILABLE'] if latest else []
        deep_requested = bool(DEEP.search(question))
        if deep_requested and not allow_research:
            limitations.append('DEEP_RESEARCH_WORKER_UNAVAILABLE')
        route = dict(baseline, decision_id=str(uuid4()), classifier='fallback', classification_status='pending', jev_attempted=False,
                     limitations=limitations, requires_latest_data=latest, refresh_sources=False)
        if requested_mode == 'auto' and allow_research and deep_requested:
            route.update(mode='research', reason='deep_research_requested',
                         classifier='rules', classification_status='rules', intent='deep_research')
        elif requested_mode != 'auto':
            route.update(mode=requested_mode, reason='explicit_selection', classifier='explicit', classification_status='explicit')
        elif not self.config.enabled:
            route['classification_status'] = 'disabled'
        elif baseline['mode'] == 'saved' and not latest:
            route.update(classifier='rules', classification_status='rules',
                         intent='market_comparison' if COMPARE.search(question) else 'saved_lookup')
        else:
            try:
                future, unavailable = self._admit(question)
                if future is None:
                    route['classification_status'] = unavailable
                else:
                    route['jev_attempted'] = True
                    result = await asyncio.wrap_future(future)
                    route['classification_status'] = result['status']
                    if result['status'] == 'ok':
                        suggestion = result['suggestion']
                        route.update(classifier_model=result['model_returned'], classification=suggestion, classifier_usage=result['usage'])
                        if suggestion['low_confidence']:
                            route['classification_status'] = 'low_confidence'
                        else:
                            intent = suggestion['intent']
                            mode = 'saved' if intent in ('saved_lookup', 'market_comparison', 'latest_information') else 'agent'
                            route.update(mode=mode, intent=intent, classifier='jev', reason='jev_intent')
                            if mode == 'saved' and requires_analysis(question):
                                route.update(mode='agent', policy_override='analysis_requested')
                            if intent == 'latest_information' or suggestion['latest_information_probability'] >= .5:
                                route['requires_latest_data'] = True
                                if 'LIVE_RESEARCH_UNAVAILABLE' not in limitations: limitations.append('LIVE_RESEARCH_UNAVAILABLE')
                            if intent == 'deep_research' and 'DEEP_RESEARCH_WORKER_UNAVAILABLE' not in limitations:
                                limitations.append('DEEP_RESEARCH_WORKER_UNAVAILABLE')
            except asyncio.CancelledError:
                raise
            except Exception:
                route.update(classifier='fallback', classification_status='internal_error', mode=baseline['mode'])
        route['classifier_elapsed_ms'] = round((time.perf_counter()-started)*1000, 3)
        self._record(question, route, identity)
        return route

    def close(self, *, wait=False):
        with self._lock:
            self._closed = True
        if self._pool:
            self._pool.shutdown(wait=wait, cancel_futures=not wait)
        self._client.close(wait=wait)
        self._writer_stop.set()
        if wait and self._writer:
            self._writer.join(timeout=3)
