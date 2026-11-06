# Menejer qabul qilgan va kassaga topshirgan pul

Direktor so‘rovi: naqd, karta va bank tushumlarining barchasi pulni qabul qilgan
xodim zimmasida yuritiladi. Pul olingan, lekin qabul qilingan topshirish bilan
yopilmagan bo‘lsa, menejer hisobida topshirilmagan summa qoladi.

## Hisoblash qoidasi

`menejerga berilgan + haqiqiy tushumlar − xarajatlar − qabul qilingan topshirishlar − shu xodim to‘lagani tasdiqlangan mijoz refundlari`.

- Tushum manbai `payments`, **savdo jami yoki mijozning to‘lanmagan qarzi emas**.
- Qarz to‘lovi savdo muallifiga emas, pulni olgan `payments.actor`ga va to‘lov sanasiga kiradi.
- Naqd/karta/bank alohida ustunlar; USD/UZS aralashtirilmaydi, integer sentlar saqlanadi.
- Eski savdo/to‘lovlar read-only hisoblanadi: ular `manager_entries`ga ko‘chirilmaydi va takror kredit qilinmaydi.
- Savdo bekor bo‘lsa pul avval qabul qilingani yo‘qolmaydi. Refundni kimning pulidan to‘lagani direktor
  alohida tasdiqlaydi: xodim yoki kompaniya kassasi/boshqa hisob. Bekor qilish muallifidan payer taxmin qilinmaydi.
  Tekshirilmagan refundlar ko‘rsatiladi, shu hisobdagi kun yopilishi bloklanadi.
- Alohida `Qabul qilgan pul` faqat savdodan tashqari tasdiqlangan tushum uchun, direktor va sabab bilan.
  Avtomatik savdo/qarz to‘lovlarini yana shu yerga kiritmaslik kerak.
- Musbat saldo — hisob bo‘yicha topshirilmagan pul. Manfiy saldo yashirilmaydi, menejer foydasidagi qoldiq.
  Bu modul umumiy kassa/bank balansi yoki sof foyda hisobi emas.

## Kassaga topshirish va qabul qilish

Yangi `return` yozuvi avval **tasdiq kutilmoqda** holatida: u qarzni kamaytirmaydi.
Direktor amalda olingan pulni `Qabul qilindi` bilan tasdiqlaydi. Xato topshirish sabab bilan rad etiladi;
yozuv o‘chirilmaydi. Bir topshirish ikki marta qabul qilinmaydi, mablag‘dan ortiq summa rad etiladi.
Direktor `Kassaga qabul qilindi` formasida to‘g‘ridan-to‘g‘ri qabulni ham qayd qilishi mumkin.
Qabul qilgan direktor, dastlab kiritgan foydalanuvchi, mas’ul xodim va vaqtlar saqlanadi.
Faolsizlantirilgan xodimning oldingi majburiyatini direktor kelishtira oladi; xodim o‘zi kira olmaydi.

Eski `manager_entries.kind=return` yozuvlari qayta yozilmaydi. Oldingi qaytarish sifatida ayiriladi,
lekin ularga soxta direktor tasdig‘i yaratilmaydi (`legacy`). Agar eski tushumlar qo‘lda `fund` sifatida ham
kiritilgan yoki topshirishlar yozilmagan bo‘lsa, tarixni operator kelishtirishi kerak. Dublikat mapping avtomatik emas.

## Kun yopilishi

Botdagi smenani tugatish va pul kunini yopish alohida. Smena tugasa ham topshirilmagan pul yo‘qolmaydi.
Direktor hisob kunini barcha valyutalarda saldo nol, pending topshirish va tekshirilmagan refund qolmaganda yopadi.
Oldingi kunning qoldig‘i carry sifatida hisoblanadi; sana filtri uni yashirmaydi.
Hisob sanasi va haqiqiy qabul qilish timestampi alohida saqlanadi: oldingi ish kunining topshirishi keyin
qabul qilinsa, tegishli hisob kuni tanlanadi, qabulning haqiqiy vaqti o‘zgartirilmaydi.

Yopilishda moliyaviy yozuvlarning fingerprinti saqlanadi. Keyin shu kungacha bo‘lgan davrga yangi yozuv,
refund manbasi yoki topshirish tasdig‘i kiritilsa, kun **qayta tekshirish** holatida ko‘rinadi.
Oldingi yopilish yozuvi o‘chmaydi. Xodimning faqat ismi o‘zgarishi kunni qayta ochmaydi.

## Migratsiya va API

Yangi `manager_money.migrate` bitta tranzaksiya/savepointda, qayta bajarishga xavfsiz.
Yangi jadvallar: `manager_return_receipts`, `manager_received`, `manager_refund_payers`, `manager_day_closings`.
Eski biznes yozuvlari, pul birliklari, smenalar yoki audit o‘zgartirilmaydi.

Direktor komandalar: `manager_received`, `manager_accept_cash`, `manager_accept_return`,
`manager_reject_return`, `manager_assign_refund`, `manager_close_day`.
Xodim o‘z `manager_request_return`ini yuboradi; mavjud `manager_record return` ham pending oqimiga o‘tadi.
Har API so‘rovida mavjud active-role/session/CSRF/Origin himoyasi va `Idempotency-Key` saqlanadi.
Yozish tranzaksiyasi parallel qabulda bitta qoldiqni ikki marta sarflashga yo‘l qo‘ymaydi.
Ko‘p so‘rovli o‘qishlar SQLite snapshotda, ichki chaqiruv tashqi tranzaksiyani commit qilmaydi.

Kabinet `/director-api/managers`: joriy saldolar va pending handoverlar; tanlangan davr jurnali/kuni;
refund review. Oddiy `/api/manager-account` va mavjud bot/Excel ham bir xil hisobdan foydalanadi.
Excelda qabul qilingan pul, pending, tasdiq manbasi va direktor uchun ish kunlari chiqadi.

## VDSga yangilash

Bu branch avvalgi direktor feature PR #20 ustiga qurilgan; main’ga merge yoki productionga avtomatik deploy yo‘q.
VDS hozir avvalgi `09f55ae2c468ce8ac1802f80bba04f569b019852`ni ishlatyapti.
Operator yangi branchni **alohida** checkout qilib, testlarni va yangi production backup nusxasida
migratsiya/idempotence/business rows preservation tekshiruvini bajarsin. So‘ng yangi konsistent backup olib,
ikkala servisni qisqa muddat to‘xtatib, faqat quyidagi runtime fayllarni yangilaydi:

`accounting.py`, `bot.py`, `core.py`, `director.py`, `i18n.py`, `miniapp.py`, `reports.py`,
`manager_money.py`, `web/accounting.js`, `web/director.js`.

Yangi dependency/secret yoki sayt deployi kerak emas. Oldingi hosting, env, custom deployment skriptlari
va o‘chiq auto-update holati saqlanadi. `Store`ni servis foydalanuvchisidan ochish migratsiyani bajaradi;
keyin servislar ishga tushiriladi. Kabinetdagi eski sessiya restartdan keyin qayta kirishni talab qilishi mumkin.
Avval test nusxasida qabul/to‘lov/kun yopishni tekshiring; tekshirish uchun productionga demo savdo yoki pul yozmang.

Rollback: eski biznes bazasini backup bilan avtomatik almashtirmang. Pending handoverlar bor paytda eski
`accounting.py`ga ko‘r-ko‘rona qaytish ularni qaytarilgan pul deb ayirishi mumkin. Bunday holatda yozishlarni
vaqtincha to‘xtatib, pendinglarni kelishtiring yoki yangi hisoblash qatlamini saqlab faqat UIni qaytaring.
Yangi jadvallar/audit saqlanadi. Tashqi umumiy kassa/bank reconciliation va eski opening balances bu ishda import qilinmaydi.
