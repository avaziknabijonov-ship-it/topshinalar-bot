# Kabinet: Excel/PDF kirimi va premium asosiy ekran

Bu branch avvalgi direktor kabineti va menejer pul hisobi ustiga qurilgan.
VDSga avtomatik qo‘llanmagan. Main’ga merge va sayt deployi yo‘q.

## Import qayerda

Kabinet yuqorisidagi `+ Excel / PDF`, `Ombor / vitrina` yoki `Sayt katalogi` bo‘limidagi
`Excel / PDF` tugmasi. Direktor ombor/vitrina va faylni tanlaydi.

Excel uchun botdagi mavjud `InventoryExcel.preview/apply`, PDF uchun mavjud
`document_import.extract/preview/apply` ishlatiladi. Alohida import biznes mexanizmi yozilmadi.

- XLSX: 4 MiB, 2000 qatorgacha, ixtiyoriy varaq; bo‘sh XLSX shablon yuklash.
- PDF: 4 MiB, 1–5 sahifa; matn/OCR, nom/ID/dona/USD narxlarini tahrirlash.
- Preview barcha qatorlarni 100 tadan ko‘rsatadi: mos kelgan ID/yangi mahsulot,
  oldingi/kelgan/yangi son, eski narx va asl valyuta, yangi USD narx.
- Tasdiq checkboxi va alohida import tugmasi. Preview biznes yozuvlarini o‘zgartirmaydi.
- Narx/qoldiq o‘zgarsa fingerprint importni rad etadi va yangi preview kerak.
- Bir previewning apply key’i tarmoq xatosidan keyingi urinishda saqlanadi; ikki marta yozmaydi.
- Mahsulot/qoldiq/outbox mavjud bitta tranzaksiyada; eski yozuvlar o‘chirilmaydi.
- Yangi mahsulotlar saytga direktor tasdiqlamaguncha chiqarilmaydi.

Bu **ta’minotchisiz kirim**: kelgan dona qo‘shiladi, USD sotuv narxi yangilanadi.
Importdan xarid tannarxi, ta’minotchi qarzi yoki to‘lov avtomatik yaratilmaydi.
Bunday hisob uchun mavjud `Mahsulot kirimi` (ta’minotchi bilan) formasi saqlandi.

Valyuta kursi ishlatilmaydi. XLSX’da explicit currency/valyuta/валюта ustuni bo‘lsa,
USD’dan boshqa birlik rad etiladi. PDF matnida UZS/so‘m/сум ko‘rinsa, narxlar
USD deb avtomatik qo‘yilmaydi: original matn/qiymat saqlanadi, USD qiymat qo‘lda
tekshirib kiritiladi. Bo‘sh yoki noma’lum narx nolga aylantirilmaydi.

## Xavfsizlik va so‘rov chegarasi

Mavjud faol direktor auth, browser sessiya/Telegram initData, CSRF/Origin va idempotency saqlandi.
Direktor route’ida 6 MiB body faqat mavjud import komandalariga ruxsat etiladi.
Boshqa komandalar va auth endpointlarida 64 KB cheklov saqlanadi.
Mavjud import modullari haqiqiy fayl tarkibi, arxiv o‘lchami, formulalar, qatorlar, miqdor va narxni tekshiradi.
Excel/PDF xatolari direktor uchun tushunarli qaytariladi; fayl/tokenlar logga yozilmaydi.

PDF uchun VDSda mavjud Poppler (`pdfinfo`, `pdftotext`, `pdftoppm`), skaner PDFlar uchun
Tesseract va eng/rus/uzb tillari kerak. Bu dasturlar yo‘q bo‘lsa mavjud modul tushunarli xato beradi;
faylni qabul qilib soxta muvaffaqiyat ko‘rsatmaydi.

## Premium dashboard

Navy/gold ranglar, SVG navigatsiya ikonkalari, tartibli moliyaviy kartalar,
sana presetlari (bugun/7/30 kun), haqiqiy ma’lumot asosidagi grafik va mobil maket.

- Davrdagi faol savdolar va haqiqiy tushumlar, qaytarilgan pul va sof tushum.
- Joriy USD mijoz qarzi va har valyutada menejer topshirmagan pul.
- Yopilmagan pul kunlari, pending topshirishlar, kechikkan qarz, ma’lum qoldiq asosidagi low-stock.
- Joriy ta’minotchi saldosi, oldindan to‘langan summalar alohida valyutalarda.
- Davrdagi oxirgi savdolar, audit va ishlaydigan operatsiya havolalari.
- Grafik faqat USD; 45 tadan ko‘p guruh yo‘q, uzoq davrlar guruhlanishi ochiq yozilgan.
  Bo‘sh davrda soxta grafik/foiz/raqam yo‘q. Jadvaldan aniq summalarni ko‘rish mumkin.
- Bir nechta so‘rov ketma-ket yuborilganda eski javob yangi filtr holatini bosmaydi.

Menejer qarzi va ta’minotchi saldosi boshqa valyutadagi kredit bilan net qilinmaydi.
Umumiy kassa/bank va sof foyda uydirilmaydi; hisoblashga ma’lumot yetishmasligi ko‘rsatiladi.

## Yangilash va rollback

Yangi schema, secret yoki Python dependency talab qilinmaydi. Menejer pul branchidagi
migratsiya bu branch bilan birga keladi, agar VDS hali `09f55ae` bo‘lsa uning oldingi
runbook’i ham qo‘llanadi. Hozirgi server kodini aniq tekshirib, fresh konsistent backup va
backup nusxasida migratsiya/data-preservation testidan keyin operator runtime fayllarni yangilaydi.
Auto-update taymerini hozircha o‘chiq saqlash kerak — main’da bu branchlar yo‘q.

Bu bosqichdagi runtime fayllar: `director.py`, `director_overview.py`, `miniapp.py`,
`excel_import.py`, `document_import.py`, `web/director.html`, `web/director.css`,
`web/director.js`, `web/director-overview.js`, `web/director-import.js`,
`web/app.js`, `web/document-import.js` (eski UI’da ham eski narxning asl valyutasi).
Oldingi manager-money branch hali o‘rnatilmagan bo‘lsa, uning runtime fayllari ham paketga kiradi.

UI rollback eski HTML/CSS/JS va direktor projection fayllarini qaytarish orqali mumkin;
import qilib bo‘lingan biznes yozuvlarini avtomatik o‘chirish yoki bazani eski backup bilan
almashtirish mumkin emas. Menejer pending handoverlari uchun oldingi runbook’dagi rollback
cheklovi saqlanadi. Hosting ID, audience, env va mahalliy deployment skriptlari o‘zgarmaydi.

## Tekshirish

Python unittest, mavjud 4 JS tekshiruvi, compileall va yangi JS syntax.
Haqiqiy Chromium’da desktop 1440×1000 va mobil 390×844:
Excel preview/unchecked-confirm/commit, PDF extraction/edit/preview/commit,
USD sentlari va ombor soni, dashboard, mavjud login/sessiya/logout va pul kunini yopish.
Yangi HTTP testlar: 64 KB’dan katta XLSX, duplicate/stale import,
permission/CSRF/revocation, real PDF, original UZS va explicit UZS fayl narxining himoyasi,
empty template, tarixiy davr va joriy qarz ajratilishi, bounded chart va valyutalar alohidaligi.

`docs/screenshots/premium-*` — faqat disposable lokal test yozuvlari.
Production fayl importi yoki production UI yangilanishi bu ishda bajarilmadi.

## Filtrlar, mijozlar va qarz tarixi

- Ombor joyi, brend, razmer, mavjud/tugagan/noma’lum qoldiq va valyuta.
- Savdoda mijoz, menejer, mahsulot, qarz/to‘langan, faol/bekor qilingan, valyuta.
- Mijozlarda mas’ul, qarzli/qarzsiz/kechikkan va qarz valyutasi; ta’minotchida valyuta va qarz/avans.
- Menejerda xodim, valyuta, operatsiya; xodimda rol/faollik; katalogda brend/sync.
  Qidirish va filtrlar serverda sahifalashdan oldin ishlaydi, bo‘lim almashganda saqlanadi.
- Mijoz qo‘shish/tahrirlash direktor huquqi bilan, o‘zgartirilgan yozuv reviziyasi tekshiriladi:
  boshqa brauzerdagi yangi tahrirni eski forma bosib ketmaydi. Bog‘liq savdo/to‘lovlar saqlanadi.
  Mas’ul xodim nom bilan tanlanadi; yangi mas’ul faol bo‘lishi kerak. Audit va idempotency saqlangan.
- Oddiy jadvallar, tafsilotlar, import preview va direktor Excel eksportida ichki ID ustunlari yo‘q.
  ID bazadan/API’dan o‘chirilmagan; mahsulotlar nomiga qarab birlashtirilmagan.
  Partiya raqami kiritish o‘rniga mahsulot/ta’minotchi/joy/sana/son orqali tanlanadi.
- Mijoz va ta’minotchi kartasida joriy qarz, davr boshidagi qarz, xronologik operatsiya,
  summa, qarz o‘zgarishi, har amaldan keyingi qoldiq va davr oxiri alohida.
  Ta’minotchining hisob sanasi va amalda kiritilgan vaqt ikkalasi ko‘rsatiladi.
  Eski savdo `paid` qiymati bilan alohida to‘lov yozuvlari mos kelmasa ogohlantirish chiqadi;
  yo‘q tarix taxmin bilan tiklanmaydi. Qarz muddati va savdo sanasi joriy mijoz qarzida ko‘rinadi.

## Tanlanadigan Excel kategoriyalari

`GET /director-api/report-categories` — ruxsat tekshirilgan 15 kategoriya.
`GET /director-api/report?start=YYYY-MM-DD&end=YYYY-MM-DD&categories=clients,suppliers`
— faqat tanlangan bo‘limlar. `all` yoki parametr yo‘q bo‘lsa barcha bo‘limlar.
Bo‘sh/noma’lum kategoriya rad etiladi. Interfeysda bir nechta checkbox va Barchasi mavjud.

Savdo va mahsulotlar, tushum/refund, joriy mijoz qarzi, ombor/vitrina, harakatlar,
mijozlar va qarz tarixi, ta’minotchilar va qarz tarixi, kirim/partiyalar, menejer puli,
xodim/smena/jarima, CRM, KP, yetkazish, sayt katalogi/sync, audit.
Tranzaksiyalar sana oralig‘ida; joriy qoldiqlarda `as_of` bor. Tarixdagi boshlang‘ich
saldo oldingi real operatsiyalardan olinadi. Har valyuta alohida qator, konvertatsiya yo‘q.
Eksport bitta read snapshot’dan, ichki ID va autentifikatsiya ma’lumoti chiqarilmaydi.
Joriy katalog narxi bo‘limida `price_cents` faqat saytga alohida belgilangan USD narx;
`price_mode` bot narxidan foydalanish holatini ajratadi.

Qo‘shimcha runtime fayllari: `director_business.py`, `director_reports.py`, `staff.py`,
`core.py`, `i18n.py`, `reports.py`, `web/director-business.js`.
Bu qo‘shimchalar yangi migratsiya yoki secret talab qilmaydi. Oldingi menejer pul migratsiyasi
va rollback cheklovlari saqlanadi. Mijoz tahriri va importlar qaytarilganda eski DB backupni
avtomatik tiklamang: undan keyingi haqiqiy savdo va to‘lovlar yo‘qoladi.

Qo‘shimcha testlar: parallel/eskirgan mijoz tahriri, direktor/xodim huquqi, faol bo‘lmagan mas’ul,
client-save idempotency, mijoz qarzi/pay/refund/cancel, tarix yetishmovchiligi ogohlantirishi,
2500−1000−500 ta’minotchi hisobi, oldinroq sanali yozuvlar, valyuta alohidaligi,
joriy qoldiqning tarixiy davrdan mustaqilligi, tanlangan va barcha Excel varaqlari, ID yo‘qligi.
Chromium’da mijoz yaratish/tahrirlash, nomli filtr, qarz tarixi va tanlangan haqiqiy XLSX yuklash.
`director-stock-filters.png`, `director-debt-history.png`, `director-report-categories.png`
rasmlari ham faqat vaqtinchalik test bazasidan.
