import logging

from .base import YaBuild, YaTestSuite


class BaseSink:
    def submit_suite(self, suite: YaTestSuite):
        pass

    def submit_build(self, build: YaBuild):
        pass

    def flush(self, force=False):
        pass

    def finish(self):
        pass


class ConsoleSink(BaseSink):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def submit_suite(self, suite: YaTestSuite):
        self.logger.info("submit-suite: %s", suite)

    def submit_build(self, build: YaBuild):
        self.logger.info("submit-build: %s", build)
