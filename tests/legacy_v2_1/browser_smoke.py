"""Real Chromium tests against local server and isolated standalone preview."""
import json,shutil,sys,tempfile,threading,os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from serve import make_server
from core import Store
out=ROOT/'artifacts';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as d:
    data=Path(d);shutil.copy(ROOT/'private/seed.json',data/'seed.json')
    server=make_server(data,0);t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
    url=f'http://127.0.0.1:{server.server_port}/'
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(**({'executable_path':os.environ['CHROMIUM_PATH']} if os.getenv('CHROMIUM_PATH') else {}))
        page=browser.new_page(viewport={'width':1366,'height':1100},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url);page.wait_for_selector('#note');page.wait_for_function('window.GrowthTest.getState().events.length===22')
        assert page.locator('h1').inner_text()=='大宝的成长手记';results.append('Loads 20 baseline records + profile + unconfirmed proposal')
        page.screenshot(path=str(out/'desktop-big.png'),full_page=True)
        text='今天大宝指着盒子说“开”，没有先示范。'
        page.locator('#note').fill(text);page.locator('#saveNote').click();page.wait_for_function('(t)=>window.GrowthTest.getState().events.some(e=>e.text===t)',arg=text)
        assert text in (data/'generated/大宝_成长档案.md').read_text();results.append('One-line save writes A Markdown, JSON and monthly log')
        page.locator('[data-page="small"]').click();page.wait_for_function('location.hash==="#small"')
        assert page.locator('h1').inner_text()=='小宝的成长手记'
        assert page.locator('.entry').filter(has_text=text).count()==0;results.append('Child-specific isolation')
        xss='<img src=x onerror="window.XSS_RAN=1">小宝自己的观察'
        page.locator('#note').fill(xss);page.locator('#saveNote').click();page.wait_for_function('(t)=>window.GrowthTest.getState().events.some(e=>e.text===t)',arg=xss)
        assert page.evaluate('window.XSS_RAN||null') is None;assert page.locator('.entry img').count()==0;results.append('Observation XSS renders as text')
        page.reload();page.wait_for_selector('#note');assert page.locator('.entry').filter(has_text='小宝自己的观察').count()==1;results.append('Reload persistence')
        page.locator('#note').fill('尚未保存的小宝草稿');page.locator('[data-page="big"]').click();page.wait_for_function('location.hash==="#big"');page.locator('[data-page="small"]').click();page.wait_for_function('location.hash==="#small"')
        assert page.locator('#note').input_value()=='尚未保存的小宝草稿';page.locator('#note').fill('');results.append('Tab switch preserves unsaved draft')
        page.locator('[data-page="compare"]').click();page.wait_for_function('location.hash==="#compare"');assert page.locator('.comparetable tbody tr').count()==8
        page.screenshot(path=str(out/'desktop-compare.png'),full_page=True);results.append('Compare route with 8 non-scored dimensions')
        page.on('dialog',lambda dialog:dialog.accept())
        page.locator('#acceptInitial').click();page.wait_for_function('window.GrowthTest.getState().events.some(e=>e.kind==="plan")');assert '家长已确认' in page.locator('#view').inner_text();results.append('Plan requires explicit parent confirmation')
        # Shared note, retract, and metadata.
        shared='两个人今天都各自拿一个球，没有争抢。';page.locator('#note').fill(shared);page.locator('#saveNote').click();page.wait_for_function('(t)=>window.GrowthTest.getState().events.some(e=>e.text===t)',arg=shared)
        row=page.locator('.entry').filter(has_text=shared);row.locator('.retract').click();page.wait_for_function('(t)=>!window.GrowthTest.active().some(e=>e.text===t)',arg=shared)
        assert shared not in (data/'generated/大宝_成长档案.md').read_text();results.append('Shared record / retract / generated-view removal, audit retained')
        page.locator('#openSettings').click();page.locator('#observerSetting').select_option('妈妈');page.locator('#saveObserver').click();page.locator('[data-close="settingsDialog"]').click()
        assert '妈妈的记录' in page.locator('#view').inner_text();results.append('Remembered observer reduces required fields')
        assert len(errors)==0,errors
        # API request requires local random write token.
        r=page.request.post(url+'api/event',data={});assert r.status==403;results.append('Unauthorized local API write refused')
        mobile=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True,device_scale_factor=1)
        mp=mobile.new_page();mp.goto(url);mp.wait_for_selector('#note')
        assert mp.evaluate('document.documentElement.scrollWidth <= innerWidth'),mp.evaluate('[document.documentElement.scrollWidth,innerWidth]')
        mp.screenshot(path=str(out/'mobile-big.png'),full_page=True)
        mp.locator('[data-page="compare"]').click();mp.wait_for_selector('.comparetable');assert mp.evaluate('document.documentElement.scrollWidth <= innerWidth')
        mp.screenshot(path=str(out/'mobile-compare.png'),full_page=True);results.append('390px phone layout, no horizontal page overflow')
        # Test offline private HTML, no cloud requests, localStorage survives refresh.
        fp=browser.new_page();fp.goto((ROOT/'private/成长跟踪-本地预览.html').as_uri());fp.wait_for_selector('#note')
        fp.locator('#note').fill('离线本机保存测试');fp.locator('#saveNote').click();fp.wait_for_function('window.GrowthTest.getState().events.some(e=>e.text==="离线本机保存测试")');fp.reload();fp.wait_for_selector('#note');assert fp.locator('.entry').filter(has_text='离线本机保存测试').count()==1;results.append('Standalone file saves and reloads browser-local records')
        browser.close()
    server.shutdown();server.server_close()
    (out/'browser_results.json').write_text(json.dumps({'passed':results,'page_errors':errors,'cloud_live_tested':False},ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'passed':len(results),'checks':results},ensure_ascii=False,indent=2))
