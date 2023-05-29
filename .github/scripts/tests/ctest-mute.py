#!/usr/bin/env python3
import argparse
import glob
import os
from log_parser import ctest_log_parser
import xml.etree.ElementTree as ET


def mute_ctest(log_fn, junit_root, ok_to_patch):
    timeout_targets = set()

    for target, reason, _ in ctest_log_parser(log_fn):
        if reason == "Timeout":
            timeout_targets.add(target)

    for fn in glob.glob(os.path.join(junit_root, "*.xml")):
        cnt = 0
        total_time = 0
        tree = ET.parse(fn)
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
            print(f"update {fn}")
            ET.ElementTree(new_root).write(fn)
        else:
            print(f"(dry-run) update {fn}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch", action="store_true", default=False)
    parser.add_argument("log")
    parser.add_argument("jsuite_root")
    args = parser.parse_args()

    mute_ctest(args.log, args.jsuite_root, args.patch)


if __name__ == "__main__":
    main()
