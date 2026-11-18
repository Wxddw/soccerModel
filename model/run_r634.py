"""M79 Shadow R6.3.4 CLI. Run with pre-match inputs or the archived development packet."""
import argparse, json
from pathlib import Path
from motivation_squad_r634 import inspect, replay_development


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['prematch','replay-dev'])
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    src=json.loads(args.input.read_text(encoding='utf-8'))
    result=inspect(src) if args.mode=='prematch' else replay_development(src)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print('wrote',args.output)


if __name__=='__main__':main()
