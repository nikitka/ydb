#!/usr/bin/env python3
import os
import glob
import argparse
import xml.etree.ElementTree as ET
from mute_utils import mute_target, update_suite_info


def parse_muted_list(fn):
    classes = set()
    methods = set()
    with open(fn, "r") as fp:
        for line in fp:
            if line.startswith("-"):
                line = line[1:].rstrip()
                if "::" in line:
                    cls, method = line.split("::", maxsplit=1)
                    methods.add((cls, method))
                else:
                    classes.add(line)
    return classes, methods


def case_iterator(root):
    for case in root.findall("testcase"):
        cls, method = case.attrib["classname"], case.attrib["name"]
        yield case, cls, method


def mute_junit(muted, folder, dry_run):
    muted_cls, muted_methods = muted

    for fn in glob.glob(os.path.join(folder, "*.xml")):
        tree = ET.parse(fn)
        root = tree.getroot()
        total_muted = 0
        for suite in root.findall("testsuite"):
            muted_cnt = 0
            for case, cls, method in case_iterator(suite):
                if cls in muted_cls or (cls, method) in muted_methods:
                    if mute_target(case):
                        muted_cnt += 1

            if muted_cnt:
                update_suite_info(suite, n_skipped=muted_cnt, n_remove_failures=muted_cnt)
                total_muted += muted_cnt

        if total_muted:
            update_suite_info(root, n_skipped=total_muted, n_remove_failures=total_muted)

            print(f"{'(dry-run) ' if dry_run else ''}patch {fn}")

            if not dry_run:
                tree.write(fn, xml_declaration=True, encoding="UTF-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter-file", required=True)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("yunit_path")
    args = parser.parse_args()

    if not os.path.isdir(args.yunit_path):
        print(f"{args.yunit_path} is not a directory, exit")
        raise SystemExit(-1)

    # FIXME: add gtest filter file ?
    muted = parse_muted_list(args.filter_file)

    if not any(muted):
        print("nothing to mute")
        return

    mute_junit(muted, args.yunit_path, args.dry_run)


if __name__ == "__main__":
    main()
