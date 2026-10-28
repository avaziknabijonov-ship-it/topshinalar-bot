#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
exec 9>/run/lock/topshinalar-auto-update.lock
flock -n 9 || exit 0
state=/var/lib/topshinalar-updater
repo="$state/repo"
export GIT_SSH_COMMAND='ssh -i /root/.ssh/topshinalar-github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new'
git -C "$repo" fetch --quiet origin main
revision=$(git -C "$repo" rev-parse origin/main)
[[ ! -f "$state/deployed" || $(cat "$state/deployed") != "$revision" ]] || exit 0
git -C "$repo" checkout --quiet --detach "$revision"
# This existing updater backs up SQLite and restores code if validation fails.
bash "$repo/deploy/update-staff-panel.sh"
printf '%s\n' "$revision" > "$state/deployed.tmp"
mv "$state/deployed.tmp" "$state/deployed"
echo "GitHub revision deployed: $revision"
