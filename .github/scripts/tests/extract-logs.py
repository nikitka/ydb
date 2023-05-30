#!/usr/bin/env python3
import argparse
import io
import os
from pathlib import Path
from typing import List
from log_parser import ctest_log_parser, parse_yunit_fails, parse_gtest_fails, log_reader


def make_md_url(base, path, title=":floppy_disk:"):
    return f"[{title}]({base}{path})"


def make_filename(*parts):
    return f'{"-".join(parts)}.log'


def save_log(err_lines: List[str], out_path: Path, *parts):
    fn = make_filename(*parts)
    print(f"write {fn} for {'::'.join(parts)}")
    with open(out_path.joinpath(fn), "wt") as fp:
        for line in err_lines:
            fp.write(f"{line}\n")

    return fn


def extract_logs(log_fp: io.StringIO, out_path: Path, url_prefix):
    # FIXME: memory inefficient because new buffer created every time
    # FIXME: extract summary generation to additional function

    summary = [
        "| Test  | Status | Log |",
        "| ----: | :----: | --: |",
    ]

    urls = {}
    for target, reason, ctest_buf in ctest_log_parser(log_fp):
        first_line = ctest_buf[0]
        failed = 0

        fn = save_log(ctest_buf, out_path, target)
        log_url = make_md_url(url_prefix, fn)
        urls[(target, target)] = log_url
        summary.append(f"| **{target}** | {reason} | {log_url} |")

        # testcases = []
        if first_line.startswith("[==========]"):
            for classname, method, err in parse_gtest_fails(ctest_buf):
                fn = save_log(err, out_path, classname, method)
                log_url = make_md_url(url_prefix, fn)
                summary.append(f"| _{ classname }::{ method }_ | | {log_url}|")
                urls[(classname, method)] = log_url
                failed += 1
        elif first_line.startswith("<-----"):
            for classname, method, err in parse_yunit_fails(ctest_buf):
                fn = save_log(err, out_path, classname, method)
                log_url = make_md_url(url_prefix, fn)
                urls[(classname, method)] = log_url
                summary.append(f"| _{ classname }::{ method }_ | | {log_url}|")
                failed += 1
        else:
            pass

    return summary, urls


def write_summary(summary):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "at") as fp:
        fp.write(f"List of failed test logs:\n")
        for line in summary:
            fp.write(f"{line}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url-prefix", default="./")
    parser.add_argument("--patch-jsuite", default=False, action="store_true")
    parser.add_argument("--decompress", action="store_true", default=False, help="decompress ctest log")
    parser.add_argument("--write-summary", action="store_true", default=False, help="update github summary")
    parser.add_argument("ctest_log")
    parser.add_argument("out_log_dir")

    parser.add_argument("jsuite_paths", nargs="*")

    args = parser.parse_args()

    if args.patch_jsuite and not args.jsuite_paths:
        print("jsuite_paths are reqruired")
        raise SystemExit(-1)

    summary, urls = extract_logs(log_reader(args.ctest_log, args.decompress), Path(args.out_log_dir), args.url_prefix)

    if args.write_summary and urls:
        write_summary(summary)


if __name__ == "__main__":
    main()
