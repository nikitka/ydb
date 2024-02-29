import logging

from .base import YaLogItem, YaTestSuite


class BaseSink:
    def submit_suite(self, suite: YaTestSuite):
        pass

    def submit_build(self, build: YaLogItem):
        pass

    def submit_style(self, build: YaTestSuite):
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

    def submit_build(self, build: YaLogItem):
        pass
        # self.logger.info("submit-build: %s", build)

    def submit_style(self, suite: YaTestSuite):
        self.logger.info("submit-style: %s", suite)
