import dataclasses
import enum
import re
from typing import Dict, List, Optional

MARKUP_PATTERN = re.compile(r"\[\[([^\[\]]*?)]]")
CHUNK_RE = re.compile(r"^\[(\d+)/(\d+)] chunk$")


# FIXME: migrate to enum.StrEnum in 3.11
class YaStatus(enum.Enum):
    OK = "OK"
    FAILED = "FAILED"
    NOT_LAUNCHED = "NOT_LAUNCHED"
    SKIPPED = "SKIPPED"
    DISCOVERED = "DISCOVERED"


class YaErrorType(enum.Enum):
    REGULAR = "REGULAR"
    TIMEOUT = "TIMEOUT"
    BROKEN_DEPS = "BROKEN_DEPS"
    FLAKY = "FLAKY"
    XFAILED = "XFAILED"
    XPASSED = "XPASSED"
    INTERNAL = "INTERNAL"


@dataclasses.dataclass
class UploadedFile:
    name: str
    url: str
    mime_type: str
    size: int

    def to_dict(self):
        return dataclasses.asdict(self)


def fix_links_paths(links):
    result = {}

    if not links:
        return result

    for k, files in links.items():
        result[k] = []
        for f in files:
            result[k].append(f.replace("build-release/", ""))
    return result


@dataclasses.dataclass
class YaTest:
    chunk_id: str
    name: str
    subtest_name: str
    path: str

    status: YaStatus
    error_type: str
    duration: float

    links: Optional[Dict[str, List[str]]] = None
    rich_snippet: Optional[str] = None
    source_code_url: str = None
    uploaded_links: List[UploadedFile] = dataclasses.field(default_factory=list)
    muted: bool = False

    @classmethod
    def parse_json(cls, data):
        status = YaStatus(data["status"])
        duration = data["duration"] or 0

        rich_snippet = data.get("rich-snippet")
        if rich_snippet:
            rich_snippet = MARKUP_PATTERN.sub("", rich_snippet).strip()

        return cls(
            data["chunk_id"],
            data["name"],
            data["subtest_name"],
            data["path"],
            status,
            data.get("error_type"),
            duration,
            fix_links_paths(data["links"]),
            rich_snippet,
        )

    @property
    def ok(self):
        return self.status == YaStatus.OK

    @property
    def failed(self):
        return self.status == YaStatus.FAILED

    @property
    def full_name(self):
        return f"{self.name}.{self.subtest_name}"

    def add_link_url(self, link: UploadedFile):
        self.uploaded_links.append(link)

    def mute(self):
        self.muted = True


class YaTestChunk:
    def __init__(
        self,
        suite_id: str,
        id_: str,
        name: str,
        subtest_name: str,
        path: str,
        status: YaStatus,
        logsdir_path: str,
    ):
        self.suite_id = suite_id
        self.id = id_
        self.name = name
        self.subtest_name = subtest_name
        self.path = path
        self.status = status
        self.logsdir_path = logsdir_path
        self.found_test = 0
        self.tests = []  # type: List[YaTest]
        self.logsdir_link = None  # type: Optional[UploadedFile]

    def __str__(self):
        return f'TestChunk path={self.path}\tname="{self.name} {self.subtest_name}"\tstatus={self.status}'

    @classmethod
    def parse_json(cls, data):
        status = YaStatus(data["status"])
        links = fix_links_paths(data.get("links"))
        logsdir_path = None

        if "logsdir" in links:
            logsdir_path = links["logsdir"][0]

        return cls(
            data["suite_id"],
            data["id"],
            data["name"],
            data["subtest_name"],
            data["path"],
            status,
            logsdir_path,
        )

    def add_test(self, test: YaTest):
        self.tests.append(test)
        self.found_test += 1

    def set_logsdir_link(self, link: UploadedFile):
        self.logsdir_link = link

    @property
    def fancy_chunk_name(self):
        if self.subtest_name == "solo chunk":
            return None

        if m := CHUNK_RE.match(self.subtest_name):
            return f"chunk-{m.group(1)}"


class YaTestSuite:
    def __init__(
        self, id_: str, path: str, status: YaStatus, error_type: Optional[YaErrorType]
    ):
        self.id = id_
        self.path = path
        self.status = status
        self.error_type = error_type
        self.chunks = []  # type: List[YaTestChunk]

    @classmethod
    def parse_json(cls, data):
        status = YaStatus(data["status"])

        error_type = None

        if "error_type" in data:
            error_type = YaErrorType(data["error_type"])

        return cls(data["id"], data["path"], status, error_type)

    def add_chunk(self, chunk: YaTestChunk):
        self.chunks.append(chunk)

    @property
    def test_count(self):
        tests = 0
        for chunk in self.chunks:
            tests += len(chunk.tests)
        return tests

    def iter_tests(self):
        for chunk in self.chunks:
            for test in chunk.tests:
                yield test

    def __str__(self):
        return f"TestSuite(path={self.path},status={self.status},tests={self.test_count},error_type={self.error_type})"


@dataclasses.dataclass
class YaBuild:
    path: str
    status: YaStatus
    error_type: Optional[YaErrorType] = None
    rich_snippet: Optional[str] = None
    muted: bool = False

    @property
    def name(self):
        return "BUILD"

    def mute(self):
        self.muted = True

    @property
    def failed(self):
        return self.status == YaStatus.FAILED

    @classmethod
    def parse_json(cls, data):
        status = YaStatus(data["status"])
        error_type = None

        if "error_type" in data:
            error_type = YaErrorType(data["error_type"])

        rich_snippet = data.get("rich-snippet")

        if rich_snippet:
            rich_snippet = MARKUP_PATTERN.sub("", rich_snippet).strip()

        return cls(data["path"], status, error_type, rich_snippet)
