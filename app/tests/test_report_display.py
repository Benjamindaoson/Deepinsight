"""Offline display fixtures; no real market review decisions."""
from bs4 import BeautifulSoup
from test_finding_verification import svc,observation
from london_product.chat_report import build_report,render_html


def test_exact_repeat_disclosures_merge_only_for_display_and_preserve_ids(svc):
 first=observation(svc,'first',approved=False)
 svc.store.put('facts','repeat',dict(first,id='repeat'))
 other=observation(svc,'other',value='9',approved=False)
 report=build_report(svc,'Analyse City vacancy Q2 2026')
 assert len(report['market_snapshot'])==2
 assert set(next(r for r in report['market_snapshot'] if r['value']=='8')['evidence_ids'])=={'first','repeat'}
 assert len(report['evidence'])==3 and len(svc.store.all('facts'))==3


def test_export_draws_released_points_and_exposes_review_actor(svc):
 observation(svc,'old',period='2026Q1',value='6.8')
 observation(svc,'new',period='2026Q2',value='6.7')
 svc.store.update('facts','new',dict(reviewed_by='Offline delegated reviewer',review_note='Fixture source review'))
 report=build_report(svc,'Analyse City vacancy Q2 2026 historical trend')
 soup=BeautifulSoup(render_html(report),'html.parser')
 assert soup.select('svg polyline')
 assert len(soup.select('svg circle'))==2
 assert '6.8' in soup.select_one('svg').get_text() and '6.7' in soup.select_one('svg').get_text()
 assert 'Offline delegated reviewer' in soup.get_text()
