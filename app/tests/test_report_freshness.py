"""Source checks, collection and local integrity verification are distinct."""
from bs4 import BeautifulSoup
from test_finding_verification import svc,observation
from london_product.chat_report import build_report,read_report,render_markdown,render_html


def test_source_check_time_never_comes_from_report_generation(svc):
 observation(svc,'v')
 svc.store.update('sources','official',dict(last_checked_at='2024-01-01T00:00:00Z'))
 report=build_report(svc,'Analyse City vacancy Q2 2026')
 reopened=read_report(svc.store,report['report_id'])
 for text in [render_markdown(reopened),BeautifulSoup(render_html(reopened),'html.parser').get_text(' ',strip=True)]:
  assert 'Source last checked: 2024-01-01T00:00:00Z' in text
  assert 'Source last checked: '+report['generated_at'] not in text
  assert 'Evidence integrity checked at:' in text
 assert reopened['evidence'][0]['evidence_integrity_status']=='verified'


def test_missing_source_check_stays_unknown(svc):
 observation(svc,'v');report=build_report(svc,'Analyse City vacancy Q2 2026')
 for text in [render_markdown(report),BeautifulSoup(render_html(report),'html.parser').get_text(' ',strip=True)]:
  assert 'Source last checked: unknown' in text
