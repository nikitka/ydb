import logging
import re


def pattern_to_re(pattern):
    res = []
    for c in pattern:
        if c == "*":
            res.append(".*")
        else:
            res.append(re.escape(c))

    return f"(?:^{''.join(res)}$)"


class YaMuteCheck:
    def __init__(self):
        self.regexps = set()
        self.regexps = []
        self.logger = logging.getLogger(__name__)

    def load(self, fn):
        with open(fn, "r") as fp:
            for line in fp:
                line = line.strip()
                try:
                    path, full_name = line.split(" ", maxsplit=1)
                except ValueError:
                    self.logger.error(f"SKIP INVALID MUTE CONFIG LINE: {line!r}")
                    continue
                self.populate(path, full_name)

    def populate(self, path, full_name):
        check = []

        for p in (pattern_to_re(path), pattern_to_re(full_name)):
            try:
                check.append(re.compile(p))
            except re.error:
                self.logger.error(f"Unable to compile regex {p!r}")
                return

        self.regexps.append(tuple(check))

    def __call__(self, suite_name, test_name):
        for ps, pt in self.regexps:
            if ps.match(suite_name) and pt.match(test_name):
                return True
        return False
