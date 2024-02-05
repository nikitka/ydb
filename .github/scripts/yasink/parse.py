import logging
import argparse
import os

from yasink.parser import parse_line
from yasink.testmo import TestmoClient


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=argparse.FileType('r'))

    args = parser.parse_args()

    tests = []
    for line in args.input:
        event = parse_line(line)
        if event is not None:
            tests.append(event)

    for t in tests:
        if t.ok:
            continue
        print(t)

    # testmo_token = os.environ['TESTMO_TOKEN']

    # logging.basicConfig(level=logging.DEBUG)
    #
    # tmo = TestmoClient('https://nebius.testmo.net', 2, testmo_token)
    # tmo_run = tmo.start_run('python', 'tst', [])
    # tmo_thread = tmo_run.new_thread()
    #
    # for chunk in chunks(tests, 250):
    #     tmo_thread.append_tests(chunk)
    #     break
    #
    # tmo_thread.complete()
    # tmo_run.complete()
