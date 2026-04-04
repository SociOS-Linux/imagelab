import json
import sys
from pathlib import Path

EXPECTED_TYPE = 'ExecutionDecision'


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: python -m validators.execution_decision <json-file>', file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('type') != EXPECTED_TYPE:
        print(f'expected type={EXPECTED_TYPE!r}, got {data.get("type")!r}', file=sys.stderr)
        return 1
    print(json.dumps({'ok': True, 'validated': EXPECTED_TYPE, 'path': str(path)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
