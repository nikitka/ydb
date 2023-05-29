#!/usr/bin/env python3
import argparse
import io
from pathlib import Path
from typing import List
from log_parser import ctest_log_parser, parse_yunit_fails, parse_gtest_fails


def make_md_url(base, path, title=":floppy_disk:"):
    return f"[{title}]({base}{path})"


def make_filename(*parts):
    return f'{"-".join(parts)}.log'


def save_log(err: List[str], out_path: Path, *parts):
    fn = make_filename(*parts)

    with open(out_path.joinpath(fn), "wt") as fp:
        for line in err:
            fp.write(line)

    return fn


def extract_logs(log_fp: io.StringIO, out_path: Path, url_prefix):
    # FIXME: memory inefficient because new buffer created every time

    summary = [
        "| Test  | Status | Log |",
        "| ----: | :----: | --: |",
    ]

    for target, reason, ctest_buf in ctest_log_parser(log_fp):
        first_line = ctest_buf[0]
        failed = 0

        fn = save_log(ctest_buf, out_path, target)
        log_url = make_md_url(url_prefix, fn)
        summary.append(f"| **{target}** | {reason} | {log_url} |")

        # testcases = []
        if first_line.startswith("[==========]"):
            for classname, method, err in parse_gtest_fails(ctest_buf):
                fn = save_log(err, out_path, classname, method)
                log_url = make_md_url(url_prefix, fn)
                summary.append(f"| _{ classname }::{ method }_ | | {log_url}|")
                failed += 1
        elif first_line.startswith("<-----"):
            for classname, method, err in parse_yunit_fails(ctest_buf):
                fn = save_log(err, out_path, classname, method)
                log_url = make_md_url(url_prefix, fn)
                summary.append(f"| _{ classname }::{ method }_ | | {log_url}|")
                failed += 1
        else:
            raise

    return summary, []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url-prefix", default="./")
    parser.add_argument("--patch-jsuite", default=False, action="store_true")

    parser.add_argument("ctest_log", type=argparse.FileType("r"))
    parser.add_argument("out_log_dir")

    parser.add_argument("jsuite_paths", nargs="*")

    args = parser.parse_args()

    if args.patch_jsuite and not args.jsuite_paths:
        print("jsuite_paths are reqruired")
        raise SystemExit(-1)

    summary, urls = extract_logs(
        args.ctest_log, Path(args.out_log_dir), args.url_prefix
    )

    print("\n".join(summary))


if __name__ == "__main__":
    main()
