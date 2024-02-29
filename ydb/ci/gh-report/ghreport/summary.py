import os
import enum
import logging
from io import BytesIO
import shutil
from pathlib import Path
from typing import Dict
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from .config import Config
from .sink import BaseSink
from .base import YaTestSuite, YaStatus, YaErrorType, YaTestType
from .utils import GzipCompressionWrapper

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates")

logger = logging.getLogger(__name__)


def render_pm(value, url=None, diff=None):
    if value and url:
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
        self.builds = {s: [] for s in SummaryStatus}
        self.tests = {s: [] for s in SummaryStatus}
        self.styles = {s: [] for s in SummaryStatus}
        self.cfg = cfg

    # def submit_build(self, build):
    #     status = SummaryStatus.ERROR if build.failed else SummaryStatus.PASS
    #     self.builds[status].append(build)

    def submit_suite(self, suite: YaTestSuite):
        if suite.type == YaTestType.STYLE:
            counter = self.styles
        else:
            counter = self.tests

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
                elif test.status in (YaStatus.SKIPPED, YaStatus.NOT_LAUNCHED):
                    status = SummaryStatus.SKIP
                else:
                    raise Exception("Unknown summary status for tests %s" % test)

            counter[status].append(test)

    def render_line(self, items):
        return f"| {' | '.join(items)} |"

    def render_counters(self, title, tests, report_url=None):
        def mk_url(suffix=""):
            if report_url:
                return f"{report_url}{suffix}"

        total_tests = sum(map(len, tests.values()))

        if not total_tests:
            return

        line = [
            title,
            render_pm(total_tests, mk_url()),
            render_pm(len(tests[SummaryStatus.PASS]), mk_url("#PASS")),
            render_pm(len(tests[SummaryStatus.ERROR]), mk_url("#ERROR")),
            render_pm(len(tests[SummaryStatus.FAIL]), mk_url("#FAIL")),
            render_pm(len(tests[SummaryStatus.SKIP]), mk_url("#SKIP")),
            render_pm(len(tests[SummaryStatus.MUTE]), mk_url("#MUTE")),
        ]
        return self.render_line(line)

    def render_badge(self, report_urls: Dict[str, str], add_footnote=False):
        footnote_url = f"{self.cfg.gh_repo}/tree/main/.github/config/muted_ya.txt"
        footnote = "[^1]" if add_footnote else f'<sup>[?]({footnote_url} "All mute rules are defined here")</sup>'

        columns = ["", "TESTS", "PASSED", "ERRORS", "FAILED", "SKIPPED", f"MUTED{footnote}"]

        headers = [
            self.render_line(columns),
            self.render_line(["---:"] * len(columns)),
        ]

        result = [
            self.render_counters("Style", self.styles, report_urls.get("styles")),
            self.render_counters("Test", self.tests, report_urls.get("tests")),
        ]
        if not any(result):
            return []

        result = headers + [r for r in result if r is not None]

        if add_footnote:
            result.append("")
            result.append(f"[^1]: All mute rules are defined [here]({footnote_url}).")
        return result

    def generate_reports(self):
        return {
            # 'builds': self._generate_report(self.builds, StringIO()),
            "styles": self._generate_report(self.styles),
            "tests": self._generate_report(self.tests),
        }

    def _generate_report(self, tests):
        env = Environment(loader=FileSystemLoader(TEMPLATES_PATH), undefined=StrictUndefined)

        status_order = [
            SummaryStatus.ERROR,
            SummaryStatus.FAIL,
            SummaryStatus.SKIP,
            SummaryStatus.MUTE,
            SummaryStatus.PASS,
        ]

        status_order = [s for s in status_order if s in tests]

        content = env.get_template("summary.html").render(status_order=status_order, tests=tests)

        fp = BytesIO()

        fp.write(content.encode('utf8'))
        fp.seek(0)
        return fp

    def upload_to_s3(self, s3_client, reports):
        urls = {}
        folder = "summary"

        extra_args = {
            "ACL": "public-read",
            "ContentType": "text/html",
            "ContentEncoding": "gzip",
        }

        for report_type, report in reports.items():
            urls[report_type] = f"{self.cfg.s3_url_prefix}/{folder}/{report_type}.html"
            with GzipCompressionWrapper(report) as zfp:
                logger.info("upload %s to %s", report_type, urls[report_type])
                s3_client.upload_fileobj(
                    zfp,
                    self.cfg.s3_bucket,
                    self.cfg.s3_bucket.join(f"{folder}/{report_type}.html"),
                    ExtraArgs=extra_args,
                )
        return urls

    def save_reports(self, reports, folder, prefix):
        urls = {}
        for report_type, report in reports.items():
            urls[report_type] = f"{prefix}/reports/{report_type}.html"
            fn = Path(folder).joinpath(f"{report_type}.html")
            with open(fn, "wb") as fp:
                shutil.copyfileobj(report, fp)
        return urls
