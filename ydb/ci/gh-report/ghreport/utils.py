import io
import logging
import os
import zipfile
import zlib
from typing import Optional

logger = logging.getLogger(__name__)


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


# from https://github.com/jschneier/django-storages/blob/master/storages/compress.py
class GzipCompressionWrapper(io.RawIOBase):
    """Wrapper for compressing file contents on the fly."""

    def __init__(self, raw, level=zlib.Z_BEST_COMPRESSION):
        super().__init__()
        self.raw = raw
        self.compress = zlib.compressobj(level=level, wbits=31)
        self.leftover = bytearray()

    def readable(self) -> bool:
        return True

    def readinto(self, buf: bytearray) -> Optional[int]:
        size = len(buf)
        while len(self.leftover) < size:
            chunk = self.raw.read(size)
            if not chunk:
                if self.compress:
                    self.leftover += self.compress.flush(zlib.Z_FINISH)
                    self.compress = None
                break
            self.leftover += self.compress.compress(chunk)
        if len(self.leftover) == 0:
            return 0
        output = self.leftover[:size]
        size = len(output)
        buf[:size] = output
        self.leftover = self.leftover[size:]
        return size


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""

    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def zip_directory(path, arc_prefix, zip_fn):
    zf = zipfile.ZipFile(
        zip_fn, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    )
    logger.info(f"put {path} into {zip_fn}")

    for root, dirs, files in os.walk(path):
        for f in files:
            filename = os.path.join(root, f)
            arcname = os.path.join(arc_prefix, os.path.relpath(filename, path))
            zf.write(filename, arcname)
    zf.close()
