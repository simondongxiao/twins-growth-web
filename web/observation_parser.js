/* Local attribution helper. No model/API/network call. Never infer a recipient's ability. */
(function(root){
'use strict';
const VERSION='2.3.0';
const ALIAS=/大宝|老大|姐姐|小宝|老二|妹妹/g;
const who=s=>/大宝|老大|姐姐/.test(s)?'A':'B';
const SHARED=/^(?:大宝(?:和|跟|与|、)?小宝|小宝(?:和|跟|与|、)?大宝|姐姐(?:和|跟|与|、)?妹妹|妹妹(?:和|跟|与|、)?姐姐|老大(?:和|跟|与|、)?老二|老二(?:和|跟|与|、)?老大|两个人|两个孩子|两位宝宝|两个宝宝|两个宝贝|姐妹俩|两姐妹|俩孩子|她俩|她们俩|她们|两人|两个都|两个都在|两个都能)/;
// Strip only introductory language, not verbs which could change the actor.
const PREFIX=/^(?:(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:\d{4}年)?\d{1,2}月\d{1,2}[日号]?|(?:上上|上|本|这)周[一二三四五六日天]?|[一二两三四五六七八九十\d]+(?:天|周|个月)前|昨天|昨晚|今天|今日|前天|大前天|刚才|刚刚|上个月|最近|这几天|前几天|目前|现在|之前|以前|下午|上午|晚上|早上|中午|睡前|饭后|吃饭时|玩球时|看书时|洗澡时|但是|不过|可是|而|但|后来|然后|随后|又|另外|同时|我发现|我觉得|我看到|我观察到|我说|爸爸说|妈妈说|阿姨说|阿姨告诉我|听阿姨说|据阿姨说|在家时|在家|在外面|在公园|在吃饭的时候|吃饭的时候)[\s：:]*)+/;
function stripIntro(s){let prev;do{prev=s;s=s.replace(PREFIX,'').trimStart()}while(s!==prev);return s;}
function atomic(text){
 const out=[];let start=0,quote=null;
 function push(end){let a=start,b=end;while(a<b&&/\s/.test(text[a]))a++;while(b>a&&/\s/.test(text[b-1]))b--;if(a<b)out.push({start:a,end:b,text:text.slice(a,b)});}
 for(let i=0;i<text.length;i++){
  const ch=text[i];if(quote){if(ch===quote)quote=null;continue}
  if(ch==='“'){quote='”';continue}if(ch==='「'){quote='」';continue}if(ch==='『'){quote='』';continue}if(ch==='"'){quote='"';continue}
  if(/[，,。；;！？!?\n]/.test(ch)){push(i);start=i+1}
 }
 push(text.length);
 // Accept common no-punctuation input, e.g. 大宝自己吃饭 小宝自己喝水.
 // Do not split recipients (给/帮/被/看见/咬了...) or names inside quotations.
 return out.flatMap(token=>{
  let masked=token.text.split(''),q=null;
  for(let i=0;i<masked.length;i++){let c=masked[i];if(q){masked[i]=' ';if(c===q)q=null}else if(c==='“'||c==='「'||c==='"'){q=c==='“'?'”':c==='「'?'」':'"';masked[i]=' ';}}
  let visible=masked.join(''),hits=[...visible.matchAll(ALIAS)],cuts=[];
  let lead=stripIntro(visible),shared=lead.match(SHARED),sharedEnd=shared?visible.indexOf(lead)+shared[0].length:0;
  for(let h of hits.slice(1)){
   if(h.index<sharedEnd)continue;
   let before=visible.slice(0,h.index),after=visible.slice(h.index+h[0].length);
   if(/(?:给|对|帮|让|带|跟|和|与|从|被|见|看|抱|咬|咬了|抢|抢了|拿走|安慰|递给|交给|抱着|比)\s*$/.test(before))continue;
   if(/的/.test(after.slice(0,1)))continue;
   if(/(?:\s|但是|但|而|不过|后来|然后|同时|另外)$/.test(before)||/^(?:自己|独自|已经|开始|还|却|也|会|不会|能|不能|没|不|今天|昨天|喝|吃|哭|跑|踢|说|主动)/.test(after)){
    let pos=h.index,m=before.match(/(?:但是|但|而|不过|后来|然后|同时|另外)\s*$/);if(m)pos=m.index;cuts.push(pos);
   }
  }
  if(!cuts.length)return[token];
  let bounds=[0,...new Set(cuts),token.text.length],parts=[];
  for(let i=0;i<bounds.length-1;i++){let a=bounds[i],b=bounds[i+1];while(a<b&&/\s/.test(token.text[a]))a++;while(b>a&&/\s/.test(token.text[b-1]))b--;if(a<b)parts.push({start:token.start+a,end:token.start+b,text:token.text.slice(a,b)})}return parts;
 });
}
function explicit(s){
 const lead=stripIntro(s),shared=lead.match(SHARED);
 if(shared)return{child:'both',status:'shared',reason:'明确写出两人共同表现',related:[],subject:shared[0]};
 const m=lead.match(/^(大宝|老大|姐姐|小宝|老二|妹妹)/);
 if(m){let child=who(m[0]);const tail=lead.slice(m[0].length);let related=[...new Set([...tail.matchAll(ALIAS)].map(x=>who(x[0])).filter(c=>c!==child))];
  // A 被 B 咬: both participants are known, but B is the actor. Keep interaction shared,
  // never treat A as the one who bites or B as having A's response.
  if(/^(?:今天|昨天|刚才|又|也|被|让)/.test(tail)&&/(?:被|让)(?:大宝|老大|姐姐|小宝|老二|妹妹)/.test(tail))return {child:'both',status:'interaction',reason:'被动/互动句，保留角色与原话，不复制成两人的能力',related:['A','B'],subject:m[0]};
  return{child,status:'explicit',reason:'按句中明确主体归档',related,subject:m[0]};}
 return null;
}
function split(text,defaultChild='both'){
 if(typeof text!=='string'||!text.trim())return[];
 if(text.length>8000)throw Error('观察最多8000字');
 let items=atomic(text),out=[],previous=null,lastTime='';
 for(const token of items){
  let s=token.text,lead=stripIntro(s),direct=explicit(s),aliases=[...s.matchAll(ALIAS)],assignment;
  if(direct)assignment=direct;
  else if(/^(?:她|她的|宝宝)/.test(lead)){
   if(previous&&['A','B'].includes(previous.child)&&!previous.related.length&&previous.status!=='needs_confirmation')assignment={child:previous.child,status:'context',reason:'承接前一个明确、无第二角色的主体',related:[],subject:'她'};
   else assignment={child:'both',status:'needs_confirmation',reason:'“她”可能指向不同孩子；保留原话，需点一次确认',related:[],subject:''};
  }else if(aliases.length||/^(?:爸爸|妈妈|父母|我们|阿姨|爷爷|奶奶|外婆|外公)/.test(lead)){
   assignment={child:'both',status:'needs_confirmation',reason:'孩子是被提及者或主体不清，不能按名字出现就归给她',related:[],subject:''};
  }else if(previous){assignment={child:previous.child,status:previous.status==='needs_confirmation'?'needs_confirmation':'context',reason:'承接前一分句；仍保留原始语境',related:[...previous.related],subject:''};}
  else if(defaultChild==='A'||defaultChild==='B')assignment={child:defaultChild,status:'page_default',reason:'未写孩子名字，使用当前孩子页面',related:[],subject:''};
  else assignment={child:'both',status:'needs_confirmation',reason:'比较页未写明确对象；未自动认定两人都会',related:[],subject:''};
  // A clause with independent dates/actors remains separate. Continuation clauses without
  // new subject/time join the previous excerpt so "没帮忙" isn't recorded as a new skill.
  let hasTime=/(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:\d{4}年)?\d{1,2}月\d{1,2}|(?:上上|上|本|这)周|[一二两三四五六七八九十\d]+(?:天|周|个月)前|昨天|昨晚|今天|前天|大前天|刚才|刚刚|最近|前几天|这几天|上个月)/.test(s);
  let timeExpression='';
  if(root.DateAge){let t=root.DateAge.resolve(s,'2026-01-15T12:00:00Z','Asia/Shanghai');timeExpression=t.expression||'';hasTime=hasTime||!!timeExpression;}
  if(hasTime)lastTime=timeExpression||s;
  let temporal=hasTime?s:(lastTime?lastTime+' '+s:s);
  let canJoin=out.length&&!direct&&!hasTime&&!/^(?:她|宝宝)/.test(lead)&&assignment.status!=='needs_confirmation'&&assignment.child===out.at(-1).child;
  if(canJoin){let prior=out.at(-1);prior.end=token.end;prior.text=text.slice(prior.start,prior.end);prior.time_text=(prior.time_prefix?prior.time_prefix+' ':'')+prior.text;}
  else out.push({...token,...assignment,time_prefix:hasTime?'':lastTime,time_text:temporal,parser_version:VERSION});
  previous=assignment;
 }
 return out.map((r,i)=>({...r,index:i}));
}
const api={VERSION,split,explicit,atomic};root.ObservationParser=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
