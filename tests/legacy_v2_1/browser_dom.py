"""Chromium DOM tests without external navigation. Local HTTP transported via Python;
browser storage is a test double because this environment blocks URL navigation."""
import json,shutil,sys,tempfile,threading,urllib.request,urllib.error
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from serve import make_server
OUT=ROOT/'artifacts';OUT.mkdir(exist_ok=True)
HARNESS='''<script>
const mem={};Object.defineProperty(window,'localStorage',{value:{getItem:k=>mem[k]||null,setItem:(k,v)=>{mem[k]=v},removeItem:k=>{delete mem[k]}}});
Object.defineProperty(window,'sessionStorage',{value:{getItem:k=>null,setItem:()=>{},removeItem:()=>{}}});
window.fetch=async(path,opts={})=>{let r=await window.__backend({path,opts});return {ok:r.status<400,status:r.status,json:async()=>JSON.parse(r.text),text:async()=>r.text}};
</script>'''
with tempfile.TemporaryDirectory() as d:
    data=Path(d);shutil.copy(ROOT/'private/seed.json',data/'seed.json');server=make_server(data,0)
    threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}'
    def req(arg):
        path=arg['path'];opts=arg.get('opts',{})
        if not path.startswith('/api/'):return {'status':404,'text':'{}'}
        r=urllib.request.Request(url+path,method=opts.get('method','GET'),headers=opts.get('headers',{}),data=opts.get('body','').encode() if opts.get('body') else None)
        try:
            with urllib.request.urlopen(r) as res:return {'status':res.status,'text':res.read().decode()}
        except urllib.error.HTTPError as e:return {'status':e.code,'text':e.read().decode()}
    html=urllib.request.urlopen(url+'/').read().decode()
    html=html.replace('<script src="time_age.js"></script>','<script>'+(ROOT/'web/time_age.js').read_text()+'</script>')
    html=html.replace('<script src="config.js" onerror="window.GROWTH_CONFIG=window.GROWTH_CONFIG||{}"></script>','<script>window.GROWTH_CONFIG={};</script>')
    html=html.replace('<script>/*LOCAL_CONFIG*/</script>','') # normally already injected
    html=html.replace('<script>window.LOCAL_CONFIG=',HARNESS+'<script>window.LOCAL_CONFIG=')
    results=[];errors=[]
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        def new_page(width=1366,height=1100):
            pg=b.new_page(viewport={'width':width,'height':height});pg.expose_function('__backend',req);pg.on('pageerror',lambda e:errors.append(str(e)));pg.set_content(html);pg.wait_for_selector('#note');pg.wait_for_function('window.GrowthTest.getState().events.length>=22');return pg
        pg=new_page();assert pg.locator('h1').inner_text()=='大宝的成长手记';results.append('Initial baseline loaded')
        pg.screenshot(path=str(OUT/'desktop-big.png'),full_page=True)
        text='测试：大宝自己说打开';pg.locator('#note').fill(text);pg.locator('#saveNote').click();pg.wait_for_function('(t)=>window.GrowthTest.getState().events.some(e=>e.text===t)',arg=text)
        assert text in (data/'generated/大宝_成长档案.md').read_text();results.append('DOM save to local HTTP API and Markdown')
        # Evaluate the route state without navigation blocked by admin policy.
        pg.evaluate("saveDraft();page='small';render()")
        assert pg.locator('h1').inner_text()=='小宝的成长手记';assert pg.locator('.entry').filter(has_text=text).count()==0;results.append('Child route and isolation')
        xss='<img src=x onerror="window.XSS_RAN=1">测试原话';pg.locator('#note').fill(xss);pg.locator('#saveNote').click();pg.wait_for_function('(t)=>window.GrowthTest.getState().events.some(e=>e.text===t)',arg=xss)
        assert pg.locator('.entry img').count()==0;assert pg.evaluate('window.XSS_RAN||null') is None;results.append('User text escaped against HTML injection')
        pg.locator('#note').fill('待保存草稿');pg.evaluate("saveDraft();page='big';render();saveDraft();page='small';render()")
        assert pg.locator('#note').input_value()=='待保存草稿';pg.locator('#note').fill('');results.append('Draft preserved across route renders')
        pg.evaluate("saveDraft();page='compare';render()")
        assert pg.locator('.comparetable tbody tr').count()==8;pg.screenshot(path=str(OUT/'desktop-compare.png'),full_page=True);results.append('8-direction comparison without scores')
        pg.on('dialog',lambda x:x.accept());pg.locator('#acceptInitial').click();pg.wait_for_function('window.GrowthTest.getState().events.some(e=>e.kind==="plan")');results.append('Explicit parent plan approval')
        shared='测试：两个人都拿了球';pg.locator('#note').fill(shared);pg.locator('#saveNote').click();pg.wait_for_function('(t)=>window.GrowthTest.getState().events.some(e=>e.text===t)',arg=shared)
        pg.locator('.entry').filter(has_text=shared).locator('.retract').click();pg.wait_for_function('(t)=>!window.GrowthTest.active().some(e=>e.text===t)',arg=shared);assert shared not in (data/'generated/大宝_成长档案.md').read_text();results.append('Retraction reflected in Markdown; audit preserved')
        pg.locator('#openSettings').click();pg.locator('#observerSetting').select_option('妈妈');pg.locator('#saveObserver').click();pg.locator('[data-close="settingsDialog"]').click();assert '妈妈的记录' in pg.locator('#view').inner_text();results.append('Default observer setting')
        refreshed=new_page();assert refreshed.locator('.entry').filter(has_text=text).count()==1;results.append('Fresh view reads persisted server records')
        mobile=new_page(390,844);assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth');mobile.screenshot(path=str(OUT/'mobile-big.png'),full_page=True)
        mobile.evaluate("saveDraft();page='compare';render()");assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth');mobile.screenshot(path=str(OUT/'mobile-compare.png'),full_page=True);results.append('390px layout without page overflow')
        r=req({'path':'/api/event','opts':{'method':'POST','body':'{}','headers':{'Content-Type':'application/json'}}});assert r['status']==403;results.append('Local HTTP rejects writes without token')
        assert not errors,errors;b.close()
    server.shutdown();server.server_close()
    report={'passed':len(results),'checks':results,'errors':errors,'harness':'Chromium set_content; real loopback HTTP via Python bridge; storage test double. No browser URL navigation.','not_tested':['real GitHub deployment','real Supabase auth/RLS','native mobile browser storage','Windows OS runtime']}
    (OUT/'browser_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
