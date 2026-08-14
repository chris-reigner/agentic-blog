<!-- The PR title becomes the squash-merge commit and drives semantic-release.
     Use Conventional Commits, e.g. `feat: add rtf ingestion` or `fix: handle empty pdf`. -->

## Description

<!-- What does this change and why? -->

## Related issues

<!-- e.g. Closes #123 -->

## Type of change

<!-- Determines the release bump when merged to main. -->

- [ ] `fix:` — bug fix (patch release)
- [ ] `feat:` — new feature (minor release)
- [ ] `feat!:` / `BREAKING CHANGE:` — breaking change (major release)
- [ ] `docs:` / `refactor:` / `test:` / `chore:` / `ci:` — no release

## Checklist

- [ ] PR title follows [Conventional Commits](https://www.conventionalcommits.org/)
- [ ] Ran `make check` locally (lint + type + tests) and it passes
- [ ] Added or updated tests for the change
- [ ] Updated docs in `docs/` if behavior changed

> **Merge with Squash** so the PR title is used as the release-driving commit message.
