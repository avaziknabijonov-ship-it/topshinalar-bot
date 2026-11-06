# TOPSHINALAR: mijozga topshirish auditi

Audit sanasi: 2026-11-06. Ish branchi: `audit/client-handoff`.
Bu branch `fix/quotation-photo-row-alignment` (`eca8218d10de24412fc200a05f8a880af62422ca`)
ustiga qurilgan. Main o‘zgartirilmadi; production deploy/restart va biznes bazasiga
yozish bajarilmadi. iBox integratsiyasi qo‘shilmadi.

## Topshirish holati

| Holat | Qism | Dalil / qolgan shart |
|---|---|---|
| PASS | Xususiy hujjatlar uchun kod | PDFlar static allowlistdan va bu branch tipidan olib tashlandi; yangi yo‘l faol xodim/direktor autentifikatsiyasini tekshiradi. |
| BLOCKER | Production hujjatlari | Audit boshida ikkala eski URL autentifikatsiyasiz HTTP 200 qaytardi. Production o‘zgartirilmagan, shuning uchun xavf yopilgan deb bo‘lmaydi. |
| BLOCKER | Public Git tarixi | Main va eski branchlar original PDFlarni saqlaydi. Branch tipidan o‘chirish tarixni yo‘qotmaydi. |
| BLOCKER | Main CI | Main `e532fb66b098a47d4161aade8fd1d7fed5f3fb79` dagi oxirgi push CI yiqilgan. Tuzatish bu branchda; main uchun alohida merge tasdig‘i kerak. |
| TEKSHIRILMAGAN | Joriy VDS versiyasi va xizmatlar | SSH credential/VPN yo‘q. Avvalgi skrinshot yangi jonli tekshiruv o‘rnini bosmaydi. |
| TEKSHIRILMAGAN | VDS backup timeri va offsite nusxa | Unit namunalari tekshirildi; haqiqatan o‘rnatilgani, oxirgi run va tashqi nusxa borligi serverdan tasdiqlanishi kerak. |
| PASS | Test bazasidagi biznes oqimi | `tests/test_handoff_flow.py`: kirim, provenance saqlaydigan transfer, savdo, to‘lov/retry, refund, ta’minotchiga qaytarish, menejer qabul/yopish, Excel va alohida bazaga restore. |
| TEKSHIRILMAGAN | Haqiqiy Telegram / mobil qurilmalar | Lokal browser sinovi haqiqiy Telegram, Safari/iOS/Android va direktor chatidagi yetkazishni tasdiqlamaydi. |

CI natijasini aynan yakuniy commitning GitHub Actions tekshiruvlaridan oling.
Lokal test natijasi CI sifatida ko‘rsatilmaydi. Shu blockerlar yopilmaguncha
loyiha mijozga to‘liq tayyor deb e’lon qilinmaydi.

## 1. Company PDFlar va tarixdagi nusxalar

`company-registration.pdf` va `vat-registration.pdf` ro‘yxatdan o‘tish/soliq
guvohnomalari; ularda tekshirish identifikatorlari va QR ma’lumotlari mavjud.
Ochiq tarqatish uchun alohida tasdiq qayd etilmaganligi sabab yopiq hujjat
sifatida boshqarildi. Hujjat matni, shaxsiy ma’lumot yoki original PDF test
fixturelariga/ushbu hisobotga ko‘chirilmagan.

Ularning `company-registration.png` va `vat-registration.png` nusxalari ham
shu katalogda topildi va olib tashlandi. Faqat PDFni o‘chirish hujjat mazmunini
yopmagan bo‘lardi. Butun `assets/quotation-attachments` katalogi Git va Docker
ignore’iga kiritildi; image smoke sinovi unda hech qanday fayl yo‘qligini tekshiradi.

Eski yo‘llar: `/company/registration.pdf`, `/company/vat.pdf`.
Ular endi public static fayllar emas. Telegram imzosi yoki haqiqiy direktor
sessiyasi tekshiriladi; noma’lum/deaktiv hisob, buzilgan/eskirgan imzo va
begona Origin rad etiladi. Har so‘rovda faol hisob qayta tekshiriladi.
Fayl `attachment`, `Cache-Control: no-store`, `nosniff` bilan qaytariladi.

`COMPANY_DOCUMENTS_DIR` sukut bo‘yicha bo‘sh: autentifikatsiyadan keyin ham
404 qaytadi. Hujjatlar zarur deb tasdiqlansa, keyingi ruxsatli o‘rnatishda
ularni checkout va Nginx web-rootidan tashqaridagi maxsus yopiq katalogda
saqlash kerak, masalan `/var/lib/topshinalar/private-documents`. Katalog
faqat xizmat hisobiga ochiq, fayllar 0600 yoki yopiq xizmat guruhi bilan
0640 bo‘lishi kerak. Original fayllarni public Git’dan qayta yuklab olishni
xavfsiz saqlash strategiyasi deb hisoblamang; egadan ishonchli nusxa oling.

Fayl nomlari serverdagi ikki elementli mapping orqali tanlanadi. URL/query
ixtiyoriy fayl tanlay olmaydi. Symlink, 8 MiB’dan katta, oddiy fayl bo‘lmagan
va PDF sarlavhasi bo‘lmagan kontent rad etiladi. Repo ichiga fallback yo‘q.
Public `/company` QR kontakt sahifasi qoladi, lekin PDF linklari olib tashlandi.

MiniApp xodimi faylni o‘zining amaldagi `X-Telegram-Init-Data` headeri bilan
oladi; direktor shu header yoki amaldagi cookie sessiyasidan foydalanadi.
Tokenni URLga yozish, doimiy imzosiz download URL yoki public fayl nusxasi yo‘q.
Bu o‘zgarish hujjatni barcha mijozlarga avtomatik yubormaydi.

Original fayllar Git tarixida `934e177` commitida paydo bo‘lgan. Auditda
main va ko‘plab tarixiy branchlar bu commitni saqlayotgani tasdiqlandi.
Tarixni tozalash doirasi shu ikki PDF bilan birga ikkala PNG nusxasini ham qamrasin.
Keyingi majburiy choralar:

1. Egasi har hujjatning tarqatish tasnifini tasdiqlaydi; kimda nusxa borligini baholaydi.
2. Alohida production o‘zgarishi tasdiqlangach, eski HTTP yo‘llari yopiladi va
   anonim 403/404, ruxsatli kirish hamda deaktiv hisob rad etilishi tekshiriladi.
3. Hujjatlar maxfiy bo‘lsa, alohida tarix-tozalash roziligi olinadi. Main,
   barcha branch/tag, PR ref, release/artifact va ehtimoliy image/cache nusxalari
   inventarizatsiya qilinadi. GitHub Support bilan cached view/PR ref nusxalari
   bo‘yicha ishlanadi; hamkorlar yangi toza clone oladi.
4. Force push, branch o‘chirish, repo visibility o‘zgarishi va tarixni qayta yozish
   ushbu auditda bajarilmagan. Oddiy delete commit eski blob URLlarini bekor qilmaydi.
   Fork/avval yuklab olingan nusxalarni to‘liq qaytarib olish kafolatlanmaydi.

## 2. Main’dagi CI sababi

Run: https://github.com/avaziknabijonov-ship-it/topshinalar-bot/actions/runs/41832718897

Job `126583686553`, `tests/web/accounting.test.js:52`: `/Витрина/` topilmadi.
Test olib tashlangan `point-kind` actionini chaqirgan, natijada yangi forma
ochilmagan va `captured` oldingi supplier-return formasini saqlab qolgan.
Bu bir xil main commitining alohida checkoutida ham qayta takrorlandi.

PR #20 da mavjud bo‘lgan dastlabki test tuzatishi bu kumulyativ branchga kiradi.
Qo‘shimcha regressiya o‘chirilgan action `false` qaytarishi va umuman forma
ochmasligini, amaldagi kirim formasi esa UZ/RU joy tanlovlari bilan ochilishini
tekshiradi. CI barcha `tests/web/*.test.js` fayllarini Node 22 bilan bajaradi.
Python to‘plami, Docker build va network’siz runtime import sinovi ham CIga kiradi.

## 3. Funksiyalar va main’ga kiritish

GitHub’da #1–19 merged. Ularning eski branchlari squash/rebase sabab ayrim
tarixiy SHA’larni alohida saqlasa ham, ularni qayta merge qilish kerak emas.
Quyidagi ochiq PRlar bitta ketma-ket zanjir; ularning barchasi audit branchida bor.

| PR | Branch / head | Mijozga kerakli qism | Main holati |
|---|---|---|---|
| #20 | `feature/director-catalog-sync` / `09f55ae` | Direktor kabineti, Telegram/desktop autentifikatsiya, ombor–vitrina, audit | Kiritish kerak |
| #21 | `feature/manager-receipts-day-close` / `25ff84e` | Naqd/karta/bank tushumi, haqiqiy kollektor, direktor qabul qilishi, yopilmagan kun | Kiritish kerak |
| #22 | `feature/director-premium-imports` / `c4d5533` | Excel/PDF import preview/confirm, filtrlar, mijoz create/edit, qarz tarixi, tanlangan hisobotlar | Kiritish kerak |
| #23 | `feature/director-business-sections` / `f5c0778` | Mahsulot, kirim, xarajat va qaytarish bo‘limlari | Kiritish kerak |
| #24 | `feature/employee-own-sales-history` / `cbaa474` | Faqat o‘z savdosi/mijoz moliyasi, kunlar, qarz va direktor xodim kartasi | Kiritish kerak |
| #25 | `feature/dashboard-product-employee-analytics` / `027634a` | Tovar va xodim bo‘yicha ikki tahlil | Kiritish kerak |
| #26 | `feature/employee-debt-receipts` / `922e1e1` | Haqiqiy qarz to‘lovi, usul, qolgan qarz, xavfsiz retry | Kiritish kerak |
| #27 | `feature/director-debt-payment-notifications` / `740a701` | Bitta aniq direktorga qarz-to‘lov bildirishnomasi | Kod kerak; Telegram ID hali tanlanmagan |
| #28 | `feature/premium-unified-workspace` / `e11b546` | Premium desktop/mobile, drawer, fokus/loading/error holatlari | Kiritish kerak |
| #29 | `feature/uz-ru-localization-quality` / `dc65439` | UZ/RU katalog, forma/xatolar/Excel, login/logout/retry | Kiritish kerak |
| #30 | `fix/quotation-photo-row-alignment` / `eca8218` | KP nom/narx markazda, kafolat kelishilgan holda | Kiritish kerak |
| Audit | `audit/client-handoff` | Xususiy PDF, legacy pay ruxsati, backup, CI va topshirish sinovi | Alohida tasdiq bilan |

Main’dan audit parentigacha 17 ta commit bor. Bitta kumulyativ audit PRini
main bilan ko‘rib chiqish dependency zanjirini saqlaydi. Uning tasdig‘i eski
PRlarni ko‘r-ko‘rona alohida merge qilish degani emas. Main’ga push/merge uchun
alohida foydalanuvchi tasdig‘i talab qilinadi.

Auditda yana `pay` eski komandasidan foydalanib boshqa xodim savdosiga pul
yozish yo‘li yopildi: yangi yozuvda Core, retry/cache javobidan oldin MiniService
egalikni tekshiradi. Direktor boshqa xodim savdosiga ham haqiqiy kollektor
sifatida yozishi mumkin. Testlar bu ajratishni va eski bot komandasini tekshiradi.

Umumiy kontakt tanlash katalogi oldingi talabga muvofiq saqlangan; xodimning
moliyaviy tarixi, qarz va eksporti esa actor bo‘yicha cheklangan. Bu “butun
kompaniya kontaktlari ham yashirin” siyosati deb talqin qilinmasin.
UZS tarixiy qiymatlar USD deb qayta belgilanmaydi; valyutalar alohida.

Chegaralar: umumiy kassa/bank bosh kitobi va to‘liq sof foyda yo‘q; sinovdagi
mijoz qaytarishi butun savdoni tasdiqli bekor qilish/refund orqali bajariladi,
qisman invoice-row qaytarishi deb ko‘rsatilmaydi. Sayt sync kodi oldingi branchdan
meros bo‘lib bor, lekin ushbu auditda yoqilmadi va sayt deploy qilinmadi.
iBox kerak emas va topshirish sharti hisoblanmaydi.

## 4. Backup va serverdan tashqari saqlash

`backup.py` SQLite backup API va read-only source orqali izchil WAL snapshot
oladi. Fayl 0600, yangi katalog 0700. Endi to‘liq `integrity_check` va
`foreign_key_check` nashrdan oldin bajariladi. `--verify-restore` berilganda
alohida vaqtinchalik bazaga tiklash, schema va barcha domain jadvallarini
500 qatordan solishtirish ham tayyor nomga rename’dan oldin bajariladi.
`WITHOUT ROWID` composite-key jadvali ham tekshiriladi. Xato bo‘lsa oldingi
backup va source o‘zgarmaydi; eski backup’lar avtomatik o‘chirilmaydi.

Unit: `User/Group=topshinalar`, `UMask=0077`, `NoNewPrivileges`, `PrivateTmp`,
`ProtectHome`, `ProtectSystem=strict`, kerakli data katalogiga yozish ruxsati.
Timer: `03:00 Asia/Tashkent`, 0–300 soniya jitter, `Persistent=true`.
Bu UTC’da oldingi kun 22:00–22:05. `systemd-analyze calendar` bilan sintaksis
tekshirildi. Bu unit/timer VDSga o‘rnatilgani yoki enabled ekaniga dalil emas.

Servis backup yo‘li `/var/lib/topshinalar/backups`; avvalgi qo‘lda olingan
skrinshot nusxalari `/var/backups/topshinalar` da. Ular bir xil jarayon emas.
Offsite upload, xatoda operatorga ogohlantirish va real restore mashqi VDSdan
tasdiqlanmaguncha bajarilgan deb belgilanmaydi.

Serverdan tashqaridagi aniq pull/encrypt/restore yo‘riqnomasi:
[BACKUP-OFFSITE-UZ.md](BACKUP-OFFSITE-UZ.md).

## 5. Version va production uchun faqat read-only dalillar

Oxirgi muvaffaqiyatli deploy skrinshoti: **`dc654390a0393d53d6dd42d0fec4f1e979e32ade`**.
Unda 43 eski jadval saqlangani va ikki servis active/running ekani ko‘rsatilgan.
Bu audit yangi VDS sessiyasini ochmagan. KP #30 va audit tuzatishlari hozirgi
serverga o‘rnatilgan deb taxmin qilinmaydi. Yakuniy commit SHA va unga bog‘langan
CI URL topshirish javobida alohida beriladi; actual server SHA tekshirilmagan.

VDSda quyidagilarni ishlatish kifoya; hech biri deploy, restart, backup yaratish
yoki bazaga yozish buyrug‘i emas. `.env`ni to‘liq chiqarib yubormang.

```bash
systemctl show topshinalar.service topshinalar-miniapp.service topshinalar-backup.service topshinalar-backup.timer --no-pager -p Id -p ActiveState -p SubState -p UnitFileState -p User -p WorkingDirectory -p Result -p ExecMainStatus -p LastTriggerUSec -p NextElapseUSecRealtime
systemctl cat topshinalar-backup.service topshinalar-backup.timer --no-pager
sudo journalctl -u topshinalar-backup.service --no-pager -n 20
sudo find /var/lib/topshinalar/backups /var/backups/topshinalar -maxdepth 2 -type f -name '*.sqlite3' -printf '%TY-%Tm-%Td %TH:%TM %s %m %u %p\n'
sudo sha256sum /opt/topshinalar/miniapp.py /opt/topshinalar/core.py /opt/topshinalar/quotation.py /opt/topshinalar/backup.py /opt/topshinalar/web/company.html
```

Hashlar aynan shu besh faylni tasdiqlaydi, butun source tree’ning Git SHA’sini
kafolatlamaydi: `/opt/topshinalar` avvalgi skrinshotlarda Git checkout emas edi.
Git staging katalogidagi HEADni actual deployed SHA deb ko‘rsatmang.
O‘zgartirishlarni keyin chiqarishda butun runtime manifest tekshirilsin.

## 6. Test bazasidagi qabul mezonlari

`tests/test_handoff_flow.py` faqat TemporaryDirectory bazasida ishlaydi;
Telegramga hech narsa yubormaydi. Uning tekshiriladigan qiymatlari:

- Kirim: 10 dona × 100.25 USD = 1002.50 USD ta’minotchi qarzi.
- Ombor/vitrina: 6/4, transferdan keyin 4/6; 3 dona savdodan keyin 3/4.
- Savdo: 451.50 USD; dastlab 50.25, keyin 100.25 to‘lov; qarz 301.00.
- To‘liq refund: 150.50; original to‘lovlar saqlanadi; qoldiq 4/6 ga qaytadi.
- Yangi savdo va 1 dona ta’minotchiga qaytarishdan keyin qoldiq 3/4 = 7 dona.
- Ta’minotchi saldosi 802.00 USD, mijozning joriy qarzi 201.00 USD.
- Menejerning haqiqiy 100.00 tushumi direktor qabul qilguncha uning zimmasida;
  qabuldan keyin saldo 0 va pul kuni yopiladi.
- UZ/RU Excel: savdo, tushum/refund, qarz, qoldiq, kirim/ta’minotchi/menejer
  varaqlari va aniq summalar tekshiriladi; xodim eksportida boshqa xodim
  mijoz/mahsuloti yo‘q.
- Shu test bazasidan backup va alohida restore: 3 savdo, 1 refund, schema/jadvallar
  va FK/integrity tekshiruvlari.

Mijozga yakuniy topshirish: CI yashil commitni mahkamlash, main tasdig‘i,
hujjatlar tarixiga oid qaror, alohida ruxsatli production chiqarish rejasi,
readonly VDS dalillari, offsite nusxa/restore isboti va haqiqiy qurilmalardagi
foydalanuvchi qabul sinovi bilan tugaydi.
