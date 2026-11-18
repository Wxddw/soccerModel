"""CLI: python run_r639.py prematch PREMATCH.json OUTPUT.json
     python run_r639.py replay-conversation RECAP.json AUDIT.json
"""
import json
import sys
from pathlib import Path
from shadow_r639 import inspect
from replay_conversation_r639 import audit_recap


def main():
    if len(sys.argv)!=4 or sys.argv[1] not in ("prematch","replay-conversation"):
        raise SystemExit("usage: python run_r639.py prematch|replay-conversation INPUT.json OUTPUT.json")
    p=Path(sys.argv[2]); out=Path(sys.argv[3])
    raw=json.loads(p.read_text(encoding="utf-8"))
    result=inspect(raw) if sys.argv[1]=="prematch" else audit_recap(raw)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    print(f"Shadow R6.3.9 {sys.argv[1]} -> {out}")

if __name__=="__main__": main()
