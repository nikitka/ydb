import gzip
import re
import sys
from typing import TextIO


def log_reader(fn, decompress):
    if fn == "-":
        if decompress:
            return gzip.open(sys.stdin.buffer, "rt")
        return sys.stdin

    if decompress:
        return gzip.open(fn, "rt")

    return open(fn, "rt")


def parse_gtest_fails(log):
    ilog = iter(log)
    while 1:
        try:
            line = next(ilog)
        except StopIteration:
            break

        if line.startswith("[ RUN      ]"):
            buf = []
            while 1:
                try:
                    line = next(ilog)
                except StopIteration:
                    break

                if line.startswith("[  FAILED  ]"):
                    plen = len("[  FAILED  ] ")
                    classname, method = line[plen:].split(" ")[0].split(".", maxsplit=1)
                    yield classname, method, buf
                    break
                elif line.startswith("[       OK ]"):
                    break
                else:
                    buf.append(line)


def parse_yunit_fails(log):
    ilog = iter(log)
    while 1:
        try:
            line = next(ilog)
        except StopIteration:
            break

        if not line.startswith("[FAIL] "):
            continue

        class_method = line[7:].split(" -> ", maxsplit=1)[0]

        buf = [line]

        while 1:
            try:
                line = next(ilog)
            except StopIteration:
                break

            if line.startswith(("[exec] ", "-----> ")):
                break

            buf.append(line)

        cls, method = class_method.split("::")
        yield cls, method, buf


def ctest_log_parser(fp: TextIO):
    start_re = re.compile(r"^\s+Start\s+\d+: ")
    status_re = re.compile(r"^\s*\d+/\d+ Test\s+#\d+: ([^ ]+) [.]+([^ ]+)")
    finish_re = re.compile(r"\d+% tests passed")

    while 1:
        line = fp.readline()
        if not line:
            break

        if "***" not in line:
            continue

        m = status_re.match(line)

        if not m:
            continue

        target = m.group(1)
        reason = m.group(2).replace("*", "")

        buf = []

        while 1:
            line = fp.readline()
            if not line:
                break

            if not (start_re.match(line) or status_re.match(line) or finish_re.match(line)):
                buf.append(line.rstrip())
            else:
                break

        if buf:
            yield target, reason, buf
