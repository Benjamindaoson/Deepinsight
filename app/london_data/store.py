"""Versioned SQLite domain store, separate from Agno internal schemas."""
import hashlib
import json
import uuid
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import create_engine,text


def now():return datetime.now(timezone.utc).isoformat()
def uid():return str(uuid.uuid4())
def dumps(x):return json.dumps(x,ensure_ascii=False,default=str)


class Repository:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.engine=create_engine('sqlite:///'+str(self.path),connect_args={'timeout':5})
        with self.engine.begin() as c:
            c.execute(text('PRAGMA journal_mode=WAL'))
            migration=Path(__file__).resolve().parents[1]/'migrations/001_initial.sql'
            for statement in migration.read_text(encoding='utf-8').split(';'):
                if statement.strip():c.execute(text(statement))
            c.execute(text('INSERT OR IGNORE INTO schema_versions VALUES(1,:t)'),{'t':now()})

    def put(self,table,identity,payload,conn=None):
        if table not in ['sources','documents','attempts','observations','comparisons']:raise ValueError('TABLE')
        if conn is None:
            with self.engine.begin() as c:return self.put(table,identity,payload,c)
        old=conn.execute(text(f'SELECT payload FROM {table} WHERE identity=:i'),{'i':identity}).scalar()
        if old:return json.loads(old)
        data=dict(payload,id=payload.get('id',uid()),created_at=now())
        conn.execute(text(f'INSERT INTO {table} VALUES(:id,:i,:p)'),{'id':data['id'],'i':identity,'p':dumps(data)})
        return data

    def all(self,table):
        if table not in ['sources','documents','attempts','observations','comparisons']:raise ValueError('TABLE')
        with self.engine.connect() as c:return [json.loads(r[0]) for r in c.execute(text(f'SELECT payload FROM {table} ORDER BY rowid'))]

    def get(self,table,id):
        return next((x for x in self.all(table) if x['id']==id),None)

    def update(self,table,id,data,conn=None):
        if table not in ['sources','documents','attempts','observations','comparisons']:raise ValueError('TABLE')
        if conn is None:
            with self.engine.begin() as c:return self.update(table,id,data,c)
        conn.execute(text(f'UPDATE {table} SET payload=:p WHERE id=:id'),{'p':dumps(data),'id':id})

    def snapshot(self,source,url,content,media,published,segments):
        sha=hashlib.sha256(content).hexdigest()
        directory=self.path.parent/'snapshots';directory.mkdir(exist_ok=True)
        file=directory/(sha+('.pdf' if media=='application/pdf' else '.html'))
        if not file.exists():file.write_bytes(content)
        row=self.put('documents',source+':'+sha,dict(source_id=source,url=url,sha256=sha,media=media,published_at=published,collected_at=now(),path=str(file),segments=segments,parser_version='pymupdf-bs4-v1',aliases=[url]))
        if url not in row['aliases']:
            row['aliases'].append(url);self.update('documents',row['id'],row)
        return row

    def attempt(self,document,version,run):
        return self.put('attempts',uid(),dict(document_id=document,version=version,run_id=run,status='running'))

    def successful(self,document,version):
        return next((a for a in reversed(self.all('attempts')) if a['document_id']==document and a['version']==version and a['status']=='succeeded'),None)

    def persist(self,attempt,facts,fail_after_first=False):
        prior=self.get('attempts',attempt['id'])
        if prior and prior['status']=='failed':raise ValueError('FAILED_ATTEMPT_REQUIRES_NEW_ATTEMPT')
        try:return self._persist(attempt,facts,fail_after_first)
        except Exception as e:
            self.update('attempts',attempt['id'],dict(attempt,status='failed',finished_at=now(),error_type=type(e).__name__))
            raise

    def _persist(self,attempt,facts,fail_after_first=False):
        with self.engine.begin() as c:
            for index,f in enumerate(facts):
                # Config attempts may differ; equivalent facts reuse document/version/semantic identity.
                identity='|'.join(str(f.get(k)) for k in ['document_id','metric','geography','period'])+'|'+attempt['version']
                data=self.put('observations',identity,dict(f,attempt_id=attempt['id'],run_id=attempt['run_id']),c)
                others=[json.loads(r[0]) for r in c.execute(text('SELECT payload FROM observations WHERE id!=:id'),{'id':data['id']})]
                for other in others:
                    if all(other.get(k)==data.get(k) for k in ['source_id','series','metric','geography','period','definition']):
                        if other.get('value')!=data.get('value'):
                            for row in [other,data]:
                                row.update(status='needs_review',conflict_with=other['id'] if row['id']==data['id'] else data['id'])
                                self.update('observations',row['id'],row,c)
                        elif other.get('status') in ['validated','needs_review'] and data.get('status') in ['validated','needs_review']:
                            other.update(status='superseded',superseded_by=data['id']);data['supersedes']=other['id']
                            self.update('observations',other['id'],other,c);self.update('observations',data['id'],data,c)
                if fail_after_first and index==0:raise RuntimeError('Injected write interruption')
            updated=dict(attempt,status='succeeded',finished_at=now());self.update('attempts',attempt['id'],updated,c)

    def observations(self,include_all=False):
        return [x for x in self.all('observations') if include_all or x['status']=='validated']

    def save_comparison(self,result):
        # Include the frozen inputs/statuses: a later conflict must create a new
        # judgement while preserving the original historical result by ID.
        ident=hashlib.sha256(dumps(result).encode()).hexdigest()
        return self.put('comparisons',ident,result)

    def current_comparisons(self):
        active={o['id']:o for o in self.observations(include_all=True) if o['status']!='superseded'}
        current={}
        for c in self.all('comparisons'):
            a,b=c['old']['id'],c['new']['id']
            if a not in active or b not in active:continue
            if any(c[side].get('status')!=active[id].get('status') or c[side].get('value')!=active[id].get('value') for side,id in [('old',a),('new',b)]):continue
            current[(a,b)]=c
        return list(current.values())
