#!/usr/bin/env python3
import os

from IPython import start_ipython

from ghreport.base import YaStatus, YaTest, YaTestChunk, YaTestSuite
from ghreport.config import Config
from ghreport.s3 import get_s3_client
# noinspection PyUnresolvedReferences
from ghreport.testmo import TestmoClient


def prepare():
    testmo_token = os.environ["TESTMO_TOKEN"]
    s3cfg_fn = os.environ["S3CMD_CONFIG"]
    s3_bucket_path = os.environ["S3_BUCKET_PATH"]
    s3_url_prefix = os.environ["S3_URL_PREFIX"]

    cfg = Config("/Users/nkozlovskiy/tmp/basedir")
    cfg.testmo(testmo_token, "https://nebius.testmo.net", 2)
    cfg.load_s3cmd_cfg(s3cfg_fn, s3_bucket_path, s3_url_prefix)

    return {
        "cfg": cfg,
        "s3": get_s3_client(cfg),
        "testmo": TestmoClient.configure(cfg),
        "YaTest": YaTest,
        "YaTestChunk": YaTestChunk,
        "YaTestSuite": YaTestSuite,
        "YaStatus": YaStatus,
    }


if __name__ == "__main__":
    start_ipython(user_ns=prepare())
