"""Chromium DOM with explicit storage double and HTTP bridge to real local Python server.
Browser navigation to localhost is blocked by this environment. No iOS/Android,
real cloud authorization, real GitHub, or user Windows deployment is claimed.
"""
import copy,json,shutil,sys,tempfile,threading,urllib.request,urllib.error
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from serve import make_server
from core import Store
OUT=ROOT/'artifacts';OUT.mkdir(exist_ok=True)
results=[];errors=[]
def check(x,msg):
 assert x,msg
 results.append(msg)
HARNESS='''<script>
const memory={},sessionMemory={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>memory[k]||null,setItem:(k,v)=>{memory[k]=v},removeItem:k=>{delete memory[k]}}});Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>sessionMemory[k]||null,setItem:(k,v)=>{sessionMemory[k]=v},removeItem:k=>{delete sessionMemory[k]}}});
window.fetch=async(path,opts={})=>{let r=await window.__backend({path,opts});return {ok:r.status<400,status:r.status,json:async()=>JSON.parse(r.text),text:async()=>r.text}};
</script>'''
def inline(html):
 for script in ['time_age.js','observation_parser.js','development_reference.js']:
  html=html.replace(f'<script src="{script}"></script>','<script>'+(ROOT/'web'/script).read_text()+'</script>')
 html=html.replace('<script src="config.js" onerror="window.GROWTH_CONFIG=window.GROWTH_CONFIG||{}"></script>','<script>window.GROWTH_CONFIG=window.GROWTH_CONFIG||{};</script>')
 return html.replace('<head>','<head>'+HARNESS,1)
with tempfile.TemporaryDirectory() as d:
 data=Path(d);shutil.copy(ROOT/'private/seed.json',data/'seed.json');server=make_server(data,0);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
 def backend(arg):
  path=arg['path'];opts=arg.get('opts',{});req=urllib.request.Request(url+path,method=opts.get('method','GET'),headers=opts.get('headers',{}),data=opts.get('body','').encode() if opts.get('body') else None)
  try:
   with urllib.request.urlopen(req) as r:return {'status':r.status,'text':r.read().decode()}
  except urllib.error.HTTPError as e:return {'status':e.code,'text':e.read().decode()}
 html=inline(urllib.request.urlopen(url).read().decode())
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
  pg=browser.new_page(viewport={'width':390,'height':844});pg.on('pageerror',lambda e:errors.append(str(e)));pg.expose_function('__backend',backend);pg.set_content(html);pg.wait_for_selector('#note');pg.wait_for_function('GrowthTest.getState().events.length>=22')
  check(pg.locator('[data-writer]').all_text_contents()==['爸爸','妈妈'],'Only two parent writer buttons')
  check('阿姨' not in pg.locator('#observerSetting').inner_text(),'No caregiver writer setting')
  check(pg.locator('[data-page]').count()==3,'Three child views preserved')
  check(pg.locator('.actionnav [data-section]').count()==4,'Four mobile actions including reference')
  pg.locator('[data-writer="妈妈"]').click()
  original='昨天大宝自己舀了两口饭，没有让我帮忙。小宝把水递给大宝。两个人都想自己用勺。'
  pg.locator('#note').fill(original)
  check(pg.locator('.attribution-row').count()==3,'Single paragraph split into A / B / shared')
  plan=pg.evaluate('GrowthTest.attributionPlan()');check([p['child'] for p in plan]==['A','B','both'],'Correct subject routing')
  check(plan[1]['related']==['A'],'Recipient A not copied as the actor')
  check(plan[0]['time']['start']==plan[1]['time']['start'],'Yesterday inherited across same report')
  pg.locator('#toast').evaluate('(e)=>e.classList.add("hidden")');pg.screenshot(path=str(OUT/'v23-mobile-entry.png'),full_page=False)
  pg.locator('.attribution-fold').evaluate('(e)=>e.open=true');pg.screenshot(path=str(OUT/'v23-mobile-entry-preview.png'),full_page=True)
  pg.locator('#saveNote').click();pg.wait_for_function('GrowthTest.getState().events.filter(e=>e.kind==="observation").length===3')
  doc=Store(data).read();obs=[e for e in doc['events'] if e['kind']=='observation'];raw=[e for e in doc['events'] if e.get('profile_type')=='source_report']
  check(len(raw)==1 and raw[0]['text']==original,'One immutable original paragraph saved')
  check(len(obs)==3 and all(e['observer']=='妈妈' for e in obs),'Three exact fragments authored by mother')
  check(original in (data/'generated/原始口述与拆分索引.md').read_text(),'Original paragraph written to Markdown')
  a=(data/'generated/大宝_成长档案.md').read_text();b=(data/'generated/小宝_成长档案.md').read_text()
  check('小宝把水递给大宝' not in a and '小宝把水递给大宝' in b,'Recipient behavior not copied to A Markdown')
  pg.locator('[data-section="history"]').click();check(pg.locator('.entry-reference').count()==2,'A history has contextual references for A/shared only')
  pg.locator('[data-section="reference"]').click();check(pg.locator('.milestone-card').count()==8,'Current 18-month selected references visible')
  check('至少75%' in pg.locator('#view').inner_text(),'75 percent node boundary visible')
  check('待补观察' in pg.locator('#view').inner_text(),'Missing logs remain unknown')
  pg.locator('#toast').evaluate('(e)=>e.classList.add("hidden")');pg.screenshot(path=str(OUT/'v23-mobile-reference.png'),full_page=False)
  pg.locator('[data-reference-month="24"]').click();check(pg.locator('.milestone-card').count()==9,'24-month preview has selected nine items')
  pg.locator('[data-check-milestone="m24_words"]').click();pg.locator('#milestoneState').select_option('not_yet');pg.locator('#saveMilestone').click();pg.wait_for_function('GrowthTest.getState().events.some(e=>e.profile_type==="milestone_check")')
  check('尚未到该参考节点' in pg.locator('#view').inner_text(),'Pre-node not-yet is not delayed')
  check('m24_words' in (data/'generated/发育参考与观察对照.md').read_text(),'Milestone check has Markdown audit')
  pg.locator('[data-check-milestone="m24_words"]').click();pg.locator('#milestoneState').select_option('lost');pg.locator('#saveMilestone').click();pg.wait_for_function('GrowthTest.getState().events.filter(e=>e.profile_type==="milestone_check").length===2')
  check('请及时咨询儿保' in pg.locator('#view').inner_text(),'Lost skill prompts consultation at any age')
  check(len([e for e in Store(data).read()['events'] if e.get('profile_type')=='milestone_check'])==2,'Check history preserved, not overwritten')
  pg.locator('[data-section="capture"]').click();pg.locator('#note').fill('大宝咬了小宝，她哭了');check('对象待确认' in pg.locator('#attributionPreview').inner_text(),'Ambiguous she is not assigned by guess')
  pg.locator('#saveNote').click();pg.wait_for_function('GrowthTest.getState().events.filter(e=>e.kind==="observation").length===5');pg.locator('[data-section="history"]').click()
  check(pg.locator('[data-fix-event]').count()==3,'Unresolved history offers one-tap subject correction')
  pg.locator('[data-fix-child="B"]').click();pg.wait_for_function('GrowthTest.getState().events.some(e=>e.replaces_id)')
  doc=Store(data).read();check(any(e['kind']=='retract' for e in doc['events']),'Correction retains withdrawn old entry')
  check(any(e.get('replaces_id') and e['child']=='B' for e in doc['events']),'Correction creates new explicit B entry')
  pg.locator('[data-section="capture"]').click();pg.locator('#note').fill('昨天大宝用勺，今天小宝跑步');plan=pg.evaluate('GrowthTest.attributionPlan()');check(plan[0]['time']['start']!=plan[1]['time']['start'],'Different dates resolved per fragment')
  pg.locator('#note').fill('');
  # Responsive checks at several real layout widths, not a phone hardware test.
  for width in [320,360,390,430,768,1366]:
   pg.set_viewport_size({'width':width,'height':900});check(pg.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'No horizontal page overflow at {width}px')
   pg.locator('[data-section="reference"]').click();check(pg.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'Reference has no page overflow at {width}px');pg.locator('[data-section="capture"]').click()
  pg.set_viewport_size({'width':390,'height':844});pg.locator('[data-section="sync"]').click();check(pg.locator('#oneClickSave').count()==1,'Existing one-click archive action preserved')
  check(not errors,'No browser JavaScript errors')
  browser.close()
 server.shutdown()
print(json.dumps({'passed':len(results),'checks':results,'js_errors':errors,'limitations':['DOM/storage double; localhost navigation blocked','HTTP bridge to real Python server','No physical phone/Windows, real cloud or GitHub deployment']},ensure_ascii=False,indent=2))
