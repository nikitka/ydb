#!/usr/bin/env python3
import argparse
from typing import TextIO

from log_parser import ctest_log_parser, log_reader
import xml.etree.ElementTree as ET


def mute_ctest(log_fp: TextIO, ctest_junit_report, ok_to_patch):
    timeout_targets = set()

    for target, reason, _ in ctest_log_parser(log_fp):
        if reason != "Failed":
            timeout_targets.add(target)

    cnt = 0
    total_time = 0
    tree = ET.parse(ctest_junit_report)
    root = tree.getroot()
    new_root = ET.Element("testsuite")

    for testcase in root.findall("testcase"):
        if testcase.attrib["classname"] in timeout_targets:
            new_root.append(testcase)
            cnt += 1
            total_time += float(testcase.attrib["time"])

    new_root.set("tests", str(cnt))
    new_root.set("failures", str(cnt))
    new_root.set("timestamp", root.attrib["timestamp"])
    new_root.set("time", str(int(total_time)))

    if ok_to_patch:
        print(f"update {ctest_junit_report}")
        ET.ElementTree(new_root).write(ctest_junit_report)
    else:
        print(f"(dry-run) update {ctest_junit_report}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", action="store_true", default=False)
    parser.add_argument("log", type=str)
    parser.add_argument("--decompress", action="store_true", default=False, help="decompress ctest log")
    parser.add_argument("ctest_junit_report")
    args = parser.parse_args()

    mute_ctest(log_reader(args.log, args.decompress), args.ctest_junit_report, args.patch)


if __name__ == "__main__":
    main()
