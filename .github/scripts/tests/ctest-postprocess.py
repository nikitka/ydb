#!/usr/bin/env python3
import argparse
from typing import TextIO
import xml.etree.ElementTree as ET

from log_parser import ctest_log_parser, log_reader
from mute_utils import mute_target, update_suite_info


def find_targets_to_remove(log_fp):
    return {target for target, reason, _ in ctest_log_parser(log_fp) if reason == "Failed"}


def postprocess_ctest(log_fp: TextIO, ctest_junit_report, mute_list, dry_run):
    to_remove = find_targets_to_remove(log_fp)

    tree = ET.parse(ctest_junit_report)
    root = tree.getroot()
    n_removed = n_removed_time = n_remove_failures = n_skipped = 0

    for testcase in root.findall("testcase"):
        target = testcase.attrib["classname"]

        if target in mute_list:
            if mute_target(testcase):
                testcase.set("status", "run")  # CTEST specific
                n_remove_failures += 1
                n_skipped += 1
        elif target in to_remove:
            n_removed_time += float(testcase.attrib["time"])
            n_removed += 1
            n_remove_failures += 1
            root.remove(testcase)

    if n_removed or n_skipped:
        update_suite_info(root, n_removed, n_remove_failures, n_skipped, n_removed_time)

        print(f"{'(dry-run) ' if dry_run else ''}update {ctest_junit_report} ({n_skipped}/{n_removed} skipped/removed)")

        if not dry_run:
            tree.write(ctest_junit_report, xml_declaration=True, encoding="UTF-8")
    else:
        print("nothing to remove")


def get_mute_list(mute_fn):
    muted = set()
    with open(mute_fn, "rt") as fp:
        for line in fp:
            target = line.strip()
            if target:
                muted.add(target)

    return muted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--filter-file", required=True)
    parser.add_argument("--decompress", action="store_true", default=False, help="decompress ctest log")
    parser.add_argument("ctest_log", type=str)
    parser.add_argument("ctest_junit_report")
    args = parser.parse_args()

    log = log_reader(args.ctest_log, args.decompress)
    mute_list = get_mute_list(args.filter_file)
    postprocess_ctest(log, args.ctest_junit_report, mute_list, args.dry_run)


if __name__ == "__main__":
    main()
