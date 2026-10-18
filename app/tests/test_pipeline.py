from pathlib import Path
import pytest
from test_foundation import load


def test_real_saved_pdf_and_html_parse():
    d=load('documents');root=Path(__file__).resolve().parents[2]
    for key in ['q1-2026','q2-2026']:
        segments=d.parse_document((root/f'b1/data/raw/bnp-{key}.pdf').read_bytes(),'application/pdf')
        assert len(segments)==13
        assert '8.4%' in segments[2]['text'] and segments[2]['page']==3
    seg=d.parse_document((root/'b1/data/raw/bnp-q3-2025.html').read_bytes(),'text/html')
    assert any('2.7 million sq ft' in x['text'] for x in seg)


def test_native_workflow_seven_registered_steps():
    p=load('pipeline')
    workflow=p.make_workflow()
    assert [s.name for s in workflow.steps]==['Fetch','Parse','Extract','Validate','Persist','Compare','Export']


def test_export_escapes_untrusted_markup(tmp_path):
    p=load('pipeline')
    result=p.export_result({'observations':[],'comparisons':[],'note':'<script>alert(1)</script>'},tmp_path)
    assert Path(result['json']).exists() and Path(result['markdown']).exists()
    assert '<script>' not in Path(result['markdown']).read_text(encoding='utf-8')


def test_private_dns_is_rejected(monkeypatch):
    d=load('documents')
    monkeypatch.setattr(d.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('10.1.2.3',443))])
    with pytest.raises(ValueError):d.check_url('https://www.realestate.bnpparibas.co.uk/x',{'www.realestate.bnpparibas.co.uk'})


def test_false_quote_value_is_not_supported():
    v=load('validation')
    from test_foundation import fact
    f=fact(value='95',evidence={'segment_id':'p1','quote':'Prime City rent £95 per sq ft per annum'})
    assert v.validate(f,[{'segment_id':'p1','text':'Prime City rent £92.50 per sq ft per annum'}])['status']=='needs_review'


def test_extract_context_selection_is_explicit_and_keeps_complete_pages():
    e=load('extraction')
    selected=e.select_segments([{'segment_id':'p1','text':'Cover'}, {'segment_id':'p3','text':'OCCUPIER OVERVIEW\nCity prime rent 95 vacancy 8.4 take-up 3.0m'}, {'segment_id':'p4','text':'Other markets'}])
    assert [s['segment_id'] for s in selected]==['p1','p3']
    assert selected[1]['text'].endswith('3.0m')


def test_publisher_complete_key_stats_cover_is_kept_intact():
    e=load('extraction');cover={'segment_id':'p1','text':'Key Stats at a Glance\nTake-Up\nVacancy Rate\nPrime Office Rents\nFull original cover'}
    assert e.select_segments([cover,{'segment_id':'p3','text':'other narrative'}])==[cover]
