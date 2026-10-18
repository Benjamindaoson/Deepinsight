"""Recompute derived fact fields after a normalization-rule change.

Deterministic, offline and idempotent: reads stored raw values, never the
network and never a model. Human review decisions are preserved; only an
already-approved fact stays validated.

Usage:  .venv/Scripts/python.exe scripts/rederive-normalization.py [--dry-run]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from london_product.store import Store
from london_product.service import MarketService
from london_product.normalization import derive


def main():
    dry = '--dry-run' in sys.argv
    store = Store(ROOT / 'data' / 'product')
    service = MarketService(store)
    if dry:
        preview = []
        for fact in store.all('facts'):
            patch = derive(fact)
            if fact.get('annualization') != patch.get('annualization'):
                preview.append(dict(id=fact['id'], metric=fact.get('metric'),
                                    before=fact.get('annualization'), after=patch.get('annualization'),
                                    unit=patch.get('normalized_unit')))
        print(json.dumps(dict(dry_run=True, changes=preview), ensure_ascii=False, indent=2))
        return
    print(json.dumps(service.rederive_facts(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
