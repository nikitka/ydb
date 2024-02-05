import hashlib
import requests
from typing import List, Literal
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt
from .events import TestEvent


def serialize_test(test: TestEvent):
    # FIXME: what about style tests ?
    key = hashlib.md5(f"{test.path}{test.name}{test.subtest_name}".encode("utf8")).hexdigest()

    # FIXME: add other statuses support
    status = "passed" if test.ok else "failed"

    return {
        "key": key,
        "status": status,
        "folder": test.path,
        "name": f"{test.name}.{test.subtest_name}"
    }


class TestmoBase:
    def __init__(self, client):
        self.client = client


class TestmoThread(TestmoBase):
    def __init__(self, client, thread_id: int):
        super().__init__(client)
        self.thread_id = thread_id

    def append_tests(self, tests: List[TestEvent]):
        data = {"tests": [serialize_test(test) for test in tests]}
        return self.client.post(f"automation/runs/threads/{self.thread_id}/append", data)

    def complete(self):
        return self.client.post(f"automation/runs/threads/{self.thread_id}/complete")


class TestmoRun(TestmoBase):
    def __init__(self, client, run_id: int):
        super().__init__(client)
        self.run_id = run_id

    def new_thread(self) -> TestmoThread:
        response = self.client.post(f"automation/runs/{self.run_id}/threads")
        return TestmoThread(self.client, response["id"])

    def complete(self):
        return self.client.post(f"automation/runs/{self.run_id}/complete")


class TestmoClient:
    def __init__(self, instance: str, project_id: int, token: str):
        self.instance = instance
        self.project_id = project_id
        self.session = requests.Session()
        self.session.headers = {"Authorization": f"Bearer {token}"}

    @retry(
        retry=retry_if_exception_type(requests.ConnectionError),
        wait=wait_exponential(multiplier=0.1, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def request(self, http_method: Literal["get", "post", "put"], api_method, data):
        print(api_method, data)
        url = f"{self.instance}/api/v1/{api_method}"
        response = getattr(self.session, http_method)(url, json=data)  # type: requests.Response

        if not response.ok:
            print(response.content)
            response.raise_for_status()

        if response.status_code != 204:
            return response.json()

    def post(self, api_method, data=None):
        return self.request("post", api_method, data or {})

    def get(self, api_method):
        return self.request("get", api_method, data=None)

    def start_run(self, name: str, source: str, tags: List[str], **kwargs) -> TestmoRun:
        data = {"name": name, "source": source, "tags": tags, **kwargs}
        response = self.post(f"projects/{self.project_id}/automation/runs", data)
        return TestmoRun(self, response["id"])
