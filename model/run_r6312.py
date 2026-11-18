"""R6.3.12: prematch | freeze | evaluate | evaluate-batch INPUT OUTPUT"""
import json
import sys
from pathlib import Path
from shadow_r6312 import inspect
from forward_validation_r6312 import freeze, evaluate, summary


def main():
    if len(sys.argv)!=4 or sys.argv[1] not in ('prematch','freeze','evaluate','evaluate-batch'):
        raise SystemExit('usage: python run_r6312.py prematch|freeze|evaluate|evaluate-batch INPUT.json OUTPUT.json')
    op=sys.argv[1]
    inp=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    if op=='prematch':out=inspect(inp)
    elif op=='freeze':out=freeze(inp)
    elif op=='evaluate':out=evaluate(inp['snapshot'],inp['actual'])
    else:out=summary([evaluate(i['snapshot'],i['actual']) for i in inp])
    Path(sys.argv[3]).write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(f'R6.3.12 {op} -> {sys.argv[3]}')
if __name__=='__main__':main()
