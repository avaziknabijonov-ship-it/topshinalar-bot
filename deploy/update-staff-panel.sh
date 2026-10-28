#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
target=/opt/topshinalar
backup_dir=/var/lib/topshinalar/backups
[[ "$EUID" == 0 ]] || { echo 'sudo bilan ishga tushiring.'; exit 1; }
for file in core.py excel_import.py staff.py bot.py miniapp.py i18n.py reports.py web/app.js web/app.css tests/test_staff.py tests/test_miniapp.py tests/test_excel_import.py tests/test_positions.py tests/test_bot.py usability.py; do
  [[ -f "$source_dir/$file" ]] || { echo "Yangilash fayli yo‘q: $file"; exit 1; }
done
[[ "$source_dir" != "$target" ]] || { echo 'Arxivni alohida papkaga oching.'; exit 1; }
[[ -f /etc/topshinalar.env && -f /var/lib/topshinalar/topshinalar.sqlite3 && -x "$target/.venv/bin/python" ]] || { echo 'Mavjud bot o‘rnatilishi topilmadi.'; exit 1; }
install -d -o topshinalar -g topshinalar -m 700 "$backup_dir"
echo 'Baza zaxirasi tekshirilmoqda...'
runuser -u topshinalar -- "$target/.venv/bin/python" "$target/backup.py" --source /var/lib/topshinalar/topshinalar.sqlite3 --directory "$backup_dir" --verify-restore
stamp="$(date +%Y%m%d-%H%M%S)-$$"
archive="$backup_dir/code-before-staff-$stamp.tar"
# Runtime code, bundled catalog, web and tests are updated together.
# Dependency changes require a separate reviewed virtualenv upgrade.
cmp -s "$source_dir/requirements.txt" "$target/requirements.txt" || { echo 'requirements.txt o‘zgargan: avval virtualenv bog‘liqliklarini yangilang.'; exit 1; }
files=()
while IFS= read -r -d '' path; do files+=("${path#./}"); done < <(
  cd "$source_dir"
  find . -maxdepth 1 -type f \( -name '*.py' -o -name '*.md' -o -name 'requirements.txt' \) -print0
  find web assets tests -type f ! -name '*.pyc' ! -path '*/__pycache__/*' -print0
)
existing=()
new_files=()
for file in "${files[@]}"; do
  if [[ -f "$target/$file" ]]; then existing+=("$file"); else new_files+=("$file"); fi
done
tar -cpf "$archive" -C "$target" "${existing[@]}"
rollback() {
  trap - ERR
  echo 'Yangilash to‘xtadi. Oldingi kod qaytarilmoqda.'
  systemctl stop topshinalar topshinalar-miniapp || true
  for file in "${new_files[@]}"; do rm -f -- "$target/$file"; done
  tar -xpf "$archive" -C "$target"
  systemctl start topshinalar topshinalar-miniapp || true
  exit 1
}
trap rollback ERR
systemctl stop topshinalar topshinalar-miniapp
for file in "${files[@]}"; do
  install -d -o root -g topshinalar -m 750 "$(dirname "$target/$file")"
  install -o root -g topshinalar -m 640 "$source_dir/$file" "$target/$file"
done
cd "$target"
echo 'Bot testlari bajarilmoqda...'
runuser -u topshinalar -- env PYTHONDONTWRITEBYTECODE=1 "$target/.venv/bin/python" -m unittest discover -s tests -q
systemctl start topshinalar topshinalar-miniapp
systemctl is-active --quiet topshinalar
systemctl is-active --quiet topshinalar-miniapp
trap - ERR
echo 'Yangilandi. Ilovani yopib, botda /app yuboring. Ish maydoni → Xodimlar.'
