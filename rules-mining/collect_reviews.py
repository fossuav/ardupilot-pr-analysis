#!/usr/bin/env python3
"""Collect human review comments on an author's ArduPilot PRs into JSONL.

usage: collect_reviews.py [out.jsonl]   (default data/comments.jsonl beside this script)


One record per comment: pr, title, state, user, kind (issue/review/inline),
path, body, url, created. Bots and the author are dropped. Resumable: PRs
already in the output are skipped.
"""
import json
import os
import re
import subprocess
import sys
import time

REPO = "ArduPilot/ardupilot"
AUTHOR = "andyp1per"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "comments.jsonl")
SKIP_USERS = {AUTHOR, "ap-review", "github-actions[bot]", "dependabot[bot]", "codecov[bot]", "Copilot",
              "copilot-pull-request-reviewer[bot]", "copilot-pull-request-reviewer"}


def api(path):
    # one compact JSON object per line, whatever the page boundaries
    cmd = ["gh", "api", "--paginate", "-H", "Accept: application/vnd.github+json", path, "--jq", ".[] | tojson"]
    for attempt in range(5):
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            return [json.loads(line) for line in p.stdout.splitlines() if line.strip()]
        if "rate limit" in p.stderr.lower():
            time.sleep(60)
            continue
        time.sleep(5)
    sys.stderr.write("failed: %s\n%s\n" % (path, p.stderr))
    return []


def search_prs():
    prs = {}
    # search returns at most 1000 per query, so split by year
    for year in range(2015, 2027):
        page = 1
        while True:
            q = "repo:%s is:pr author:%s created:%d-01-01..%d-12-31" % (REPO, AUTHOR, year, year)
            p = subprocess.run(["gh", "api", "-X", "GET", "search/issues", "-f", "q=" + q,
                                "-f", "per_page=100", "-f", "page=%d" % page],
                               capture_output=True, text=True)
            if p.returncode != 0:
                if "rate limit" in p.stderr.lower():
                    time.sleep(60)
                    continue
                sys.stderr.write(p.stderr)
                break
            d = json.loads(p.stdout)
            for it in d.get("items", []):
                prs[it["number"]] = (it["title"], it["state"], it["comments"])
            if len(d.get("items", [])) < 100:
                break
            page += 1
            time.sleep(2)
        time.sleep(2)
    return prs


done = set()
if os.path.exists(OUT):
    with open(OUT) as fh:
        for line in fh:
            done.add(json.loads(line)["pr"])
    # a PR with no human comments leaves no record; track those separately
DONE_EMPTY = OUT + ".empty"
if os.path.exists(DONE_EMPTY):
    done |= {int(x) for x in open(DONE_EMPTY).read().split()}

prs = search_prs()
sys.stderr.write("%d PRs, %d already done\n" % (len(prs), len(done)))
n = 0
with open(OUT, "a") as out, open(DONE_EMPTY, "a") as empty:
    for num in sorted(prs):
        if num in done:
            continue
        title, state, _ = prs[num]
        recs = []
        for kind, path in (("issue", "repos/%s/issues/%d/comments" % (REPO, num)),
                           ("review", "repos/%s/pulls/%d/reviews" % (REPO, num)),
                           ("inline", "repos/%s/pulls/%d/comments" % (REPO, num))):
            for c in api(path):
                user = (c.get("user") or {}).get("login", "")
                body = (c.get("body") or "").strip()
                if not user or user in SKIP_USERS or user.endswith("[bot]") or not body:
                    continue
                # tridge's /reviewprs posted as tridge before the AP-Review account existed;
                # same markers pr_review.py uses (AI_MARKER, apreview verdict marker, head line)
                ai = ("AI-generated" in body or "apreview:" in body
                      or bool(re.search(r"^\s*\**\s*Verdict\s*:", body, re.M))
                      or bool(re.search(r"\b(Re-)?reviewed at head\b", body, re.I)))
                suspect = (not ai and user.lower() == "tridge" and len(body) > 1500
                           and ("\n## " in body or "\n### " in body or "|---" in body))
                recs.append({"pr": num, "title": title, "state": state, "user": user, "kind": kind,
                             "ai": ai, "ai_suspect": suspect,
                             "path": c.get("path", ""), "body": body,
                             "url": c.get("html_url", ""),
                             "created": c.get("created_at") or c.get("submitted_at") or ""})
        for r in recs:
            out.write(json.dumps(r) + "\n")
        if not recs:
            empty.write("%d\n" % num)
        out.flush()
        empty.flush()
        n += 1
        if n % 50 == 0:
            sys.stderr.write("%d PRs fetched\n" % n)
sys.stderr.write("done, %d PRs fetched this run\n" % n)
