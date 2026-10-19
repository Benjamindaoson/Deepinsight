"""Summarize local shadow receipts; never calls a provider or changes routes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from london_product.shadow_metrics import read_receipts, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipts', type=Path, required=True, help='observations.jsonl path')
    parser.add_argument('--labels', type=Path, help='Optional JSON object: submission_id -> human intent label')
    parser.add_argument('--output', type=Path, help='Optional summary JSON destination')
    args = parser.parse_args()
    if args.output and args.output.resolve() in {p.resolve() for p in (args.receipts, args.labels) if p}:
        parser.exit(2, 'Summary output must not overwrite receipts or human labels.\n')
    try:
        rows, invalid_lines = read_receipts(args.receipts)
        labels = json.loads(args.labels.read_text(encoding='utf-8-sig')) if args.labels else None
        result = dict(summarize(rows, labels), invalid_receipt_lines=invalid_lines)
        text = json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text+'\n', encoding='utf-8')
        print(text)
    except (OSError, ValueError, TypeError):
        parser.exit(2, 'Cannot summarize: check local receipt/label files and six-category labels.\n')


if __name__ == '__main__':
    main()
