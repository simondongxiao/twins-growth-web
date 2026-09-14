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

        pg=new_page(); results.append('V2.1 template and private profile load')
        expected=pg.evaluate("currentAge('A')")
        assert expected in pg.locator('.hero .age').inner_text();results.append('Live age header uses confirmed birthday')
        pg.evaluate("formReportedAt='2026-09-14T03:52:34Z'")
        pg.locator('#note').fill('昨天大宝做了测试动作（仅测试）')
        assert '2026-09-13' in pg.locator('#timePreview').inner_text()
        pg.locator('#saveNote').click();pg.wait_for_function("GrowthTest.active().some(e=>e.kind==='observation'&&e.text.includes('测试动作'))")
        e=pg.evaluate("GrowthTest.active().filter(e=>e.kind==='observation').at(-1)")
        assert e['time']['reference_date']=='2026-09-14' and e['date']=='2026-09-13'
        md=(data/'generated/大宝_成长档案.md').read_text();assert '2026-09-13' in md and '发生时月龄' in md;results.append('Yesterday parsed, previewed, saved via HTTP and written to Markdown')
        pg.evaluate("saveDraft();page='small';render();formReportedAt='2026-09-14T03:52:34Z'")
        pg.locator('#note').fill('上周小宝有一个测试变化（仅测试）')
        assert '2026-09-07 至 2026-09-13' in pg.locator('#timePreview').inner_text()
        pg.locator('#saveNote').click();pg.wait_for_function("GrowthTest.active().some(e=>e.text.includes('测试变化'))")
        x=pg.evaluate("GrowthTest.active().find(e=>e.text.includes('测试变化'))")
        assert x['date'] is None and x['time']['precision']=='range'
        assert '2026-09-07 至 2026-09-13' in (data/'generated/小宝_成长档案.md').read_text();results.append('Previous calendar week stays a range with corresponding age range')
        pg.locator('#calendar summary').click();pg.evaluate("calendarMonth='2026-09';calendarSelected='2026-09-14';paintCalendar()")
        assert pg.locator('[data-cal-day]').count()==42
        pg.locator('[data-cal-day="2026-09-12"]').click()
        assert '区间覆盖，非当天已确认' in pg.locator('.cal-notes').inner_text();results.append('Calendar range marks do not assert daily occurrences')
        pg.locator('#useCalendarDay').click();assert pg.locator('#noteDate').input_value()=='2026-09-12'
        pg.locator('#note').fill('不写日期的日历测试')
        assert '2026-09-12' in pg.locator('#timePreview').inner_text()
        pg.locator('#saveNote').click();pg.wait_for_function("GrowthTest.active().some(e=>e.text==='不写日期的日历测试')");results.append('Calendar day selection overrides automatic text date')
        pg.locator('#note').fill('前几天小宝有个模糊时间测试')
        pg.locator('#saveNote').click();pg.wait_for_function("GrowthTest.active().some(e=>e.text.includes('模糊时间测试'))")
        assert pg.evaluate("GrowthTest.active().find(e=>e.text.includes('模糊时间测试')).time.start") is None;results.append('Vague date remains unknown in saved evidence')
        before=pg.evaluate('GrowthTest.getState().events.length');pg.locator('#note').fill('明天大宝要做未来测试');pg.locator('#saveNote').click()
        pg.wait_for_timeout(150);assert pg.evaluate('GrowthTest.getState().events.length')==before
        assert '未来' in pg.locator('#toast').inner_text();pg.locator('#note').fill('');results.append('Future observation rejected without changing journal')
        pg.locator('#note').fill('昨天做了测试，上周也做过测试');pg.locator('#saveNote').click();pg.wait_for_function("GrowthTest.active().some(e=>e.text==='昨天做了测试，上周也做过测试')")
        assert pg.evaluate("GrowthTest.active().find(e=>e.text==='昨天做了测试，上周也做过测试').time.precision")=='ambiguous';results.append('Multi-time narrative not forced into one exact day')
        pg.evaluate("saveDraft();page='compare';render()")
        assert pg.locator('.comparetable tbody tr').count()==8
        assert '报告时间' in pg.evaluate('GrowthTest.buildMD()');results.append('Three views and browser Markdown retain event/report time separation')
        mobile=new_page(390,844);mobile.locator('#calendar summary').click()
        assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth')
        mobile.screenshot(path=str(OUT/'calendar-mobile.png'),full_page=True)
        pg.evaluate("saveDraft();page='big';render()")
        pg.locator('#calendar summary').click();pg.screenshot(path=str(OUT/'calendar-desktop.png'),full_page=True)
        results.append('Expanded calendar works at 390px with no horizontal overflow')
        assert not errors,errors;b.close()
    server.shutdown();server.server_close()
    report={'passed':len(results),'checks':results,'errors':errors,'harness':'Chromium set_content; real loopback HTTP via Python bridge; storage test double. No browser URL navigation.','not_tested':['real GitHub deployment','real Supabase auth/RLS','native mobile browser storage','Windows OS runtime']}
    (OUT/'calendar_browser_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
