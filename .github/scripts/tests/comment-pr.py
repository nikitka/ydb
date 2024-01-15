#!/usr/bin/env python
import os
import json
import argparse
from github import Github, Auth as GithubAuth
from github.PullRequest import PullRequest
from gh_status import update_pr_comment_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rewrite', dest="rewrite", action='store_true')
    parser.add_argument('text', type=argparse.FileType('r'))

    args = parser.parse_args()

    build_preset = os.environ["BUILD_PRESET"]

    gh = Github(auth=GithubAuth.Token(os.environ["GITHUB_TOKEN"]))

    with open(os.environ["GITHUB_EVENT_PATH"]) as fp:
        event = json.load(fp)

    pr = gh.create_from_raw_data(PullRequest, event["pull_request"])

    update_pr_comment_text(pr, build_preset, args.text.read(), args.rewrite)


if __name__ == '__main__':
    main()
