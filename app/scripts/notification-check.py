"""Read-only by default. Explicit send uses the existing report notification API."""
import argparse
import json
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--send-report', metavar='REPORT_ID')
parser.add_argument('--confirm-external-send', action='store_true',
                    help='Only use after approval of the configured recipient and report')
args = parser.parse_args()
base = 'http://127.0.0.1:7780/api/market'
with urllib.request.urlopen(base + '/notifications/configuration', timeout=10) as response:
    config = json.load(response)
print(json.dumps(config, ensure_ascii=False, indent=2))
if args.send_report:
    if not args.confirm_external_send:
        parser.error('Sending requires explicit recipient/report authorization and --confirm-external-send')
    if config['status'] != 'configured':
        raise SystemExit('No send: ' + config['status'])
    request = urllib.request.Request(base + '/notifications',
        data=json.dumps({'report_id': args.send_report}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=90) as response:
        print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
