import configparser
import os
from pathlib import Path
from urllib.parse import urlparse


class Config:
    basedir: Path = None

    testmo_token: str = None
    testmo_instance: str = None
    testmo_project: str = None

    gh_repo: str = None
    gh_sha: str = None

    s3_access_key: str = None
    s3_secret_key: str = None
    s3_host_base: str = None
    s3_url_prefix: str = None
    s3_bucket: str = None
    s3_path: Path = None

    def testmo(self, token, instance, project):
        self.testmo_token = token
        self.testmo_instance = instance
        self.testmo_project = project

    def github(self, repo, sha):
        self.gh_repo = repo
        self.gh_sha = sha

    def load_s3cmd_cfg(self, fn, bucket_path, url_prefix):
        cfg = configparser.RawConfigParser()
        if not os.path.isfile(fn):
            raise Exception(f"s3cmd config {fn} is not found")
        cfg.read(fn)
        conf = cfg["default"]
        for k, v in conf.items():
            if hasattr(self, f"s3_{k}"):
                setattr(self, f"s3_{k}", v)

        bucket_url = urlparse(bucket_path)
        self.s3_bucket = bucket_url.netloc
        self.s3_path = Path(bucket_url.path.lstrip("/"))
        self.s3_url_prefix = url_prefix
