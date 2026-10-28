#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ $EUID == 0 ]] || { echo 'sudo bash bilan ishga tushiring'; exit 1; }
command -v git >/dev/null
command -v flock >/dev/null
install -d -m 700 /root/.ssh /var/lib/topshinalar-updater
key=/root/.ssh/topshinalar-github
if [[ ! -f "$key" ]]; then
  ssh-keygen -q -t ed25519 -N '' -C topshinalar-read-only -f "$key"
fi
export GIT_SSH_COMMAND="ssh -i $key -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
url=git@github.com:avaziknabijonov-ship-it/topshinalar-bot.git
if ! git ls-remote "$url" refs/heads/main >/dev/null; then
  echo 'GitHub > topshinalar-bot > Settings > Deploy keys > Add deploy key'
  echo 'Title: topshinalar-server. Allow write access BELGILAMANG.'
  cat "$key.pub"
  echo 'Kalitni qoshgach, shu buyruqni qayta bajaring.'
  exit 1
fi
repo=/var/lib/topshinalar-updater/repo
if [[ ! -d "$repo/.git" ]]; then git clone --branch main "$url" "$repo"; fi
git -C "$repo" fetch origin main
git -C "$repo" checkout --detach origin/main
install -m 700 "$repo/deploy/github-auto-update.sh" /usr/local/sbin/topshinalar-auto-update
cat > /etc/systemd/system/topshinalar-auto-update.service <<'UNIT'
[Unit]
Description=Update TOPSHINALAR from GitHub main
Wants=network-online.target
After=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/topshinalar-auto-update
TimeoutStartSec=15min
UMask=0077
UNIT
cat > /etc/systemd/system/topshinalar-auto-update.timer <<'UNIT'
[Unit]
Description=Check TOPSHINALAR GitHub updates every two minutes
[Timer]
OnBootSec=2min
OnUnitInactiveSec=2min
Persistent=true
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl start topshinalar-auto-update.service
systemctl enable --now topshinalar-auto-update.timer
systemctl list-timers --no-pager topshinalar-auto-update.timer
echo 'Avtoyangilanish yoqildi.'
