"""Chromium DOM + real local HTTP bridge + simulated cloud. Navigation is blocked
by this environment; set_content and explicit storage test doubles are used.
No real Supabase/RLS, GitHub, native phone storage, Windows or iOS tests claimed.
"""
import copy,json,shutil,sys,tempfile,threading,urllib.request,urllib.error,uuid
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from serve import make_server
from core import Store
from handoff import run_handoff
OUT=ROOT/'artifacts';OUT.mkdir(exist_ok=True)
FAMILY='10000000-0000-4000-8000-000000000001';USER='20000000-0000-4000-8000-000000000001'
results=[];errors=[]
def check(test,label):
    assert test,label
    results.append(label)

class CloudFixture:
    def __init__(self,seed):self.events=copy.deepcopy(seed['events']);self.fail_posts=False;self.fail_receipts=False
    def login(self):pass
    def read(self):return {'schema_version':2,'events':copy.deepcopy(self.events)}
    def write(self,events):
        ids={e['id'] for e in self.events}
        for e in events:
            if e['id'] not in ids:self.events.append(copy.deepcopy(e));ids.add(e['id'])
    def http(self,arg):
        path=arg['path'];opts=arg.get('opts',{});method=opts.get('method','GET')
        if 'growth_members?' in path:return {'status':200,'text':json.dumps([{'family_id':FAMILY}])}
        if 'growth_events?' in path:
            if method=='POST':
                if self.fail_posts:return {'status':503,'text':'{"error":"simulated offline"}'}
                body=json.loads(opts['body']);self.write([r['payload'] for r in body]);return {'status':201,'text':json.dumps(body)}
            rows=self.events
            if '&id=in.(' in path:
                ids=set(path.split('&id=in.(')[1].split(')')[0].split(','));rows=[e for e in rows if e['id'] in ids]
            return {'status':200,'text':json.dumps([{'payload':e} for e in rows])}
        return {'status':404,'text':'{}'}

HARNESS='''<script>
const memory={},sessionMemory={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>memory[k]||null,setItem:(k,v)=>{memory[k]=v},removeItem:k=>{delete memory[k]}}});
Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>sessionMemory[k]||null,setItem:(k,v)=>{sessionMemory[k]=v},removeItem:k=>{delete sessionMemory[k]}}});
window.fetch=async(path,opts={})=>{let r=await window.__backend({path,opts});return {ok:r.status<400,status:r.status,json:async()=>JSON.parse(r.text),text:async()=>r.text}};
</script>'''

def inline(html):
    html=html.replace('<script src="time_age.js"></script>','<script>'+(ROOT/'web/time_age.js').read_text()+'</script>')
    html=html.replace('<script src="config.js" onerror="window.GROWTH_CONFIG=window.GROWTH_CONFIG||{}"></script>','<script>window.GROWTH_CONFIG=window.GROWTH_CONFIG||{};</script>')
    return html.replace('<head>','<head>'+HARNESS,1)

with tempfile.TemporaryDirectory() as d:
    data=Path(d);shutil.copy(ROOT/'private/seed.json',data/'seed.json');server=make_server(data,0);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
    def backend(arg):
        path=arg['path'];opts=arg.get('opts',{})
        if not path.startswith('/api/'):return {'status':404,'text':'{}'}
        req=urllib.request.Request(url+path,method=opts.get('method','GET'),headers=opts.get('headers',{}),data=opts.get('body','').encode() if opts.get('body') else None)
        try:
            with urllib.request.urlopen(req) as r:return {'status':r.status,'text':r.read().decode()}
        except urllib.error.HTTPError as e:return {'status':e.code,'text':e.read().decode()}
    html=inline(urllib.request.urlopen(url).read().decode())
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        def page_for(content=html,width=390,height=844,cb=backend):
            pg=browser.new_page(viewport={'width':width,'height':height});pg.on('pageerror',lambda e:errors.append(str(e)));pg.expose_function('__backend',cb);pg.set_content(content);pg.wait_for_selector('#note');return pg
        pg=page_for();pg.wait_for_function('GrowthTest.getState().events.length>=22')
        check(pg.locator('[data-page]').count()==3,'Top navigation retains big/small/comparison')
        check(pg.locator('.actionnav [data-section]').count()==3,'Bottom navigation has capture/history/sync')
        check(pg.locator('#saveNote').bounding_box()['y']+pg.locator('#saveNote').bounding_box()['height']<844-65,'Save button visible in initial 390x844 viewport')
        check(pg.locator('#note').evaluate('(e)=>getComputedStyle(e).fontSize')=='16px','Phone input font is 16px')
        check(pg.locator('#saveNote').bounding_box()['height']>=44,'Primary save tap target at least 44px')
        pg.screenshot(path=str(OUT/'v22-mobile-record.png'),full_page=False)
        pg.locator('[data-writer="妈妈"]').click();pg.evaluate("formReportedAt='2026-09-14T04:31:29Z'")
        pg.locator('#note').fill('昨天大宝自己舀了两口饭（界面测试）')
        check('2026-09-13' in pg.locator('#timePreview').inner_text(),'Relative date preview uses frozen report time')
        pg.locator('#saveNote').click();pg.wait_for_function("GrowthTest.active().some(e=>e.text.includes('界面测试'))")
        check('自己舀了两口饭' in (data/'generated/大宝_成长档案.md').read_text(),'Browser save writes actual local Markdown through HTTP')
        check(pg.evaluate("GrowthTest.active().find(e=>e.text.includes('界面测试')).observer")=='妈妈','Mother identity retained on observation')
        pg.locator('.actionnav [data-section="history"]').click();check(pg.locator('.history-entry').count()==1,'History view displays saved observation')
        pg.locator('[data-filter="mother"]').click();check(pg.locator('.history-entry').count()==1,'Mother history filter works')
        pg.locator('.actionnav [data-section="sync"]').click();pg.wait_for_selector('#oneClickSave');pg.locator('#oneClickSave').click();pg.wait_for_function("document.querySelector('#syncResult').textContent.includes('本地Markdown已保存')")
        check('云端未配置' in pg.locator('#syncResult').inner_text(),'One-click local mode never claims missing cloud was synced')
        check(any(e.get('stage')=='local_markdown' for e in json.loads((data/'growth.json').read_text())['events']),'One-click creates actual local archive receipt')
        pg.locator('.actionnav [data-section="history"]').click();pg.locator('[data-filter="archived"]').click();check(pg.locator('.sync-tag.archived').count()==1,'History shows per-record archive receipt')
        pg.screenshot(path=str(OUT/'v22-mobile-history.png'),full_page=False)
        pg.locator('#calendar summary').click();pg.locator('#useCalendarDay').click()
        check(pg.locator('#note').is_visible() and pg.locator('#noteDate').input_value()!='','Calendar in history can open the capture form without losing the chosen date')
        pg.locator('#note').fill('');pg.locator('#noteDate').evaluate('(e)=>e.value=""');pg.evaluate('saveDraft()')
        for width in [320,360,390,430,768,1366]:
            pg.set_viewport_size({'width':width,'height':900})
            for section in ['capture','history','sync']:
                pg.evaluate('(s)=>GrowthTest.setSection(s)',section)
                check(pg.evaluate('document.documentElement.scrollWidth<=innerWidth'),f'No horizontal overflow at {width}px / {section}')
        pg.set_viewport_size({'width':390,'height':844});pg.evaluate("page='compare';GrowthTest.setSection('capture')")
        check(pg.locator('.comparison-item').count()==8,'Comparison uses eight mobile cards instead of a wide table')
        check(pg.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Comparison has no horizontal overflow')
        # Use evaluate to switch: URL navigation is forbidden in this environment.
        pg.evaluate("page='big';GrowthTest.setSection('capture')")
        pg.locator('#note').fill('未提交的草稿测试');pg.evaluate("page='small';GrowthTest.setSection('capture')");pg.evaluate("page='big';GrowthTest.setSection('capture')")
        # setSection saves current rendered child's input; direct page mutation is not real tab flow.
        # Real draft persistence is checked by saveDraft, clearing memory, restoring from storage.
        pg.locator('#note').fill('刷新后应保留的草稿');pg.evaluate('saveDraft();drafts={};drafts=loadJSON(key()+":drafts",{});render()')
        check(pg.locator('#note').input_value()=='刷新后应保留的草稿','Drafts survive reinitialization from device storage')
        pg.locator('#note').fill('');pg.evaluate('saveDraft()')
        # Cloud/mother: schema fixture contains seed only; no live service is contacted.
        fixture=CloudFixture(json.loads((ROOT/'private/seed.json').read_text()))
        cloudhtml=inline((ROOT/'web/index.html').read_text())
        config=f"window.GROWTH_CONFIG={{url:'https://test.supabase.co',key:'sb_publishable_TEST',familyId:'{FAMILY}'}};"
        cloudhtml=cloudhtml.replace('<script>/*LOCAL_CONFIG*/</script>','<script>'+config+f"Object.defineProperty(window,'sessionStorage',{{value:{{getItem:k=>k.endsWith(':session')?JSON.stringify({{access_token:'test',refresh_token:'test',user:{{id:'{USER}'}},expires_at:Date.now()+3600000}}):null,setItem:()=>{{}},removeItem:()=>{{}}}},configurable:true}});"+'</script>')
        # The first storage property must be configurable for the cloud session fixture.
        cloudhtml=cloudhtml.replace("Object.defineProperty(window,'sessionStorage',{value:","Object.defineProperty(window,'sessionStorage',{configurable:true,value:")
        mother=page_for(cloudhtml,cb=fixture.http);mother.wait_for_function('GrowthTest.getState().events.length>=22')
        mother.locator('[data-writer="妈妈"]').click();mother.evaluate("saveDraft();page='small';render()");fixture.fail_posts=True
        mother.locator('#note').fill('昨天小宝把盒子递给我（云端失败测试）');mother.locator('#saveNote').click();mother.wait_for_function("GrowthTest.active().some(e=>e.text.includes('云端失败测试'))")
        mother.wait_for_timeout(300)
        check(mother.evaluate('GrowthTest.pendingEvents().length')==1,'Failed upload keeps queued event in device ledger')
        check(not any('云端失败测试' in e['text'] for e in fixture.events),'No fake cloud success when server rejects upload')
        check(mother.evaluate("GrowthTest.active().find(e=>e.text.includes('云端失败测试')).child")=='B','Selected child is retained in queued cloud observation')
        mother.evaluate("GrowthTest.setSection('history')");check('待上传' in mother.locator('.sync-tag').inner_text(),'Mother sees explicit pending-upload status')
        fixture.fail_posts=False;mother.evaluate('GrowthTest.refresh()');mother.wait_for_function('GrowthTest.pendingEvents().length===0')
        check(sum('云端失败测试' in e['text'] for e in fixture.events)==1,'Retry uploads exactly once by immutable ID')
        mother.evaluate("GrowthTest.setSection('history')");check('已上传' in mother.locator('.sync-tag').inner_text(),'Cloud confirmation changes only after verified readback')
        with tempfile.TemporaryDirectory() as fatherdir:
            run_handoff(Store(Path(fatherdir)),cloud=fixture)
            mother.evaluate('GrowthTest.refresh()');mother.wait_for_function("GrowthTest.active().some(e=>e.profile_type==='archive_receipt')")
            mother.evaluate("GrowthTest.setSection('history')")
            check('归档已确认' in mother.locator('.sync-tag').inner_text(),'Mother receives father archive receipt through shared history')
            mother.screenshot(path=str(OUT/'v22-mobile-cloud-history.png'),full_page=False)
        mother.evaluate("GrowthTest.setSection('sync')");mother.screenshot(path=str(OUT/'v22-mobile-sync.png'),full_page=False)
        check(not errors,'No browser JavaScript errors')
        browser.close()
    server.shutdown();server.server_close()
report={'passed':len(results),'checks':results,'errors':errors,'test_environment':'Chromium set_content; real Python loopback HTTP bridge; localStorage/sessionStorage test doubles; simulated cloud API. Browser navigation to localhost blocked by administrator.','not_tested':['real Supabase authentication/RLS','actual GitHub upload','native iOS/Android browser persistence','Windows runtime','actual two-phone internet access']}
(OUT/'v22-browser-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
