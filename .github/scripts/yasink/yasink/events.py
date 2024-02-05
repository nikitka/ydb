import dataclasses
import enum
from typing import Optional, List, Dict, Literal

STATUS_OK = 1
STATUS_FAILED = 2
STATUS_NOT_LAUNCHED = 3


class TestStatus(enum.Enum):
    OK = 1
    FAILED = 2
    NOT_LAUNCHED = 3


@dataclasses.dataclass
class TestEvent:
    name: str
    subtest_name: str
    path: str

    status: str
    # noinspection PyTypeHints
    status: Literal[STATUS_OK, STATUS_FAILED, STATUS_NOT_LAUNCHED]

    links: Optional[Dict[str, List[str]]] = None
    rich_snippet: Optional[str] = None

    @classmethod
    def parse_ya(cls, line):
        status = getattr(TestStatus, line['status'])

        return cls(
            line['name'], line['subtest_name'], line['path'], status,
            line['links'], line.get('rich_snippet')
        )

    @property
    def ok(self):
        return self.status == TestStatus.OK
