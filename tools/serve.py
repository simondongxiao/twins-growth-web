"""Local loopback service: saves HTML observations to private JSON and Markdown."""
from __future__ import annotations
import argparse, json, secrets, sys, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from core import Store, validate_doc
from handoff import run_handoff
ROOT=Path(__file__).resolve().parents[1]

def make_server(private:Path, port:int=8765, open_browser=False):
    store=Store(private); token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass  # Do not log private observations.
        def reply(self,status,body,content_type='application/json; charset=utf-8'):
            data=body.encode('utf-8') if isinstance(body,str) else body
            self.send_response(status); self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
        def allowed(self):
            allowed={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
            return self.headers.get('Host') in allowed and self.headers.get('Sec-Fetch-Site')!='cross-site'
        def do_GET(self):
            if not self.allowed(): return self.reply(403,'{"error":"只允许本机访问"}')
            p=urlsplit(self.path).path
            if p=='/api/state': return self.reply(200,json.dumps(store.read(),ensure_ascii=False))
            if p=='/api/status':
                last=private/'sync-status.json'
                return self.reply(200,json.dumps({'mode':'local','markdown_dir':str(private/'generated'),
                    'cloud_configured':(private/'cloud.local.json').exists(),
                    'github_configured':(private/'github.local.json').exists(),
                    'last_sync':json.loads(last.read_text('utf-8')) if last.exists() else None},ensure_ascii=False))
            if p in ('/','/index.html'):
                html=(ROOT/'web/index.html').read_text('utf-8')
                html=html.replace('/*LOCAL_CONFIG*/', 'window.LOCAL_CONFIG='+json.dumps({'token':token})+';')
                return self.reply(200,html,'text/html; charset=utf-8')
            if p in ('/config.js','/time_age.js','/observation_parser.js','/development_reference.js'):
                path=ROOT/'web'/p[1:]
                return self.reply(200,path.read_text('utf-8'),'text/javascript; charset=utf-8')
            return self.reply(404,'{"error":"不存在"}')
        def do_POST(self):
            try:
                if not self.allowed() or self.headers.get('X-Growth-Token')!=token: return self.reply(403,'{"error":"本地授权无效，请重新打开本地页"}')
                origin=self.headers.get('Origin')
                if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}: return self.reply(403,'{"error":"来源不允许"}')
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8_000_000: return self.reply(413,'{"error":"文件为空或超过8MB"}')
                obj=json.loads(self.rfile.read(size))
                if self.path=='/api/sync-save':
                    result=run_handoff(store,use_github=obj.get('github') is True)
                    return self.reply(200,json.dumps({'ok':True,'result':result,'state':store.read()},ensure_ascii=False))
                if self.path=='/api/event': doc=store.append(obj)
                elif self.path=='/api/import': doc=store.merge(obj)
                else: return self.reply(404,'{"error":"不存在"}')
                self.reply(200,json.dumps({'ok':True,'state':doc,'markdown_dir':str(private/'generated')},ensure_ascii=False))
            except Exception as exc:
                self.reply(400,json.dumps({'error':str(exc)},ensure_ascii=False))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    return server

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765);parser.add_argument('--data-dir',type=Path,default=ROOT/'private');parser.add_argument('--no-open',action='store_true')
    args=parser.parse_args()
    server=make_server(args.data_dir,args.port)
    url=f'http://127.0.0.1:{server.server_port}/'
    print(f'HTML: {url}\nMarkdown: {args.data_dir / "generated"}\n只监听本机；窗口关闭后停止回填。')
    if not args.no_open: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: print('\n已停止。')
    finally: server.server_close()
if __name__=='__main__': main()
