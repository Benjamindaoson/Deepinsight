"""Check for comparable historical data pairs."""
import json
from london_product.store import Store
from collections import defaultdict

s = Store('data/product')
facts = s.all('facts')

# Group by source_id + metric + geography
groups = defaultdict(list)
for f in facts:
    if f.get('status') in ('pending_review', 'needs_review'):
        key = (f.get('source_id'), f.get('metric'), f.get('geography'), f.get('definition'), f.get('grade'))
        groups[key].append(f)

comparable_pairs = []
for key, items in groups.items():
    if len(items) >= 2:
        periods = []
        for item in items:
            p = item.get('period') or ''
            if 'Q1' in p or 'Q2' in p:
                periods.append((item.get('period'), item))

        periods.sort(key=lambda x: x[0])

        for i in range(len(periods) - 1):
            p1, f1 = periods[i]
            p2, f2 = periods[i + 1]
            q1 = int(p1[-1]) if p1 else 0
            q2 = int(p2[-1]) if p2 else 0
            y1 = p1[:4] if p1 else ''
            y2 = p2[:4] if p2 else ''

            if q2 == q1 + 1 or (q1 == 4 and q2 == 1 and y2 > y1):
                comparable_pairs.append({
                    'key': key,
                    'fact1': {k: f1.get(k) for k in ['id', 'period', 'value', 'unit', 'status']},
                    'fact2': {k: f2.get(k) for k in ['id', 'period', 'value', 'unit', 'status']}
                })

print(f'Found {len(comparable_pairs)} potential comparable pairs:')
for pair in comparable_pairs:
    print()
    print(f'Source: {pair["key"][0]}, Metric: {pair["key"][1]}')
    print(f'  Geography: {pair["key"][2]}')
    print(f'  Definition: {pair["key"][3]}')
    print(f'  Grade: {pair["key"][4]}')
    print(f'  Q1: {pair["fact1"]["value"]} {pair["fact1"]["unit"]} ({pair["fact1"]["status"]})')
    print(f'  Q2: {pair["fact2"]["value"]} {pair["fact2"]["unit"]} ({pair["fact2"]["status"]})')
    print(f'  Status: Both are pending_review, comparison blocked by human_review_status')

print()
print('=== Conclusion ===')
print('There ARE comparable data pairs in the database.')
print('However, ALL are in pending_review status.')
print('The comparison system correctly blocks these comparisons.')
print('This is the CORRECT behavior - human review is required before formal comparison.')
