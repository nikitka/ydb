#!/usr/bin/env python3
import argparse
import logging
import logging.config
import os
import pathlib
import json
import sys

from ghreport.config import Config
from ghreport.mute import YaMuteCheck
from ghreport.pipeline import ParserPipeline
from ghreport.s3 import get_s3_client
from ghreport.sink import ConsoleSink
from ghreport.testmo import TestmoClient, TestmoField, TestmoLink, TestmoRun, TestmoSink, TestmoState
from ghreport.summary import SummarySink


def prepare_logger():
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": True,
            "formatters": {
                "default": {"format": "%(asctime)s [%(levelname)8s] %(message)s"},
            },
            "handlers": {
                "default": {
                    "level": "DEBUG",
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                },
            },
            "loggers": {
                "": {"handlers": ["default"], "level": "INFO", "propagate": False},
                "ghreport": {
                    "handlers": ["default"],
                    "level": "DEBUG",
                    "propagate": False,
                },
                "__main__": {
                    "handlers": ["default"],
                    "level": "DEBUG",
                    "propagate": False,
                },
            },
        }
    )


def parse_args():
    def base_sink_args(cmd_parser):
        cmd_parser.add_argument("--basedir", type=pathlib.Path, help="ya make output directory", required=True)
        cmd_parser.add_argument("--github-repo", help="github repository name", required=True)
        cmd_parser.add_argument("--github-sha", help="github sha", required=True)
        cmd_parser.add_argument("-m", "--mute-conf", help="mute_check test list")
        cmd_parser.add_argument("-i", "--input", type=argparse.FileType("r"))
        cmd_parser.add_argument("--summary-out-path")
        cmd_parser.add_argument("--summary-url-prefix")
        cmd_parser.add_argument("--badge-out-path", type=argparse.FileType("w"), default=sys.stdout)

    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="command", help="sub-command help")

    console_sink = subparsers.add_parser("console")
    base_sink_args(console_sink)

    testmo_cmd = subparsers.add_parser("testmo")

    testmo_sp = testmo_cmd.add_subparsers(dest="testmo_cmd")

    testmo_run = testmo_sp.add_parser("create-run")
    testmo_run.add_argument("--project", type=int, default=2, help="testmo project id")
    testmo_run.add_argument("--instance", default="https://nebius.testmo.net", help="testmo instance url")
    testmo_run.add_argument("--name", required=True, help="testmo run name")
    testmo_run.add_argument("--source", required=True)
    testmo_run.add_argument("--tag", action="append")
    testmo_run.add_argument(
        "--run-link",
        nargs="*",
        metavar="NAME URL NOTE?",
        help="testmo run links",
        action=TestmoLink.argparse_action(),
    )
    testmo_run.add_argument(
        "--run-field",
        nargs="*",
        metavar="NAME TYPE VALUE",
        help="testmo run fields",
        action=TestmoField.argparse_action(),
    )
    testmo_run.add_argument(
        "--state",
        dest="testmo_state",
        metavar="FILENAME",
        help="state file with ids and links (must be passed to the sink step)",
    )

    testmo_sink = testmo_sp.add_parser("sink")
    base_sink_args(testmo_sink)
    testmo_sink.add_argument("--state", dest="testmo_state", metavar="FILENAME", help="state file with ids and links")
    testmo_sink.add_argument("--s3", dest="enable_s3", action="store_true", help="enable s3 log upload")
    testmo_sink.add_argument(
        "--thread-link",
        nargs="*",
        metavar="NAME URL NOTE?",
        help="testmo thread links",
        action=TestmoLink.argparse_action(),
    )
    testmo_sink.add_argument(
        "--thread-field",
        nargs="*",
        metavar="NAME TYPE VALUE",
        help="testmo thread fields",
        action=TestmoField.argparse_action(),
    )
    testmo_finish = testmo_sp.add_parser("complete-run")
    testmo_finish.add_argument("--state", dest="testmo_state", metavar="FILENAME", help="state file with ids and links")

    return parser.parse_args()


def main():
    prepare_logger()

    logger = logging.getLogger(__name__)

    args = parse_args()

    cfg = Config()

    s3_client = None

    if getattr(args, "enable_s3", False):
        cfg.load_s3cmd_cfg(
            os.environ["S3CMD_CONFIG"],
            os.environ["S3_BUCKET_PATH"],
            os.environ["S3_URL_PREFIX"],
        )
        s3_client = get_s3_client(cfg)

    if args.command == "testmo":
        if args.testmo_cmd == "create-run":
            cfg.testmo(os.environ["TESTMO_TOKEN"], args.instance, args.project)
            testmo = TestmoClient.configure(cfg)

            tags = [t.strip() for t in args.tag if t.strip()]
            testmo_run = testmo.start_run(args.name, args.source, tags, args.run_field, args.run_link)
            logger.info("testmo run_id=%s: %s", testmo_run.run_id, testmo_run.url)

            TestmoState(instance=args.instance, project=args.project,
                        run_id=testmo_run.run_id, run_url=testmo_run.url).save(args.testmo_state)

            return
        elif args.testmo_cmd == "complete-run":
            state = TestmoState.load(args.testmo_state)
            cfg.testmo(os.environ["TESTMO_TOKEN"], state.instance, state.project)

            testmo = TestmoClient.configure(cfg)

            testmo_run = TestmoRun(testmo, state.run_id)
            testmo_run.complete()

            return
        elif args.testmo_cmd == "sink":
            state = TestmoState.load(args.testmo_state)
            cfg.testmo(os.environ["TESTMO_TOKEN"], state.instance, state.project)
            testmo = TestmoClient.configure(cfg)

            testmo_run = TestmoRun(testmo, state.run_id)

            testmo_thread = testmo_run.new_thread(args.thread_field, args.thread_link)
            logger.info("testmo run_id=%s, thread_id=%s", testmo_run.run_id, testmo_thread.thread_id)
            logger.info("testmo run: %s", testmo_run.url)
            logger.info("testmo thread: %s", testmo_thread.url)

            sink = TestmoSink(testmo_thread)
        else:
            raise Exception("Invalid testmo sub command")

    elif args.command == "console":
        sink = ConsoleSink()
    else:
        raise Exception("Invalid command")

    mute_check = YaMuteCheck()

    if args.mute_conf:
        mute_check.load(args.mute_conf)
    else:
        logger.info("no mute rules")

    cfg.github(args.github_repo, args.github_sha)
    cfg.basedir = args.basedir

    summary = SummarySink(cfg)
    pipeline = ParserPipeline(cfg, mute_check, s3_client, [sink, summary])

    for line in args.input:
        pipeline.put(line)

    sink.flush(force=True)
    sink.finish()

    for line in summary.render(""):
        args.badge_out_path.write(line)
        args.badge_out_path.write("\n")


if __name__ == "__main__":
    main()
