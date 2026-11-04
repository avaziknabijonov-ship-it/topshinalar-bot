# Direktor kabineti va bir tomonlama katalog sinxronlash

Bu hujjat draft feature uchun. Productionga qo‘llanmadi; iBox integratsiyasi yo‘q.
Sayt tomoni: [Topshinalar feature branch](https://github.com/avaziknabijonov-ship-it/Topshinalar/tree/feature/bot-catalog-sync).

## Tekshirilgan boshlang‘ich holat

2026-11-04: bot `main` — `e532fb66b098a47d4161aade8fd1d7fed5f3fb79`.
Ikkala checkout daraxtida AGENTS.md topilmadi. Branchlar va eng so‘nggi PRlar tekshirildi.
Bot PR #19 umumiy Excelga menejer/ta’minotchi jurnallarini qo‘shgan; qayta yozilmadi.
#17 ko‘chirishni, #18 alohida joy-turi tugmasini olib tashlagan. Ko‘chirish yangi kabinetda
partiya kelib chiqishini saqlaydigan tranzaksiya bilan qaytarildi. Eski bot buyruqlari o‘chirilmadi.
Mavjud `ACCOUNTING-UZ.md` ichidagi eski tugma tavsifi kodga mos kelmasligi aniqlandi.
Eski JS testi shu olib tashlangan tugmani chaqirardi; RU tekshiruvi amaldagi kirim joyi tanloviga ko‘chirildi.

Bot `core.py`/`accounting.py`/`miniapp.py` va bitta SQLite biznes bazasi bilan qoladi.
Direktor kabineti shu MiniServerdagi `/director`; sayt bazasi mustaqil ommaviy nusxa.
Sayt Vinext/Vite, Cloudflare Workers, D1 `DB`, R2 `BUCKET`. Hosting identifikatori va audience o‘zgartirilmadi.
Saytning mavjud admin autentifikatsiyasi saqlandi. Kabinet ChatGPT login talab qilmaydi.

## Tayyor imkoniyatlar

- Desktop va kichik ekranlar; UZ/RU tanlovi; qidirish, 25 qatorli sahifalash, bo‘sh/yuklanish/xato holatlari.
- Davrdagi faol savdo summasi, davrda tushgan/qaytarilgan pul; joriy mijoz qarzi/kechikkan qarz;
  har valyutada ta’minotchi saldosi; faqat o‘rnatilgan minimum va ma’lum qoldiq asosidagi kam qolgan mahsulotlar; audit.
  Kartalar tegishli savdo/to‘lov/qaytarish/qarz operatsiyalarini ochadi.
- Savdolarda davr, mijoz, menejer, mahsulot va to‘lov holati; tafsilot va to‘lovlar;
  mavjud xavfsiz bekor qilish: olingan pulni qaytarish tasdig‘i, `expected_paid`, sabab va asl partiyaga qaytarish.
- Joylar bo‘yicha qoldiq, kirimlar va partiyalar, ta’minotchiga qaytarish; joy turi;
  partiya/tannarx/ta’minotchini saqlaydigan ombor ↔ vitrina ko‘chirish.
- Inventarizatsiya: joriy/haqiqiy son/farq, sabab, ikkinchi tasdiq, parallel o‘zgarishda rad etish, audit.
- Mijoz kartasi, savdo/to‘lov/qarz tarixi va mavjud CRM vazifa/qo‘ng‘iroq yozish; qarz to‘lovi va muddati.
- Ta’minotchi kartasi, jurnal va valyutalar bo‘yicha saldo; kirim/to‘lov/qaytarish mavjud hisob modellarini ishlatadi.
- Menejer: berilgan, sarflangan, qaytarilgan, joriy saldo; mas’ul menejer va yozuv muallifi.
- Mavjud xodim takliflari, aktivlik va rol boshqaruvi, davrdagi savdo natijasi; audit.
- Mavjud Excel hisobot bo‘limlari va KP PDF yuklash. Balanslar/qoldiqlar joriy, operatsiyalar davr bo‘yicha.
- Bot menyusida direktor uchun bitta `📊 Direktor kabineti`; kundalik xodim tugmalari va eski buyruqlar qoladi.

## Kirish va xavfsizlik

`PUBLIC_APP_URL` — MiniServerga yo‘nalgan HTTPS origin, yo‘lsiz.
Telegramda mavjud HMAC bilan tasdiqlanadigan initData faqat faol direktor uchun 5 daqiqagacha qabul qilinadi.
Bir initData sessiyaga faqat bir marta almashtiriladi. Yangi kompyuter cookie sessiyasi 8 soat amal qiladi. Telegram sessiyasi 1 soatgacha.
Telegram Web iframe cookie cheklasa, mavjud signed initData headeri serverda ro‘yxatdan o‘tgan,
bekor qilinadigan sessiya sifatida ishlatiladi; har so‘rov bir martalik nonce bilan.
Yangi frontend bearer tokeni berilmaydi. Logout raw initData sessiyasini ham bekor qiladi.

Kompyuterda `/director`: kod olish → brauzerdagi `/cabinet_login KOD`ni aynan o‘z botiga yuborish → brauzerga qaytish.
Kod 180 soniyalik, bir martalik; faqat oldindan ruxsat berilgan faol direktor tasdiqlaydi.
Tasdiqlash kodi brauzerning tasodifiy HttpOnly cookie hashiga bog‘langan; boshqa brauzer uni poll qilib ololmaydi.
Login urinishlari va poll cheklangan. Kod/haqiqiy sessiya tokeni URLga yoki logga yozilmaydi.

Cookie: `__Host-`, `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`.
Har direktor API so‘rovida bazadagi faol direktor roli tekshiriladi.
Har cookie POSTda qat’iy Origin va sessiyaga bog‘langan CSRF header talab qilinadi.
Logout serverdagi sessiyani o‘chiradi. `users.active=0` yoki direktor rolidan tushirish triggeri sessiyalarni o‘chiradi;
qayta faollashtirish eski sessiyani tiklamaydi. Xodim initData’si direktor APIga yo‘l ochmaydi.
MiniServer mavjud `configure()` oqimi vaqtincha barcha foydalanuvchilarni o‘chirishi sababli servis keyinchalik qayta ishga tushirilganda
brauzer sessiyalari ham qayta tasdiqlashni talab qilishi mumkin.
Nginx MiniServerni internetga to‘g‘ridan-to‘g‘ri chiqarmasin; tashqarida HTTPS bo‘lsin.

## Migratsiya

`Store`ga ikkita yangi additive migratsiya chaqiruvi qo‘shilgan; avvalgi migratsiyalar qayta yozilmadi.
Har yangi migratsiya `BEGIN IMMEDIATE`/savepoint va bitta tranzaksiyada, qayta bajarishga xavfsiz.

- `website_products`: direktorning nashr, USD sent, kategoriya/model, UZ/RU tavsif, joy va rasm tasdiqlari.
- `catalog_outbox`: har mahsulotning manba versiyasi, yuborilgan versiya, urinish, keyingi urinish, muvaffaqiyat/xato.
- `catalog_images`: tasdiqlangan rasm ref-hashi → ommaviy content hashli yo‘l.
- `director_sessions`, `director_logins`, `director_replays`, `director_limits`, `director_telegram_sessions`, `director_request_nonces`: vaqtinchalik xavfsizlik yozuvlari.
- Mahsulot/qoldiq/galereya/sayt-sozlama triggerlari shu biznes tranzaksiyasida outboxni o‘zgartiradi.

Eski mahsulot, narx, mijoz, savdo, to‘lov, qarz, ombor, qoldiq va partiyalar almashtirilmaydi/o‘chirilmaydi.
Yangi katalog mahsulotlari avtomatik nashr qilinmaydi. Aniq tanlangan joylar bo‘lmasa yoki ularning qoldig‘i belgilanmagan bo‘lsa,
ommaviy mavjudlik `null`; noma’lum narx `null`. `12500` sent — `125.00 USD`. Kurs ishlatilmaydi. Direktor narx manbasini tanlaydi: botning tasdiqlangan USD narxiga ergashish yoki alohida sayt narxi.
Bot narxiga ergashishda legacy UZS yoki price_pending hech qachon USD deb olinmaydi.
Eski UZS yozuvlari USD deb qayta belgilanmaydi. Botning avvalgi KP konvertatsiya oqimi bu syncdan alohida saqlandi.

## Sozlash va bosqichma-bosqich chiqarish (bu ishda bajarilmagan)

1. Biznes SQLite’ning konsistent backupini va sayt D1/R2 nusxasini operator o‘z tartibida olsin.
   Avval staging nusxalarida migratsiya va dry-run tekshirilsin.
2. Saytda `drizzle/0001_catalog_replica.sql`ni odatiy D1 transactional migration runner orqali qo‘llash.
   Eski `0000`ni qayta ishga tushirmaslik; feature DB jadvallari koddan oldin mavjud bo‘lsin.
3. Ikki tomonga bir xil kamida 32 belgili `CATALOG_SYNC_SECRET`ni secret storage orqali qo‘ying.
   Botga `CATALOG_SYNC_URL=https://topshinalar.uz/api/sync/catalog`; mavjud `BOT_TOKEN`, `DB_PATH`,
   `PUBLIC_APP_URL` saqlansin. Saytning `ADMIN_EMAIL`, DB/BUCKET bindinglari o‘zgarmaydi.
4. **Birinchi haqiqiy DB ochilishidan oldin read-only dry-run**:
   `python catalog_sync.py --db /operator/copied.sqlite3 dry-run > /secure/catalog-inventory.json`.
   Bu `mode=ro`, Store yaratmaydi va biznes bazasiga migratsiya ham yozmaydi.
   Sync secret/URL mavjud bo‘lsa, saytning autentifikatsiyalangan inventory endpointi ham solishtiriladi.
   Endpoint faqat replay nonce yozadi; katalog/biznes yozuvlarini o‘zgartirmaydi.
   Namuna, bog‘lanmagan, legacy UZS, dublikat va narx/qoldiq farqlari alohida chiqadi.
   Noaniq mosliklarni nom/razmerdan avtomatik birlashtirish yo‘q.
5. Operator tasdiqlagach botning odatiy yangilanishi orqali additive migratsiyalarni qo‘llash.
   Kabinetda saytga chiqariladigan mahsulotlarni, USD narxlarini, joylarini va rasmlarini direktor tasdiqlasin.
6. Boshlang‘ich to‘liq snapshotlarni yuborish: `python catalog_sync.py --db "$DB_PATH" requeue`,
   keyin `python catalog_sync.py --db "$DB_PATH" once`. `requeue` faqat sync versiyalarini oshiradi.
   Birinchi qabul qilingan haqiqiy snapshot saytni real katalog rejimiga o‘tkazadi: namunalar bazada qoladi, ommadan yashiriladi.
7. Keyingi avtomatik yetkazish uchun `deploy/topshinalar-catalog-sync.service` va `.timer` namunalarini
   haqiqiy User/WorkingDirectory/venv/DB yo‘llariga moslab operator o‘rnatsin. Bu ishda ular o‘rnatilmadi/yoqilmadi.
   Har daqiqa eng ko‘pi 100 pending mahsulot; HTTPS timeout 20s; exponential backoff 5s…1h, 10 urinishdan keyin qo‘lda retry.
   Outbox SQLite’da saqlanadi, worker to‘xtasa yo‘qolmaydi. Savdo/kirim/to‘lov tarmoqni kutmaydi.
8. Solishtirishni qayta `dry-run` bilan bajarish; farq bo‘lsa `requeue` + `once` yoki kabinetdagi `Qayta yuborish`.
   Barcha qoldiqlar delta emas, to‘liq versiyalangan holat; kech kelgan xabar yangisini bosmaydi.

## Maydon egaligi va rasmlar

Saytning `bot-{source_product_id}` mahsulotlari uchun nom/brend/model/razmer/kategoriya/tavsif/rasmlar/USD sent/qoldiq/nashr
bot biznes backendi va direktor tasdiqlaridan keladi. Sayt admini bularni tahrirlay/o‘chira olmaydi.
Legacy mahsulotlar avtomatik mapping qilinmaydi. Namespace to‘qnashuvi qabul qilinmaydi, operator tekshiruvi talab qilinadi.
Banner, aloqa, kompaniya sozlamalari va mijoz so‘rovlari saytga tegishli. Ular sinxronlash payloadiga kirmaydi.

Rasm faqat mavjud bot galereyasidan server orqali olinadi; foydalanuvchi tashqi URL yuklata olmaydi.
Pillow haqiqiy rasmni decode/verify qiladi, hajm va piksel chegarasini tekshiradi, metadata olib tashlab JPEGga qayta kodlaydi.
Sayt ham JPEGni mustaqil decode qilib, MIME/strukturani, hajmni va SHA-256ni tekshiradi.
R2’da SHA-256.jpg; o‘zgarmagan Telegram ref qayta yuklanmaydi. Telegram tokenli URL/file_id ommaga yuborilmaydi.
Galereyadan o‘chirilgan rasm keyingi snapshotdan olinadi. R2 fayli avtomatik o‘chirilmaydi:
shared rasmlar havolasini buzmaslik uchun GC alohida reference tekshiruvi va operator siyosatini talab qiladi.

## Rollback

Avval sync timerini to‘xtatish; yangi biznes yozuvlarini eski backup bilan almashtirmaslik.
Receiver secretini olib qo‘yish sync yozishni yopadi, mavjud katalogni saqlaydi.
Bot UI/worker kodini avvalgi revisionga qaytarish mumkin; additive jadvallar va auditni tashlamaslik.
Saytda yangi read-only katalog filtri va replica o‘qishni saqlang: eski auto-seed kodiga ko‘r-ko‘rona qaytish namunalarni qayta ko‘rsatishi mumkin.
Jadvallarni DROP yoki mahsulotlarni DELETE qilish rollbackning bir qismi emas.
Backup restore faqat alohida avariya jarayoni, yangi operatsiyalarni kelishtirish bilan; bu feature uni bajarmaydi.

## Testlar va tekshirilmagan joylar

`python -m unittest discover -s tests -q`; mavjud to‘rtta `node tests/web/*.test.js` alohida;
`python -m compileall -q .`; `node --check web/director.js`.
`python tests/browser_director.py` — disposable bazada haqiqiy Chromium bilan 1440×1000 va 390×844,
login, bo‘limlar, narx sentlari, inventarizatsiya preview/tasdiq, RU, logout.
`docs/screenshots`dagi tasvirlar **faqat lokal test yozuvlari**, production biznes ma’lumoti emas.

Production DB/R2 o‘qilmadi yoki yozilmadi; haqiqiy inventarizatsiya/dry-run bajarilgani da’vo qilinmaydi.
2026-11-04 ommaviy `https://topshinalar.uz/api/catalog` GET HTTP 403 qaytardi; jonli katalog narx/qoldig‘i tasdiqlanmadi.
Haqiqiy Telegram Telegram-client initData bilan login, production HTTPS/cookie, real Telegram rasmlarini olish,
real Workerga cross-host yetkazish, tashqi audience va katta hajmdagi yuklama hali stagingda tekshirilishi kerak.

## Moliyaviy chegaralar va iBox’dan chiqish

Menejer pul jurnali umumiy kassa emas. Tannarx noma’lum qoldiqlarga foyda taxmin qilinmaydi.
Hozir umumiy kassa/bank bosh kitobi, cash reconciliation, bank statement import, xarajatlar to‘liq tasnifi,
soliq/QQS/chegirmalar va barcha qaytarishlarni qamrab oladigan sof foyda hisobi yo‘q.
Ta’minotchi boshlang‘ich saldosi va menejer boshlang‘ich pulini tasdiqlangan import qilish, eski tannarxlarni tiklash,
qisman mijoz tovar qaytarishi va to‘liq moliyaviy ko‘chirishni kelishtirish alohida ish.
Tizim iBox’ning to‘liq o‘rnini bosishga tayyor deb e’lon qilinmaydi.

Kelajak importi uchun CSV/XLSX eksportlarda kerak bo‘ladigan maydonlar:

- Mahsulot: tashqi ID, SKU, nom/brend/model/razmer/kategoriya, valyuta, integer sent narx,
  kirim tannarxi mavjudligi, rasm fayllari va ularning egalik/foydalanish huquqi.
- Joy/qoldiq: tashqi joy ID, ombor/vitrina turi, mahsulot ID, haqiqiy son, holat sanasi, partiya va kirim ID.
- Ta’minotchi: tashqi ID, nom/kontakt, valyuta bo‘yicha boshlang‘ich saldo va sana;
  kirimlar, to‘lov usullari, qaytarishlar va hujjat raqamlari.
- Mijoz: tashqi ID, telefon/manzil, mas’ul; savdo/hujjat ID, qatorlar, original valyuta, sent summa,
  to‘lovlar/refundlar, muddat va boshlang‘ich qarzning tasdiqlangan sanasi.
- Xodim: tashqi ID, Telegram ID bilan **operator tasdiqlagan** mapping, faol rol;
  menejer puli jurnali, berish/xarajat/qaytarish, mas’ul va yozuv muallifi.
- Kassa/bank: hisob ID, valyuta, ochilish saldosi/sanasi, tushum/chiqim/ko‘chirish, kontragent/hujjat ID,
  bank reconciliation belgisi, xarajat turi va soliq maydonlari.

Eksport hozir mavjud emas; import bajarilmadi. Keyingi migratsiya stagingda dry-run, explicit ID mapping,
valyuta va opening balances reconciliation, tasdiqlash va audit bilan alohida tayyorlanadi.

## Tekshirish natijasi (2026-11-04)

Python unit/integratsion suite, to‘rtta mavjud JS tekshiruvi, compileall va Chromium smoke o‘tdi.
Sayt hamkor branchida API/locale testlari, TypeScript va Vinext build o‘tdi.
CI holati draft PRda alohida ko‘rsatiladi; lokal natijalar CI natijasi deb berilmaydi.
