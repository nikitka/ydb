import enum
from .config import Config
from .sink import BaseSink
from .base import YaTestSuite, YaStatus, YaErrorType


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
    PASSED = enum.auto()
    FAILED = enum.auto()
    ERRORS = enum.auto()
    SKIPPED = enum.auto()
    MUTED = enum.auto()


class SummarySink(BaseSink):
    def __init__(self, cfg: Config):
        self.counter = {s: 0 for s in SummaryStatus}
        self.cfg = cfg

    def submit_suite(self, suite: YaTestSuite):
        for test in suite.iter_tests():
            if test.failed:
                if test.muted:
                    status = SummaryStatus.MUTED
                else:
                    if test.error_type == YaErrorType.REGULAR:
                        status = SummaryStatus.FAILED
                    else:
                        status = SummaryStatus.ERRORS
            else:
                if test.status == YaStatus.OK:
                    status = SummaryStatus.PASSED
                elif test.status in (YaStatus.SKIPPED, YaStatus.NOT_LAUNCHED):
                    status = SummaryStatus.SKIPPED
                else:
                    raise Exception("Unknown summary status for tests %s" % test)

            self.counter[status] += 1

    def render_line(self, items):
        return f"| {' | '.join(items)} |"

    def generate_report(self):
        pass

    def render(self, report_url: str, add_footnote=False):
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
            render_pm(self.counter[SummaryStatus.PASSED], f"{report_url}#PASS", 0),
            render_pm(self.counter[SummaryStatus.ERRORS], f"{report_url}#ERROR", 0),
            render_pm(self.counter[SummaryStatus.FAILED], f"{report_url}#FAIL", 0),
            render_pm(self.counter[SummaryStatus.SKIPPED], f"{report_url}#SKIP", 0),
            render_pm(self.counter[SummaryStatus.MUTED], f"{report_url}#MUTE", 0),
        ])
        result.append(self.render_line(row))

        if add_footnote:
            result.append("")
            result.append(f"[^1]: All mute rules are defined [here]({footnote_url}).")
        return result

