"""Usage: python run_r6310.py prematch PREMATCH.json OUT.json
          python run_r6310.py recap-chat RECAP_11_JSON OUT.json
"""
import json
import sys
from pathlib import Path
from shadow_r6310 import inspect
from replay_conversation_r6310 import audit_recap

if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] not in ('prematch', 'recap-chat'):
        raise SystemExit('usage: python run_r6310.py prematch|recap-chat INPUT.json OUTPUT.json')
    data = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
    out = inspect(data) if sys.argv[1] == 'prematch' else audit_recap(data)
    Path(sys.argv[3]).write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Shadow R6.3.10 {sys.argv[1]} completed -> {sys.argv[3]}')
