#!/usr/bin/env python3
import argparse
from muter import mute_junit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log_file")
    parser.add_argument("out_path")
    parser.add_argument("--patch-junit-reports", action="store_true", default=False)
    parser.add_argument("--base-url", default="./")
