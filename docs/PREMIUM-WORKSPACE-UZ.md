# Bot ish oynasi va direktor kabinetining yagona dizayni

`feature/premium-unified-workspace`, #27 ustiga qurilgan. Bu hujjatdagi va ekran
tasvirlaridagi sonlar faqat vaqtinchalik lokal sinov bazasidan. Production ma’lumoti
olinmagan, almashtirilmagan va demo yozuvlar ilovaga qo‘shilmagan.

## Tayyor o‘zgarishlar

- Direktor kabineti va Telegram Mini App uchun umumiy navy, oq, oltin va yashil palitra,
  kattaroq yozuvlar, kontrastli kartalar, bir xil input/tugmalar va jadvallar.
- 17 bo‘limning barchasi saqlangan, to‘rt menyu guruhiga joylangan. Yon menyu alohida
  aylanadi; pastdagi til va chiqish amallari doim ko‘rinadi.
- 900 px va kichik ekranlarda ochiladigan yon menyu: fonni bosish yoki Escape bilan
  yopish, bo‘lim tanlanganda yopish, klaviatura fokusini menyuda ushlash va qaytarish.
  Yopiq menyu hamda ochiq menyu orqasidagi kontent `inert`; logout va ekran kengligi
  almashishi asosiy oynani bloklangan holatda qoldirmaydi.
- Dashboarddagi savdo/tushum/qarz/menejer puli ajratilishi, tovar va xodim analitikasi
  saqlangan. Qolgan hisobotlar yangi dizayndan foydalanadi.
- Haqiqiy yuklanish indikatori, bo‘sh qidiruv natijasi, o‘qilishi oson xato va ishlaydigan
  qayta urinish. Eskirgan so‘rov javobi yangi bo‘limni yoki logout holatini almashtirmaydi.
- Mijoz, mahsulot va boshqa jadval kartalarini Enter yoki Space bilan ochish.
- Oddiy dashboardda texnik ID o‘rniga savdo sanasi, xodim ismi va operatsiya nomi.
  Ichki bog‘lanishlar va saqlangan ID’lar o‘zgarmaydi.
- Xodim oynasida profil ismi, qulay katalog/savat, kartalar va moslashuvchan pastki menyu.
  Direktor uchun desktopda kabinet havolasi bor; xodimning server ruxsatlari o‘zgarmagan.
- Mini App pul formatida sentlar `BigInt` bilan aniq, doim ikki kasr bilan ko‘rsatiladi.
  Noma’lum yoki allaqachon aniqligini yo‘qotgan raqam 0 deb ko‘rsatilmaydi.
- Tashqi shrift, yangi CDN yoki yangi frontend kutubxona qo‘shilmagan. Reduced-motion
  sozlamasi, fokus ko‘rinishi va mobil klaviatura yordamchisi saqlangan.

Telegramning o‘z chat oynasi ko‘rinishini bot boshqarmaydi. Ushbu yangilanish botdan
ochiladigan ish oynasi va direktor web-kabinetini qamrab oladi. Bot komandalariga yangi
murakkab menyu qo‘shilmagan; mavjud «📊 Direktor kabineti» tugmasi saqlanadi.

## Tekshirish

- 336 Python testi — o‘tdi.
- 7 Node suite — o‘tdi; yangi sent formatlash tekshiruvi CI’ga qo‘shilgan.
- Python compile, barcha browser JS fayllarining sintaksisi, `git diff --check`.
- Haqiqiy Chromium’da beshta ssenariy: `browser_premium_workspace.py`,
  `browser_director.py`, `browser_dashboard_analytics.py`, `browser_employee_sales.py`,
  `browser_employee_receipts.py`.
- Desktop va mobil, 320/390/768/900/1024/1440 px sahifada gorizontal chiqish yo‘qligi;
  UZ/RU, login/logout, barcha bo‘limlar, drawer fokusi/Escape/resize, loading/xato/retry,
  bo‘sh qidiruv, keyboard detail, Excel/PDF import va tasdiq, mijoz create/edit,
  inventarizatsiya, qaytarishlar, tanlangan Excel hisobotlari, analitika va drill-down.
- Xodimning faqat o‘z savdosi/mijozi/qarzi, boshqa xodimga URL orqali kira olmasligi,
  naqd/karta/bank qarz to‘lovi, yo‘qolgan javobni bir xil kalit bilan xavfsiz takrorlash.

Mahalliy takrorlash:

```bash
python -m unittest discover -s tests -q
for test_file in tests/web/*.test.js; do node "$test_file" || exit; done
python tests/browser_premium_workspace.py
SCREENSHOT_DIR=/tmp/topshinalar-ui-check python tests/browser_director.py
```

Brauzer tekshiruvi uchun Playwright va Chromium kerak. `CHROMIUM_PATH` bilan Chromium
yo‘lini, `SCREENSHOT_DIR` bilan tasvirlar papkasini tanlash mumkin. Barcha ssenariylar
vaqtinchalik DB yaratadi; haqiqiy Telegram xabari yubormaydi. Testdagi Telegram initData
faqat test tokeni bilan imzolangan; production login himoyasiga istisno qo‘shilmagan.

## Ekran tasvirlari

- [Direktor, desktop](screenshots/workspace-premium-director-desktop.png)
- [Direktor, telefon](screenshots/workspace-premium-director-mobile.png)
- [Telefondagi bo‘limlar menyusi](screenshots/workspace-premium-mobile-menu.png)
- [Hisobotlar](screenshots/workspace-premium-reports-desktop.png)
- [Xodim katalogi](screenshots/workspace-premium-employee-catalog.png)
- [Xodim ish oynasi, desktop](screenshots/workspace-premium-employee-desktop.png)
- [Xodim ish oynasi, telefon](screenshots/workspace-premium-employee-mobile.png)

## O‘rnatish va qaytarish

Bu PR’da yangi schema, migratsiya, credential yoki maxfiy sozlama yo‘q. Runtime fayllar:

```text
miniapp.py
web/director.html
web/director.js
web/director-overview.js
web/index.html
web/app.js
web/workspace.css
web/workspace-shell.js
```

Yangi CSS va script `miniapp.py`ning mavjud statik allowlist’i orqali beriladi;
API auth, cookie, hosting identifikatori va audience o‘zgarmagan. Build bundler yo‘q:
bu backend statik HTML/CSS/JS fayllarini beradi. Sayt repozitoriysi va uning deploy’i
ushbu UI yangilanishida o‘zgartirilmagan.

VDS’da oxirgi tasdiqlangan versiya `09f55ae`. U yerga faqat bu sakkiz faylni tashlash
yetmaydi: #21–27 dagi backend, ruxsatlar, hisobot, import va moliyaviy o‘zgarishlar ham
bor. Tasdiqlangan umumiy release tayyorlanib, mavjud runbooklar bo‘yicha konsistent
backup, DB nusxasida migratsiya/integrity/FK va eski ma’lumotlarning saqlanishi
tekshirilishi lozim. Bu ish davomida main merge, production publish, VDS restart yoki
production bazasiga yozish bajarilmagan. Auto-update o‘chiq holati saqlanadi.

Faqat ushbu UI yangilanishini qaytarish uchun runtime fayllarini birgalikda uning
parenti `740a701` versiyasiga qaytarish mumkin. HTML’ni yangi JS/CSSsiz qoldirmang.
DB’ni tiklash yoki pul yozuvlarini o‘chirish kerak emas; #21–27 backend himoyalari
alohida saqlanishi kerak.

Jonli VDS/Telegram Mini App, Safari/iOS va Android WebView’da sinov bajarilmagan.
Direktorning qarz bildirishnomasi hali alohida tanlangan `DIRECTOR_DEBT_CHAT_ID` talab
qiladi va sozlanmaguncha o‘chiq. Umumiy kassa/bank, sof foyda, iBox’dan haqiqiy import
va sayt sync’ining production ishga tushirilgani ushbu PR natijasi deb e’lon qilinmaydi.
