"""Explicit, desktop-only backup to an already configured PRIVATE GitHub repository.
Uses gh's local login, never a browser token. Only validated journal and generated
Markdown are uploaded; credentials/config/HTML/photos are NEVER included.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, re, subprocess, uuid
from pathlib import Path
from core import atomic_write, render_markdown, validate_doc
ROOT=Path(__file__).resolve().parents[1]

class GitHub:
    def api(self, path, method='GET', data=None):
        args=['gh','api',path,'--method',method]
        if data is not None: args += ['--input','-']
        try:
            r=subprocess.run(args,input=None if data is None else json.dumps(data,ensure_ascii=False),
                text=True,encoding='utf-8',capture_output=True,timeout=60,check=False)
        except FileNotFoundError: raise RuntimeError('尚未安装GitHub CLI；先在本机安装gh并登录。') from None
        if r.returncode:
            # gh may print server-side details: never expose them to browser/logs.
            raise RuntimeError('GitHub操作未确认。请检查本机gh登录、仓库权限或分支冲突；没有强制覆盖。')
        return json.loads(r.stdout) if r.stdout.strip() else None

def validate_repo(repo, api):
    if not isinstance(repo,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
        raise ValueError('仓库必须是明确的 OWNER/REPOSITORY。')
    info=api.api('repos/'+repo)
    if info.get('private') is not True: raise ValueError('拒绝上传儿童记录：数据仓库必须是私有仓库。')
    if info.get('has_pages'): raise ValueError('数据仓库不能启用GitHub Pages，请使用独立私有备份仓库。')
    if info.get('archived'): raise ValueError('仓库已归档，不可写入。')
    branch=info.get('default_branch')
    if not branch or not re.fullmatch(r'[A-Za-z0-9_./-]+',branch) or '..' in branch:
        raise ValueError('请先在数据仓库创建README初始化默认分支。')
    return branch

def backup(doc, config_path:Path, api=None):
    cfg=json.loads(config_path.read_text('utf-8')) if config_path.exists() else {}
    repo=cfg.get('repo'); api=api or GitHub(); branch=validate_repo(repo,api)
    doc=validate_doc(doc)
    content=json.dumps(doc,ensure_ascii=False,indent=2)
    digest=hashlib.sha256(content.encode()).hexdigest()
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder='archives/'+stamp+'-'+uuid.uuid4().hex[:8]
    # Build only an allowlisted in-memory snapshot, not a recursive directory upload.
    files={folder+'/growth.json':content}
    files.update({folder+'/markdown/'+name:text for name,text in render_markdown(doc).items()})
    files['latest.json']=json.dumps({'archive':folder,'sha256':digest,'event_count':len(doc['events']),'created_at':stamp},ensure_ascii=False,indent=2)
    for name,text in files.items():
        if '..' in name.split('/') or not isinstance(text,str): raise ValueError('非法备份路径。')
    ref=api.api('repos/'+repo+'/git/ref/heads/'+branch)
    head=ref['object']['sha']
    commit=api.api('repos/'+repo+'/git/commits/'+head)
    tree=api.api('repos/'+repo+'/git/trees','POST',{'base_tree':commit['tree']['sha'],
        'tree':[{'path':path,'mode':'100644','type':'blob','content':text} for path,text in files.items()]})
    new=api.api('repos/'+repo+'/git/commits','POST',{'message':'Private growth archive '+stamp,'tree':tree['sha'],'parents':[head]})
    # Non-fast-forward updates are refused. Never use force.
    result=api.api('repos/'+repo+'/git/refs/heads/'+branch,'PATCH',{'sha':new['sha'],'force':False})
    if result.get('object',{}).get('sha')!=new['sha']: raise RuntimeError('GitHub提交回执不符，未标记备份成功。')
    return {'status':'confirmed','repo':repo,'commit':new['sha'],'archive':folder,'sha256':digest}

def configure(path):
    repo=input('已有的独立私有数据仓库（OWNER/REPO，须初始化README，不启用Pages）：').strip()
    validate_repo(repo,GitHub())
    if input('仅在电脑点击“一键更新”并勾选备份时上传记录。确认配置? [yes]: ').strip().lower()!='yes':
        print('未保存配置。');return
    atomic_write(path,json.dumps({'repo':repo},ensure_ascii=False,indent=2));print('配置保存在private，仅含仓库名。登录凭据由本机gh管理。')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--configure',action='store_true');p.add_argument('--config',type=Path,default=ROOT/'private/github.local.json');a=p.parse_args()
    if a.configure: configure(a.config)
    else: p.error('Use --configure; archive uploads are triggered by handoff.py --github.')
