"""Import a browser JSON export and mechanically refresh local Markdown."""
import argparse,json
from pathlib import Path
from core import Store
p=argparse.ArgumentParser(description=__doc__);p.add_argument('json_file',type=Path);p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[1]/'private');args=p.parse_args()
s=Store(args.data_dir);d=s.merge(json.loads(args.json_file.read_text('utf-8')));print(f'{len(d["events"])} records; Markdown: {s.private/"generated"}')
