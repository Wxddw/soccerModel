"""M79 Shadow R6.3.5 CLI. Research only; never alters M79.3.6 Production."""
import argparse, json
from pathlib import Path
from shadow_r635 import inspect, replay_recap13


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prematch', 'replay-recap13'])
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    src = json.loads(args.input.read_text(encoding='utf-8'))
    result = inspect(src) if args.mode == 'prematch' else replay_recap13(src)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print('wrote', args.output)


if __name__ == '__main__':
    main()
