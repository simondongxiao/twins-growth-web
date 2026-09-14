/* Calendar arithmetic only. Original observations and unknowns are preserved. */
(function(root){
'use strict';
const ZONES={'Asia/Shanghai':8,'Asia/Tokyo':9,'UTC':0};
const pad=n=>String(n).padStart(2,'0');
function iso(d){return d.toISOString().slice(0,10)}
function date(s){if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s))throw Error('日期须为YYYY-MM-DD');let d=new Date(s+'T00:00:00Z');if(!Number.isFinite(+d)||iso(d)!==s)throw Error('日期不存在');return d}
function shift(s,n){let d=date(s);d.setUTCDate(d.getUTCDate()+n);return iso(d)}
function ref(at,zone='Asia/Shanghai'){if(!(zone in ZONES)||typeof at!=='string'||!/(Z|[+-]\d{2}:\d{2})$/.test(at))throw Error('报告时间或家庭时区无效');let d=new Date(at);if(!Number.isFinite(+d))throw Error('报告时间无效');return iso(new Date(+d+ZONES[zone]*3600000))}
function addMonths(s,n){let d=date(s), total=d.getUTCFullYear()*12+d.getUTCMonth()+n,y=Math.floor(total/12),m=total-y*12,last=new Date(Date.UTC(y,m+1,0)).getUTCDate();return iso(new Date(Date.UTC(y,m,Math.min(d.getUTCDate(),last))))}
function ageOn(birth,day){let b=date(birth),e=date(day);if(e<b)return{months:null,days:null,label:'出生前，需核实日期'};let m=(e.getUTCFullYear()-b.getUTCFullYear())*12+e.getUTCMonth()-b.getUTCMonth();let a=date(addMonths(birth,m));if(a>e){m--;a=date(addMonths(birth,m))}let days=Math.round((e-a)/86400000);return{months:m,days,label:`${m}个月${days}天`}}
function numeric(s){if(/^\d+$/.test(s))return +s;let ns={零:0,一:1,二:2,两:2,三:3,四:4,五:5,六:6,七:7,八:8,九:9};if(s==='十')return 10;if(s.includes('十')){let[a,b]=s.split('十');return(ns[a]??1)*10+(ns[b]??0)}if(!(s in ns))throw Error('未支持的中文数词');return ns[s]}
function resolve(text,at,zone='Asia/Shanghai',manualStart=null,manualEnd=null,unknown=false){
 let reference=ref(at,zone),d=date(reference);let out={rule_version:1,reported_at:at,reference_date:reference,timezone:zone,expression:'',precision:'unknown',start:null,end:null,source:'text_rule',note:''};
 function result(start=null,end=null,expression='',precision=null,note='',source='text_rule'){
  end=end||start;Object.assign(out,{start,end,expression,precision:precision||(start&&start===end?'day':'range'),note,source});
  if(start)try{let s=date(start),e=date(end);if(e<s)throw Error('结束日早于开始日');if(e>d)throw Error('未来日期不能记成已发生的观察')}catch(e){Object.assign(out,{start:null,end:null,precision:'invalid',note:e.message})}return out;
 }
 if(unknown)return result(null,null,'','unknown','家长选择日期不详；仅保存报告时间。','manual_unknown');
 if(manualStart)return result(manualStart,manualEnd,'家长选择日历日期',null,'','manual');
 if(/前几天|前些天|最近(?![0-9零一二两三四五六七八九十]+天|一周)|这阵子|这几天|前一阵|前段时间|前一段|几天前|前不久|左右|大概|差不多|好像是|记不清|不记得/.test(text))return result(null,null,text.slice(0,120),'unknown','时间含模糊限定；不捏造具体日期或窄区间。');
 if(/转发|当时说|之前说|上次说|那天说/.test(text))return result(null,null,text.slice(0,120),'ambiguous','转述可能有另一报告时间；需按原话发生的对话日期解析。');
 const weekday='(?:上上周|上周|本周|这周|上星期|本星期|这个星期)[一二三四五六日天]',weekrange='上上周|上周|上星期|本周|这周|本星期|这个星期',num='[0-9零一二两三四五六七八九十]+';
 const pattern=new RegExp(`\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}|(?:\\d{4}年)?\\d{1,2}月\\d{1,2}[日号]?|${weekday}|(?:过去|最近|近|这)(?:${num})天|(?:过去|最近|近)一周|${num}(?:天|周|个月|月)前|${weekrange}|上个月|上月|本月|这个月|大前天|前天|昨天|昨晚|今天|今日|刚才|刚刚|明天|后天|下周|下个月`,'g');
 let hits=[...text.matchAll(pattern)];
 if(hits.length===2){let[a,b]=hits,sep=text.slice(a.index+a[0].length,b.index).trim(),absolute=s=>/^(\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:\d{4}年)?\d{1,2}月\d{1,2}[日号]?)$/.test(s);if(['至','到','—','～','~','–'].includes(sep)&&absolute(a[0])&&absolute(b[0])){let x=resolve(a[0],at,zone),y=resolve(b[0],at,zone);if(x.precision==='day'&&y.precision==='day')return result(x.start,y.start,a[0]+sep+b[0])}return result(null,null,hits.map(h=>h[0]).join(' / '),'ambiguous','一句里有多个时间，请分条；当前只保留原话，不替整段指定某一天。')}
 if(hits.length>2)return result(null,null,hits.map(h=>h[0]).join(' / '),'ambiguous','包含多个时间，请分条或由成人结合原话核对。');
 if(!hits.length)return result(null,null,'','unknown','未说明发生时间；不会把报告当天当成已确认的发生日。','missing');
 let p=hits[0][0];if(['明天','后天','下周','下个月'].includes(p))return result(null,null,p,'invalid','这是未来时间，不能记成已发生的观察。');
 let delta={大前天:-3,前天:-2,昨天:-1,昨晚:-1,今天:0,今日:0,刚才:0,刚刚:0};if(p in delta)return result(shift(reference,delta[p]),null,p);
 let m=p.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);if(m)return result(`${m[1]}-${pad(+m[2])}-${pad(+m[3])}`,null,p);
 m=p.match(/^(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号]?$/);if(m)return result(`${m[1]||d.getUTCFullYear()}-${pad(+m[2])}-${pad(+m[3])}`,null,p,null,m[1]?'':'未写年份；按报告当年解释，已展示供核对。');
 m=p.match(new RegExp(`^(${num})(天|周|个月|月)前$`));if(m){let n=numeric(m[1]),s=['天','周'].includes(m[2])?shift(reference,-n*(m[2]==='周'?7:1)):addMonths(reference,-n);return result(s,null,p)}
 m=p.match(new RegExp(`^(?:过去|最近|近|这)(${num})天$`));if(m||['过去一周','最近一周','近一周'].includes(p)){let n=m?numeric(m[1]):7;if(n<1)return result(null,null,p,'invalid','天数必须大于0');return result(shift(reference,1-n),reference,p,null,'按包含报告当天的最近N个自然日记录；不是前一自然周。')}
 let mon=shift(reference,-((d.getUTCDay()+6)%7));if(new RegExp(`^${weekday}$`).test(p)){let off=p.startsWith('上上')?-14:p.startsWith('上')?-7:0,idx={一:0,二:1,三:2,四:3,五:4,六:5,日:6,天:6}[p.slice(-1)];return result(shift(mon,off+idx),null,p)}
 if(new RegExp(`^(?:${weekrange})$`).test(p)){let off=p.startsWith('上上')?-14:p.startsWith('上')?-7:0,s=shift(mon,off),e=shift(s,6);return result(s,e>reference?reference:e,p,'range','自然周按周一至周日；本周只截至报告日。区间不代表每天都发生。')}
 if(['上个月','上月','本月','这个月'].includes(p)){let s=reference.slice(0,7)+'-01',e=reference;if(['上个月','上月'].includes(p)){e=shift(s,-1);s=e.slice(0,7)+'-01'}return result(s,e,p,'range','自然月区间；不据此推断首次出现日期。')}
 return result(null,null,p,'unknown','未可靠识别；保留原话。');
}
function profile(events,c='both'){let all=events.filter(e=>e.kind==='profile'&&e.birth_date&&(c==='both'?e.child==='both':[c,'both'].includes(e.child)));return all.sort((a,b)=>a.created_at.localeCompare(b.created_at)||a.id.localeCompare(b.id)).at(-1)||null}
function eventTime(e){return e.time||{start:e.date||null,end:e.date||null,precision:e.date?'day':'unknown',expression:'',source:'legacy',note:'旧版原始日期；未从内容重新猜测发生日。',reported_at:e.created_at,timezone:'Asia/Shanghai'}}
function label(t){return t.start?(t.precision==='day'?t.start:`${t.start} 至 ${t.end}`):t.precision==='ambiguous'?'多时间表述，发生日待拆分':'发生日未知'}
function ageLabel(p,t){if(!p)return'生日待填写';if(!t.start)return'发生时间不确定，不计算事件月龄';let a=ageOn(p.birth_date,t.start).label;return t.start===t.end?a:a+'—'+ageOn(p.birth_date,t.end).label}
function validateTime(t,eventDate=null){if(!t||t.rule_version!==1||ref(t.reported_at,t.timezone)!==t.reference_date)throw Error('报告时间与参考日期不一致');if(!['day','range','unknown','ambiguous'].includes(t.precision))throw Error('请先修正无法保存的日期');for(let k of ['expression','note','source'])if(typeof(t[k]||'')!=='string'||(t[k]||'').length>2000)throw Error('时间说明无效');if(['day','range'].includes(t.precision)){date(t.start);date(t.end);if(t.end<t.start||t.end>t.reference_date)throw Error('发生时间区间无效或在报告日以后');if(t.precision==='day'&&t.start!==t.end)throw Error('具体日期不能带两个端点');if(eventDate!==(t.precision==='day'?t.start:null))throw Error('事件日期与时间区间不一致')}else if(t.start!=null||t.end!=null||eventDate!=null)throw Error('不确定日期不能同时保存为精确日期');return t}
const api={ZONES,date,shift,ref,addMonths,ageOn,numeric,resolve,profile,eventTime,label,ageLabel,validateTime};
root.DateAge=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
