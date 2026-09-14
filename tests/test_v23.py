"""New attribution, immutable raw-source, and reference-boundary regression cases."""
import json,subprocess,sys,uuid
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from core import Store,validate_doc,render_markdown
from development_reference import BY_ID,status,candidates

def event(**kw):
    return {'id':str(uuid.uuid4()),'kind':'observation','child':'A','text':'今天大宝尝试用勺','category':'精细与自理','date':'2026-09-14','created_at':'2026-09-14T06:00:00Z','observer':'爸爸',**kw}

def parse(text,child='A'):
    cmd=f"require({json.dumps(str(ROOT/'web/time_age.js'))});const p=require({json.dumps(str(ROOT/'web/observation_parser.js'))});const a=JSON.parse(require('fs').readFileSync(0,'utf8'));console.log(JSON.stringify(p.split(a.text,a.child)));"
    return json.loads(subprocess.run(['node','-e',cmd],input=json.dumps({'text':text,'child':child}),text=True,capture_output=True,check=True).stdout)

@pytest.mark.parametrize('text,children',[
 ('昨天大宝吃饭，小宝喝水',['A','B']),
 ('昨天大宝自己吃饭 小宝自己喝水',['A','B']),
 ('大宝自己吃饭小宝喝水',['A','B']),
 ('昨天两个人都想自己用勺',['both']),
 ('大宝和小宝都喜欢球',['both']),
 ('两人都喜欢球，但小宝还不会踢，大宝会踢',['both','B','A']),
 ('大宝咬了小宝',['A']),
 ('小宝给大宝拿水',['B']),
 ('小宝把水递给大宝',['B']),
 ('大宝被小宝咬了',['both']),
 ('老大自己走上去，老二跟着走',['A','B']),
 ('姐姐安慰妹妹，妹妹给姐姐拿水',['A','B']),
 ('阿姨说昨天小宝会踢球了',['B']),
 ('自己舀了两口，没有帮忙',['A']),
 ('今天她俩都玩球',['both']),
 ('大宝说“妈妈，小宝喝水”，小宝随后拿杯子',['A','B']),
 ('昨天大宝💗自己吃饭，小宝喝水',['A','B']),
])
def test_parser_cases(text,children):
    rows=parse(text);assert [x['child'] for x in rows]==children
    for row in rows:
        assert text.encode('utf-16-le')[row['start']*2:row['end']*2].decode('utf-16-le')==row['text']

def test_multiple_dates_preserved():
    r=parse('昨天大宝用勺，上周小宝会踢球了');assert '昨天' in r[0]['time_text'] and '上周' in r[1]['time_text'] and '昨天' not in r[1]['time_text']

def test_inherited_date():
    r=parse('昨天大宝吃饭，小宝喝水');assert r[1]['time_prefix']=='昨天'

def test_ambiguous_pronoun_not_shared_ability():
    r=parse('大宝咬了小宝，她哭了');assert r[1]['status']=='needs_confirmation'
    assert candidates(event(text=r[1]['text'],attribution={'status':'needs_confirmation'}))==[]

def test_comparison_unspecified():assert parse('想自己吃饭','both')[0]['status']=='needs_confirmation'

def test_related_child_is_not_actor():
    r=parse('小宝给大宝拿水')[0];assert r['child']=='B' and r['related']==['A']

def test_unknown_is_not_delay():assert status([], 'A',BY_ID['m18_words'],'2025-02-18','2026-09-14')['key']=='unknown'

def check(state='not_yet',date='2026-09-14',**kw):
    return event(**({'kind':'profile','profile_type':'milestone_check','milestone_id':'m24_words','check_state':state,'parent_confirmed':True,'evidence_ids':[],'date':date}|kw))

def test_before_node_not_delay():assert status([check()], 'A',BY_ID['m24_words'],'2025-02-18','2026-09-14')['key']=='emerging'

def test_stale_pre_node_is_recheck_not_diagnosis():assert status([check()], 'A',BY_ID['m24_words'],'2025-02-18','2027-02-18')['key']=='recheck'

def test_explicit_not_yet_after_node_is_consult():assert status([check(date='2027-02-18')], 'A',BY_ID['m24_words'],'2025-02-18','2027-02-18')['key']=='consult'

def test_lost_any_age_is_consult():assert status([check('lost')], 'A',BY_ID['m24_words'],'2025-02-18','2026-09-14')['key']=='consult'

def test_seen_is_not_advanced():
    r=status([check('observed')], 'A',BY_ID['m24_words'],'2025-02-18','2026-09-14');assert r['key']=='seen' and '超前' not in r['label']

def test_no_number_norm():assert not any('1–10' in r['title'] or '拍球'==r['title'] for r in BY_ID.values())

def test_invalid_reference_id_rejected():
    with pytest.raises(ValueError):validate_doc({'schema_version':2,'events':[check(milestone_id='fake')]})

def test_legacy_caregiver_unchanged():
    e=event(observer='阿姨');assert validate_doc({'schema_version':2,'events':[e]})['events'][0]['observer']=='阿姨'

def make_batch(text):
    source=event(kind='profile',child='both',text=text,date=None,profile_type='source_report');rows=[source]
    for part in parse(text):rows.append(event(child=part['child'],text=part['text'],attribution={'source_id':source['id'],'source_start':part['start'],'source_end':part['end'],'status':part['status'],'related_children':part['related'],'reason':part['reason']}))
    return {'schema_version':2,'events':rows}

def test_batch_immutable_source_and_child_md(tmp_path):
    d=make_batch('昨天大宝自己吃饭，小宝自己喝水');s=Store(tmp_path);s.merge(d)
    a=(tmp_path/'generated/大宝_成长档案.md').read_text();b=(tmp_path/'generated/小宝_成长档案.md').read_text()
    assert '大宝自己吃饭' in a and '> 小宝自己喝水' not in a
    assert '> 小宝自己喝水' in b and '大宝自己吃饭' not in b
    assert (tmp_path/'generated/原始口述与拆分索引.md').exists() and (tmp_path/'generated/发育参考与观察对照.md').exists()
    s.merge(d);assert len(s.read()['events'])==3

def test_mutated_excerpt_rejected():
    d=make_batch('大宝用勺，小宝玩球');d['events'][1]['text']='大宝会写字'
    with pytest.raises(ValueError):validate_doc(d)

def test_emoji_span_valid():validate_doc(make_batch('昨天大宝💗自己吃饭，小宝喝水'))

def test_check_history_separated_from_birthday():
    md=render_markdown({'schema_version':2,'events':[check('observed')]},'2026-09-14')
    assert 'm24_words' not in md['共同档案_current.md'] and 'm24_words' in md['发育参考与观察对照.md']

def test_js_and_python_catalog_match():
    cmd=f"console.log(JSON.stringify(require({json.dumps(str(ROOT/'web/development_reference.js'))}).data));"
    js=json.loads(subprocess.run(['node','-e',cmd],capture_output=True,text=True,check=True).stdout)
    py=json.loads((ROOT/'web/development_catalog.json').read_text());assert js==py

def test_installer_stops_on_customized_interface(tmp_path):
    from install_calendar_update import install
    target=tmp_path/'custom';(target/'web').mkdir(parents=True);(target/'tools').mkdir()
    (target/'web/index.html').write_text('<html>custom</html>');(target/'tools/core.py').write_text('# custom')
    with pytest.raises(ValueError,match='本地定制'):install(target)
    assert (target/'web/index.html').read_text()=='<html>custom</html>'
