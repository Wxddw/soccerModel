"""Research-only R6.3.8 JSON CLI: python run_r638.py prematch INPUT.json OUTPUT.json"""
import json
import sys
from pathlib import Path
from shadow_r638 import inspect


def main():
    if len(sys.argv)!=4 or sys.argv[1]!="prematch":
        raise SystemExit("usage: python run_r638.py prematch PREMATCH.json SHADOW_OUTPUT.json")
    inp=Path(sys.argv[2]); outp=Path(sys.argv[3])
    with inp.open(encoding="utf-8") as f: packet=json.load(f)
    result=inspect(packet)
    outp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Shadow R6.3.8 research audit ->",outp)


if __name__=="__main__": main()
