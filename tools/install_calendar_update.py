"""Create/upgrade only the named growth app; never replace an existing journal.
Run from the unpacked V2.3 delivery directory. No git/cloud writes are performed.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, shutil, subprocess, sys, urllib.request, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def install(target: Path):
    target=target.resolve()
    if target==ROOT.resolve():
        raise ValueError('请将升级包放在旧项目以外的目录，再运行；直接使用本包请运行start_local.bat。')
    if target.exists() and any(target.iterdir()) and not ((target/'web/index.html').exists() and (target/'tools/core.py').exists()):
        raise ValueError('目标不是可识别的成长项目，停止，未改动其他目录。')
    interface=target/'web/index.html'
    if interface.exists():
        supported={x['sha256'] for x in json.loads((ROOT/'docs/已知界面版本.json').read_text('utf-8'))}
        supported.add(hashlib.sha256((ROOT/'web/index.html').read_bytes()).hexdigest())
        if hashlib.sha256(interface.read_bytes()).hexdigest() not in supported:
            raise ValueError('现有界面有本地定制。已停止自动覆盖；请Codex按增量说明合并V2.3功能并保留样式与配置。')
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/status',timeout=.5) as res:
            if res.status==200: raise RuntimeError('请先关闭旧版本地服务及同步器窗口，再升级。')
    except (OSError,urllib.error.URLError): pass
    target.mkdir(parents=True,exist_ok=True)
    code=[]
    for name in ('web','tools','docs','tests'):
        code += [p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
    code += [ROOT/n for n in ('README.md','CODEX_执行说明.md','CODEX_手机协作一次部署.md','CODEX_增量升级V2.3.md','start_local.bat','start_sync.bat','configure_sync.bat','one_click_sync.bat','configure_github_backup.bat','.gitignore') if (ROOT/n).exists()]
    archive=target/'private/code_backups'/('before-v23-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.zip')
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in code:
            old=target/p.relative_to(ROOT)
            if old.is_file(): z.write(old,str(old.relative_to(target)))
    for p in code:
        dest=target/p.relative_to(ROOT)
        if str(p.relative_to(ROOT)).replace('\\','/')=='web/config.js' and dest.exists(): continue
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    private=target/'private';private.mkdir(exist_ok=True)
    if not (private/'growth.json').exists() and not (private/'seed.json').exists() and (ROOT/'private/seed.json').exists():
        shutil.copy2(ROOT/'private/seed.json',private/'seed.json')
    birth=ROOT/'private/birthday_update.json'
    code="import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from core import Store;s=Store(Path(sys.argv[2]));p=Path(sys.argv[3]);s.merge(json.loads(p.read_text('utf-8'))) if p.exists() else None;s.save(s.read());print(s.private/'generated')"
    subprocess.run([sys.executable,'-c',code,str(target/'tools'),str(private),str(birth)],check=True)
    print('升级完成。原growth.json已按ID合并，历史未覆盖。')
    print('代码备份：',archive)
    print('现在从目标目录运行start_local.bat；公开GitHub发布与云端同步没有自动执行。')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',type=Path,default=Path(r'D:\codex\twins-growth-web-v2'))
    a=p.parse_args()
    try: install(a.target)
    except Exception as exc:
        print('未完成升级：'+str(exc),file=sys.stderr);return 1
    return 0
if __name__=='__main__':sys.exit(main())
