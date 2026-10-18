"""Bounded acquisition and stable evidence segments; never executes document content."""
import ipaddress
import socket
import time
from urllib.parse import urlparse, urljoin
import httpx
import httpcore
import pymupdf
from bs4 import BeautifulSoup
from .deadlines import call_until

MAX_BYTES=12*1024*1024
MAX_PAGES=40


def check_url(url, allowed_hosts):
    p=urlparse(url)
    if p.scheme!='https' or p.hostname not in allowed_hosts or p.username or p.password or p.port not in (None,443):
        raise ValueError('SOURCE_POLICY: HTTPS allowlisted host required')
    addresses={a[4][0] for a in socket.getaddrinfo(p.hostname,443,type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError('SOURCE_POLICY: non-public destination')
    return p


class PublicBackend(httpcore.SyncBackend):
    def connect_tcp(self,host,port,timeout=None,local_address=None,socket_options=None):
        host=host.decode() if isinstance(host,bytes) else host
        addresses={a[4][0] for a in socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
            raise ValueError('SOURCE_POLICY: DNS resolution is not public')
        # Connect to the checked numeric address: no second DNS lookup/rebinding window.
        return super().connect_tcp(sorted(addresses)[0],port,timeout,local_address,socket_options)


def fetch(url, allowed_hosts, prefixes=None,transport=None,deadline=None):
    deadline=deadline or time.monotonic()+480
    holder={}
    def close():
        if holder.get('client'):holder['client'].close()
    return call_until(lambda:_fetch(url,allowed_hosts,prefixes,transport,deadline,holder),deadline,close)


def _fetch(url,allowed_hosts,prefixes,transport,deadline,holder):
    if transport is None:
        transport=httpx.HTTPTransport(retries=0)
        transport._pool._network_backend=PublicBackend()
    with httpx.Client(transport=transport,timeout=httpx.Timeout(60,connect=15),follow_redirects=False,trust_env=False) as c:
        holder['client']=c
        for _ in range(4):
            if time.monotonic()>=deadline:raise ValueError('DOCUMENT_DEADLINE')
            p=check_url(url,allowed_hosts)
            if prefixes and not any(p.path.startswith(x) for x in prefixes):raise ValueError('SOURCE_POLICY: path not allowed')
            with c.stream('GET',url,headers={'User-Agent':'DeepInsightLite-B1/1.0 (local research validation)'}) as r:
                if r.is_redirect:
                    url=urljoin(url,r.headers['location']);continue
                r.raise_for_status();chunks=[];size=0
                for chunk in r.iter_bytes():
                    if time.monotonic()>=deadline:raise ValueError('DOCUMENT_DEADLINE')
                    size+=len(chunk)
                    if size>MAX_BYTES:raise ValueError('DOCUMENT_TOO_LARGE')
                    chunks.append(chunk)
                media=r.headers.get('content-type','').split(';')[0]
                if media not in ('text/html','application/pdf'):raise ValueError('UNSUPPORTED_MEDIA')
                return b''.join(chunks),media,url
    raise ValueError('TOO_MANY_REDIRECTS')


def parse_document(content: bytes, media: str) -> list[dict]:
    if media=='application/pdf':
        try:
            with pymupdf.open(stream=content,filetype='pdf') as doc:
                if doc.page_count>MAX_PAGES:raise ValueError('PAGE_BUDGET')
                rows=[{'segment_id':f'p{i+1}','page':i+1,'text':p.get_text(sort=False)} for i,p in enumerate(doc)]
        except Exception as e:raise ValueError('PDF_PARSE_FAILED: '+type(e).__name__) from e
        if any(not x['text'].strip() for x in rows):raise ValueError('SCAN_OR_EMPTY_PAGE_REQUIRES_REVIEW')
        return rows
    if media!='text/html':raise ValueError('UNSUPPORTED_MEDIA')
    soup=BeautifulSoup(content,'html.parser')
    for el in soup(['script','style','nav','footer','form','noscript']):el.decompose()
    article=soup.find('article') or soup.find('main') or soup.body or soup
    scope=next((h.get_text(' ',strip=True) for h in article.find_all(['h1','h2']) if 'Central London Office Market' in h.get_text(' ',strip=True)),None)
    rows=[]
    for idx,el in enumerate(article.find_all(['h1','h2','h3','p','ul','li','td'])):
        text=el.get_text(' ',strip=True)
        if text:rows.append({'segment_id':f'html-{idx}','page':None,'text':text,'tag':el.name,'offset':0,'scope_text':scope})
    if not rows:raise ValueError('HTML_EMPTY')
    if sum(len(x['text']) for x in rows)>240000:raise ValueError('TEXT_BUDGET')
    return rows
