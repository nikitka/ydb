from github.PullRequest import PullRequest


def update_pr_comment_text(pr: PullRequest, build_preset: str, text: str, rewrite: bool):
    header = f'<!-- status pr={pr.number}, preset={build_preset} -->'

    body = comment = None
    for c in pr.get_issue_comments():
        if c.body.startswith(header):
            print(f"found comment id={c.id}")
            comment = c
            if not rewrite:
                body = [c.body, ""]
            break

    if body is None:
        body = [header]

    body.append(text)

    body = '\n'.join(body)

    if comment is None:
        print(f"post new comment")
        pr.create_issue_comment(body)
    else:
        print(f"edit comment")
        comment.edit(body)
