# Backup’ni serverdan tashqarida saqlash va tiklashni sinash

Bu yo‘riqnoma production’da hech narsa ishga tushirmaydi. Joriy auditda
backup xizmati start/enable qilinmadi, baza tiklanmadi va nusxa o‘chirilmadi.
Real offsite manzil, kalit, operator va jadval hali tasdiqlanishi kerak.

## Shartlar

1. VDSdagi readonly dalillardan aynan muvaffaqiyatli `--verify-restore` runiga
   tegishli **tayyor** `.sqlite3` fayl tanlanadi. `.tmp`, live SQLite, alohida
   `-wal` yoki `-shm`ni ko‘chirmang. Timerning enabled holati o‘zi yetarli emas.
2. Tashqi ishonchli kompyuter/backup host boshqa fizik joy yoki accountda bo‘ladi.
   U yerda repo’ning tasdiqlangan versiyasi, Python dependencies, `age` va
   ishlatiladigan obyekt ombori klienti o‘rnatilgan bo‘ladi.
3. SSH host key oldindan mustaqil tekshirilgan. Namuna mavjud vakolatli
   `ubuntu` hisobining tanlangan backup’ni `sudo -n` bilan o‘qish huquqiga
   tayanadi. Bu huquq mavjud bo‘lmasa buyruq to‘xtaydi: himoyalarni o‘chirmang,
   umumiy `NOPASSWD: ALL` qo‘shmang. Administrator alohida ruxsatlangan,
   faqat backup o‘qiy oladigan hisob/yo‘lni keyin tasdiqlashi kerak.
4. Shifrlashning private kaliti VDSda/Gitda saqlanmaydi. Public `age` recipient
   va offsite bucket nomi egasi bilan tanlanadi; bu faylda real credential yo‘q.

## Bir nusxani pull qilish — tashqi kompyuterda

Quyidagi buyruqlar VDSdan faqat o‘qiydi. `TANLANGAN_FAYL`ni readonly
inventarizatsiyada ko‘rilgan haqiqiy tayyor basename bilan almashtiring.
`SHA256_KUTILGAN` — o‘sha fayl uchun serverdan olingan 64 belgili hash.

```bash
set -euo pipefail
set -o noclobber
umask 077
mkdir -p ./topshinalar-offsite/incoming
cd ./topshinalar-offsite/incoming

# Serverda faqat tanlangan tayyor nusxaning hashini o‘qish:
ssh -o BatchMode=yes ubuntu@46.8.114.124 'sudo -n -u topshinalar sha256sum /var/lib/topshinalar/backups/TANLANGAN_FAYL.sqlite3'

# Serverga fayl yaratmaydi yoki live bazani ochmaydi:
ssh -o BatchMode=yes ubuntu@46.8.114.124 'sudo -n -u topshinalar cat /var/lib/topshinalar/backups/TANLANGAN_FAYL.sqlite3' > TANLANGAN_FAYL.sqlite3.partial
```

SSH exit code 0 bo‘lmasa davom etmang. Qisman olingan fayl tayyor backup deb
nomlanmasin. Har ishga tushirish uchun yangi basename tanlab, oldingi
`.partial` yoki tayyor nusxaning ustiga yozmang (`set -o noclobber` ishlatish mumkin).

```bash
printf '%s  %s\n' 'SHA256_KUTILGAN' 'TANLANGAN_FAYL.sqlite3.partial' | sha256sum -c -
```

Faqat hash mos kelgach, tasdiqlangan repo katalogidan tashqi nusxani tekshiring.
Quyidagi funksiya tanlangan nusxani o‘zgartirmaydi: yonida alohida vaqtinchalik
restore yaratadi, schema va barcha jadvallarni solishtirib, test faylini yopadi.
Bu productionga restore qilish buyrug‘i emas.

```bash
python3 -c 'from backup import verify_restore; import sys; result=verify_restore(sys.argv[1]); print("RESTORE_OK",len(result),"tables")' /TO‘LIQ/YO‘L/TANLANGAN_FAYL.sqlite3.partial
```

## Shifrlash va ikkinchi tashqi joy

Ushbu qism ham tashqi kompyuterda bajariladi. Avval haqiqiy public recipient
va offsite accountning autentifikatsiyasini administrator sozlaydi.

```bash
age -r AGE_PUBLIC_RECIPIENT -o TANLANGAN_FAYL.sqlite3.age TANLANGAN_FAYL.sqlite3.partial
sha256sum TANLANGAN_FAYL.sqlite3.age > TANLANGAN_FAYL.sqlite3.age.sha256
aws --profile client-backup s3 cp TANLANGAN_FAYL.sqlite3.age s3://BACKUP_BUCKET/topshinalar/TANLANGAN_FAYL.sqlite3.age --sse AES256
aws --profile client-backup s3 cp TANLANGAN_FAYL.sqlite3.age.sha256 s3://BACKUP_BUCKET/topshinalar/TANLANGAN_FAYL.sqlite3.age.sha256 --sse AES256
```

Bucket public emas; versioning va imkon bo‘lsa Object Lock yoqiladi.
Backup yozish hisobiga delete huquqi berilmaydi. Shifrlangan nusxani qayta
yuklab olib checksum va alohida saqlangan kalit bilan decrypt/restore tekshiruvi
o‘tkazilmaguncha offsite saqlash tasdiqlangan hisoblanmaydi.

Har kuni timer runidan keyin shu jarayonni tashqi host jadvali bilan bajaring.
Exit code, backup va offsite obyekt nomi, original/encrypted SHA256, vaqt va
restore natijasi qayd qilinadi; xatoda mas’ul operatorga ogohlantirish kerak.
Kalit yoki mijoz ma’lumotlari logga chiqmasin.

Taklif etiladigan saqlash siyosati: kamida 30 kunlik va 12 oylik nusxa;
retention/delete alohida tasdiqlanadi, ushbu loyiha backup’larni o‘chirmaydi.
Maqsad RPO ≤24 soat; RTO actual restore mashqida o‘lchanadi. Har oy izolyatsiyalangan
hostda shifrlangan offsite nusxani yuklab olish → decrypt → integrity/FK →
schema/jadvallar → test ilova ishga tushishi mashqi bajarilsin. Production token
yoki haqiqiy Telegram jo‘natish ishga tushirilmasin. DBni `/var/lib/topshinalar`
ustiga ko‘chirish ushbu sinovning bir qismi emas.
