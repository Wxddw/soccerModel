import json,sys
from pathlib import Path
from shadow_r637 import inspect,replay_conversation_recap25

def main():
    if len(sys.argv)!=4 or sys.argv[1] not in ('prematch','replay-recap25'):
        raise SystemExit('Usage: python run_r637.py prematch INPUT.json OUTPUT.json | replay-recap25 INPUT.json OUTPUT.json')
    mode,src,dst=sys.argv[1:]
    data=json.loads(Path(src).read_text(encoding='utf-8'))
    out=inspect(data) if mode=='prematch' else replay_conversation_recap25(data)
    Path(dst).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{mode}: wrote {dst}')
if __name__=='__main__': main()
