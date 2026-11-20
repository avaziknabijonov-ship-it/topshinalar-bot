# Prixod, Kassa va O'tkazma xabarlari uchun guruh

Bot shaxsiy chatni to'ldirmasligi uchun pul va kirim xabarlari bitta **yopiq direktorlar guruhi**ning
alohida **mavzularida** (Topics) chiqadi. Sozlanmasa hech narsa o'zgarmaydi.

## Qaysi xabar qayerga tushadi

| Mavzu | Nimalar |
|---|---|
| **Prixod** | Yetkazib beruvchidan tovar kirimi, yetkazib beruvchiga qaytarish |
| **Kassa** | Savdo tushumi (to'langan summa bor sotuvlar), qarz to'lovi, sotuv bekor qilinishi, yetkazib beruvchiga to'lov, yetkazish haqi, mas'ul xarajati (chiqim) |
| **O'tkazma** | Kassaga pul berish, pul topshirish va uni qabul/rad qilish, mas'ulga pul qabul qilindi, kun yopilishi |

Faqat qarzga berilgan (to'lovsiz) sotuv Kassaga tushmaydi, chunki bu pul tushumi emas.
Yoqilishdan oldingi tarixiy amallar yuborilmaydi.

## Sozlash (5 daqiqa)

1. Telegramda yangi guruh yarating, unga faqat direktorlarni qo'shing.
2. Guruh sozlamalarida **Topics (Mavzular)** ni yoqing. Mavzular yarating: `Prixod`, `Kassa`, `O'tkazma`.
3. Botni guruhga qo'shing va **admin** qiling (xabar yuborish huquqi yetarli).
4. Guruh ID va mavzu ID'larini oling. Mavzudagi xabar havolasi `t.me/c/1234567890/5/17` bo'lsa:
   guruh ID = `-100` + `1234567890` = `-1001234567890`, mavzu ID = `5`.
5. Serverdagi `.env` ga yozing (bot xizmatida):
   ```
   NOTIFY_PRIXOD=-1001234567890:5
   NOTIFY_KASSA=-1001234567890:6
   NOTIFY_OTKAZMA=-1001234567890:7
   NOTIFY_LANG=uz
   ```
6. Botni qayta ishga tushiring.

Mavzu ID'siz (`NOTIFY_KASSA=-1001234567890`) yozsangiz, xabar guruhning umumiy chatiga tushadi.
Istalgan turkumni bo'sh qoldirsangiz, u o'chiq bo'ladi.

## Xavfsizlik

- Xabarlar ichida pul summalari bor, shuning uchun bot yuborishdan oldin guruhni tekshiradi:
  guruh a'zolari soni `faol direktorlar + bot` dan oshmasa yuboradi. Begona odam qo'shilsa,
  yuborish to'xtaydi va logda ogohlantirish chiqadi.
- Havola orqali qo'shilishni o'chiring, guruhni yopiq qiling.
- Bot tokeni va ID'lar kodda emas, faqat serverdagi `.env` da turadi.
- Telegram ishlamay qolsa, xabar navbatda qoladi va keyin yuboriladi. Guruh manzili o'zgartirilsa,
  eski navbatdagi xabarlar yangi guruhga ko'chmaydi.
- Mavjud "qarz to'lovi" shaxsiy xabari (`DIRECTOR_DEBT_CHAT_ID`) o'z holicha qoladi. Guruh ishlay
  boshlagach uni bo'sh qoldirib, takrorlanishni o'chirishingiz mumkin.

## Har bir menejerga o'z xabarlari (shaxsiy chatda)

Guruhda hamma menejerlarning pul harakatlari aralash chiqadi. Menejer "qancha pul berdim, qancha pul menda"
deb hisoblashda adashmasligi uchun bot har bir menejerga **faqat uning o'z** harakatlarini bot bilan
shaxsiy chatida yuboradi: unga pul berilishi, chiqim, pul topshirish so'rovi, qabul/rad, kun yopilishi.
Har bir xabar ostida "Sizdagi qoldiq" va tasdiq kutayotgan summa ko'rsatiladi. Boshqa menejerning puli
bu xabarlarga hech qachon tushmaydi. Direktorlar guruhi avvalgidek ishlayveradi.

Bu sukut bo'yicha yoqilgan, yoqilishdan oldingi tarix yuborilmaydi. O'chirish uchun `.env` ga
`NOTIFY_MANAGER_DM=0` yozing.
