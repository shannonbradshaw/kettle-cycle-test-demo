---
name: pre-commit
description: Runs before git commits to ensure tests pass and docs are updated
---

1. Run tests: `go test ./...`
2. If tests fail, abort commit and report failures
3. Run docs-updater agent to update README and CLAUDE.md
4. Run changelog-updater agent to update changelog.md
5. Stage any doc changes made by agents
6. Proceed with commit
