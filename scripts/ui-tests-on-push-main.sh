#!/usr/bin/env sh
# Run mocked Playwright UI tests when the push includes main.
set -eu

run=0
while read -r _local_ref _local_sha remote_ref _remote_sha; do
  case "$remote_ref" in
    refs/heads/main|refs/heads/master) run=1 ;;
  esac
done

[ "$run" -eq 0 ] && exit 0

root=$(git rev-parse --show-toplevel)
echo "Running mocked UI tests before push to main…"
make -C "$root" test-ui
