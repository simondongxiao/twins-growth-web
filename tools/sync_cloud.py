"""Bidirectional cloud event merge and local Markdown export. Runs ONLY while invoked."""
from __future__ import annotations
import argparse, base64, getpass, json, os, time, urllib.error, urllib.parse, urllib.request, uuid
from pathlib import Path
from core import Store, atomic_write, merge_docs, validate_doc
ROOT=Path(__file__).resolve().parents[1]

class Cloud:
    def __init__(self, config:dict):
        self.cfg=config;self.token=None;self.user_id=None
        u=urllib.parse.urlsplit(config['url'])
        if u.scheme!='https' or not (u.hostname or '').endswith('.supabase.co') or u.path not in ('','/'):
            raise ValueError('Use an HTTPS Supabase project URL')
        uuid.UUID(config['family_id'])
        key=config['key']
        if key.startswith('sb_secret_'):raise ValueError('Do not use a secret key')
        if key.startswith('eyJ'):
            try: role=json.loads(base64.urlsafe_b64decode(key.split('.')[1]+'==='))['role']
            except Exception: raise ValueError('Invalid anon key') from None
            if role!='anon':raise ValueError('Use publishable/anon key, never service_role')
        elif not key.startswith('sb_publishable_'):raise ValueError('Use publishable/anon key')
    def request(self,path,method='GET',data=None,headers=None):
        h={'apikey':self.cfg['key'],'Content-Type':'application/json'}
        if self.token:h['Authorization']='Bearer '+self.token
        h.update(headers or {})
        req=urllib.request.Request(self.cfg['url'].rstrip('/')+path,method=method,headers=h,data=None if data is None else json.dumps(data,ensure_ascii=False).encode())
        try:
            with urllib.request.urlopen(req,timeout=30) as r:
                b=r.read();return json.loads(b) if b else None
        except urllib.error.HTTPError as exc:
            # Never print account credentials or request body.
            body=exc.read().decode('utf-8','replace')[:240]
            raise RuntimeError(f'Cloud HTTP {exc.code}: {body}') from None
    def login(self):
        result=self.request('/auth/v1/token?grant_type=password','POST',{'email':self.cfg['email'],'password':self.cfg['password']})
        self.token=result['access_token'];self.user_id=result['user']['id']
        members=self.request('/rest/v1/growth_members?select=family_id&family_id=eq.'+self.cfg['family_id'])
        if not members:raise RuntimeError('Account is not a member of the configured household')
    def read(self):
        events=[];offset=0
        while True:
            rows=self.request('/rest/v1/growth_events?select=payload&family_id=eq.'+self.cfg['family_id']+f'&order=id.asc&limit=500&offset={offset}')
            events.extend(r['payload'] for r in rows)
            if len(rows)<500:break
            offset+=500
            if offset>50000:raise RuntimeError('Dataset exceeds current limit')
        return validate_doc({'schema_version':2,'events':events})
    def write(self,events):
        for i in range(0,len(events),100):
            batch=[{'id':e['id'],'family_id':self.cfg['family_id'],'created_by':self.user_id,'payload':e} for e in events[i:i+100]]
            self.request('/rest/v1/growth_events?on_conflict=id','POST',batch,{'Prefer':'resolution=ignore-duplicates,return=representation'})

def sync_once(store:Store,cloud:Cloud):
    cloud.login();remote=cloud.read();local=store.read()
    merged=merge_docs(local,remote) # same-ID conflict aborts before any write.
    remote_ids={e['id'] for e in remote['events']}
    pending=[e for e in merged['events'] if e['id'] not in remote_ids]
    cloud.write(pending)
    verified=cloud.read()
    verified_ids={e['id'] for e in verified['events']}
    if any(e['id'] not in verified_ids for e in pending):raise RuntimeError('Upload not confirmed; local records retained')
    final=store.merge(verified) # merges against latest disk, preserving records saved during network I/O.
    return {'events':len(final['events']),'uploaded':len(pending),'markdown':str(store.private/'generated')}

def load_config(path):
    if path.exists(): return json.loads(path.read_text('utf-8'))
    keys={'url':'GROWTH_CLOUD_URL','key':'GROWTH_CLOUD_KEY','family_id':'GROWTH_FAMILY_ID','email':'GROWTH_EMAIL','password':'GROWTH_PASSWORD'}
    cfg={k:os.getenv(v,'') for k,v in keys.items()}
    if not all(cfg.values()):raise ValueError('Missing cloud configuration. Run --configure first, or set GROWTH_* environment variables.')
    return cfg

def configure(path):
    print('One-time local sync configuration. Password is not echoed. File stays in private/ (gitignored).')
    cfg={'url':input('Supabase project URL: ').strip().rstrip('/'),'key':input('Publishable / anon key: ').strip(),'family_id':input('Family UUID: ').strip(),'email':input('Parent account email: ').strip(),'password':getpass.getpass('Parent account password: ')}
    cloud=Cloud(cfg);cloud.login()
    atomic_write(path,json.dumps(cfg,ensure_ascii=False,indent=2))
    try:os.chmod(path,0o600)
    except OSError:pass
    print('Saved locally. On Windows, verify private/ permissions. This file is plaintext; do not share it.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=ROOT/'private');p.add_argument('--config',type=Path,default=ROOT/'private/cloud.local.json');p.add_argument('--configure',action='store_true');p.add_argument('--watch',type=int,default=0)
    args=p.parse_args()
    if args.configure:configure(args.config);return
    if args.watch and args.watch<30:raise SystemExit('--watch must be >=30 seconds')
    store=Store(args.data_dir)
    while True:
        try:
            r=sync_once(store,Cloud(load_config(args.config)));print(time.strftime('%H:%M:%S'),json.dumps(r,ensure_ascii=False),flush=True)
        except Exception as e:
            print('Sync failed; local data retained:',e,flush=True)
            if not args.watch:raise SystemExit(1)
        if not args.watch:break
        time.sleep(args.watch)
if __name__=='__main__':main()
