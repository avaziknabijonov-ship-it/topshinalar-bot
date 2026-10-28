# TOPSHINALAR botini VPSga joylash

Python 3.12 bilan Ubuntu 24.04 uchun tayyorlangan. Bu fayllar serverga hali o‘rnatilmagan; quyidagi amallar server olingach bajariladi. Domen va pullik boshqaruv paneli talab qilinmaydi. Telegram APIga tashqi HTTPS ulanishi kerak.

## 1. Tayyorlash

Arxivdagi loyiha fayllarini `/opt/topshinalar`ga yuklang. Buyruqlar VPS terminalida administrator tomonidan bajariladi:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv fonts-dejavu-core
sudo useradd --system --user-group --home-dir /var/lib/topshinalar --shell /usr/sbin/nologin topshinalar
sudo install -d -o topshinalar -g topshinalar -m 700 /var/lib/topshinalar
cd /opt/topshinalar
sudo python3 -m venv .venv
sudo .venv/bin/python -m pip install -r requirements.txt
sudo install -m 600 .env.example /etc/topshinalar.env
sudo nano /etc/topshinalar.env
```

Mavjud `topshinalar` foydalanuvchisi bo‘lsa `useradd`ni takrorlamang. Sozlamalar fayli mavjud bo‘lsa uni namunaga almashtirmang: mavjud faylni tahrirlang. `BOT_TOKEN`, `DIRECTOR_IDS` va `EMPLOYEE_IDS`ni to‘ldiring. Tokenni terminal buyrug‘iga yozmang. systemd bazani `/var/lib/topshinalar/topshinalar.sqlite3`da saqlaydi, `.env`dagi DB_PATHdan qat’i nazar.

## 2. Kompyuterdagi ma’lumotlarni ko‘chirish

Eski kompyuterda botni Ctrl+C bilan to‘xtating. Windowsdagi amaldagi baza odatda `%LOCALAPPDATA%\TOPSHINALAR\staff-bot\<bot-ID>\topshinalar.sqlite3`da. Aniq ishlayotgan bazani tanlang, yangi bo‘sh nusxani emas.

Eski kompyuterdagi bot papkasidan izchil eksport oling:

```text
.venv\Scripts\python.exe backup.py --source "BAZAGA_TO‘LIQ_YO‘L" --directory "server-backup"
```

Chiqqan `.sqlite3` faylini VPSga maxfiy SSH/SFTP orqali yuboring. Serverdagi botni hali yoqmang. Agar serverda baza mavjud bo‘lsa, avval uni ham zaxiralang; almashtirish qarorini ma’lumotlarni ko‘rib qabul qiling. Import manbasi va serverdagi mavjud faylni avtomatik birlashtirish yo‘q.

Yangi serverda maqsad fayli yo‘qligini tekshirgach, eksportni `/var/lib/topshinalar/topshinalar.sqlite3`ga o‘rnating, egasi `topshinalar:topshinalar`, ruxsati `600` bo‘lsin. Importda `users`, `points`, `products`, `stock`, `sales` sonlarini tekshiring. Sozlamadagi IDlar mavjud xodimlar bilan mos bo‘lishi kerak; aks holda bot ishga tushganda ruxsatlarni yangi ro‘yxatga moslaydi. Eski kompyuterdagi botni qayta yoqmang.

## 3. Doimiy xizmat

```bash
cd /opt/topshinalar
sudo install -m 644 deploy/topshinalar.service /etc/systemd/system/
sudo install -m 644 deploy/topshinalar-backup.service /etc/systemd/system/
sudo install -m 644 deploy/topshinalar-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now topshinalar.service
sudo systemctl status topshinalar.service --no-pager
sudo journalctl -u topshinalar.service -n 50 --no-pager
```

Xizmat muvaffaqiyatli ishga tushgach:

```bash
sudo systemctl start topshinalar-backup.service
sudo systemctl status topshinalar-backup.service --no-pager
sudo systemctl enable --now topshinalar-backup.timer
sudo systemctl list-timers topshinalar-backup.timer
```

Backup xizmati nusxani alohida vaqtinchalik bazaga tiklab, barcha jadvallarni ham solishtiradi. Kunlik zaxira Toshkent vaqti bilan 03:00–03:05 oralig‘ida yaratiladi. Server o‘chiq bo‘lsa o‘tkazib yuborilgan vazifa yoqilganda bajariladi. Zaxiralar `/var/lib/topshinalar/backups`da, eski nusxalar avtomatik o‘chirilmaydi. Diskni kuzatib boring va zaxiralarni serverdan tashqariga ham ko‘chiring. Bu xizmat nusxa yaratadi; tashqi serverga avtomatik yuborish sozlanmagan.

Bot xatolik bilan to‘xtasa 10 soniyadan keyin qayta ishga tushadi; VPS qayta yoqilganda xizmat ham boshlanadi. `systemctl stop topshinalar` orqali qo‘lda to‘xtatilganda ishga tushmaydi. Docker va systemdni bir token uchun bir vaqtda ishlatmang.

## 4. Serverdagi qabul sinovi

- Direktor va xodim `/start` bosadi; begona hisob ichki ma’lumot ololmaydi.
- `/points`, `/stock`, mijoz va sotuvlar import bilan mosligini tekshirish.
- Sinov mahsuloti bilan kirim → sotuv → qoldiq → qarz to‘lovi; real hisobotga aralashmasligi uchun sinov bazasi va alohida test tokenidan foydalanish.
- КПda uchta to‘lov turidan bittasi va olib ketish/yetkazib berish; UZ/RU PDF va Excelda ismlar.
- Yaqin vaqtga eslatma qo‘yish, SSH oynasini yopish, eslatma yetib kelishini tekshirish.
- `systemctl restart topshinalar`dan keyin qoldiq va dialog davom etishini tekshirish.
- Kelishilgan vaqtda VPSni qayta yoqib xizmat va timer boshlanishini tekshirish.

Jarima avtomatik hisoblanmaydi; direktor qo‘lda kiritadi. Avtomatik qoidalar buyurtmachi ularni belgilagach qo‘shiladi.
