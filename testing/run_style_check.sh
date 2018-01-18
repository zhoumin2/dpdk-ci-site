#!/bin/bash
# Run flake8 against all Python files
# Expected to be run in root cisite repository directory

set -o pipefail

# Activate virtualenv containing ansible and review tools
. venv/bin/activate

if [[ -n "${bamboo_planRepository_1_previous_revision}" ]]; then
  prev=${bamboo_planRepository_1_previousRevision}
  cur=${bamboo_planRepository_1_revision}
  git diff "${prev}" "${cur}" \
    | flake8 --config=../code-review-standards/python/flake8.cfg --diff \
    || exit 1
else
  git ls-files | grep '\.py$' \
    | xargs flake8 --config=../code-review-standards/python/flake8.cfg \
    || exit 1
fi
