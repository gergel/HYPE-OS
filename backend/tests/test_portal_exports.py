"""Isolated DB and S3-double tests; never uses production data."""
import io
import hashlib
from datetime import timedelta
from unittest.mock import patch
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.pool import StaticPool

# Production engine is not connected. Test uses its own SQLite engine.
from app.models import Base
from app.models.portal import Portal, PortalImage, PortalFolder
from app.models.portal_export import PortalExport
from app.services import portal_exports as exports
from app.api.routes.portal_exports import Access, ExportRequest, Item, create, check
from app.api.routes.portal_public import _create_unlock_token
from fastapi import HTTPException
from app.services.zip64 import Zip64Writer, PlannedEntry, ArcNameAllocator, sanitize_component
from app.services.export_storage.s3 import _MultipartWriter

@compiles(JSONB, 'sqlite')
def jsonb_sqlite(element, compiler, **kw):
    return 'JSON'

@pytest.fixture
def db(monkeypatch):
    engine = sa.create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(exports, 'SessionLocal', factory)
    # SQLite strips timezones; compare naive UTC in tests only.
    original_now = exports.now
    monkeypatch.setattr(exports, 'now', lambda: original_now().replace(tzinfo=None))
    import app.api.routes.portal_exports as routes
    monkeypatch.setattr(routes, 'now', exports.now)
    from app.workers.portal_export_tasks import build_export
    monkeypatch.setattr(build_export, 'delay', lambda *a: None)
    with factory() as session:
        p = Portal(slug='test-portal', status='live', title_override='Test')
        session.add(p);session.flush()
        session.add_all([PortalImage(portal_id=p.id, key='images/a.jpg', title='same', size_bytes=3),
                         PortalImage(portal_id=p.id, key='images/b.jpg', title='same', size_bytes=4)])
        session.commit()
        yield session
    engine.dispose()


def req(**kw):
    return ExportRequest(access=Access(slug='test-portal'), images=[Item(id=1),Item(id=2)], **kw)


def test_idempotent_and_names(db):
    a=create(req(),db); b=create(req(),db)
    assert a['id']==b['id']
    j=db.get(PortalExport,a['id'])
    assert [x['path'] for x in j.manifest]==['same.jpg','same (2).jpg']
    assert j.total_bytes==7

@pytest.mark.parametrize('mode',['hidden','folder_hidden','wrong_portal','password','expired','archived'])
def test_access_denied(db,mode):
    p=db.get(Portal,1)
    if mode=='hidden': db.get(PortalImage,1).rejtett=True
    if mode=='folder_hidden':
        f=PortalFolder(portal_id=1,name='Private',rejtett=True);db.add(f);db.flush();db.get(PortalImage,1).folder_id=f.id
    if mode=='wrong_portal':
        q=Portal(slug='other',status='live');db.add(q);db.flush();db.get(PortalImage,1).portal_id=q.id
    if mode=='password': p.password_hash='protected'
    if mode=='expired': p.expires_at=exports.now().date()-timedelta(days=1)
    if mode=='archived': p.status='archived'
    db.commit();db.expire_all()
    with pytest.raises(HTTPException): create(req(),db)


def test_password_unlock_and_job_recheck(db):
    p=db.get(Portal,1);p.password_hash='protected';db.commit()
    r=req();r.access.authorization=_create_unlock_token(1)
    a=create(r,db)
    assert check(a['id'],r.access,db)['state']=='queued'
    db.get(PortalImage,1).rejtett=True;db.commit();db.expire_all()
    with pytest.raises(HTTPException): check(a['id'],r.access,db)


def test_folder_share_limited(db):
    f=PortalFolder(portal_id=1,name='Shared',share_token='folder-token');db.add(f);db.flush()
    db.get(PortalImage,1).folder_id=f.id;db.commit();db.expire_all()
    r=req();r.access=Access(part='folder-token')
    with pytest.raises(HTTPException): create(r,db)
    r.images=[Item(id=1)];assert create(r,db)['state']=='queued'

class FakeS3:
    def __init__(self): self.data={'media-portal/images/a.jpg':b'abc','media-portal/images/b.jpg':b'defg'}
    def head_object(self, Bucket, Key):
        data=self.data[Key];return {'ContentLength':len(data),'ETag':hashlib.md5(data).hexdigest()}
    def get_object(self, Bucket, Key, IfMatch):
        assert IfMatch==self.head_object(Bucket,Key)['ETag']
        return {'Body':io.BytesIO(self.data[Key])}

class FakeStore:
    def __init__(self): self.data={}
    def open_write(self,key,**kw):
        from contextlib import contextmanager
        from types import SimpleNamespace
        @contextmanager
        def ctx():
            stream=io.BytesIO();holder=SimpleNamespace(write=stream.write,result=None)
            yield holder
            data=stream.getvalue();self.data[key]=data
            holder.result=SimpleNamespace(size=len(data),sha256=hashlib.sha256(data).hexdigest())
        return ctx()
    def delete(self,key): self.data.pop(key,None)
    def presigned_download_url(self,key,**kw): return 'https://example.test/'+key


def test_worker_integrity_and_duplicate_claim(db,monkeypatch):
    store=FakeStore();client=FakeS3()
    monkeypatch.setattr(exports.storage,'_client',lambda:client)
    monkeypatch.setattr(exports,'object_store',lambda:store)
    j=create(req(),db);exports.run_export(j['id']);exports.run_export(j['id'])
    db.expire_all();job=db.get(PortalExport,j['id'])
    assert job.state=='ready' and job.attempts==1
    import zipfile
    z=zipfile.ZipFile(io.BytesIO(store.data[job.object_key]))
    assert z.testzip() is None
    assert [z.read(n) for n in z.namelist()]==[b'abc',b'defg']
    assert job.bytes_done==job.total_bytes==7


def test_missing_source_never_ready(db,monkeypatch):
    client=FakeS3();client.data.pop('media-portal/images/a.jpg')
    monkeypatch.setattr(exports.storage,'_client',lambda:client)
    monkeypatch.setattr(exports,'object_store',lambda:FakeStore())
    j=create(req(),db)
    for _ in range(3): exports.run_export(j['id'])
    db.expire_all();job=db.get(PortalExport,j['id'])
    assert job.state=='failed' and job.attempts==3


def test_change_during_export(db,monkeypatch):
    client=FakeS3();original=client.get_object
    def changed(**kw):
        out=original(**kw);client.data[kw['Key']]=b'xyz';return out
    client.get_object=changed
    monkeypatch.setattr(exports.storage,'_client',lambda:client)
    monkeypatch.setattr(exports,'object_store',lambda:FakeStore())
    j=create(req(),db);exports.run_export(j['id']);db.expire_all()
    assert db.get(PortalExport,j['id']).state=='failed'


def test_delete_guard():
    with pytest.raises(ValueError): exports.safe_delete('media-portal/images/original.jpg')


def test_multipart_boundaries():
    class Client:
        def __init__(self): self.parts=[]
        def upload_part(self,**kw): self.parts.append(kw['Body']);return {'ETag':str(len(self.parts))}
    client=Client();writer=_MultipartWriter(client,'bucket','key','upload',5*1024*1024)
    data=b'x'*(12*1024*1024+3)
    for n in range(0,len(data),1024*1024): writer.write(data[n:n+1024*1024])
    parts,size,digest=writer.finish()
    assert b''.join(client.parts)==data and len(parts)==3 and size==len(data)
    assert digest==hashlib.sha256(data).hexdigest()

@pytest.mark.skipif(not __import__('os').environ.get('RUN_R2_EXPORT_TEST'), reason='explicit real R2 test only')
def test_real_r2_export_and_range(db):
    import requests, uuid, zipfile, json, time
    from app.core.config import settings
    prefix='media-portal/export-smoke-'+uuid.uuid4().hex+'/'
    client=exports.storage._client()
    keys=[prefix+'a.jpg',prefix+'b.jpg']
    # >32 MiB exercises actual multipart part upload/completion.
    data=[b'photo-a-'*(5*1024*1024), b'photo-b-'*(1024*1024)]
    job=None;started=time.monotonic()
    try:
        for i,(key,content) in enumerate(zip(keys,data),1):
            client.put_object(Bucket=settings.r2_bucket_name,Key=key,Body=content)
            image=db.get(PortalImage,i);image.key=key;image.size_bytes=len(content)
        db.commit()
        created=create(req(),db);exports.run_export(created['id']);db.expire_all()
        job=db.get(PortalExport,created['id']);assert job.state=='ready',job.error
        result=check(job.id,Access(slug='test-portal'),db)
        url=result['url']
        first=requests.get(url,headers={'Range':'bytes=0-1048575'},timeout=90)
        assert first.status_code==206
        renewed=check(job.id,Access(slug='test-portal'),db)['url']
        tail=requests.get(renewed,headers={'Range':'bytes=1048576-', 'If-Range':first.headers['ETag']},timeout=90)
        assert tail.status_code==206 and tail.headers['ETag']==first.headers['ETag']
        archive=first.content+tail.content
        assert len(archive)==job.object_size
        assert hashlib.sha256(archive).hexdigest()==job.sha256
        z=zipfile.ZipFile(io.BytesIO(archive));assert z.testzip() is None
        assert [hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()]==[hashlib.sha256(d).hexdigest() for d in data]
        print(json.dumps({'source_bytes':sum(map(len,data)),'archive_bytes':len(archive),
            'sha256':job.sha256,'range_status':tail.status_code,'seconds':round(time.monotonic()-started,2)}))
    finally:
        for key in keys: client.delete_object(Bucket=settings.r2_bucket_name,Key=key)
        if job and job.object_key: exports.safe_delete(job.object_key)
