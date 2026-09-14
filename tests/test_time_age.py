"""Synthetic fixtures only; no family birthday or real observations in public tests."""
import json, subprocess, sys, uuid
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from time_age import *
from core import Store, render_markdown, validate_event, merge_docs
from record_observation import record

AT='2025-08-13T03:00:00Z'
BIRTH='2024-01-17'
CASES=[
 ('昨天有变化','day','2025-08-12','2025-08-12'),
 ('昨晚有变化','day','2025-08-12','2025-08-12'),
 ('前天有变化','day','2025-08-11','2025-08-11'),
 ('大前天有变化','day','2025-08-10','2025-08-10'),
 ('刚才有变化','day','2025-08-13','2025-08-13'),
 ('上周有变化','range','2025-08-04','2025-08-10'),
 ('上上周有变化','range','2025-07-28','2025-08-03'),
 ('上周三有变化','day','2025-08-06','2025-08-06'),
 ('上星期天有变化','day','2025-08-10','2025-08-10'),
 ('本周一有变化','day','2025-08-11','2025-08-11'),
 ('本周有变化','range','2025-08-11','2025-08-13'),
 ('过去一周有变化','range','2025-08-07','2025-08-13'),
 ('最近三天有变化','range','2025-08-11','2025-08-13'),
 ('一周前有变化','day','2025-08-06','2025-08-06'),
 ('两天前有变化','day','2025-08-11','2025-08-11'),
 ('二十一天前有变化','day','2025-07-23','2025-07-23'),
 ('一个月前有变化','day','2025-07-13','2025-07-13'),
 ('上个月有变化','range','2025-07-01','2025-07-31'),
 ('本月有变化','range','2025-08-01','2025-08-13'),
 ('2025年8月10日有变化','day','2025-08-10','2025-08-10'),
 ('8月10号有变化','day','2025-08-10','2025-08-10'),
 ('2025-08-10有变化','day','2025-08-10','2025-08-10'),
 ('8月4日到8月10日有变化','range','2025-08-04','2025-08-10'),
 ('前几天有变化','unknown',None,None),
 ('最近有变化','unknown',None,None),
 ('上周左右有变化','unknown',None,None),
 ('有变化','unknown',None,None),
 ('昨天改变了，上周也试过','ambiguous',None,None),
 ('转发妈妈昨天的话','ambiguous',None,None),
 ('明天会变化','invalid',None,None),
 ('8月30日会变化','invalid',None,None),
 ('2025年2月30日有变化','invalid',None,None),
]
@pytest.mark.parametrize('text,precision,start,end',CASES)
def test_date_rules(text,precision,start,end):
    x=resolve_time(text,AT)
    assert (x['precision'],x['start'],x['end'])==(precision,start,end)

def test_javascript_python_parity():
    js="const D=require(process.argv[1]);const c=JSON.parse(process.argv[2]);console.log(JSON.stringify(c.map(x=>D.resolve(x[0],process.argv[3]))));"
    result=subprocess.check_output(['node','-e',js,str(ROOT/'web/time_age.js'),json.dumps(CASES,ensure_ascii=False),AT],text=True)
    for row,actual in zip(CASES,json.loads(result)):
        expected=resolve_time(row[0],AT)
        for key in ('precision','start','end','reference_date','reported_at','expression','timezone','source'):
            assert actual[key]==expected[key],(row[0],key,actual,expected)

@pytest.mark.parametrize('birth,day,expected',[
 (BIRTH,'2025-08-13','18个月27天'),
 (BIRTH,'2025-08-17','19个月0天'),
 ('2024-01-31','2024-02-29','1个月0天'),
 ('2024-01-31','2024-03-30','1个月30天'),
 ('2024-02-29','2025-02-28','12个月0天'),
 ('2024-05-11','2024-05-11','0个月0天'),
 ('2024-05-11','2024-05-10','出生前，需核实日期'),
])
def test_age_math(birth,day,expected):
    assert age_on(birth,day)['label']==expected
    js='const D=require(process.argv[1]);console.log(D.ageOn(process.argv[2],process.argv[3]).label)'
    assert subprocess.check_output(['node','-e',js,str(ROOT/'web/time_age.js'),birth,day],text=True).strip()==expected

def test_week_cross_year_and_anchor():
    x=resolve_time('上周有变化','2025-01-01T01:00:00Z')
    assert (x['start'],x['end'])==('2024-12-23','2024-12-29')
    assert reference_day('2025-08-13T16:30:00Z','Asia/Shanghai')=='2025-08-14'
    assert resolve_time('昨天有变化','2025-08-13T16:30:00Z')['start']=='2025-08-13'

def test_manual_and_unknown_priority():
    assert resolve_time('昨天',AT,manual_start='2025-08-01')['start']=='2025-08-01'
    x=resolve_time('昨天',AT,manual_start='2025-08-01',manual_end='2025-08-05')
    assert x['precision']=='range'
    assert resolve_time('昨天',AT,unknown=True)['start'] is None
    assert resolve_time('昨天',AT,manual_start='2025-08-03',manual_end='2025-08-01')['precision']=='invalid'

def setup(store):
    p={'id':str(uuid.uuid4()),'kind':'profile','child':'both','text':'Synthetic birthday',
       'birth_date':BIRTH,'timezone':'Asia/Shanghai','date':'2025-08-13','created_at':AT,'observer':'测试'}
    store.append(p);return p

def test_cli_and_markdown_no_fake_exact_date(tmp_path):
    s=Store(tmp_path);setup(s)
    result=record(s,'上周小宝更愿意求助','B',AT,source_id='test-msg-1')
    assert result['event_date']=='2025-08-04 至 2025-08-10'
    assert result['age_at_event']=='18个月18天—18个月24天'
    text=(tmp_path/'generated/小宝_成长档案.md').read_text()
    assert '18个月18天—18个月24天' in text and '上周小宝更愿意求助' in text
    record(s,'上周小宝更愿意求助','B',AT,source_id='test-msg-1')
    assert len(s.read()['events'])==2
    assert '2025-08-04 至 2025-08-10' in render_markdown(s.read(),as_of='2026-01-01')['小宝_成长档案.md']
    assert (tmp_path/'generated/月龄/018个月.md').exists()

def test_unknown_is_not_report_date(tmp_path):
    s=Store(tmp_path);setup(s);record(s,'前几天大宝有个变化','A',AT)
    e=s.read()['events'][-1]
    assert e['date'] is None and e['time']['start'] is None
    assert (tmp_path/'generated/月度/日期未知.md').exists()
    assert '发生时间不确定，不计算事件月龄' in (tmp_path/'generated/大宝_成长档案.md').read_text()

def test_invalid_metadata_rejected(tmp_path):
    s=Store(tmp_path);setup(s);record(s,'昨天有变化','A',AT)
    e=s.read()['events'][-1];e['time']['reference_date']='2025-08-14'
    with pytest.raises(ValueError): validate_event(e)

def test_upgrade_preserves_originals(tmp_path):
    s=Store(tmp_path);old={'id':str(uuid.uuid4()),'kind':'baseline','child':'both','text':'旧口述近似月龄与已有表现',
                        'date':None,'created_at':AT}
    s.append(old);setup(s)
    assert s.read()['events'][0]==old
    assert '建档时对已有表现的回顾' in render_markdown(s.read())['大宝_成长档案.md']

def test_installer_keeps_own_journal_and_is_idempotent(tmp_path,monkeypatch):
    import install_calendar_update as upgrade
    def no_service(*a,**kw): raise OSError('No loopback service in isolated test')
    monkeypatch.setattr(upgrade.urllib.request,'urlopen',no_service)
    target=tmp_path/'old-growth';(target/'web').mkdir(parents=True);(target/'tools').mkdir()
    # V2.3 rejects unknown/custom HTML; use an approved template for this preservation test.
    (target/'web/index.html').write_bytes((upgrade.ROOT/'web/index.html').read_bytes());(target/'tools/core.py').write_text('# old core')
    s=Store(target/'private')
    old={'id':str(uuid.uuid4()),'kind':'observation','child':'A','text':'Synthetic pre-upgrade observation',
         'date':'2025-08-10','created_at':AT,'category':'待整理'}
    s.append(old)
    upgrade.install(target)
    after=Store(target/'private').read();assert old in after['events']
    n=len(after['events']);upgrade.install(target)
    assert len(Store(target/'private').read()['events'])==n
    assert list((target/'private/code_backups').glob('*.zip'))
    assert (target/'web/time_age.js').exists()
