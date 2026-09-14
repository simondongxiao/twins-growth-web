"""Calendar-month ages and conservative Chinese date expressions (no model/API).

Every relative expression is anchored to the report timestamp, never to a later
read/export time. Vague and multi-date reports keep their original uncertainty.
"""
from __future__ import annotations
import calendar
import datetime as dt
import re
from typing import Any

TIMEZONES = {'Asia/Shanghai': 8, 'Asia/Tokyo': 9, 'UTC': 0}
DEFAULT_TIMEZONE = 'Asia/Shanghai'
RULE_VERSION = 1

def parse_day(value: str) -> dt.date:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期须为YYYY-MM-DD')
    return dt.date.fromisoformat(value)

def reference_day(reported_at: str, timezone: str = DEFAULT_TIMEZONE) -> str:
    if timezone not in TIMEZONES: raise ValueError('不支持的家庭时区')
    stamp = dt.datetime.fromisoformat(reported_at.replace('Z', '+00:00'))
    if stamp.tzinfo is None: raise ValueError('报告时间必须包含时区')
    return stamp.astimezone(dt.timezone(dt.timedelta(hours=TIMEZONES[timezone]))).date().isoformat()

def add_months(day: str, months: int) -> str:
    d = parse_day(day)
    total = d.year * 12 + d.month - 1 + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    return dt.date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()

def age_on(birth: str, event_day: str) -> dict[str, Any]:
    b, e = parse_day(birth), parse_day(event_day)
    if e < b: return {'months': None, 'days': None, 'label': '出生前，需核实日期'}
    months = (e.year - b.year) * 12 + e.month - b.month
    anchor = parse_day(add_months(birth, months))
    if anchor > e:
        months -= 1
        anchor = parse_day(add_months(birth, months))
    days = (e - anchor).days
    return {'months': months, 'days': days, 'label': f'{months}个月{days}天'}

def numeric(s: str) -> int:
    if s.isdigit(): return int(s)
    nums = dict(zip('零一二三四五六七八九', range(10))); nums['两'] = 2
    if s == '十': return 10
    if '十' in s:
        a, b = s.split('十', 1)
        return nums.get(a, 1) * 10 + nums.get(b, 0)
    if s not in nums: raise ValueError('未支持的中文数词')
    return nums[s]

def resolve_time(text: str, reported_at: str, timezone: str = DEFAULT_TIMEZONE,
                 manual_start: str | None = None, manual_end: str | None = None,
                 unknown: bool = False) -> dict[str, Any]:
    ref = reference_day(reported_at, timezone); day = parse_day(ref)
    out = {'rule_version': RULE_VERSION, 'reported_at': reported_at,
           'reference_date': ref, 'timezone': timezone, 'expression': '',
           'precision': 'unknown', 'start': None, 'end': None,
           'source': 'text_rule', 'note': ''}
    def result(start=None, end=None, expression='', precision=None, note='', source='text_rule'):
        end = end or start
        out.update(start=start, end=end, expression=expression, source=source,
                   precision=precision or ('day' if start == end and start else 'range'), note=note)
        if start:
            try:
                s, e = parse_day(start), parse_day(end)
                if e < s: raise ValueError('结束日早于开始日')
                if e > day: raise ValueError('未来日期不能记成已发生的观察')
            except (ValueError, TypeError) as exc:
                out.update(start=None, end=None, precision='invalid', note=str(exc))
        return out
    if unknown: return result(precision='unknown', note='家长选择日期不详；仅保存报告时间。', source='manual_unknown')
    if manual_start: return result(manual_start, manual_end, '家长选择日历日期', source='manual')
    # Vague language is deliberately not converted into exact dates.
    if re.search(r'前几天|前些天|最近(?![0-9零一二两三四五六七八九十]+天|一周)|这阵子|这几天|前一阵|前段时间|前一段|几天前|前不久|左右|大概|差不多|好像是|记不清|不记得', text):
        return result(precision='unknown', expression=text[:120], note='时间含模糊限定；不捏造具体日期或窄区间。')
    if re.search(r'转发|当时说|之前说|上次说|那天说', text):
        return result(precision='ambiguous', expression=text[:120], note='转述可能有另一报告时间；需按原话发生的对话日期解析。')
    weekday = r'(?:上上周|上周|本周|这周|上星期|本星期|这个星期)[一二三四五六日天]'
    weekrange = r'上上周|上周|上星期|本周|这周|本星期|这个星期'
    num = r'[0-9零一二两三四五六七八九十]+'
    pattern = rf'\d{{4}}[-/]\d{{1,2}}[-/]\d{{1,2}}|(?:\d{{4}}年)?\d{{1,2}}月\d{{1,2}}[日号]?|{weekday}|(?:过去|最近|近|这)(?:{num})天|(?:过去|最近|近)一周|{num}(?:天|周|个月|月)前|{weekrange}|上个月|上月|本月|这个月|大前天|前天|昨天|昨晚|今天|今日|刚才|刚刚|明天|后天|下周|下个月'
    hits = list(re.finditer(pattern, text))
    # A supported explicit ISO or Chinese range is allowed; all other multi-time
    # sentences require separate observations or remain uncertain.
    if len(hits) == 2:
        left, right = hits
        separator = text[left.end():right.start()].strip()
        absolute = lambda s: bool(re.fullmatch(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:\d{4}年)?\d{1,2}月\d{1,2}[日号]?', s))
        if separator in ('至', '到', '—', '～', '~', '–') and absolute(left[0]) and absolute(right[0]):
            a = resolve_time(left[0], reported_at, timezone); b = resolve_time(right[0], reported_at, timezone)
            if a['precision'] == b['precision'] == 'day': return result(a['start'], b['start'], left[0]+separator+right[0])
        return result(precision='ambiguous', expression=' / '.join(h[0] for h in hits), note='一句里有多个时间，请分条；当前只保留原话，不替整段指定某一天。')
    if len(hits) > 2:
        return result(precision='ambiguous', expression=' / '.join(h[0] for h in hits), note='包含多个时间，请分条或由成人结合原话核对。')
    if not hits:
        return result(precision='unknown', note='未说明发生时间；不会把报告当天当成已确认的发生日。', source='missing')
    phrase = hits[0][0]
    shift = lambda n: (day + dt.timedelta(days=n)).isoformat()
    if phrase in {'明天','后天','下周','下个月'}:
        return result(precision='invalid', expression=phrase, note='这是未来时间，不能记成已发生的观察。')
    deltas = {'大前天':-3,'前天':-2,'昨天':-1,'昨晚':-1,'今天':0,'今日':0,'刚才':0,'刚刚':0}
    if phrase in deltas: return result(shift(deltas[phrase]), expression=phrase)
    m = re.fullmatch(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})',phrase)
    if m: return result(f'{int(m[1]):04}-{int(m[2]):02}-{int(m[3]):02}',expression=phrase)
    m = re.fullmatch(r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号]?',phrase)
    if m:
        y = int(m[1]) if m[1] else day.year
        note = '' if m[1] else '未写年份；按报告当年解释，已展示供核对。'
        return result(f'{y:04}-{int(m[2]):02}-{int(m[3]):02}',expression=phrase,note=note)
    m = re.fullmatch(rf'({num})(天|周|个月|月)前',phrase)
    if m:
        n = numeric(m[1]); date = shift(-n*(7 if m[2]=='周' else 1)) if m[2] in ('天','周') else add_months(ref,-n)
        return result(date,expression=phrase)
    m = re.fullmatch(rf'(?:过去|最近|近|这)({num})天',phrase)
    if m or phrase in {'过去一周','最近一周','近一周'}:
        n = numeric(m[1]) if m else 7
        if n < 1: return result(precision='invalid',expression=phrase,note='天数必须大于0')
        return result(shift(1-n),ref,phrase,note='按包含报告当天的最近N个自然日记录；不是前一自然周。')
    monday = day - dt.timedelta(days=day.weekday())
    if re.fullmatch(weekday,phrase):
        offset = -14 if phrase.startswith('上上') else -7 if phrase.startswith('上') else 0
        idx = {'一':0,'二':1,'三':2,'四':3,'五':4,'六':5,'日':6,'天':6}[phrase[-1]]
        return result((monday+dt.timedelta(days=offset+idx)).isoformat(),expression=phrase)
    if re.fullmatch(weekrange,phrase):
        offset = -14 if phrase.startswith('上上') else -7 if phrase.startswith('上') else 0
        start = monday + dt.timedelta(days=offset)
        end = min(start+dt.timedelta(days=6),day)
        return result(start.isoformat(),end.isoformat(),phrase,precision='range',note='自然周按周一至周日；本周只截至报告日。区间不代表每天都发生。')
    if phrase in {'上个月','上月','本月','这个月'}:
        start = day.replace(day=1)
        if phrase in {'上个月','上月'}:
            end = start-dt.timedelta(days=1); start=end.replace(day=1)
        else: end=day
        return result(start.isoformat(),end.isoformat(),phrase,precision='range',note='自然月区间；不据此推断首次出现日期。')
    return result(precision='unknown',expression=phrase,note='未可靠识别；保留原话。')

def get_profile(events: list[dict], child: str = 'both') -> dict | None:
    matches = [e for e in events if e.get('kind')=='profile' and e.get('birth_date')
               and (e.get('child') in (child,'both') if child != 'both' else e.get('child')=='both')]
    return max(matches, key=lambda e:(e['created_at'],e['id'])) if matches else None

def event_time(event: dict) -> dict:
    if event.get('time'): return event['time']
    date = event.get('date')
    return {'start':date,'end':date,'precision':'day' if date else 'unknown',
            'expression':'','source':'legacy','note':'旧版原始日期；未从内容重新猜测发生日。',
            'reported_at':event.get('created_at'),'timezone':DEFAULT_TIMEZONE}

def time_label(time: dict) -> str:
    if time.get('start'):
        return time['start'] if time.get('precision')=='day' else f"{time['start']} 至 {time['end']}"
    return '发生日未知' if time.get('precision')!='ambiguous' else '多时间表述，发生日待拆分'

def age_label(profile: dict | None, time: dict) -> str:
    if not profile: return '生日待填写'
    if not time.get('start'): return '发生时间不确定，不计算事件月龄'
    left=age_on(profile['birth_date'],time['start'])['label']
    return left if time['start']==time.get('end') else left+'—'+age_on(profile['birth_date'],time['end'])['label']

def validate_time(t: dict, event_date: str | None = None):
    if not isinstance(t,dict) or t.get('rule_version')!=RULE_VERSION: raise ValueError('时间元数据版本无效')
    ref=reference_day(t.get('reported_at',''),t.get('timezone',''))
    if ref != t.get('reference_date'): raise ValueError('报告时间与参考日期不一致')
    if t.get('precision') not in {'day','range','unknown','ambiguous'}: raise ValueError('请先修正无法保存的日期')
    for key in ('expression','source','note'):
        if not isinstance(t.get(key,''),str) or len(t.get(key,''))>2000: raise ValueError('时间说明无效')
    if t['precision'] in {'day','range'}:
        start,end=parse_day(t.get('start','')),parse_day(t.get('end',''))
        if end<start or end>parse_day(ref): raise ValueError('发生时间区间无效或在报告日以后')
        if t['precision']=='day' and start!=end: raise ValueError('具体日期不能带两个不同端点')
        if event_date!=(t['start'] if t['precision']=='day' else None): raise ValueError('事件日期与时间区间不一致')
    elif t.get('start') is not None or t.get('end') is not None or event_date is not None:
        raise ValueError('不确定日期不能同时保存为精确日期')
