"""One click: pull family history, merge by immutable ID, write local Markdown,
return archive receipts to family cloud, optionally back up to a PRIVATE GitHub repo.
No background job or cloud/GitHub account is provisioned by this module.
"""
from __future__ import annotations
import argparse, hashlib, json, os, uuid
from pathlib import Path
from core import Store, atomic_write, now, process_lock, validate_event
from sync_cloud import Cloud, load_config, sync_once
from github_backup import backup
ROOT=Path(__file__).resolve().parents[1]

def is_receipt(e): return e.get('kind')=='profile' and e.get('profile_type')=='archive_receipt'
def acknowledged(doc, stage):
    return {i for e in doc['events'] if is_receipt(e) and e.get('stage')==stage for i in e.get('event_ids',[])}

def make_receipts(doc,stage,extra=None):
    known=acknowledged(doc,stage)
    ids=sorted(e['id'] for e in doc['events'] if not is_receipt(e) and e['id'] not in known)
    stamp=now(); receipt=[]
    for i in range(0,len(ids),200):
        batch=ids[i:i+200]
        item={'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'growth-archive:'+stage+':'+','.join(batch))),
            'kind':'profile','profile_type':'archive_receipt','child':'both','category':'待整理',
            'text':'记录已写入电脑Markdown；这是存储回执，不是对孩子表现或计划的审批。' if stage=='local_markdown' else '记录已提交独立私有GitHub备份仓库。',
            'created_at':stamp,'date':None,'observer':'电脑归档','evidence_type':'程序存储回执',
            'stage':stage,'event_ids':batch,**(extra or {})}
        receipt.append(validate_event(item))
    return receipt

def run_handoff(store, use_github=False, cloud=None, backup_func=None):
    """Injected cloud/backup_func are for isolated tests only; no file mutation outside private."""
    with process_lock(store.private/'.handoff.lock'):
        cfg=store.private/'cloud.local.json'; before=store.read()
        result={'started_at':now(),'cloud':'not_configured','github':{'status':'not_requested'},'warnings':[]}
        if cloud is None and (cfg.exists() or os.environ.get('GROWTH_CLOUD_URL')):
            cloud=Cloud(load_config(cfg))
        if cloud is not None:
            remote_result=sync_once(store,cloud)
            result['cloud']='confirmed';result['uploaded']=remote_result['uploaded']
        # Serialize with HTTP writes/cloud watcher. Never save a stale snapshot.
        with process_lock(store.private/'.growth.lock'):
            current=store.read();store._save_unlocked(current)
        before_ids={e['id'] for e in before['events']}
        result['new_observations']=sum(e['kind']=='observation' and e['id'] not in before_ids for e in current['events'])
        receipts=make_receipts(current,'local_markdown')
        if receipts: store.merge({'schema_version':2,'events':receipts})
        result['local_markdown']='confirmed'
        result['newly_archived_observations']=sum(e['kind']=='observation' and e['id'] in {i for r in receipts for i in r['event_ids']} for e in current['events'])
        if use_github:
            snapshot=store.read()
            outstanding=[e for e in snapshot['events'] if not is_receipt(e) and e['id'] not in acknowledged(snapshot,'github_private')]
            if outstanding:
                try:
                    result['github']=(backup_func or backup)(snapshot,store.private/'github.local.json')
                    if result['github'].get('status')!='confirmed': raise RuntimeError('未收到GitHub提交确认。')
                    github_receipts=make_receipts(snapshot,'github_private',{'commit':result['github']['commit']})
                    if github_receipts: store.merge({'schema_version':2,'events':github_receipts});receipts.extend(github_receipts)
                except Exception as exc:
                    result['github']={'status':'failed'};result['warnings'].append('本地已保存，但GitHub备份未确认：'+str(exc))
            else: result['github']={'status':'unchanged','message':'没有未备份的事实记录。'}
        if cloud is not None:
            # Retry ALL receipts, including any lost acknowledgement from an earlier run.
            all_receipts=[e for e in store.read()['events'] if is_receipt(e)]
            try:
                cloud.write(all_receipts)
                verified=cloud.read(); vm={e['id']:e for e in verified['events']}
                if any(vm.get(e['id'])!=e for e in all_receipts): raise RuntimeError('归档回执校验不符。')
                # Do not ingest new observations after marking this archive complete.
                # Those are fetched on the next click and must not be falsely acknowledged.
                result['receipt_cloud']='confirmed'
            except Exception:
                result['receipt_cloud']='pending';result['warnings'].append('本地归档完成，云端回执未确认；妈妈页面会暂时显示待归档，下次点击会重试。')
        else: result['receipt_cloud']='not_configured'
        result.update({'finished_at':now(),'markdown_dir':str(store.private/'generated'),
            'events':len(store.read()['events']), 'observations':sum(e['kind']=='observation' for e in store.read()['events'])})
        atomic_write(store.private/'sync-status.json',json.dumps(result,ensure_ascii=False,indent=2))
        return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',type=Path,default=ROOT/'private');p.add_argument('--github',action='store_true');args=p.parse_args()
    try: print(json.dumps(run_handoff(Store(args.data_dir),args.github),ensure_ascii=False,indent=2))
    except Exception as e: print('同步未完成；没有用远端覆盖本地：'+str(e));return 1
    return 0
if __name__=='__main__': raise SystemExit(main())
