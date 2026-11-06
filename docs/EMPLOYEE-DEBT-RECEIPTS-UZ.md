# Xodim mijozdan olgan qarz to‘lovini belgilashi

Branch #25 (`feature/dashboard-product-employee-analytics`) ustiga qurilgan.
Production/VDS kod, baza va servislar bu ishda o‘zgarmagan.

## Ishlatish

- **Ish maydoni → Mening savdo tarixim → Qarz to‘lovini qabul qilish**.
- **Mijozlar → Savdo tarixi** ichida ham shu amal mavjud.
- Mavjud **Qarzlar → To‘lov kiritish** yangi aniq summa/preview oynasidan foydalanadi.

Xodim haqiqatan olgan summani va naqd/karta/bank usulini kiritadi.
Tasdiqlashdan oldin eski qarz, olingan pul va qoladigan qarz ko‘rsatiladi.
Faqat tasdiqlashdan keyin yoziladi. Qisman yoki to‘liq to‘lov; musbat va qarzdan oshmagan summa.
Qarz to‘liq yopilsa tugma yo‘qoladi. Har bir to‘lov **tanlangan savdoga** bog‘lanadi;
bir mijozning boshqa savdolariga avtomatik taqsimlanmaydi.

Saqlangach summa, qolgan qarz, server sanasi/vaqti va qabul qilgan xodim ko‘rinadi.
To‘lov tarixida qabul qilgan xodim ham chiqadi. So‘rov javobi uzilsa o‘sha kalit bilan qayta
uriniladi; summa yana qo‘shilmaydi. Oynaga qaytilganda eski toast yangi qoldiqni berkitmaydi.

## Hisob va ruxsat

Yangi `collect_debt` komandi mavjud `Store.payment`ni ishlatadi. Alohida to‘lov yoki menejer
puli bazasi yo‘q. Savdoning paid qiymati, payments yozuvi, audit va idempotency natijasi mavjud
bitta SQLite tranzaksiyada. Store.payment mustaqil chaqirilganda ham savepoint bilan atomik.

Xodim yangi oqimda faqat o‘zi qilgan savdo qarzini qabul qiladi; direktor boshqa savdoga ham.
Bu tekshiruv cached/idempotency natijasidan oldin ham bajariladi. Sana, kollektor va valyuta
serverdan olinadi: frontend actor/date/currency parametri bilan almashtirilmaydi.
Kirish yopilgan foydalanuvchi, begona savdo va bekor qilingan savdo rad etiladi.
Tasdiqlangan paytdagi paid boshqa oynada o‘zgargan bo‘lsa `debt_changed`: yangilab qayta
tekshirish kerak, hatto yangi summa qolgan qarzga sig‘sa ham. Ortiqcha to‘lov yozilmaydi.

`collect_debt` — `debts` ruxsati, amaldagi Telegram auth/Origin va `money_version=2` talablari bilan.
Director staff-card’dagi umumiy tarix read-only bo‘lib qoladi, unga collect callback berilmaydi.

Eski bot `/pay`, qo‘lda savdo ID tanlash va dasturiy `pay` oqimlari olib tashlanmagan.
Ularning ilgari mavjud kollektor siyosati saqlangan: boshqa xodim savdosiga haqiqatan pul olgan
kollektor yozuvi mumkin. Bu mavjud testlarda tasdiqlangan biznes oqimi; ushbu branch uni
almashtirmaydi. **Yangi shaxsiy UI/collect_debt** esa qat’iy o‘z savdosiga cheklangan.
Boshqa xodimning savdo/qarz tarixini ko‘rsatish uchun ruxsat kengaytirilmagan.

Payments’dagi actor pulni haqiqatan olgan foydalanuvchi. Mavjud menejer puli projection’i
naqd/karta/bank tushumini bir marta shu xodimga yozadi; manager_received/manager_entries’ga
ikkinchi nusxa kiritilmaydi. Bu avtomatik kassaga topshirish yoki kunni yopish emas.
Eski savdo uchun bugun olingan pul bugungi tushum bo‘ladi; yangi savdo deb sanalmaydi.
Sayt, ombor qoldig‘i, ta’minotchi qarzi va savdo jami o‘zgarmaydi.

Pul Decimal/butun sentlarda; frontend BigInt bilan parse/difference/format qiladi.
`paid_cents`, `debt_cents`, `total_cents` — aniq string sentlar. Preview uchun expected_paid ham
string. Saqlangan eski UZS qarz UZS’da yoziladi; kurs yoki USD deb qayta belgilash yo‘q.

## O‘rnatish va rollback

Yangi schema/migratsiya, dependency yoki secret yo‘q. Oldingi stacked migration/runbooklar
saqlanadi. Fresh backup va nusxadagi tekshiruvdan so‘ng runtime paketi birga yangilanadi.
Hosting identifikatori, audience, env, mahalliy deploy skriptlari va o‘chiq auto-update saqlanadi.

Runtime: `core.py`, `miniapp.py`, `staff.py`, `i18n.py`, `employee_receipts.py`, `employee_sales.py`,
`web/app.js`, `web/index.html`, `web/employee-debt.js`, `web/employee-sales.js`,
`web/employee-sales.css`. Workflow fayli faqat yangi Node tekshiruvini CIga qo‘shadi.

UI rollback eski runtime bilan mumkin: haqiqiy yozilgan to‘lovlar oddiy mavjud payments’da
saqlangan. To‘lovlarni o‘chirmang, paid qiymatini qo‘lda kamaytirmang, eski DB backupni keyingi
savdo/to‘lovlar ustiga tiklamang. #24 mijoz kartasi maxfiyligi tuzatishini saqlang.

## Tekshirish

323 Python testi: yangi 12 ta receipt testi qisman/to‘liq to‘lov, idempotency/kalit o‘zgarishi,
begona sale/rol o‘zgargan cached natija, stale tasdiq, ortiqcha/0/manfiy/aniq bo‘lmagan summa,
uchala usul va menejer hisobi, bekor qilingan/faolsiz kirish, asl valyuta va server sanasi/actor,
payment yozuvi xatosidagi rollback, parallel tasdiq, HTTP auth/version va eski savdoning bugungi
tushumini qamraydi. Eski xodimlararo kollektor testlari ham saqlanib o‘tadi.
6 Node suite, shu jumladan BigInt sent/format/validation/difference. Compileall, JS syntax, diff check.

Haqiqiy Chromium: tarixdan va eski Qarzlar bo‘limidan to‘lov, ortiqcha summaning preview’da
rad etilishi, naqd/karta/bank, qolgan qarz, to‘liq yopish, RU, desktop/mobil. Server to‘lovni
saqlagach HTTP javobini ataylab uzish tekshirilgan: bir xil key bilan 2 POST, bitta to‘lov.
Oldingi xodim maxfiyligi va direktorning read-only staff-card smoke’i ham o‘tgan.

`employee-debt-confirm-desktop.png`, `employee-debt-confirm-mobile.png`,
`employee-debt-saved-mobile.png` — faqat vaqtinchalik test bazasi. Jonli xodim akkaunti,
production pul operatsiyasi yoki VDS deploy/restart/merge bu ishda bajarilmagan.
