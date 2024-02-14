import os
import enum
from .config import Config
from .sink import BaseSink
from .base import YaTestSuite, YaStatus, YaErrorType
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates")


def render_pm(value, url, diff=None):
    if value:
        text = f"[{value}]({url})"
    else:
        text = str(value)

    if diff is not None and diff != 0:
        if diff == 0:
            sign = "±"
        elif diff < 0:
            sign = "-"
        else:
            sign = "+"

        text = f"{text} {sign}{abs(diff)}"

    return text


class SummaryStatus(enum.Enum):
    PASS = enum.auto()
    FAIL = enum.auto()
    ERROR = enum.auto()
    SKIP = enum.auto()
    MUTE = enum.auto()


class SummarySink(BaseSink):
    def __init__(self, cfg: Config):
        self.counter = {s: 0 for s in SummaryStatus}
        self.cfg = cfg

    def submit_suite(self, suite: YaTestSuite):
        for test in suite.iter_tests():
            if test.failed:
                if test.muted:
                    status = SummaryStatus.MUTE
                else:
                    if test.error_type == YaErrorType.REGULAR:
                        status = SummaryStatus.ERROR
                    else:
                        status = SummaryStatus.FAIL
            else:
                if test.status == YaStatus.OK:
                    status = SummaryStatus.PASS
                elif test.status in (YaStatus.SKIP, YaStatus.NOT_LAUNCHED):
                    status = SummaryStatus.SKIP
                else:
                    raise Exception("Unknown summary status for tests %s" % test)

            self.counter[status] += 1

    def render_line(self, items):
        return f"| {' | '.join(items)} |"

    def generate_report(self, path, prefix):
        env = Environment(loader=FileSystemLoader(TEMPLATES_PATH), undefined=StrictUndefined)

        status_test = {}
        has_any_log = set()

        for t in rows:
            status_test.setdefault(t.status, []).append(t)
            if any(t.log_urls.values()):
                has_any_log.add(t.status)

        for status in status_test.keys():
            status_test[status].sort(key=attrgetter("full_name"))

        status_order = [SummaryStatus.ERROR, SummaryStatus.FAIL, SummaryStatus.SKIP, SummaryStatus.MUTE, SummaryStatus.PASS]

        # remove status group without tests
        status_order = [s for s in status_order if s in status_test]

        content = env.get_template("summary.html").render(
            status_order=status_order, tests=status_test, has_any_log=has_any_log
        )

        with open(path, "w") as fp:
            fp.write(content)

    def render_badge(self, report_url: str, add_footnote=False):
        footnote_url = f"{self.cfg.gh_repo}/tree/main/.github/config/muted_ya.txt"
        footnote = "[^1]" if add_footnote else f'<sup>[?]({footnote_url} "All mute rules are defined here")</sup>'

        columns = [
            "TESTS", "PASSED", "ERRORS", "FAILED", "SKIPPED", f"MUTED{footnote}"
        ]

        result = [
            self.render_line(columns),
            self.render_line(['---:'] * len(columns))
        ]

        row = []

        row.extend([
            render_pm(sum(self.counter.values()), f"{report_url}", 0),
            render_pm(self.counter[SummaryStatus.PASS], f"{report_url}#PASS", 0),
            render_pm(self.counter[SummaryStatus.ERROR], f"{report_url}#ERROR", 0),
            render_pm(self.counter[SummaryStatus.FAIL], f"{report_url}#FAIL", 0),
            render_pm(self.counter[SummaryStatus.SKIP], f"{report_url}#SKIP", 0),
            render_pm(self.counter[SummaryStatus.MUTE], f"{report_url}#MUTE", 0),
        ])
        result.append(self.render_line(row))

        if add_footnote:
            result.append("")
            result.append(f"[^1]: All mute rules are defined [here]({footnote_url}).")
        return result

