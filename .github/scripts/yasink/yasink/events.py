import dataclasses

@dataclasses.dataclass
class TestEvent:
    name: str
    subtest_name: str
    path: str

    status: str


    @property
    def ok(self):
        return self.status == 'OK'
