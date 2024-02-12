import argparse
import base64
import dataclasses
import hashlib
import html
import logging
from typing import Dict, List, Literal, Optional

import requests
from tenacity import (retry, retry_if_exception_type, stop_after_attempt,
                      wait_exponential)

from .base import YaBuild, YaStatus, YaTest, YaTestSuite
from .config import Config
from .sink import BaseSink
from .utils import chunks

FIELD_STRING = 1
FIELD_PLAIN_TEXT = 2
FIELD_HTML = 3
FIELD_MONOSPACED = 4
FIELD_URL = 5


status_map = {
    YaStatus.OK: "passed",
    YaStatus.FAILED: "failed",
    YaStatus.NOT_LAUNCHED: "untested",
    YaStatus.SKIPPED: "skip",
}

logger = logging.getLogger(__name__)


def serialize_build(build: YaBuild):
    key = hashlib.md5(f"build-{build.path}".encode("utf8")).hexdigest()

    if build.failed and build.muted:
        # FIXME: change to mute
        status = "skipped"
    else:
        # FIXME: add other statuses support
        status = status_map[build.status]

    output = f'<pre class="code-block">{html.escape(build.rich_snippet)}</pre>'

    fields = [{"type": FIELD_HTML, "name": "Output", "value": output.strip()}]

    name = "BUILD"

    return {
        "key": key,
        "status": status,
        "folder": build.path,
        "name": name,
        "fields": fields,
        "elapsed": 0,
    }


def serialize_test(test: YaTest, key=None):
    if key is None:
        # FIXME: what about style and build tests ?
        key = hashlib.md5(
            f"{test.path}{test.name}{test.subtest_name}".encode("utf8")
        ).hexdigest()

    if test.failed and test.muted:
        # FIXME: change to mute
        status = "skipped"
    else:
        # FIXME: add other statuses support
        status = status_map[test.status]

    fields = [
        {
            "type": FIELD_URL,
            "name": "Code",
            "value": test.source_code_url,
        },
    ]

    if test.rich_snippet:
        output = f"""
<pre class="code-block">
{html.escape(test.rich_snippet)}
</pre>
"""
        fields.append({"type": FIELD_HTML, "name": "Output", "value": output.strip()})

    artifacts = []

    for link_data in test.uploaded_links:
        artifacts.append(link_data.to_dict())

    return {
        "key": key,
        "status": status,
        "folder": test.path,
        "name": test.full_name,
        "fields": fields,
        "artifacts": artifacts,
        "elapsed": int(test.duration * 1000000 // 1),
    }


class TestmoException(Exception):
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content

    def __str__(self):
        return f"{self.status_code}: {self.content}"


@dataclasses.dataclass
class TestmoLink:
    name: str
    url: str
    note: Optional[str] = None

    def to_dict(self):
        result = {"name": self.name, "url": self.url}
        if self.note is not None:
            result["note"] = self.note
        return result

    @staticmethod
    def argparse_action():
        class Action(argparse.Action):
            def __call__(self, parser, args, values, option_string=None):
                if len(values) not in (2, 3):
                    raise argparse.ArgumentTypeError("Invalid link: %r" % values)

                items = getattr(args, self.dest, None)
                # noinspection PyUnresolvedReferences,PyProtectedMember
                items = argparse._copy_items(items)
                items.append(TestmoLink(*values))
                setattr(args, self.dest, items)

        return Action


@dataclasses.dataclass
class TestmoField:
    name: str
    type: str
    value: str

    def to_dict(self):
        return {"name": self.name, "type": self.type, "value": self.value}

    @staticmethod
    def argparse_action():
        type_map = {
            "string": 1,
            "html": 3,
            "text": 2,
            "console": 4,
            "url": 5,
        }

        class Action(argparse.Action):
            def __call__(self, parser, args, values, option_string=None):
                if len(values) != 3:
                    raise argparse.ArgumentTypeError("Invalid field: %r" % values)

                name, type_, value = values
                if type_ not in type_map:
                    raise argparse.ArgumentTypeError("Invalid field type %r" % type_)

                items = getattr(args, self.dest, None)
                # noinspection PyUnresolvedReferences,PyProtectedMember
                items = argparse._copy_items(items)
                items.append(TestmoField(name, type_map[type_], value))
                setattr(args, self.dest, items)

        return Action


class TestmoBase:
    def __init__(self, client):
        self.client = client


class TestmoThread(TestmoBase):
    def __init__(self, client, run, thread_id: int):
        super().__init__(client)
        self.run = run
        self.thread_id = thread_id

    def append(self, tests: List[Dict[any, any]], **kwargs):
        data = {"tests": tests, **kwargs}
        return self.client.post(
            f"automation/runs/threads/{self.thread_id}/append", data
        )

    def complete(self):
        return self.client.post(f"automation/runs/threads/{self.thread_id}/complete")

    @property
    def url(self):
        fvalue = (
            b'{"mode":1,"conditions":{"automation_run_tests:thread_id":{"values":[%d]}}}'
            % self.thread_id
        )
        fvalue = base64.urlsafe_b64encode(fvalue).rstrip(b"=").decode()
        return f"{self.client.instance}/automation/runs/results/{self.run.run_id}?filter={fvalue}"


class TestmoRun(TestmoBase):
    def __init__(self, client, run_id: int):
        super().__init__(client)
        self.run_id = run_id

    def new_thread(
        self,
        fields: Optional[List[TestmoField]] = None,
        links: Optional[List[TestmoLink]] = None,
        **kwargs,
    ) -> TestmoThread:
        data = {}

        if fields:
            data["fields"] = [f.to_dict() for f in fields]

        if links:
            data["links"] = [f.to_dict() for f in links]

        data.update(kwargs)
        response = self.client.post(f"automation/runs/{self.run_id}/threads", data=data)
        return TestmoThread(self.client, self, response["id"])

    def complete(self):
        return self.client.post(f"automation/runs/{self.run_id}/complete")

    @property
    def url(self):
        return f"{self.client.instance}/automation/runs/view/{self.run_id}"


class TestmoClient:
    def __init__(self, instance: str, project_id: str, token: str):
        self.instance = instance
        self.project_id = project_id
        self.session = requests.Session()
        self.session.headers = {"Authorization": f"Bearer {token}"}

    @classmethod
    def configure(cls, cfg: Config):
        return TestmoClient(cfg.testmo_instance, cfg.testmo_project, cfg.testmo_token)

    @retry(
        retry=retry_if_exception_type(requests.ConnectionError),
        wait=wait_exponential(multiplier=0.1, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def request(self, http_method: Literal["get", "post", "put"], api_method, data):
        url = f"{self.instance}/api/v1/{api_method}"

        response = getattr(self.session, http_method)(
            url, json=data
        )  # type: requests.Response

        if not response.ok:
            import json
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w+t", delete=False) as fp:
                logger.info("save request to %s", fp.name)
                json.dump(data, fp)
            raise TestmoException(response.status_code, response.text)

        if response.status_code != 204:
            return response.json()

    def post(self, api_method, data=None):
        return self.request("post", api_method, data or {})

    def get(self, api_method):
        return self.request("get", api_method, data=None)

    def start_run(
        self,
        name: str,
        source: str,
        tags: List[str],
        fields: Optional[List[TestmoField]] = None,
        links: Optional[List[TestmoLink]] = None,
        **kwargs,
    ) -> TestmoRun:
        data = {"name": name, "source": source, "tags": tags, **kwargs}

        if fields:
            data["fields"] = [f.to_dict() for f in fields]

        if links:
            data["links"] = [f.to_dict() for f in links]
        response = self.post(f"projects/{self.project_id}/automation/runs", data)
        return TestmoRun(self, response["id"])


class TestmoSink(BaseSink):
    def __init__(self, thread: TestmoThread):
        self.thread = thread
        self.queue = []

    def flush(self, force=False):
        if force or len(self.queue) >= 250:
            for chunk in chunks(self.queue, 250):
                logger.info("testmo: send %s tests", len(chunk))
                self.thread.append(chunk)
            self.queue = []

    def enqueue(self, data: Dict[any, any]):
        self.queue.append(data)

    def submit_suite(self, suite: YaTestSuite):
        for test in suite.iter_tests():
            self.enqueue(serialize_test(test))
        self.flush()

    def submit_build(self, build: YaBuild):
        self.enqueue(serialize_build(build))
        self.flush()

    def finish(self):
        self.thread.complete()
