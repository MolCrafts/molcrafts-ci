#!/usr/bin/env bash
# The rules behind actions/ci-context, readable on their own and runnable
# outside Actions (tests/test_ci_context.py). Reads CI_OWNER, CI_REPOSITORY,
# CI_EVENT, CI_REF, CI_PR_HEAD; appends key=value lines to $GITHUB_OUTPUT and
# echoes them.
set -euo pipefail

for var in CI_OWNER CI_REPOSITORY CI_EVENT CI_REF; do
    [ -n "${!var:-}" ] || { echo "::error::ci-context: $var is empty"; exit 1; }
done

# Upstream: the organization's own repository, not a fork.
upstream=false
[ "$CI_OWNER" = MolCrafts ] && upstream=true

# Integration ref: what gets merged into and released from.
case "$CI_REF" in
    refs/heads/dev | refs/heads/master | refs/heads/main | refs/tags/*) integration=true ;;
    *) integration=false ;;
esac

# The fast tier is only for a feature-branch push to MolCrafts. A fork proves
# the full tier before its pull request; pull requests, dispatches and
# schedules are deliberate runs.
tier=fast
if [ "$upstream" = false ] || [ "$integration" = true ] || [ "$CI_EVENT" != push ]; then
    tier=full
fi

# Run each commit once: a pull request inside a fork was already run, full
# tier, by its push. Same-repository pull requests upstream (Dependabot) do
# run, so their required checks appear, and so does a pull request whose head
# repository is gone (a deleted fork: CI_PR_HEAD is empty).
skip_pr=false
if [ "$CI_EVENT" = pull_request ] && [ "${CI_PR_HEAD:-}" = "$CI_REPOSITORY" ] && [ "$upstream" = false ]; then
    skip_pr=true
fi

# Only feature refs cancel their superseded runs.
cancel=true
[ "$integration" = true ] && cancel=false

{
    echo "tier=$tier"
    echo "upstream=$upstream"
    echo "integration=$integration"
    echo "skip-pr=$skip_pr"
    echo "cancel=$cancel"
} | tee -a "${GITHUB_OUTPUT:-/dev/null}"
