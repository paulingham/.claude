# pdr-rtv Test Fixtures

Test-side fixtures for `skills/pdr-rtv/tests/`. The bats suites build their
worktree + summary fixtures dynamically inside `mktemp -d` directories
(see `setup()` blocks in `test_distill.bats` and `test_dispatch.bats`).
This directory exists so `find` and the canonical-template audit can
verify the `tests/` tree shape; persistent fixture files are intentionally
absent — tests own their fixtures end-to-end to keep the suite hermetic.
