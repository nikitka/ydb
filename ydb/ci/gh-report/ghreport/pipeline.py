import logging
import os
import re
from typing import List, Optional

import orjson

from .base import (UploadedFile, YaLogItem, YaStatus, YaTest, YaTestChunk,
                   YaTestSuite, YaTestType)
from .config import Config
from .mute import YaMuteCheck
from .sink import BaseSink
from .utils import GzipCompressionWrapper, zip_directory

logger = logging.getLogger(__name__)


def normalize_filename(filename):
    """
    Replace invalid for file names characters with string equivalents
    :param filename: string to be converted to a valid file name
    :return: valid file name
    """
    not_allowed_pattern = r"[\[\]\/:*?\"\'<>|+\0\\\t\n\r\x0b\x0c ]"
    filename = re.sub(not_allowed_pattern, ".", filename)
    return re.sub(r"\.{2,}", ".", filename)


def check_file(fn):
    if not os.path.isfile(fn):
        logger.error("no such file: %s", fn)
        return False

    if not os.access(fn, os.R_OK):
        logger.error("permission denied: %s", fn)
        return False

    return True


def check_directory(fn):
    if not os.path.isdir(fn):
        logger.error("no such directory: %s", fn)
        return False

    if not os.access(fn, os.R_OK | os.X_OK):
        logger.error("permission denied: %s", fn)
        return False

    return True


class ParserPipeline:
    def __init__(self, cfg: Config, mute_check: YaMuteCheck, s3_client, sinks: List[BaseSink]):
        self.current_suite = None  # type: Optional[YaTestSuite]
        self.current_chunk = None  # type: Optional[YaTestChunk]
        self.cfg = cfg
        self.s3 = s3_client
        self.mute_check = mute_check
        self.sinks = sinks

    def put(self, data: str):
        data = orjson.loads(data)

        # if data["type"] == "build":
        #     build = YaLogItem.parse_json(data)
        #     self.on_build_finished(build)

        if data["type"] not in ("style", "test"):
            self.on_suite_finished()

        if data.get("status") == "DISCOVERED" or data["type"] not in ("style", "test"):
            return

        if data.get("suite"):
            self.on_suite_finished()

            suite = YaTestSuite.parse_json(data)
            self.current_suite = suite
        elif data.get("chunk"):
            chunk = YaTestChunk.parse_json(data)

            self.current_chunk = chunk

            if self.current_chunk.suite_id != self.current_suite.id:
                raise Exception("suite != current_suite")

            self.current_suite.add_chunk(chunk)

        else:
            test = YaTest.parse_json(data)
            if test.chunk_id != self.current_chunk.id:
                raise Exception("Chunk != current_chunk")

            self.current_chunk.add_test(test)

    def finish(self):
        self.on_suite_finished()

    def on_style_finished(self, style: YaLogItem):
        if style.status != YaStatus.OK and self.mute_check(style.path, "BUILD"):
            style.mute()

        self.submit_style(style)

    def on_build_finished(self, build: YaLogItem):
        if build.status != YaStatus.OK and self.mute_check(build.path, "BUILD"):
            build.mute()

        self.submit_build(build)

    def on_suite_finished(self):
        suite = self.current_suite
        self.current_suite = None

        if not suite:
            return

        for chunk in suite.chunks:
            save_logsdir = False

            for test in chunk.tests:

                test.source_code_url = (
                    f"{self.cfg.gh_repo}/tree/{self.cfg.gh_sha}/{test.path}"
                )

                if test.status in (YaStatus.OK, YaStatus.SKIPPED):
                    continue

                if self.mute_check(test.path, test.full_name):
                    test.mute()

                if "logsdir" in test.links:
                    save_logsdir = True

                # save logs for failed tests
                if test.status == YaStatus.FAILED:
                    # upload stdout, stderr
                    for name, logs in test.links.items():
                        if name == "logsdir":
                            continue

                        for fn in logs:
                            fn = self.cfg.basedir.joinpath(fn)

                            if not check_file(fn):
                                continue

                            if os.stat(fn).st_size == 0:
                                logger.info("skip empty %s file %s", name, fn)
                                continue

                            s3_fn = self.gen_filename(test.path, test.full_name, name)

                            # FIXME: add better guessing
                            if str(fn).endswith(".html"):
                                mime_type = "text/html"
                            else:
                                mime_type = "text/plain"

                            link = self.upload_file(
                                name, s3_fn, fn, mime_type, inline=True, gzip=True
                            )
                            test.add_link_url(link)

            if save_logsdir:
                logger.info("save logsdir for %s", chunk.path)

                s3_fn = self.gen_filename(
                    chunk.path, chunk.fancy_chunk_name, "testing_out_stuff.zip"
                )

                logsdir_path = self.cfg.basedir.joinpath(chunk.logsdir_path)

                if not check_directory(logsdir_path):
                    continue

                zip_fn = self.archive_directory(
                    s3_fn,
                    self.gen_filename(chunk.path, chunk.fancy_chunk_name),
                    logsdir_path,
                )
                link = self.upload_file(
                    "testing_out_stuff.zip", s3_fn, zip_fn, "application/zip"
                )
                # chunk.set_logsdir_link(link)
                for test in chunk.tests:
                    test.add_link_url(link)

        self.submit_suite(suite)

    def gen_filename(self, *parts):
        pieces = []
        for p in parts:
            if p is None:
                continue
            pieces.append(normalize_filename(p.replace("/", "-")))
        return "-".join(pieces)

    def archive_directory(self, fn, chunk_path, folder):
        # FIXME: build-release
        zip_fn = self.cfg.basedir.joinpath(fn)
        zip_directory(self.cfg.basedir.joinpath(folder), chunk_path, zip_fn)
        return zip_fn

    def upload_file(self, name, s3_name, fn, mime_type, inline=False, gzip=False):
        if self.s3 is None:
            return UploadedFile(
                name=name,
                url="fake_url",
                mime_type=mime_type,
                size=0,
            )

        s3_path = str(self.cfg.s3_path.joinpath(s3_name))
        extra_args = {
            "ACL": "public-read",
            "ContentType": mime_type,
        }

        if inline:
            extra_args["ContentDisposition"] = "inline"

        if gzip:
            extra_args["ContentEncoding"] = "gzip"
            with open(fn, "rb") as fp, GzipCompressionWrapper(fp) as zfp:
                self.s3.upload_fileobj(
                    zfp, self.cfg.s3_bucket, s3_path, ExtraArgs=extra_args
                )
        else:
            self.s3.upload_file(fn, self.cfg.s3_bucket, s3_path, ExtraArgs=extra_args)

        return UploadedFile(
            name=name,
            url=f"{self.cfg.s3_url_prefix}/{s3_name}",
            mime_type=mime_type,
            size=os.stat(fn).st_size,
        )

    def submit_build(self, build: YaLogItem):
        for sink in self.sinks:
            sink.submit_build(build)

    def submit_suite(self, suite: YaTestSuite):
        logger.info("submit %s", suite)
        for sink in self.sinks:
            sink.submit_suite(suite)
