import boto3
from botocore.config import Config as BotoConfig

from .config import Config


def get_s3_client(cfg: Config):
    client = boto3.client(
        "s3",
        config=BotoConfig(
            connect_timeout=20, read_timeout=30, retries={"max_attempts": 8}
        ),
        aws_access_key_id=cfg.s3_access_key,
        aws_secret_access_key=cfg.s3_secret_key,
        endpoint_url=f"https://{cfg.s3_host_base}",
    )

    return client
