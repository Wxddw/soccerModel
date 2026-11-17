"""Standalone R6.3.13 research CLI: JSON in, JSON out."""
import json
import sys
from pathlib import Path
import shadow_r6313
import candidate_models_r6313
import forward_validation_r6313 as validation


def main():
    if len(sys.argv)!=4 or sys.argv[1] not in ('prematch','candidate-grid','freeze','evaluate','evaluate-batch'):
        raise SystemExit('usage: python run_r6313.py prematch|candidate-grid|freeze|evaluate|evaluate-batch INPUT OUTPUT')
    mode=sys.argv[1];data=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    if mode=='prematch':out=shadow_r6313.inspect(data)
    elif mode=='candidate-grid':out=candidate_models_r6313.generate_grid(data)
    elif mode=='freeze':out=validation.freeze(data)
    elif mode=='evaluate':out=validation.evaluate(data['snapshot'],data['actual'])
    else:out=validation.summary([validation.evaluate(row['snapshot'],row['actual']) for row in data])
    Path(sys.argv[3]).write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('R6.3.13 '+mode+' -> '+sys.argv[3])
if __name__=='__main__':main()
