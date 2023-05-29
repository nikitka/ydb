#!/usr/bin/env python3
import argparse
import re


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


def ctest_log_parser(filename):
    start_re = re.compile(r"^\s+Start\s+\d+: ")
    status_re = re.compile(r"^\s*\d+/\d+ Test\s+#\d+: ([^ ]+) [.]+([^ ]+)")

    fp = open(filename, "rt")

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

            if not start_re.match(line) and not status_re.match(line):
                buf.append(line.rstrip())
            else:
                break

        if buf:
            yield target, reason, buf


def make_md_url(base, path, title=":floppy_disk:"):
    return f"[{title}]({base}{path})"


def make_filename(*parts):
    return f'{"-".join(parts)}.log'


def parse_log_debug(filename, out_path, base_url):
    # FIXME: memory inefficient because new buffer created every time

    total = 0
    summary = [
        "| Test  | Status | Log |",
        "| ----: | :----: | --: |",
    ]

    for target, reason, log in ctest_log_parser(filename):
        first_line = log[0]
        total += sum([len(l) for l in log])
        failed = 0

        testcases = []
        if first_line.startswith("[==========]"):
            for classname, method, err in parse_gtest_fails(log):
                failed += 1
                log_url = make_md_url(base_url, make_filename(classname, method))
                testcases.append(f"| _{ classname }::{ method }_ | | {log_url}|")
        elif first_line.startswith("<-----"):
            for classname, method, err in parse_yunit_fails(log):
                log_url = make_md_url(base_url, make_filename(classname, method))
                testcases.append(f"| _{ classname }::{ method }_ | | {log_url}|")
                failed += 1
        else:
            raise

        log_url = make_md_url(base_url, make_filename(target))
        summary.append(f"| **{target}** | {reason} | {log_url} |")
        summary.extend(testcases)

    print("\n".join(summary))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="./")
    parser.add_argument("log")
    parser.add_argument("out_path")
    args = parser.parse_args()
    parse_log_debug(args.log, args.out_path, args.base_url)


if __name__ == "__main__":
    main()
