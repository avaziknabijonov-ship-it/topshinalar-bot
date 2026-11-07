# UZ/RU matnlari va ish oqimlari tekshiruvi

`feature/uz-ru-localization-quality` #28 ustiga qurilgan. Oldingi PR’lar saqlangan.
Bu ishda production/VDS’ga o‘rnatish, restart, main merge yoki haqiqiy Telegram
xabari yuborish bajarilmagan. Ekran tasvirlari vaqtinchalik sinov bazasidan.

## Tuzatilgan kamchiliklar

- `active`, `pending`, `draft`, `employee`, `synced`, `retry_required` va boshqa
  tizim holatlari jadvallarda ichki kod holida chiqardi. Endi nomlari UZ/RU’da.
- Ayrim kartalarda `balance_after`, `receipt_qty`, `source`, `price_mode` kabi
  texnik maydonlar, amallar tarixida esa JSON matni ko‘rinardi. Maydonlar tarjima
  qilindi; audit payload’i o‘rniga amal nomi ko‘rsatiladi. Asl audit saqlanadi.
- Sana/vaqt Toshkent vaqti bilan `DD.MM.YYYY HH:MM` ko‘rinishida; pul sentlarda
  qoladi. Belgilanmagan narx yoki summa nol deb ko‘rsatilmaydi.
- To‘lov kartasidagi ombor raqami o‘rniga uning nomi, hali ismi kiritilmagan xodim
  raqami o‘rniga «Ism kiritilmagan / Имя не указано» ko‘rsatiladi.
- Asosiy filtrlar, kirish, chiqish, yordamchi yorliqlar va mobil login til tanlovi
  tanlangan tilda. «preview», «refund», «sync» kabi interfeys atamalari almashtirildi.
  Fayl formatlari (Excel/PDF/XLSX), USD/UZS, shina kategoriyalari va brend nomlari saqlanadi.
- Ruscha kabinetdan yuklangan Excel oldin akkaunt tilida chiqishi mumkin edi.
  Endi hisobot va bo‘sh import shabloni interfeys tiliga mos. Ruscha shablonni
  mavjud import parseri bilan qayta o‘qish tekshirildi.
- Excel va hujjat import xatolari tanlangan tilda. Ichki holat kodlari bazada
  tarjima qilinmaydi; faqat taqdimoti o‘zgaradi. Eski va buyurtmachi yozgan maxsus
  to‘lov nomlari, mijoz/xodim ismlari, brendlar, tavsif va izohlar o‘zgarmaydi.
- Botdagi holat tanlash tugmalari tarjima qilindi. Eski inglizcha komandalar va
  holat kodlari ham qabul qilinadi. Direktorning yagona kabinet tugmasi UZ/RU’da.
  O‘zbekcha bank to‘lovi «BANK O‘TKAZMASI», eski `PERECHISLENIYA` kiritish esa ishlaydi.
- Bot kartalaridagi pul maydonlari sentlarni ko‘rsatib yubormaydi: 12500 → 125.00 USD.
- Eski UZS savdosi qarz to‘lovi oynasida noto‘g‘ri USD deb yozilardi. Endi
  shu savdoning asl valyutasi ko‘rsatiladi; konvertatsiya yoki qayta belgilash yo‘q.
- Xodim taklifi JSON o‘rniga nusxalash mumkin bo‘lgan tartibli havola bilan chiqadi.

## Ishonchlilik

- Chiqish so‘rovi muvaffaqiyatsiz bo‘lsa, kabinet chiqilgandek ko‘rsatmaydi.
  Aniq xato va qayta urinish imkoni bor; muvaffaqiyatli chiqish server sessiyasini bekor qiladi.
- To‘lov/operatsiya saqlanib, keyingi ro‘yxat yangilanishi ishlamasa, foydalanuvchiga
  «Saqlandi» deyiladi. Qayta moliyaviy yozuv yaratmasdan ro‘yxatni yangilash mumkin.
- Login tasdig‘ini tekshirish so‘rovlari ustma-ust ketmaydi. Oldingi kirish urinishining
  kechikkan javobi yangi urinishni almashtirmaydi. Direktor API so‘rovlari cheklangan
  muddatdan keyin lokal tarmoq xabari bilan tugaydi; hujjat o‘qishga uzoqroq muddat beriladi.
- Mini App’da noto‘g‘ri HTML/buzilgan JSON javobi texnik JavaScript xatosi sifatida
  chiqmaydi. Mavjud xavfsiz qayta urinish va bir xil idempotency kaliti saqlanadi.
- Fayl/rasmni o‘qish yoki yuklab olishdagi brauzer xatolari ham foydalanuvchi tilida.
- `X-UI-Language` faqat `uz`/`ru` tanlaydi. Ruxsat, summa, valyuta yoki sessiyaga
  ta’sir qilmaydi. Akkaunt tilini ham bu header bilan o‘zgartirib bo‘lmaydi.

## Bitta tarjima manbasi

`locales/uz-ru.json` — maydonlar, holatlar, amallar, to‘lov nomlari va doimiy yorliqlar.
`ui_text.py` uni Excel va bot taqdimotida ishlatadi. `/ui-text.js` shu katalogni
`web/ui-text.js` yordamchi funksiyalari bilan same-origin JavaScript sifatida beradi.
Bu ommaviy asset’da biznes yozuvlari yoki sirlar yo‘q. Yangi tashqi kutubxona, shrift,
CDN yoki foydalanuvchi ma’lumotini tashqi xizmatga yuborish qo‘shilmagan.

## Tekshiruv

- 352 Python testi (16 ta yangi lokalizatsiya/integratsion tekshiruv), 8 ta Node suite.
- 6 ta haqiqiy Chromium ssenariysi: direktor oqimlari, ikkita analitika, xodimning
  o‘z savdolari, qarz to‘lovi, premium menyu va yangi UZ/RU matritsasi.
- Yangi matritsa: barcha 17 bo‘lim va ma’lumotli kartalar ikkala tilda; PDF yuklash,
  holat/rol/maydon tarjimasi, asl UZS yorlig‘i, saqlashdan keyingi tarmoq xatosi,
  muvaffaqiyatsiz/muvaffaqiyatli logout, mobil login til tanlovi va sekin poll.
- Oldingi brauzer tekshiruvlari: desktop/mobil, 320–1440 px, UZ/RU, login/logout,
  ruxsatlar, xodim izolyatsiyasi, Excel/PDF import, inventarizatsiya, qaytarishlar,
  tanlangan Excel kategoriyalari, haqiqiy naqd/karta/bank qarz to‘lovi va yo‘qolgan
  javobni bir xil kalit bilan takrorlash.
- Python compile, barcha JS sintaksisi va `git diff --check`.

Mahalliy buyruqlar:

```bash
python -m unittest discover -s tests -q
for test_file in tests/web/*.test.js; do node "$test_file" || exit; done
python tests/browser_localization.py
```

Brauzer uchun Playwright va Chromium kerak. `CHROMIUM_PATH`, `SCREENSHOT_DIR` bilan
yo‘llarni tanlash mumkin. Testlar haqiqiy bazadan foydalanmaydi, Telegram’ga yozmaydi.

## Ekranlar

- [UZ asosiy ekran](screenshots/workspace-uz-overview.png)
- [RU asosiy ekran](screenshots/workspace-ru-overview.png)
- [RU xodimlar](screenshots/workspace-ru-staff.png)
- [UZ telefon menyusi](screenshots/workspace-uz-menu.png)
- [RU telefon menyusi](screenshots/workspace-ru-menu.png)

## O‘rnatish va rollback

Bu PR’da yangi schema, migratsiya yoki credential yo‘q. O‘zgargan runtime fayllar
va uchta yangi katalog/yordamchi fayl birgalikda yangilanishi kerak:

```text
locales/uz-ru.json
ui_text.py
web/ui-text.js
bot.py
director.py
director_reports.py
document_import.py
excel_import.py
i18n.py
miniapp.py
payments.py
reports.py
web/accounting.js
web/app.js
web/director-business.js
web/director-import.js
web/director-overview.js
web/director.html
web/director.js
web/document-import.js
web/employee-debt.js
web/employee-sales.js
web/index.html
web/workspace.css
```

Faqat yangi HTML/JS’ni eski backendga tashlamang: yangi asset generatori va katalogi
ham kerak. So‘nggi tasdiqlangan VDS versiyasi `09f55ae`; #21–28 o‘zgarishlarini ham
qamrab oladigan release, konsistent backup va bazaning nusxasida tekshiruv zarur.
Hosting identifikatori, audience, mavjud auth va o‘chiq auto-update saqlangan.

Faqat bu PR’ni qaytarish uchun runtime fayllarni uning parenti `e11b546` holatiga
birgalikda qaytarish mumkin. DB tiklash yoki yozuv o‘chirish kerak emas.

Bu sinovlar mutlaqo xato bo‘lmasligiga kafolat bermaydi. Jonli VDS, haqiqiy Telegram
WebView, Safari/iOS/Android va production sayt sinxronlash sinovi bajarilmagan.
Umumiy kassa/bank, to‘liq sof foyda va haqiqiy iBox eksportidan ko‘chirish oldingi
chegaralaricha qoladi. Direktor bildirishnomalari uchun tanlangan Telegram ID hali
alohida sozlanishi kerak. Tizim iBox’ni to‘liq almashtirdi deb e’lon qilinmaydi.
