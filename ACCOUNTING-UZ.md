# Yetkazib beruvchilar, Sklad / Vitrina va menejer puli

## Migratsiya va mavjud ma’lumotlar

`Store` ochilganda `accounting.migrate` qo‘shimcha migratsiyasi bitta
tranzaksiyada bajariladi. Takroran ochishda kirimlar yoki partiyalar
takrorlanmaydi. Mavjud mahsulot, narx, savdo, to‘lov, qoldiq va foydalanuvchi
yozuvlari o‘chirilmaydi. Production bazasiga bu ish doirasida ulanilmagan.

Yangi jadvallar: `suppliers`, `receipts`, `inventory_lots`,
`sale_allocations`, `supplier_entries`, `manager_entries`.
`points.kind` saqlash joyi turini, `sale_items.point` mahsulot berilgan joyni,
`sale_items.location_kind` esa sotuv paytidagi joy turini saqlaydi.
Eski sotuvlarda bu ikki yangi maydon NULL; avvalgi `sales.point` ishlatiladi.

Eski qoldiqlar `receipt=NULL` partiyaga olinadi: **yetkazib beruvchi
belgilanmagan**. Ular uchun qarz yoki taxminiy kirim narxi yaratilmaydi.
Eski joylar `sklad` turi bilan davom etadi. Direktor Mini App’dagi
**Sklad / Vitrina turi** yoki `/point_kind` orqali haqiqiy vitrinalarni belgilaydi.
Mavjud joylar qayta yaratilmaydi, qoldiqlar boshqa joyga ko‘chirilmaydi.

Eski `/income`, mijozdan `/return`, boshlang‘ich qoldiq, Excel/PDF/rasm
importlari ishlashda davom etadi. Yetkazib beruvchi ko‘rsatilmagan shu
operatsiyalar ham alohida belgilanmagan partiya bo‘lib qoladi. Yangi qarzli
kirim uchun Mini App’dagi **Mahsulot kirimi** yoki botdagi `/prixod` ishlatiladi.

## Yetkazib beruvchi hisobi

Direktor **Yetkazib beruvchilar** bo‘limida qo‘shadi, tahrirlaydi va saldoni ko‘radi.
Xodim kirim/to‘lov uchun faqat yetkazib beruvchi ID va nomini tanlay oladi;
barcha yetkazib beruvchilarning saldosi va hisoboti direktor uchun.

Kirimda mahsulot, yetkazib beruvchi, bir dona kirim narxi, valyuta, sana,
izoh va bir yoki ikki saqlash joyi miqdori kiritiladi. Ikki joy har xil
bo‘lishi kerak. Nol miqdorli ikkinchi joy kiritilmaydi. Tasdiqlashdan oldin
ma’lumotlar ko‘rsatiladi; tasdiqlangach qoldiq va qarz birga yoziladi.

Saldo har bir valyuta uchun alohida:

`kirimlar summasi − yetkazib beruvchiga to‘lovlar − qaytarilgan tovar qiymati`.

Tovar qaytarishda mavjud kirim partiyasi va miqdor tanlanadi. Summa aynan
shu kirim narxida hisoblanadi; mahsulotning hozirgi sotuv narxi ishlatilmaydi.
Eski, yetkazib beruvchisiz qoldiqni yetkazib beruvchiga qaytarish orqali
uning saldosiga o‘zboshimchalik bilan bog‘lash mumkin emas.

To‘lovda menejer tanlansa, bir tranzaksiyada uning xarajati ham yoziladi.
Uni yana oddiy **Menejer xarajati** sifatida kiritish kerak emas.
Direktor menejerni tanlamasdan o‘z pulidan ham to‘lov qayd qilishi mumkin.
Xodim faqat o‘z pulidan to‘lov qayd qiladi.

## Sotuv va vitrina

Mini App sotuv formasida har bir mahsulot uchun alohida joy tanlanadi.
Botda `ID|dona|narx|joy ID` formati ham qabul qilinadi. Oldingi uch
ustunli format va botning savat tanlovlari hujjatda tanlangan joydan beradi.

Joy ichida avval yetkazib beruvchisi belgilanmagan qoldiq, undan keyin
kirim ID tartibida partiyalar sarflanadi (FIFO). Bu qoida hisob manbasini
aniq va qayta tekshiriladigan qiladi; eski qoldiqqa yetkazib beruvchi tayinlamaydi.
Bir mahsulotni ikki joydan sotish API/botda ikki qator bilan mumkin.

Sotuv bekor qilinganda tovarlar aynan avvalgi joy va partiyalariga qaytadi.
Bekor qilingan sotuvlar yetkazib beruvchining vitrindan sotilgan hisobiga
kirmaydi. Yetkazib beruvchiga qarz sotuv yoki uning bekor qilinishidan o‘zgarmaydi.

**Sklad ↔ Vitrina** ko‘chirishida yetkazib beruvchi va kirim narxi saqlanadi;
yangi qarz yaratilmaydi. Kamomad, sotuv va ko‘chirishda manfiy qoldiqqa yo‘l qo‘yilmaydi.

Hisobotdagi vitrina qoldig‘i — hozirgi holat; sotilgan mahsulotlar esa
tanlangan sana oralig‘idagi faol sotuvlar. Yangi sotuvlarda joy turi
sotuv paytidagi nusxadan olinadi. Tarixiy sotuvlarda o‘sha joyning joriy turi
ishlatiladi, chunki eski bazada joy turi tarixi yo‘q. Hisobotda eski
mahsulotlar alohida **yetkazib beruvchi belgilanmagan** bo‘lib ko‘rinadi.

## Menejer puli va ruxsatlar

Direktor menejerga pul beradi; direktor yoki menejer o‘z xarajati va
qaytargan pulini qayd qiladi. Direktor boshqa menejer uchun ham yozishi mumkin.
Har bir yozuvda mas’ul menejer, kiritgan foydalanuvchi, hisob sanasi,
yaratilgan vaqt, valyuta va izoh bor. Barcha amallar `audit`ga yoziladi;
yetkazib beruvchi tahririda oldingi va yangi qiymatlar ham saqlanadi.

Saldo: `berilgan pul − xarajatlar − qaytarilgan pul`.
USD va UZS aralashtirilmaydi, avtomatik konvertatsiya yo‘q.
Xarajat berilgan puldan oshsa haqiqiy manfiy saldo ko‘rsatiladi.
Xodim faqat o‘z jurnalini ko‘radi; direktor barcha menejerlarni ko‘radi.
O‘chirilgan foydalanuvchi bot va API orqali yozolmaydi yoki o‘qiy olmaydi.
Hisob yozuvlarini tahrirlash/o‘chirish uchun yangi yo‘l ochilmagan.

Bot buyruqlari:

- `/supplier_new`, `/supplier_edit`, `/suppliers` — yetkazib beruvchilar.
- `/prixod`, `/supplier_payment`, `/supplier_return` — kirim/to‘lov/qaytarish.
- `/supplier_report` — davr, yetkazib beruvchi (0 — hammasi), Excel hisoboti;
  qoldiq, sotuv, hisob yozuvlari, saldo va qaytarish uchun partiya ID’lari.
- `/manager_fund`, `/manager_expense`, `/manager_return` — pul yozuvlari.
- `/manager_account` — saldo va Excel jurnali.
- `/point_kind`, `/transfer` — joy turi va ko‘chirish.

Mini App yozuvlari mavjud `Idempotency-Key` tizimi orqali takror yozilishdan
himoyalangan. Bot yozuvlari mavjud `update_id` tekshiruvidan foydalanadi.
Barcha yangi yozuvlarda ichki savepoint bor: xato ikkinchi qator birinchi
qatorni qoldirib ketmaydi. Bot va Mini App bir SQLite bazasida ishlashda davom etadi.

## Tekshirish

```sh
python -m unittest discover -s tests -q
node tests/web/api_retry.test.js
node tests/web/mobile_keyboard.test.js
node tests/web/pdf_chat.test.js
node tests/web/accounting.test.js
```

CI shu buyruqlarni bajaradi. Yangi testlar migratsiya, qayta ochish,
kirimgacha bo‘lgan eski qoldiq/sotuvlar, partiyalar, joylar, bekor qilish,
hisob formulalari, valyutalar, ruxsatlar, HTTP, takroriy so‘rovlar va
Mini App formalarini tekshiradi. Testlar vaqtinchalik SQLite fayllardan foydalanadi.

Joylarni Vitrina deb belgilash, boshlang‘ich yetkazib beruvchi qarzi yoki
menejerning avvaldan qolgan pulini ko‘chirish avtomatik bajarilmaydi.
Avvaldan mavjud pul/qarz saldolarini import qilish bu o‘zgarish doirasiga kirmaydi.
PR alohida tekshirish va keyingi chiqarish uchun tayyorlanadi; merge yoki
production serverni yangilash bajarilmaydi.
