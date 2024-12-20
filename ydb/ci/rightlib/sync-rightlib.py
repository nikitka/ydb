#!/usr/bin/env python3
import os
import datetime
import logging
import subprocess
from operator import attrgetter
from typing import Optional
from github import Github
from github.PullRequest import PullRequest


class RightlibSync:
    pr_label_rightlib = "rightlib"
    pr_label_fail = "rightlib-fail"
    rightlib_sha_file = "ydb/ci/rightlib.txt"
    check_name = "checks_integrated"
    failed_comment_mark = "<!--RightLibSyncFailed-->"
    rightlib_check_status_name = "rightlib-merge"

    def __init__(self, repo, token):
        self.repo_name = repo
        self.token = token
        self.gh = Github(login_or_token=self.token)
        self.repo = self.gh.get_repo(self.repo_name)
        self.dtm = self.get_dtm()
        self.logger = logging.getLogger("sync")
        self.workflow_url = None
        self.detect_env()

    def detect_env(self):
        if "GITHUB_RUN_ID" in os.environ:
            self.workflow_url = (
                f"{os.environ['GITHUB_SERVER_URL']}/{self.repo_name}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
            )

    def get_dtm(self):
        return datetime.datetime.now().strftime("%y%m%d-%H%M")

    def rightlib_latest_repo_sha(self):
        return self.repo.get_branch("rightlib").commit.sha

    def rightlib_sha_file_contents(self, ref):
        return self.repo.get_contents(self.rightlib_sha_file, ref=ref).decoded_content.decode().strip()

    def rightlib_latest_sync_commit(self):
        return self.rightlib_sha_file_contents(ref="main")

    def get_pr_rightlib_sha(self, pr: PullRequest):
        return self.rightlib_sha_file_contents(ref=pr.head.sha)

    def get_latest_open_pr(self) -> Optional[PullRequest]:
        query = f"label:{self.pr_label_rightlib} repo:{self.repo_name} is:pr state:open sort:created-desc"
        result = self.gh.search_issues(query).get_page(0)
        if result:
            return result[0].as_pull_request()
        return None

    def check_rightlib_sha_has_status(self, pr: PullRequest):
        sha = self.get_pr_rightlib_sha(pr)
        statuses = [c for c in self.repo.get_commit(sha).get_statuses() if c.context == self.rightlib_check_status_name]
        if not statuses:
            return True
        # GitHub API doesn't call for remove commit status, so we ignore latest status if it is pending
        return statuses[-1].state == "pending"

    def set_rightlib_sha_status(self, pr: PullRequest, state: str, description: str):
        sha = self.get_pr_rightlib_sha(pr)
        self.logger.info("set state=%s for rightlib commit %s", state, sha)
        self.repo.get_commit(sha).create_status(
            context=self.rightlib_check_status_name, state=state, target_url=pr.html_url, description=description
        )

    def check_opened_pr(self, pr: PullRequest):
        self.logger.info("check opened pr %r", pr)

        if self.pr_label_fail in pr.labels:
            self.logger.info("pr has %s label, exit", self.pr_label_fail)
            return

        self.logger.debug("check for rightlib commit has status")

        if self.check_rightlib_sha_has_status(pr):
            self.logger.info("rightlib commit already has status, exit")
            return

        checks = [c for c in self.repo.get_commit(pr.head.sha).get_statuses() if c.context == self.check_name]
        checks.sort(key=attrgetter("id"))

        if not checks:
            self.logger.info("no %r checks found", self.check_name)
            return

        self.logger.info("found checks %s", checks)

        check = checks[-1]

        if check.state == "failure":
            self.logger.info("%s check failed", self.check_name)
            self.add_failed_comment(pr, f"`{self.check_name}` failed, disabling future checks")
            self.set_rightlib_sha_status(pr, "failure", f"`{self.check_name}` failed")
            return

        elif check.state == "success":
            self.set_rightlib_sha_status(pr, "success", f"`{self.check_name}` success")
            self.logger.info("check success, going to merge")
            self.merge_pr(pr)
        else:
            self.logger.info("wait for success")

    def add_pr_failed_label(self, pr: PullRequest):
        pr.add_to_labels(self.pr_label_fail)

    def git_merge_pr(self, pr: PullRequest):
        self.git_run("clone", f"https://{self.token}@github.com/{self.repo_name}.git", "merge-repo")
        os.chdir("merge-repo")
        self.git_run("fetch", "origin", f"pull/{pr.number}/head:PR")
        self.git_run("checkout", "main")

        try:
            self.git_run("merge", "PR", "--no-edit")
        except subprocess.CalledProcessError:
            self.add_failed_comment(pr, "Unable to merge PR")
            self.add_pr_failed_label(pr)

        try:
            self.git_run("push")
        except subprocess.CalledProcessError:
            self.add_failed_comment(pr, "Unable to push merged revision")
            self.add_pr_failed_label(pr)

    def merge_pr(self, pr: PullRequest):
        self.logger.info("start merge %s into main", pr)
        self.git_merge_pr(pr)
        self.logger.info("deleting ref %r", pr.head.ref)
        self.repo.get_git_ref(f"heads/{pr.head.ref}").delete()
        body = f"The PR was successfully merged into main using workflow"
        pr.create_issue_comment(body=body)

    def add_failed_comment(self, pr: PullRequest, text: str):
        if self.workflow_url:
            text += f" Please see logs in the workflow [run]({self.workflow_url})."
        pr.create_issue_comment(f"{self.failed_comment_mark}\n{text}")

    def git_run(self, *args):
        args = ["git"] + list(args)

        self.logger.info("run: %r", args)
        try:
            output = subprocess.check_output(args).decode()
        except subprocess.CalledProcessError as e:
            self.logger.error(e.output.decode())
            raise
        else:
            self.logger.info("output:\n%s", output)
        return output

    def git_revparse_head(self):
        return self.git_run("rev-parse", "HEAD").strip()

    def create_new_pr(self):
        dev_branch_name = f"merge-libs-{self.dtm}"
        commit_msg = f"Import libraries {self.dtm}"
        pr_title = f"Library import {self.dtm}"

        self.git_run("clone", f"https://{self.token}@github.com/{self.repo_name}.git", "ydb-new-pr")
        os.chdir("ydb-new-pr")
        self.git_run("checkout", "rightlib")
        rightlib_sha = self.git_revparse_head()

        self.logger.info(f"{rightlib_sha=}")

        self.git_run("checkout", "main")
        self.git_run(f"checkout", "-b", dev_branch_name)

        prev_sha = self.git_revparse_head()

        self.git_run("merge", "rightlib", "--no-edit")

        cur_sha = self.git_revparse_head()

        if prev_sha == cur_sha:
            logging.info("Merge did not bring any changes, exiting")
            return

        with open("ydb/ci/rightlib.txt", "w") as fp:
            fp.write(f"{rightlib_sha}\n")

        self.git_run("add", ".")
        self.git_run("commit", "-m", commit_msg)
        self.git_run("push", "--set-upstream", "origin", dev_branch_name)

        if self.workflow_url:
            pr_body = f"PR was created by rightlib sync workflow [run]({self.workflow_url})"
        else:
            pr_body = f"PR was created by rightlib sync script"

        pr = self.repo.create_pull("main", dev_branch_name, title=pr_title, body=pr_body)
        pr.add_to_labels(self.pr_label_rightlib)

        self.set_rightlib_sha_status(pr, "pending", f"will be check in #{pr.number}")


    def sync(self):
        pr = self.get_latest_open_pr()

        if pr:
            self.check_opened_pr(pr)
        else:
            cur_sha = self.rightlib_latest_repo_sha()
            latest_sha = self.rightlib_latest_sync_commit()
            self.logger.info("cur_sha=%s", cur_sha)
            self.logger.info("latest_sha=%s", latest_sha)

            if cur_sha != latest_sha:
                self.create_new_pr()


def main():
    log_fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(format=log_fmt, level=logging.DEBUG)
    repo = os.environ["REPO"]
    token = os.environ["TOKEN"]
    syncer = RightlibSync(repo, token)
    syncer.sync()


if __name__ == "__main__":
    main()
