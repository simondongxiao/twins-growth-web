"""Public reference plus parent observations. No diagnosis or automated milestone pass."""
from __future__ import annotations
import json,re
from pathlib import Path
from time_age import age_on,get_profile
CATALOG=json.loads((Path(__file__).resolve().parents[1]/'web/development_catalog.json').read_text('utf-8'))
BY_ID={x['id']:x for x in CATALOG['items']}
CHECK_STATES={'observed','not_yet','unsure','lost'}

def candidates(event:dict)->list[dict]:
    if event.get('kind') not in {'baseline','observation'} or event.get('attribution',{}).get('status')=='needs_confirmation':return []
    return [x for x in CATALOG['items'] if re.search(x['keywords'],event.get('text',''),re.I)][:4]

def status(events:list,child:str,item:dict,birth:str|None,today:str)->dict:
    rows=sorted([e for e in events if e.get('profile_type')=='milestone_check' and e.get('kind')=='profile' and e.get('child')==child and e.get('milestone_id')==item['id']],key=lambda e:(e['created_at'],e['id']))
    e=rows[-1] if rows else None
    current=age_on(birth,today)['months'] if birth else None
    if not e:return dict(key='unknown',label='待补观察',text='没有家长核对记录；不等于不会。',check=None)
    then=age_on(birth,e['date'])['months'] if birth and e.get('date') else None
    state=e['check_state']
    if state=='lost':return dict(key='consult',label='请及时咨询儿保',text='家长报告能力变少或消失，不等月度复盘；网页未作诊断。',check=e)
    if state=='observed':return dict(key='seen',label='已观察到（家长核对）',text=f"核对日：{e.get('date') or '未知'}；不是首次获得日期或整体发育结论。",check=e)
    if state=='not_yet' and then is not None and then>=item['months']:return dict(key='consult',label='建议咨询儿保',text='家长在达到参考节点后核对为尚未出现，可带记录咨询，不自动诊断迟缓。',check=e)
    if state=='not_yet' and current is not None and current>=item['months']:return dict(key='recheck',label='到节点，请重新核对',text='旧报告来自节点之前，不能据此断定今天仍然不会。',check=e)
    if state=='not_yet':return dict(key='emerging',label='家长报告尚未出现',text='尚未到该节点；不是滞后标签，有担忧无需等待。',check=e)
    return dict(key='unknown',label='信息不足',text='没有留意或不确定，保留未知。',check=e)

def render_reference(events:list,today:str)->str:
    out='# 发育参考与观察对照\n\n生成日：'+today+'；参考版本：'+CATALOG['version']+'。\n\n'+CATALOG['boundary']+'\n\n'+CATALOG['extra']+'\n'
    out+='\n依据是CDC公开精选观察点，不是完整筛查、智商测验或中国儿保诊断标准。出生孕周未知，不计算矫正月龄。\n'
    out+='\n## 各自的观察状态\n'
    for c,label in [('A','大宝'),('B','小宝')]:
        out+='\n### '+label+'\n\n';p=get_profile(events,c);birth=p['birth_date'] if p else None
        for item in CATALOG['items']:
            r=status(events,c,item,birth,today);out+=f"- {item['months']}个月参考：{item['title']} → {r['label']}。{r['text']}\n"
            if r['check']:out+=f"  核对ID：{r['check']['id']}；证据ID：{', '.join(r['check'].get('evidence_ids',[])) or '未关联'}。\n"
    out+='\n## 家长核对历史（原结果不被覆盖）\n\n'
    rows=[e for e in events if e.get('profile_type')=='milestone_check']
    if not rows:out+='尚无家长核对。不根据关键词匹配填成已会，也不把没有日志填成未达标。\n'
    for e in rows:
        out+=f"### {e.get('date') or '日期未知'} · {e['child']} · {e.get('observer','未知')}\nID：{e['id']}；项目：{e['milestone_id']}；状态：{e['check_state']}\n"
        out+='\n'.join('> '+line for line in e['text'].splitlines())+'\n\n'
    out+='\n## 核查过的官方来源\n\n'
    for source in CATALOG['sources'].values():out+=f"- {source['title']}：{source['url']}（核验 {source['checked']}）\n"
    out+='\n## 如何行动\n\n明确没有出现参考节点的能力、能力倒退或家长持续担忧，应联系儿保/儿科，必要时由医生安排听力与语言等评估；不等到24个月或AI提醒。AAP一般发育筛查9/18/30个月、孤独症筛查18/24个月属于美国专业建议，实际安排与当地儿保核对。\n'
    return out
