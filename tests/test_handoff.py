"""Isolated collaboration tests. No real family cloud, GitHub or user files are written."""
import copy, json, sys, uuid
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from core import Store, validate_doc
from handoff import run_handoff, is_receipt, make_receipts
from github_backup import backup, validate_repo

def event(text='测试观察',observer='妈妈',child='B'):
    return {'id':str(uuid.uuid4()),'kind':'observation','child':child,'text':text,'date':'2026-09-13','created_at':'2026-09-14T04:00:00Z','observer':observer,'category':'沟通语言'}
class MemoryCloud:
    def __init__(self,events=None):self.events=copy.deepcopy(events or []);self.fail_read=False;self.fail_receipts=False
    def login(self):pass
    def read(self):
        if self.fail_read:raise RuntimeError('模拟网络读取失败')
        return validate_doc({'schema_version':2,'events':copy.deepcopy(self.events)})
    def write(self,events):
        if self.fail_receipts and any(is_receipt(e) for e in events):raise RuntimeError('模拟回执上传失败')
        existing={e['id'] for e in self.events}
        for e in events:
            if e['id'] not in existing:self.events.append(copy.deepcopy(e));existing.add(e['id'])

def test_mother_cloud_to_local_and_receipt(tmp_path):
    e=event();c=MemoryCloud([e]);s=Store(tmp_path)
    r=run_handoff(s,cloud=c)
    assert r['new_observations']==1 and r['local_markdown']=='confirmed' and r['receipt_cloud']=='confirmed'
    assert e['text'] in (tmp_path/'generated/小宝_成长档案.md').read_text()
    assert any(e['id'] in x.get('event_ids',[]) for x in c.events)
    assert (tmp_path/'sync-status.json').exists()

def test_repeat_click_is_idempotent(tmp_path):
    s=Store(tmp_path);c=MemoryCloud([event()]);run_handoff(s,cloud=c);before=s.read()
    r=run_handoff(s,cloud=c)
    assert r['new_observations']==0 and r['newly_archived_observations']==0 and s.read()==before

def test_local_offline_no_fake_cloud_success(tmp_path):
    s=Store(tmp_path);s.append(event());r=run_handoff(s)
    assert r['cloud']=='not_configured' and r['receipt_cloud']=='not_configured' and r['local_markdown']=='confirmed'

def test_conflict_stops_without_overwriting(tmp_path):
    s=Store(tmp_path);e=event('原话');s.append(e);remote=dict(e,text='冲突版本');before=s.read()
    with pytest.raises(ValueError):run_handoff(s,cloud=MemoryCloud([remote]))
    assert s.read()==before and not any(is_receipt(x) for x in s.read()['events'])

def test_failed_cloud_does_not_create_receipt(tmp_path):
    s=Store(tmp_path);s.append(event());before=s.read();c=MemoryCloud();c.fail_read=True
    with pytest.raises(RuntimeError):run_handoff(s,cloud=c)
    assert s.read()==before

def test_receipt_failure_retries_without_duplicate(tmp_path):
    s=Store(tmp_path);c=MemoryCloud([event()]);c.fail_receipts=True;r=run_handoff(s,cloud=c)
    assert r['receipt_cloud']=='pending' and r['local_markdown']=='confirmed'
    ids=[x['id'] for x in s.read()['events'] if is_receipt(x)]
    c.fail_receipts=False;r=run_handoff(s,cloud=c)
    assert r['receipt_cloud']=='confirmed'
    assert [x['id'] for x in s.read()['events'] if is_receipt(x)]==ids
    assert all(any(e['id']==i for e in c.events) for i in ids)

def test_github_failure_preserves_local_success(tmp_path):
    def fail(*_):raise RuntimeError('模拟GitHub不可用')
    s=Store(tmp_path);c=MemoryCloud([event()]);r=run_handoff(s,True,c,fail)
    assert r['github']['status']=='failed' and r['local_markdown']=='confirmed'
    assert not any(e.get('stage')=='github_private' for e in s.read()['events'])
    assert r['receipt_cloud']=='confirmed'

def test_github_success_receipt_and_no_repeat_upload(tmp_path):
    called=[]
    def ok(*args):called.append(1);return {'status':'confirmed','commit':'a'*40}
    s=Store(tmp_path);c=MemoryCloud([event()]);r=run_handoff(s,True,c,ok)
    assert r['github']['status']=='confirmed'
    assert any(e.get('stage')=='github_private' for e in c.events)
    assert run_handoff(s,True,c,ok)['github']['status']=='unchanged' and len(called)==1

def test_receipts_batch_200(tmp_path):
    doc={'schema_version':2,'events':[event() for _ in range(401)]}
    rs=make_receipts(doc,'local_markdown');assert [len(x['event_ids']) for x in rs]==[200,200,1]

class FakeGitHub:
    def __init__(self,private=True,pages=False):self.private=private;self.pages=pages;self.calls=[]
    def api(self,path,method='GET',data=None):
        self.calls.append((path,method,data))
        if path=='repos/owner/data':return {'private':self.private,'has_pages':self.pages,'default_branch':'main','archived':False}
        if '/git/ref/heads/' in path:return {'object':{'sha':'a'*40}}
        if '/git/commits/' in path:return {'tree':{'sha':'b'*40}}
        if path.endswith('/git/trees'):return {'sha':'c'*40}
        if path.endswith('/git/commits'):return {'sha':'d'*40}
        if '/git/refs/heads/' in path:return {'object':{'sha':'d'*40}}
        raise AssertionError(path)

def test_public_repo_refused():
    a=FakeGitHub(private=False)
    with pytest.raises(ValueError):validate_repo('owner/data',a)
    assert len(a.calls)==1

def test_pages_enabled_data_repo_refused():
    with pytest.raises(ValueError):validate_repo('owner/data',FakeGitHub(pages=True))

def test_backup_allowlist_and_non_force(tmp_path):
    cfg=tmp_path/'github.local.json';cfg.write_text('{"repo":"owner/data"}')
    (tmp_path/'cloud.local.json').write_text('SENSITIVE_PASSWORD_SHOULD_NOT_BE_READ')
    a=FakeGitHub();r=backup({'schema_version':2,'events':[event()]},cfg,a)
    assert r['status']=='confirmed'
    tree=next(data for path,method,data in a.calls if path.endswith('/git/trees'))
    assert all(x['path'].endswith(('.md','.json')) for x in tree['tree'])
    assert 'SENSITIVE_PASSWORD' not in json.dumps(tree)
    patch=next(data for path,method,data in a.calls if method=='PATCH');assert patch['force'] is False

@pytest.mark.parametrize('repo',['https://evil.invalid/data','../../data','owner/data/extra','owner;echo/data',''])
def test_repo_validation_rejects_invalid(repo):
    with pytest.raises(ValueError):validate_repo(repo,FakeGitHub())

def test_retracted_raw_record_remains(tmp_path):
    s=Store(tmp_path);e=event('错误观察');s.append(e);s.append({'id':str(uuid.uuid4()),'kind':'retract','child':'B','text':'撤回','date':None,'created_at':'2026-09-14T04:30:00Z','target_id':e['id']})
    run_handoff(s)
    assert any(x['text']=='错误观察' for x in s.read()['events'])
    assert '错误观察' not in (tmp_path/'generated/小宝_成长档案.md').read_text()
