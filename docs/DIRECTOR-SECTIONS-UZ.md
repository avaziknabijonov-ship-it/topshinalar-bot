# Direktor kabinetidagi biznes bo‘limlari

Bu feature `feature/director-premium-imports` (#22) ustiga qurilgan.
Production/VDS kodi, bazasi yoki servislari bu ishda o‘zgartirilmagan.

## Qo‘shilgan bo‘limlar

| Bo‘lim | Ma’lumot va amallar |
| --- | --- |
| Mahsulotlar | Ombor soniga bog‘lanmagan biznes katalogi, brend/razmer/faollik/valyuta filtrlari, yaratish, tahrirlash, mavjud Excel/PDF importi. Yangi mahsulot saytga avtomatik chiqarilmaydi. |
| Savdo tushumlari | Mavjud haqiqiy savdo/qarz to‘lovlari; mijoz, pulni olgan xodim, usul, valyuta, davr. Savdo summasi yoki boshqa qo‘lda olingan pul bu jurnalga qo‘shilmaydi. Qo‘lda tushum menejer pulida saqlanadi. |
| Xaridlar / tovar kirimi | Ta’minotchili xaridlar va alohida manba filtri bilan Excel/PDF/boshqa kirim. Mavjud ta’minotchili kirim va partiyalar, Excel/PDF amallari. Ta’minotchi kirimi boshqa kirimga takror kiritilmaydi. |
| Mijozdan qaytarishlar | To‘liq bekor qilingan savdolar, mahsulotlar, mijoz, xodim, qaytarilgan haqiqiy pul va sabab. «Savdoni tanlash» orqali mavjud xavfsiz to‘liq bekor qilish/tovar va to‘lov qaytarish tasdig‘i. Nol pul olingan bekor qilish ham ko‘rinadi. |
| Ta’minotchiga qaytarishlar | Mavjud partiyani nom/joy/sana orqali tanlash, son va sabab; haqiqiy qaytarishlar jurnali, valyuta/ta’minotchi/joy filtrlari. Asl kirim tannarxi saqlanadi. |
| Xarajatlar | Mavjud `manager_entries` xarajatlari, mas’ul va kiritgan xodim, valyuta/davr/ta’minotchi filtri. Yangi xarajat mavjud `manager_record` orqali. Ta’minotchiga bog‘langan menejer xarajati bitta yozuv bo‘lib ko‘rinadi. |

Mavjud KP/PDF ro‘yxati ham menyuda alohida. Savdo, mijozlar, ombor, ta’minotchilar,
menejer puli, xodimlar, hisobot, sayt katalogi va audit saqlangan.
Bot direktor menyusiga yangi boshqaruv tugmalari qo‘shilmadi; avvalgi yagona kabinet tugmasi qoladi.
Uzun desktop menyusi ichida vertikal aylantirish, kichik ekranda mavjud gorizontal menyu ishlaydi.

## Hisob va chegaralar

Yangi moliyaviy jurnal yoki parallel mahsulot bazasi yaratilmagan.
Barcha mutationlar mavjud biznes funksiyasi, tranzaksiya, idempotency, audit va outbox bilan.
Har bir yangi API GET mavjud direktor autentifikatsiyasi va faol rol tekshiruvidan o‘tadi.
Ichki ID ko‘rsatilmaydi. Eski UZS qiymati USD deb belgilanmaydi; noma’lum narx nol emas.

Xarajatlar bo‘limi **menejer xarajatlari** hisobidir. Umumiy kassa/bank, xarajatlarni umumiy
moliyaviy hisobga taqsimlash va sof foyda bu o‘zgarish bilan yaratilmagan.
Mijozdan qisman tovar qaytarish, savdodan mustaqil buyurtma lifecycle’i va xarid buyurtmasi
modullari mavjud emas; KP ularga almashtirib ko‘rsatilmagan. Yangi «Buyurtmalar» uchun
ishlamaydigan tugma chiqarilmagan. Sozlamalarning mavjud til/chiqish, xodim ruxsatlari,
ombor joyi turi va sayt konfiguratsiyasi tegishli amaldagi joylarida qoladi.
iBox integratsiyasi yoki to‘liq o‘rnini bosish da’vosi yo‘q.

## Excel

19 ta kategoriya: oldingi 15 taga Mahsulotlar, Menejer xarajatlari, Mijozdan qaytarishlar,
Ta’minotchiga qaytarishlar qo‘shilgan. Kirim kategoriyasida boshqa kirimlar alohida varaqda.
Menejer xarajatlari varag‘i manager-journal bilan solishtirish uchun shu yozuvlarning boshqa
ko‘rinishi: ikki varaqni qo‘shib umumiy xarajat hisoblamang. Mijozdan qaytarishdagi summa —
qaytarilgan pul, savdo qiymati esa alohida; ikki marta net qilish kerak emas.
Amallar sana bo‘yicha, mahsulot va qoldiqlar joriy `as_of` bilan. Valyutalar alohida.

## O‘rnatish / rollback

Qo‘shimcha schema, secret yoki dependency yo‘q. #20 → #21 → #22 migration/runbook talablari
saqlanadi. Hozirgi production versiyani tekshiring, fresh konsistent backup oling, nusxasida
migratsiya/tekshiruv bajaring; auto-update taymeri o‘chiq qoladi.

Ushbu qatlamning runtime fayllari: `director.py`, `director_sections.py`, `director_business.py`,
`director_reports.py`, `reports.py`, `web/director.js`, `web/director-business.js`,
`web/director-overview.js`, `web/director.css`.
Hosting identifikatori, audience, env, mavjud deploy skriptlari saqlanadi.

UI va read projection rollback’i uchun oldingi runtime fayllarni qaytarish mumkin;
yangi ko‘rinishlar orqali kiritilgan kirim/qaytarish/xarajatlarni o‘chirmang va eski DB backupini
avtomatik qaytarmang. Menejer pending topshirishlar bo‘yicha #21 rollback ogohlantirishi amal qiladi.

## Tekshiruv

288 Python testi (yangi 7 ta): direktor/xodim va read-only, narx/valyuta, kirimlarni takror
sanamaslik, haqiqiy xarajat/saldo, asl to‘lov saqlangan to‘liq bekor qilish, partiyadan qaytarish
idempotency/stock/asl tannarx/ta’minotchi qarzi, yangi eksport kategoriyalari va ID yo‘qligi.
Mavjud 4 Node UI suite, compileall, JS syntax, diff whitespace.

Real Chromium: desktop 1440×1000, mobil 390×844, barcha bo‘limlar, mahsulot tahriri,
xarajat yozish, kirim manbasini almashtirish, ta’minotchiga qaytarish, savdoni xavfsiz to‘liq
bekor qilish va qaytarishlar jurnali; mavjud login/RU/logout, import/qarz/Excel ham qayta tekshirilgan.

`docs/screenshots/business-sections-products.png`, `business-sections-supplier-returns.png`,
`business-sections-mobile.png` — vaqtinchalik lokal test bazasi. Jonli VDS amallari,
haqiqiy mijoz fayllari yoki production integratsiya tekshiruvi bajarilmagan.
