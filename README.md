# ido-benchmark

A public, reproducible benchmark of AI pull-request reviewers.

**Warning: this repository intentionally contains known-vulnerable code. Do not use any of it.**
The code is copied from public open-source projects at versions that were later fixed by public
security advisories (and from ordinary commits, for comparison). It is here only so that review
tools can be measured on it. Do not copy it into software, do not run it, and do not report the
issues to the upstream projects: every one of them is already public and fixed.

## How it works

- `main` holds one folder per case, `cases/<case_id>/`, with an excerpt of the upstream file(s).
- Each case has a pull request from a branch `case/<case_id>` that changes those excerpts to
  another real upstream version of the same code. Every installed review app reviews every pull
  request with its default settings, and the comments are then scored against known labels.
- The cases are the 87 cases of the `real_v1` dataset (60 with a known issue, 27 ordinary
  commits). Pull requests are never merged.

## Sources and licences

Every case, its upstream project, commit, advisory (if any) and licence are listed in
[`NOTICE.md`](NOTICE.md). The licence texts are in [`licenses/`](licenses/). The excerpts stay
under their original licences and copyright; nothing here relicenses them.
