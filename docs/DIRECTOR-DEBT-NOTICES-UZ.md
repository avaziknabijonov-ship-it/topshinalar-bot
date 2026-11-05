# Direktor chatiga qarz to‘lovi bildirishnomasi

Branch #26 (`feature/employee-debt-receipts`) ustiga qurilgan.
Production/VDS yoki haqiqiy Telegram chatiga bu ishda xabar yuborilmagan.

## Qayerga yuboriladi

Faqat **bitta aniq belgilangan** direktorning shaxsiy Telegram chatiga:

`DIRECTOR_DEBT_CHAT_ID=<direktorning_raqamli_telegram_id_si>`

Haqiqiy ID kodga/Gitga yozilmaydi. Serverning mavjud env faylida bot va Mini App uchun
bir xil qiymat qo‘yiladi. `.env.example`da qiymat bo‘sh.

Bu yangi credential emas: mavjud bot tokeni ishlatiladi. Qabul qiluvchi biznes bazasida
oldindan mavjud, faol va director rolida bo‘lishi shart. Raqamli shaxsiy ID; guruhning
manfiy ID’si, username, bir nechta ID va oddiy xodim qabul qilinmaydi.

**Bo‘sh/noto‘g‘ri/faolsiz direktor = bildirishnoma o‘chiq.** To‘lov saqlanadi, boshqa faol
direktor avtomatik tanlanmaydi. Hamma direktorga broadcast yo‘q. Yuborish oldidan ham
joriy config, faollik va director roli tekshiriladi. Manzil almashtirilsa eski kutilayotgan
xabar boshqa chatga ko‘chirilmaydi; skipped bo‘ladi. Yoqishdan oldingi tarixiy to‘lovlar
keyin birdaniga yuborilmaydi.

User qaysi direktor ID’sini tanlashi hali kutilmoqda. Sozlanmaguncha bu feature xabar yubormaydi.
Avtomatik xavfsizlik tekshiruvi barcha faol direktorlarga yuborish variantini oluvchilar
ro‘yxati tasdiqlanmagani uchun rad etgan; yakuniy implementatsiya bitta aniq manzilga cheklangan.

## Xabar

Mijoz qarzidan qisman to‘lov uchun:

```text
💵 Mijoz qarzidan to‘lov
Mijoz: Customer
To‘landi: 50.25 USD
To‘lovdan keyingi qarz: 149.75 USD
Kim tomonidan: Seller A
Usul: Naqd
Sana: <to‘lovning server vaqti>
```

Bu namuna faqat lokal test fixture’idan. Haqiqiy mijoz/xodim ma’lumoti emas.
Qarz to‘liq yopilsa sarlavha «✅ Mijoz qarzini to‘ladi». Qisman to‘lov to‘liq yopildi deb
ko‘rsatilmaydi. USD yoki saqlangan eski UZS alohida; kurs yoki konvertatsiya yo‘q.
Direktorning mavjud UZ/RU tili qo‘llanadi.

«Kim tomonidan» — savdoni qilgan yoki mijozga mas’ul kishi emas, **pulni amalda qabul qilgan
payments.actor xodimining ismi**. Eski kollektor oqimida boshqa xodim pul olgan bo‘lsa ham
shu haqiqiy kollektor yoziladi. To‘langan summa — shu bitta to‘lov, butun savdo jami emas.
Qolgan qarz shu to‘lov yozilgan paytdagi holat. Vaqt Asia/Tashkent.

## Navbat va tranzaksiya

`Store.payment` yangi haqiqiy qarz to‘lovini yozganda bir xil shared oqim ishlaydi:
MiniApp tarix, Qarzlar, kabinet va eski bot `/pay`. Sotuv paytidagi dastlabki to‘lov uchun
ushbu qarz bildirishnomasi yaratilmaydi. Boshqa to‘lov jurnali yoki tarmoq chaqiruvi yo‘q.

Payments, sales.paid, audit, notification marker va mavjud bot outbox yozuvi bitta
tranzaksiyada. Rollback bo‘lsa xabar ham yo‘q. Bot drain ochiq biznes tranzaksiyasi vaqtida
yubormaydi. Telegram ishlamasa haqiqiy to‘lov saqlanganicha qoladi; mavjud outbox keyin urinadi.

**Bir to‘lov bir marta navbatga qo‘yiladi**, takroriy API key yoki outbox cleanup qayta
bildirishnoma yaratmaydi. Telegram sendMessage tashqi idempotency kalitini qabul qilmaydi:
Telegram qabul qilib, javob yo‘qolgan juda noaniq transport holatida mavjud outbox qayta
urinishi takror yetkazishga olib kelishi mumkin. Transport darajasida mutlaq exactly-once
va’da qilinmaydi. Yangi haqiqiy partial to‘lovlar alohida yangi bildirishnomalardir.

## Migratsiya

Yangi `debt_notifications.migrate`: tranzaksiyali, qayta bajarishga xavfsiz.
- Mavjud outbox bo‘lmasa aynan mos sxema bilan yaratadi; bor xabarlar o‘zgarmaydi.
- `debt_payment_notifications`: payment PK (bitta xabar), director, outbox_id, state, created.
- Sent outbox tozalanganda FK `ON DELETE SET NULL`; marker idempotency uchun qoladi.
- Payment’ga FK mavjud to‘lovni o‘chirishdan himoya qiladi. Biznes yozuvlari o‘chirilmaydi.
- Eski migratsiya o‘zgartirilmagan; tarixiy to‘lovlar uchun backfill yoki demo yozuv yo‘q.

## O‘rnatish / rollback

Oldingi stacked runbooklar amal qiladi. Fresh konsistent backup va nusxadagi migration,
oldingi yozuvlar/integrity/FK tekshiruvi birinchi. Runtime fayllar:
`core.py`, `bot.py`, `debt_notifications.py`. Yangi maxfiy token talab qilinmaydi.

Bot va MiniApp bir DB/env bilan birga yangilanishi kerak. Eski bot worker hali ishlayotganida
yangi enqueue qismini alohida yoqmang: eski worker’da direktor rolini qayta tekshiruvchi
notification guard yo‘q. Hosting ID, audience, token, mahalliy deployment scriptlar va o‘chiq
auto-update saqlanadi. Main merge, production deploy/restart bu ishda bajarilmagan.

O‘chirish uchun env qiymatini bo‘shatish mumkin; yangi to‘lovlarga bildirishnoma yozilmaydi,
pending xabarlar yangi worker’da skipped qilinadi. Eski Bot.drain’ga to‘liq rollback qilishdan
oldin yangi guard’ni saqlang yoki operator worker’ni to‘xtatib, pending notification’larni
tranzaksiyada bekor qilsin:

```sql
BEGIN IMMEDIATE;
UPDATE outbox SET sent=1 WHERE id IN (
  SELECT outbox_id FROM debt_payment_notifications WHERE state='queued'
);
UPDATE debt_payment_notifications SET state='skipped' WHERE state='queued';
COMMIT;
```

Bu faqat notification’ni bekor qiladi; pul, savdo yoki audit yozuvini o‘chirmaydi.
Jadvalni drop qilish yoki eski DB backupni keyingi haqiqiy to‘lovlar ustiga qaytarish kerak emas.

## Tekshirish

336 Python testi (yangi 13): bitta configured target, boshqa faol direktorga yubormaslik,
UZ/RU, partial/full summa, haqiqiy kollektor, UZS, retry/cleanup/marker, boshlang‘ich
sotuvga bildirishnoma yo‘qligi, noto‘g‘ri/bo‘sh/ko‘p target’lar, disabled/role change,
recipient change, offline/recovery, commit/rollback, queue/marker failure va migration
rerun/reopen’da eski biznes va pending outbox saqlanishi. Telegram chaqiruvi Recorder bilan mock.
Mavjud 6 Node suite, compileall va whitespace tekshiruvi ham o‘tgan.

UI o‘zgarmagan; yangi vizual brauzer tekshiruvi kerak emas. Haqiqiy Telegram API/bot
akkaunti, jonli direktor ID’si yoki production bazasi bilan sinov bajarilmagan.
To‘liq kassa/bank/sof foyda va iBox integratsiyasi bu feature’ga qo‘shilmagan.
