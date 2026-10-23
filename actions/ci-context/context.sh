#!/usr/bin/env bash
# The rules behind actions/ci-context, readable on their own and runnable
# outside Actions (tests/test_ci_context.py). Reads CI_OWNER, CI_REPOSITORY,
# CI_EVENT, CI_REF, CI_PR_HEAD, CI_PR_HEAD_REF; appends key=value lines to
# $GITHUB_OUTPUT and echoes them.
set -euo pipefail

for var in CI_OWNER CI_REPOSITORY CI_EVENT CI_REF; do
    [ -n "${!var:-}" ] || { echo "::error::ci-context: $var is empty"; exit 1; }
done

# Upstream: the organization's own repository, not a fork.
upstream=false
[ "$CI_OWNER" = MolCrafts ] && upstream=true

# Integration ref: what gets merged into and released from.
case "$CI_REF" in
    refs/heads/dev | refs/heads/master | refs/tags/*) integration=true ;;
    *) integration=false ;;
esac

# The fast tier is only for a feature-branch push to MolCrafts. A fork proves
# the full tier before its pull request; pull requests, dispatches and
# schedules are deliberate runs.
tier=fast
if [ "$upstream" = false ] || [ "$integration" = true ] || [ "$CI_EVENT" != push ]; then
    tier=full
fi

# Run each commit once. A same-repository pull request is skipped when its
# head commit was already run, full tier, by its push -- required checks are
# keyed by commit SHA, so that push already satisfied them:
#   - inside a fork, every such pull request (every fork push is full tier);
#   - upstream, only one whose head is an integration branch (dev or master,
#     as in `integration` above), such as the dev -> master release PR.
# These do run: an upstream same-repository pull request from a feature
# branch (Dependabot), whose push ran only the fast tier, so its required
# full-tier checks must come from the pull request; a pull request from a fork
# into upstream, whose push ran in the fork, not here; and a pull request
# whose head repository is gone (a deleted fork: CI_PR_HEAD is empty).
case "${CI_PR_HEAD_REF:-}" in
    dev | master) head_integration=true ;;
    *) head_integration=false ;;
esac
skip_pr=false
if [ "$CI_EVENT" = pull_request ] && [ "${CI_PR_HEAD:-}" = "$CI_REPOSITORY" ]; then
    if [ "$upstream" = false ] || [ "$head_integration" = true ]; then
        skip_pr=true
    fi
fi

# Publish: upload to a registry, deploy, cut a GitHub Release. Only a `v*`
# tag pushed to MolCrafts: never a fork's tag, never a branch (not even
# master), never a dispatch -- a dispatch of release.yml is the dry run.
publish=false
if [ "$upstream" = true ] && [ "$CI_EVENT" = push ]; then
    case "$CI_REF" in refs/tags/v*) publish=true ;; esac
fi

# A nightly channel is built from dev, never from a separate nightly branch.
# Scheduled workflows execute on the default branch; the shared context
# workflow resolves dev once and returns its commit to every build job.
nightly=false
source_ref=$CI_REF
if [ "$upstream" = true ] && [ "${CI_WORKFLOW:-}" = nightly ]; then
    case "$CI_EVENT:$CI_REF" in
        schedule:refs/heads/master | workflow_dispatch:refs/heads/master | workflow_dispatch:refs/heads/dev)
            nightly=true
            source_ref=refs/heads/dev
            ;;
    esac
fi

# Stable application/docs deployments are distinct from registry releases.
# Manual deployment still has to select the stable branch.
deploy=false
if [ "$upstream" = true ]; then
    case "$CI_EVENT:$CI_REF" in
        push:refs/heads/master | workflow_dispatch:refs/heads/master | repository_dispatch:refs/heads/master)
            deploy=true
            ;;
    esac
fi

{
    echo "tier=$tier"
    echo "upstream=$upstream"
    echo "integration=$integration"
    echo "skip-pr=$skip_pr"
    echo "publish=$publish"
    echo "nightly=$nightly"
    echo "source-ref=$source_ref"
    echo "deploy=$deploy"
} | tee -a "${GITHUB_OUTPUT:-/dev/null}"
