"""Every format keeps existing artifact content; fixtures remain synthetic."""
from bs4 import BeautifulSoup
from test_finding_verification import svc,observation
from london_product.chat_report import build_report,render_markdown,render_html


def test_raw_definitions_and_all_chart_slot_metadata_survive_both_exports(svc):
    observation(svc,'city',approved=False,definition='SYNTHETIC distinct stock-share definition')
    report=build_report(svc,'Compare City and Canary Wharf vacancy Q2 2026')
    report['charts'][0].update(unit='SYNTHETIC-UNIT',reason='SYNTHETIC missing compatible series')
    markdown=render_markdown(report)
    html=BeautifulSoup(render_html(report),'html.parser').get_text(' ',strip=True)
    for text in ['SYNTHETIC distinct stock-share definition','SYNTHETIC-UNIT','SYNTHETIC missing compatible series','Research scope:']:
        assert text in markdown and text in html
    for chart in report['charts']:
        assert chart['title'] in markdown and chart['title'] in html


def test_related_disclosure_definition_and_scope_note_survive_both_exports(svc):
    observation(svc,'combined',geography='Canary Wharf & Docklands',approved=False,definition='SYNTHETIC combined submarket denominator')
    report=build_report(svc,'Compare City and Canary Wharf vacancy Q2 2026')
    assert report['related_observations']
    row=report['related_observations'][0]
    md=render_markdown(report);page=BeautifulSoup(render_html(report),'html.parser').get_text(' ',strip=True)
    for text in [row['definition'],row['geography'],row['scope_note']]:
        assert text in md and text in page
