import orjson
from .events import TestEvent


def parse_line(data: str):
    data = orjson.loads(data)
    if data['type'] == 'test':
        if 'suite' in data or 'chunk' in data:
            return
        return TestEvent.parse_ya(data)

    return None
