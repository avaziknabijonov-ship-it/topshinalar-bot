# Dashboard: tovarlar va xodimlar tahlili

Branch `feature/employee-own-sales-history` (#24) ustiga qurilgan.
VDS, production baza, hosting/audience yoki servislar bu ishda o‘zgartirilmagan.

## Ikkita tahlil

Direktorning asosiy ekranida umumiy ko‘rsatkichlardan keyin:

1. **Tovarlar bo‘yicha tahlil** — sotilgan dona, shu tovar qatnashgan savdolar soni va
   tovarning sotuv qiymati. Grafikni dona, summa yoki savdolar soniga almashtirish mumkin.
2. **Xodimlar bo‘yicha tahlil** — savdolar, alohida mijozlar va sotilgan donalar soni,
   savdo summasi, shu savdolardan hozirgacha to‘langan pul va hozirgi qolgan mijoz qarzi.
   Grafik: summa, savdolar soni, dona yoki qarz.

Har birida valyuta, nom bo‘yicha qidirish, haqiqiy Top-5, ochiladigan to‘liq jadval va
10 qatorli sahifalash mavjud. Sana oralig‘i dashboardning mavjud filtridan olinadi.
USD/UZS alohida; kurs yoki konvertatsiya ishlatilmaydi. Ma’lumot bo‘lmasa soxta bar yo‘q.

Grafik/jadvaldagi ↗ savdolar bo‘limiga mahsulot yoki xodim, asl valyuta va `active` filtri
bilan o‘tadi. Davr saqlanadi. Tovar filtri bilan ochilganda jadval butun savdolarni ko‘rsatadi:
bu jadval summasi butun chekniki, faqat tovar qiymati tahlilda. Bu farq ekranda yozilgan.

## Hisob qoidalari

`director_analytics.analytics` ikkala tahlilni bitta SQLite read snapshot’dan hisoblaydi.
Faqat tanlangan sanada yaratilgan faol savdolar olinadi. Bekor qilingan savdo,
kirim, transfer yoki ombor soni savdo sifatida hisoblanmaydi.

- Tovarlar **product ID + valyuta** bo‘yicha; o‘xshash nom/razmer bilan birlashtirilmaydi.
- Bir tovar bir savdoda bir nechta joy/qator bilan sotilsa dona va satr qiymatlari qo‘shiladi,
  lekin savdolar soni bir marta sanaladi.
- Xodim summasi har bir savdoning `sales.total` qiymatidan bir marta olinadi;
  mahsulotlar soniga ko‘paytirilmaydi. Mas’ul — savdoni yaratgan `sales.actor`.
- Eski xodim/mahsulot faolsiz bo‘lsa ham haqiqiy tarix tahlildan yo‘qolmaydi.
- Tovar qiymati sale_items’dagi asl narx/dona/chegirmadan hisoblanadi. Tarixiy chegirmada
  dastlabki Store.items kabi half-even sent yaxlitlash ishlatiladi; hisob butun sonlarda.
- Bir savdoning satrlari jami `sales.total` bilan tekshiriladi. Mos kelmasa tegishli
  tovar summasi **noma’lum**, 0 emas. Tekshirish kerakligi aynan shu valyutada ko‘rsatiladi.
  Satrlar butunlay yo‘q bo‘lsa ham savdo tekshiruv soniga kiradi, xodim donasi noma’lum.
- Qarzni yoki tushumni tovarlarga taxminiy taqsimlash yo‘q. Tannarx/foyda hisoblanmaydi.
- Xodimning `paid_to_date` va `debt_to_date` qiymatlari tanlangan savdolarning **joriy holati**.
  Bu mijoz qarzi, menejer zimmasidagi pul alohida hisoblanadi. Bu davrda xodim shaxsan qabul qilgan pul emas; keyinroq kiritilgan haqiqiy to‘lov ham
  shu savdoning hozirgi qarzini kamaytiradi. Asosiy ekrandagi davr tushumi o‘z ma’nosini saqlaydi.

## API, ruxsat va aniqlik

`GET /director-api/analytics?start=YYYY-MM-DD&end=YYYY-MM-DD` va overview ichidagi
`analytics` bir xil himoyalangan projection’dan foydalanadi. Faqat mavjud faol direktor.
Employee MiniApp `/api/dashboard` yoki `/api/my-sales` orqali boshqa xodim tahlilini olmaydi;
#24 dagi shaxsiy tarix chegaralari o‘zgarmagan. Ommaviy sayt API’si o‘zgarmagan.

Backend butun sentlarda. Analytics JSON’dagi pul maydonlari decimal **string sentlar**:
`"12500"` — `125.00 USD`; `null` — ma’lumot yetarli emas. Brauzer BigInt bilan formatlaydi
va saralaydi; faqat bar kengligi 0–100 oralig‘ida hisoblangan geometriyadir.
9 007 199 254 740 993 sent ham aniqligini yo‘qotmaydi.

## Excel

21 kategoriya: avvalgi 19 taga tovar va xodim tahlili qo‘shilgan. Tovar tahlili bilan
valyutalar bo‘yicha tekshirish kerak bo‘lgan savdolar soni uchun alohida varaq ham beriladi.
Ichki ID, tannarx/foyda yoki token chiqarilmaydi. Sana va `as_of` saqlanadi.

Excel 15 ta ahamiyatli raqamdan keyin aniqlik yo‘qotishi mumkin. 10^15 sent va undan
katta pul qiymatlari XLSX’da aniq decimal matn sifatida chiqariladi; odatiy summalar
raqamli katak bo‘lib qoladi. Katta matn qiymatlarni Excel SUM avtomatik jamlamaydi;
bu sentlarni yashirincha yaxlitlashdan saqlash uchun qilingan.

## O‘rnatish va rollback

Yangi schema/migratsiya, secret yoki dependency yo‘q. Avvalgi stacked branchlar/runbooklar
qoidalari saqlanadi. Fresh konsistent backup va nusxadagi tekshiruvdan keyin operator
runtime paketini birga yangilaydi. Auto-update taymeri avvalgidek o‘chiq qoladi.

Runtime: `director_analytics.py`, `director_overview.py`, `director.py`, `director_reports.py`,
`reports.py`, `miniapp.py`, `web/director-analytics.js`, `web/director-overview.js`,
`web/director-business.js`, `web/director.html`, `web/director.css`.
`.github/workflows/tests.yml` faqat yangi Node tekshiruvini CIga qo‘shadi; productiondagi
mahalliy deploy/config fayllari bilan almashtirilmaydi.

Read projection va UI rollback’i oldingi runtime paket bilan mumkin; biznes yozuvlarini
o‘chirish yoki bazani eski backup bilan almashtirish talab qilinmaydi. #24 shaxsiy tarix
ruxsat tuzatishini rollback bilan olib tashlamang. Main merge, production deploy/restart yo‘q.

## Tekshiruv

311 Python unittest: yangi 11 tahlil testi ko‘p mahsulot/joyli savdoda ikki marta sanamaslik,
bekor qilish/kirim/transferni chiqarish, davr va keyingi sana to‘lovi, valyutalar,
faolsiz tarix, nom bir xil bo‘lgan turli tovarlar, eski chegirma sentlari, nomuvofiq/yo‘q satrlar,
read-only/huquqlar, katta sent API/XLSX aniqligi va ikki eksportni qamraydi.
5 Node suite, shu jumladan BigInt format/saralash/unknown va valyuta/qidirish testi.
Compileall, JS syntax va whitespace tekshiruvlari ham o‘tgan.

Chromium desktop 1440×1100 va mobil 390×844: ikki tahlil, haqiqiy grafiklar, saralash,
valyuta/qidirish, jadval/sahifalash, mahsulot/xodim savdolariga aniq drill-down, RU,
bo‘sh davr va gorizontal document overflow yo‘qligi. Eski direktor/import/moliya smoke’i ham o‘tgan.

`dashboard-two-analytics-desktop.png`, `dashboard-two-analytics-mobile.png` faqat
vaqtinchalik test yozuvlaridan. Jonli VDS tahlili va production eksporti tekshirilmagan.
Bu iBox’dan ko‘chirish yoki to‘liq kassa/bank va sof foyda moduli emas.
