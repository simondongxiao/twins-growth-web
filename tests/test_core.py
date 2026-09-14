import copy, json, multiprocessing, sys, threading, time, uuid
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from core import Store, validate_doc, merge_docs, active_events, render_markdown
from sync_cloud import sync_once

def event(text='今天自己说开',child='A',kind='observation',**kw):
    return {'id':str(uuid.uuid4()),'kind':kind,'child':child,'text':text,'category':'沟通语言','date':'2026-09-14','created_at':'2026-09-14T03:00:00Z','observer':'爸爸',**kw}
def doc(*es):return {'schema_version':2,'events':list(es)}
def append_worker(path,n):
    s=Store(Path(path))
    for i in range(n): s.append(event(f'process {i}'))

def test_roundtrip_markdown(tmp_path):
    s=Store(tmp_path);e=event();s.append(e)
    assert e['text'] in (tmp_path/'generated/大宝_成长档案.md').read_text()
    assert e['text'] not in (tmp_path/'generated/小宝_成长档案.md').read_text()
    assert s.read()['events']==[e]
def test_shared_not_duplicated_in_ledger(tmp_path):
    s=Store(tmp_path);e=event(child='both');s.append(e)
    assert len(s.read()['events'])==1
    assert e['text'] in (tmp_path/'generated/小宝_成长档案.md').read_text()
def test_idempotent_and_conflict(tmp_path):
    s=Store(tmp_path);e=event();s.append(e);s.append(e);assert len(s.read()['events'])==1
    changed={**e,'text':'different'}
    with pytest.raises(ValueError):s.append(changed)
    assert s.read()['events'][0]['text']==e['text']
def test_unknown_date():
    e=event(date=None);d=validate_doc(doc(e));assert '发生日未知' in render_markdown(d)['大宝_成长档案.md']
def test_retract_preserves_audit_removes_month_view(tmp_path):
    s=Store(tmp_path);e=event();s.append(e);r=event(kind='retract',target_id=e['id']);s.append(r)
    assert len(s.read()['events'])==2;assert active_events(s.read())==[]
    assert not (tmp_path/'generated/月度/2026-09.md').exists()
def test_three_actions_and_confirmation():
    with pytest.raises(ValueError):validate_doc(doc(event(kind='proposal',actions=['1','2','3','4'])))
    with pytest.raises(ValueError):validate_doc(doc(event(kind='plan',actions=['1'])))
    assert validate_doc(doc(event(kind='plan',actions=['1'],parent_confirmed=True)))
def test_invalid_future_shapes():
    with pytest.raises(ValueError):validate_doc(doc(event(date='2026-02-31')))
    with pytest.raises(ValueError):validate_doc(doc(event(child='C')))
    with pytest.raises(ValueError):validate_doc(doc(event(text='')))
def test_atomic_import_rejects_conflict(tmp_path):
    s=Store(tmp_path);e=event();s.append(e)
    with pytest.raises(ValueError):s.merge(doc(event(),{**e,'text':'bad'}))
    assert len(s.read()['events'])==1
def test_thread_parallel(tmp_path):
    s=Store(tmp_path)
    ts=[threading.Thread(target=lambda:s.append(event())) for _ in range(12)]
    for t in ts:t.start()
    for t in ts:t.join()
    assert len(s.read()['events'])==12
def test_process_parallel(tmp_path):
    Store(tmp_path)
    ps=[multiprocessing.get_context("spawn").Process(target=append_worker,args=(str(tmp_path),8)) for _ in range(3)]
    for p in ps:p.start()
    for p in ps:p.join(20);assert p.exitcode==0
    assert len(Store(tmp_path).read()['events'])==24
class FakeCloud:
    def __init__(self,remote):self.remote=remote
    def login(self):pass
    def read(self):return copy.deepcopy(self.remote)
    def write(self,events):self.remote=merge_docs(self.remote,doc(*events))
def test_cloud_mock_union_and_repeat(tmp_path):
    s=Store(tmp_path);a=event(child='A');b=event(child='B');s.append(a);c=FakeCloud(doc(b))
    sync_once(s,c);assert len(s.read()['events'])==2;assert len(c.remote['events'])==2
    sync_once(s,c);assert len(s.read()['events'])==2
def test_cloud_mock_failure_retains(tmp_path):
    s=Store(tmp_path);a=event();s.append(a)
    c=FakeCloud(doc());c.write=lambda es:(_ for _ in ()).throw(RuntimeError('offline'))
    with pytest.raises(RuntimeError):sync_once(s,c)
    assert s.read()['events']==[a]
def test_cloud_mock_merge_new_during_network(tmp_path):
    s=Store(tmp_path);a=event();s.append(a);c=FakeCloud(doc());base=c.write
    def write(es):base(es);s.append(event(text='saved during network'))
    c.write=write;sync_once(s,c);assert len(s.read()['events'])==2
