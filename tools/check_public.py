"""Conservative publication guard; complements, does not replace, manual review."""
import re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
allowed={'index.html','config.js','time_age.js','observation_parser.js','development_reference.js','development_catalog.json','.nojekyll'}
errors=[]
for p in (ROOT/'web').rglob('*'):
    if not p.is_file():continue
    if p.name not in allowed:errors.append(f'Unexpected publish file: {p.name}')
    text=p.read_text('utf-8')
    for pat in [r'window\.PRIVATE_SEED\s*=',r'sb_secret_[A-Za-z0-9_\-]{10,}',r'gh[pousr]_[A-Za-z0-9_]{20,}',r'github_pat_[A-Za-z0-9_]{20,}',r'800\s*ml',r'20[–—-]30种动物',r'父母带睡妹妹']:
        if re.search(pat,text,re.I):errors.append(f'Sensitive payload/pattern detected: {p.name}')
try:
    names=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).splitlines()
    for name in names:
        if name.startswith('private/') or name.endswith('.zip') or '本地预览' in name:errors.append('Private file tracked: '+name)
except (subprocess.CalledProcessError,FileNotFoundError):pass
if errors:print('\n'.join(errors));sys.exit(1)
print('Publication guard passed: only template code, no seed payload detected.')
