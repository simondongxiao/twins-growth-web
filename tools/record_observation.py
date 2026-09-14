"""Append one parent report with calendar dates; intended for a local AI/CLI agent.

Parents use the HTML. This command also supports chat-to-Markdown recording without
requiring them to edit the ledger. No web/API call and no diagnosis are made.
"""
from __future__ import annotations
import argparse, json, uuid
from pathlib import Path
from core import Store, active_events, now
from time_age import resolve_time, get_profile, age_label, time_label

def record(store: Store, text: str, child: str, reported_at: str, observer='爸爸',
           manual_start=None, manual_end=None, unknown=False, category='待整理',
           source_id=None):
    if child not in ('A','B','both'): raise ValueError('请明确A=大宝、B=小宝或both=共同；不凭语序猜主体')
    events=active_events(store.read()); profile=get_profile(events,child)
    zone=(profile or get_profile(events) or {}).get('timezone','Asia/Shanghai')
    time=resolve_time(text,reported_at,zone,manual_start,manual_end,unknown)
    if time['precision']=='invalid': raise ValueError(time['note'])
    if time['start'] and profile and time['start']<profile['birth_date']: raise ValueError('发生日期早于出生日期')
    # Stable with an explicitly supplied source_id; importing the same chat line twice is idempotent.
    eid=str(uuid.uuid5(uuid.NAMESPACE_URL,'growth-observation:'+source_id)) if source_id else str(uuid.uuid4())
    existing=next((e for e in store.read()['events'] if e['id']==eid),None)
    event={'id':eid,'kind':'observation','child':child,'text':text.strip(),'category':category,
           'date':time['start'] if time['precision']=='day' else None,'time':time,
           'created_at':existing['created_at'] if existing else now(),
           'observer':observer,'evidence_type':'家长原话；日期经规则整理'}
    if source_id: event['source_report_id']=source_id
    store.append(event)
    return {'id':eid,'event_date':time_label(time),'age_at_event':age_label(profile,time),
            'precision':time['precision'],'markdown_dir':str(store.private/'generated')}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--text',required=True);p.add_argument('--child',required=True,choices=['A','B','both'])
    p.add_argument('--reported-at',default=None,help='Original report ISO timestamp with Z/+08:00; defaults to now')
    p.add_argument('--observer',default='爸爸');p.add_argument('--date');p.add_argument('--date-end')
    p.add_argument('--unknown',action='store_true');p.add_argument('--source-id')
    p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[1]/'private')
    a=p.parse_args()
    result=record(Store(a.data_dir),a.text,a.child,a.reported_at or now(),a.observer,a.date,a.date_end,a.unknown,source_id=a.source_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
