# Xodimning shaxsiy savdo tarixi

Ushbu branch `feature/director-business-sections` (#23) ustiga qurilgan.
Production kodi, servislar va bazaga bu ishda tegilmagan.

## Qayerdan ochiladi

- Xodim Telegram ilovasida **Ish maydoni → Mening savdo tarixim**.
- Xodim **Mijozlar → Savdo tarixi** orqali o‘z mijozining faqat o‘zi qilgan savdolarini ko‘radi.
- Direktor kabinetida **Xodimlar → xodim kartasi → Xodimning savdo tarixi**.
- Botdagi mavjud sotuv tarixi buyrug‘i saqlanadi; matnda mahsulot, son, sana, jami,
  to‘langan pul va qolgan qarz sentlardan to‘g‘ri formatlanadi. Yangi asosiy menyu tugmalari yo‘q.

Ko‘rinishda sana, mijoz, mahsulotlar, dona va dona narxi, chegirma, savdo summasi,
to‘langan pul, qolgan qarz, to‘lov muddati, asl to‘lov/qaytarish tarixi va savdo holati bor.
Sana oralig‘i, mijoz/mahsulot qidirish, o‘z mijozlari, valyuta, qarz/to‘langan va
faol/bekor qilingan holati filtrlari mavjud. Har sahifada 20 ta; 100 tadan keyingi tarix ham ochiladi.
Kunlik savdo ro‘yxati va valyutalar bo‘yicha jami sahifalashdan oldin hisoblanadi.
Bo‘sh/xato/yuklanish holati, retry, stale response guard, UZ/RU va mobil ko‘rinish mavjud.

## Ruxsat va hisoblash

`GET /api/my-sales` Telegram bilan autentifikatsiyalangan foydalanuvchining `uid` qiymatini
serverda scope qiladi. URLdagi `employee`, `actor`, `owner` yoki `manager` boshqa kishining
savdolarini ochmaydi. `sale` orqali begona savdoni olish — 403; boshqa mijoz filtri bo‘sh ro‘yxat.
Mijozning mas’uli emas, **savdoni yaratgan xodim (`sales.actor`)** asosiy chegara.
Shuning uchun umumiy mijozning boshqa menejer savdosi, qarzi va refundi ko‘rinmaydi;
mijoz mas’uli o‘zgarsa eski savdo egasi almashmaydi.

`GET /director-api/employee-sales?employee=...` faqat mavjud faol direktor auth orqali.
Direktor faolsizlangan xodimning tarixini ham tekshirishi mumkin; faolsiz xodimning o‘zi kira olmaydi.
Eski `/api/sales`, `/api/debts` va Excel `Store.report` xodim scope’ini saqlaydi.
Eski bot mijoz kartasi (`Store.client_card`) ham endi savdo/CRM/quote/refund yozuvlarini
xodimning o‘z actor’i bo‘yicha cheklaydi: umumiy mijoz orqali boshqa xodim moliyasi chiqmaydi.

MiniApp mijozlar sahifasi `scope=mine` bilan o‘zi yaratgan yoki o‘zi sotgan mijozlarni ko‘rsatadi.
Mavjud sotuv/KP tuzishdagi kontakt tanlash katalogi saqlangan — umumiy mijozga yangi savdo
qilish mumkin, lekin uning boshqa menejer bilan savdo tarixi ochilmaydi.

Sana filtri — **savdo sanasi**. `paid_to_date` va `debt_to_date` — shu tanlangan savdolarning
**hozirgi** to‘langan puli va qarzi, davrda kelgan pul emas. Keyingi sanada tushgan to‘lov
oldingi savdoning joriy qarzini kamaytiradi. Bu farq interfeysda aniq yozilgan.
Bekor qilingan savdo faol savdo jamiga qo‘shilmaydi, qarzi nol; asl paid/to‘lov/refund yozuvi
saqlanadi. USD/UZS alohida, konvertatsiya yo‘q. Eski to‘lov yozuvlari paid bilan mos kelmasa
ogohlantirish chiqadi; yangi tarix yoki sana taxmin qilinmaydi.

Ommaviy sayt API’si o‘zgarmaydi. Shaxsiy tarix javobi whitelisted: tannarx, foyda,
ta’minotchi yoki token ma’lumoti yo‘q. API read projection’da biznes yozuvi yaratilmaydi.

## O‘rnatish va rollback

Yangi schema, secret yoki dependency yo‘q. Avvalgi stacked branchlarning migration/runbook
qoidalari saqlanadi. Fresh backup va nusxadagi tekshiruvdan keyin operator yangilaydi.
Hosting identifikatori, audience, env va mavjud deploy skriptlariga o‘zgartirish yo‘q.

Runtime fayllar: `employee_sales.py`, `core.py`, `miniapp.py`, `director.py`, `usability.py`,
`web/app.js`, `web/index.html`, `web/director.js`, `web/director.html`,
`web/employee-sales.js`, `web/employee-sales.css`.

UI rollback eski HTML/JS’ni qaytarishi mumkin; eski API shakli saqlangan.
`core.py`dagi xodimga tegishli mijoz kartasi cheklovini rollback bilan olib tashlamang:
eski versiya umumiy mijozning boshqa xodim savdosini chiqarishi mumkin.
DB restore talab qilinmaydi, haqiqiy keyingi savdo/to‘lovlarni backup bilan almashtirmang.

## Tekshiruv

300 Python unittest (yangi 12): bitta mijozga ikki menejer, qalbaki employee/actor/manager
parametrlari, begona sale ID, autentifikatsiyasiz/faolsiz foydalanuvchi, direktorning tanlangan
xodim tarixi, egasi o‘zgargan mijoz, mijoz kartasi/refund va eski API/export scope’i,
mahsulot/dona/to‘lov/qarz/muddat, keyingi sana to‘lovi, kun chegarasi, 103 savdo/sahifalash,
valyutalar, bekor qilish, yo‘q tarix ogohlantirishi va bot matnidagi to‘g‘ri sentlar.
Mavjud 4 Node suite, compileall, JS syntax va whitespace tekshiruvlari.

Real Chromium: xodim desktop 1440×1000/mobil 390×844, shaxsiy tarix, umumiy mijoz
izolyatsiyasi, mahsulot/qarz/kunlar, begona URL 403, qidirish/bo‘sh/reset, RU,
direktorning xodim kartasi va o‘chirilgan kirish. Oldingi direktor/import/moliya smoke’i ham o‘tgan.
Skriptlar: `python tests/browser_employee_sales.py`, `python tests/browser_director.py`.

`employee-sales-desktop.png`, `employee-sales-mobile.png`, `employee-sales-mobile-detail.png`,
`staff-sales-history.png` — faqat vaqtinchalik lokal test bazasi. Production Telegram akkauntlari,
jonli xodimlar va VDS deployi tekshirilmagan; bu turn’da deploy/restart/merge yo‘q.
