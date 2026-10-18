"""Human review workflow: decisions, gates, audit trail and directional effect."""
import pytest

from london_product.service import MarketService
from london_product.store import Store


@pytest.fixture
def service(tmp_path):
    store = Store(tmp_path)
    store.put('documents', 'doc-1', dict(id='doc-1', title='BNP Q1 2026', url='https://example.test/bnp.pdf',
                                         sha256='a' * 64, path='unused', segments=[]))
    return MarketService(store)


def make_fact(service, identity, **overrides):
    payload = dict(
        id=identity, metric='takeup', value='2.5', normalized_value='2500000.0', unit='m sq ft',
        normalized_unit='sqft', geography='Central London', period='2026Q1', normalized_period='2026Q1',
        definition='Central London take-up, deals over 1,000 sq ft', status='pending_review',
        human_review_status='pending_review', source_id='bnp', document_id='doc-1',
        annualization='not_applicable', evidence=dict(quote='2.5m sq ft in Q1 2026', page=3, locator='pdf:page:3'),
    )
    payload.update(overrides)
    return service.store.put('facts', identity, payload)


def test_approve_requires_a_note_when_validation_flags_are_present(service):
    make_fact(service, 'flagged', status='needs_review')
    with pytest.raises(ValueError, match='note is required'):
        service.review_fact('flagged', 'approve', 'alice')
    result = service.review_fact('flagged', 'approve', 'alice', 'checked the quote on page 3')
    assert result['fact']['status'] == 'validated'
    assert result['fact']['human_review_status'] == 'approved'
    assert result['fact']['reviewed_by'] == 'alice'


def test_rent_without_annual_basis_cannot_be_approved(service):
    make_fact(service, 'rent-unknown', metric='rent', unit='GBP', normalized_unit=None,
              annualization='unknown', normalized_value=None)
    with pytest.raises(ValueError, match='RENT_ANNUAL_BASIS_UNRESOLVED'):
        service.review_fact('rent-unknown', 'approve', 'alice', 'looks fine')


def test_convention_rent_requires_an_explicit_reviewer_note(service):
    """Industry-convention annualisation may be approved, but only in writing."""
    make_fact(service, 'rent-convention', metric='rent', value='95', unit='GBP/sqft',
              normalized_value='95', normalized_unit='GBP/sqft/year',
              annualization='industry_convention', status='pending_review')
    with pytest.raises(ValueError, match='note is required'):
        service.review_fact('rent-convention', 'approve', 'alice')
    assert service.store.get('facts', 'rent-convention')['human_review_status'] == 'pending_review'
    approved = service.review_fact('rent-convention', 'approve', 'alice',
                                   'confirmed the annual quoting convention with the publisher note')
    assert approved['fact']['status'] == 'validated'
    assert approved['review']['annualization'] == 'industry_convention'
    assert 'ANNUAL_BASIS_ASSUMED' in approved['review']['blockers']


def test_reject_requires_a_reason_and_removes_the_fact_from_answers(service):
    make_fact(service, 'bad')
    with pytest.raises(ValueError, match='rejection reason'):
        service.review_fact('bad', 'reject', 'alice')
    result = service.review_fact('bad', 'reject', 'alice', 'quote does not match the original')
    assert result['fact']['status'] == 'rejected'
    assert result['fact']['human_review_status'] == 'rejected'


def test_every_decision_is_audited_with_the_prior_state(service):
    make_fact(service, 'audited')
    service.review_fact('audited', 'approve', 'alice')
    service.review_fact('audited', 'reopen', 'bob', 'second look')
    decisions = [r for r in service.store.all('reviews') if r['fact_id'] == 'audited']
    assert [d['decision'] for d in decisions] == ['reopen', 'approve']
    approve = decisions[-1]
    assert approve['prior_status'] == 'pending_review'
    assert approve['prior_review_status'] == 'pending_review'
    assert approve['fact_snapshot_sha256'] and len(approve['fact_snapshot_sha256']) == 64
    assert service.store.get('facts', 'audited')['status'] == 'pending_review'


def test_queue_counts_and_eligibility(service):
    make_fact(service, 'ok-1')
    make_fact(service, 'ok-2', geography='West End')
    make_fact(service, 'blocked', metric='rent', unit='GBP', annualization='unknown', normalized_value=None)
    queue = service.review_queue('pending')
    assert queue['total'] == 3
    assert queue['counts'] == dict(pending=3, approved=0, rejected=0)
    blocked = next(f for f in queue['items'] if f['id'] == 'blocked')
    assert blocked['approval']['eligible'] is False
    assert 'RENT_ANNUAL_BASIS_UNRESOLVED' in blocked['approval']['blockers']
    service.review_fact('ok-1', 'approve', 'alice')
    approved = service.review_queue('approved')
    assert approved['total'] == 1 and approved['items'][0]['id'] == 'ok-1'


def test_validated_pair_upgrades_the_directional_basis(service):
    from london_product import directional
    make_fact(service, 'q1', normalized_value='2500000.0')
    make_fact(service, 'q2', period='2026Q2', normalized_period='2026Q2', value='3.0',
              normalized_value='3000000.0', evidence=dict(quote='3.0m sq ft in Q2 2026', page=3, locator='pdf:page:3'))
    candidate = directional.assess(service.store)['series'][0]
    assert candidate['basis'] == 'candidate_observations_only'
    assert candidate['direction'] == 'up'
    service.review_fact('q1', 'approve', 'alice')
    service.review_fact('q2', 'approve', 'alice')
    reviewed = directional.assess(service.store)['series'][0]
    assert reviewed['basis'] == 'human_approved'
    assert reviewed['reviewed'] is True
    assert reviewed['absolute_change'] == '500000.0000'
