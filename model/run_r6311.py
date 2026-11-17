"""CLI: prematch|freeze|evaluate|evaluate-batch|recap-dev14 INPUT OUTPUT"""
import json
from pathlib import Path
import sys
from shadow_r6311 import inspect
from forward_validation_r6311 import freeze,evaluate,summary
from replay_conversation_r6311 import audit_dev14


def main():
    if len(sys.argv)!=4 or sys.argv[1] not in ('prematch','freeze','evaluate','evaluate-batch','recap-dev14'):
        raise SystemExit('usage: python run_r6311.py prematch|freeze|evaluate|evaluate-batch|recap-dev14 INPUT.json OUTPUT.json')
    op=sys.argv[1];data=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    if op=='prematch':out=inspect(data)
    elif op=='freeze':out=freeze(data)
    elif op=='evaluate':out=evaluate(data['snapshot'],data['actual'])
    elif op=='evaluate-batch':out=summary([evaluate(row['snapshot'],row['actual']) for row in data])
    else:out=audit_dev14(data)
    Path(sys.argv[3]).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'R6.3.11 {op} => {sys.argv[3]}')
if __name__=='__main__':main()
