import pytest
from london_product.sources import _check_url


@pytest.mark.parametrize('url',[
 'https://www.colliers.com/en-gb/research/london-offices-snapshot-july-2026',
 'https://www.carterjonas.co.uk/insights/central-london-net-effective-rents-monitor-q2-2026',
])
def test_named_public_research_publishers_are_registered(url):
 assert _check_url(url).scheme=='https'


@pytest.mark.parametrize('url',['http://www.colliers.com/a','https://www.colliers.com.evil.invalid/a','https://127.0.0.1/a'])
def test_new_publisher_registration_does_not_allow_arbitrary_hosts(url):
 with pytest.raises(ValueError):_check_url(url)
