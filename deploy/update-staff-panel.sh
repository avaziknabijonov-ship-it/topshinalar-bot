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
# Prepare the local PDF/photo reader while the running bot remains online.
ocr_missing=false
for executable in pdfinfo pdftotext pdftoppm tesseract; do
  command -v "$executable" >/dev/null || ocr_missing=true
done
if command -v tesseract >/dev/null; then
  tesseract --list-langs 2>/dev/null | grep -qx rus || ocr_missing=true
  tesseract --list-langs 2>/dev/null | grep -qx uzb || ocr_missing=true
fi
if "$ocr_missing"; then
  echo 'PDF va rasm o‘qish dasturlari o‘rnatilmoqda...'
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-rus tesseract-ocr-uzb
fi
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
# Validate an isolated candidate while both production services stay online.
# Never run the suite in the downtime window or against production configuration.
preflight_dir="$(mktemp -d /var/lib/topshinalar/preflight.XXXXXX)"
cleanup_preflight() { rm -rf -- "$preflight_dir"; }
trap cleanup_preflight EXIT
chown root:topshinalar "$preflight_dir"
chmod 750 "$preflight_dir"
for file in "${files[@]}"; do
  install -d -o root -g topshinalar -m 750 "$(dirname "$preflight_dir/$file")"
  install -o root -g topshinalar -m 640 "$source_dir/$file" "$preflight_dir/$file"
done
echo 'Xizmatlar ishlamoqda. Yangi nusxa testlari bajarilmoqda...'
(
  cd "$preflight_dir"
  runuser -u topshinalar -- env -u BOT_TOKEN -u DB_PATH -u PUBLIC_APP_URL -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 "$target/.venv/bin/python" -m unittest discover -s tests -q
)
cleanup_preflight
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
systemctl start topshinalar topshinalar-miniapp
systemctl is-active --quiet topshinalar
systemctl is-active --quiet topshinalar-miniapp
# is-active alone can succeed before the HTTP listener has finished starting.
"$target/.venv/bin/python" - <<'HEALTH'
import time,urllib.request,urllib.error
for attempt in range(20):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/api/me',timeout=1) as response:
            ready=response.status==200
    except urllib.error.HTTPError as error:
        ready=error.code==403
    except (OSError,TimeoutError):
        ready=False
    if ready:break
    time.sleep(0.5)
else:raise SystemExit('Mini App HTTP readiness failed')
HEALTH
trap - ERR
echo 'Yangilandi. Ilovani yopib, botda /app yuboring. Ish maydoni → Xodimlar.'
