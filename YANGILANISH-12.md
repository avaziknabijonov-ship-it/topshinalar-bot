# TOPSHINALAR: 12 ta qulaylik

## Qidirish va kundalik ishlash

1. **Oddiy razmer qidiruvi.** Asosiy menyuda `315/80`, `315 80`, `315/80R22.5` yoki mahsulot/brend nomini yuboring. Harf kattaligi ahamiyatli emas. Dialog ichida yozilgan matn o‘sha qadamning qiymati yoki qidiruvi bo‘lib qoladi.
2. **Mahsulot kartasi.** Surat, nom, brend, razmer, narx va savdo nuqtalari bo‘yicha qoldiq bir kartada. Har sahifada 4 ta mahsulot. Surat bo‘lmasa aniq yoziladi; sifat yuklangan asl suratga bog‘liq.
3. **Karta tugmalari.** `Sotish`, `КП tayyorlash`, `Rasmni ko‘rish`; direktor uchun `Tahrirlash`. Sotish yoki КП tugmasi tanlangan mahsulotni eslab qoladi; keyin mijoz, ombor, dona va narx tanlanadi.
4. **Nom bo‘yicha tanlash.** Mijoz, ombor, mahsulot, sotuv, xodim va tegishli yozuvlar tugmalardan tanlanadi. Nom yoki telefon yozib filtrlash, oldingi/keyingi sahifaga o‘tish bor. ID orqali eski kiritish usuli ham saqlangan. Mijozlar, vazifalar, КПlar, xodimlar va nuqtalar ro‘yxatlari ham sahifalanadi.
5. **Orqaga va bekor qilish.** Har bir forma qadamida mavjud. Orqaga oldingi qiymatni qayta tanlash imkonini beradi, undan oldingi ma’lumotlar saqlanadi. Birinchi qadamdan Orqaga menyuga qaytaradi. Bekor qilish tasdiqlanmagan operatsiyani yozmaydi.
6. **Yakuniy tekshiruv.** Sotuvdan oldin mahsulotlar, dona, narx, jami, to‘langan summa, qolgan qarz, mijoz va ombor ko‘rinadi. `Tasdiqlash` bosilmaguncha savdo saqlanmaydi. Tugma orqali bir nechta mahsulot qo‘shish yoki eski uch maydonli qatorni yozish mumkin.

## Direktor va hisoblar

7. **Xato sotuvni bekor qilish.** Faqat direktor: sotuvni tanlash → sabab → olingan pul qaytarilganini tasdiqlash → yakuniy tasdiqlash. Tovar dastlabki nuqtaga qaytadi, qarz faol ro‘yxatdan chiqadi. Sotuv va dastlabki to‘lovlar o‘chirilmaydi; alohida qaytarilgan pul yozuvi va audit saqlanadi. Takroriy bekor qilish va bekor qilingan sotuvga yangi to‘lov bloklangan. Tasdiqlash oralig‘ida to‘lov o‘zgarsa summa qayta tekshiriladi.

   Bu butun xato sotuvni bekor qilish funksiyasi. Tovar haqiqatda qaytarilgan va olingan pul mijozga to‘liq qaytarilgan bo‘lishi kerak. Bot bank orqali pul o‘tkazmaydi. Qisman tovar/pul qaytarish yoki avansga o‘tkazish bu oqimda yo‘q. Labo haqi alohida bo‘lib qoladi.

8. **Mahsulotni yangilash.** Direktor nom, brend, razmer, narx va suratni tahrirlaydi. `-` oldingi qiymatni saqlaydi. Eski sotuv va КПning nom/narx nusxalari hamda ombor qoldig‘i o‘zgarmaydi. Yangi rasm oddiy Telegram fotosi sifatida yuboriladi.
9. **Minimal qoldiq.** Direktor mahsulot, nuqta va minimumni belgilaydi. Qoldiq minimumga teng yoki undan kam bo‘lsa direktorlarga xabar keladi. Xabar har tekshiruvda takrorlanmaydi; qoldiq tiklanib yana kamayganda yangidan keladi. Minimum `0` bo‘lsa xabar o‘chadi. `Kam qolgan tovarlar` orqali joriy holat ko‘riladi.
10. **Qarz muddati.** Qisman to‘langan sotuv saqlangach `To‘lov muddati` tugmasi chiqadi. Muddat `YYYY-MM-DD` shaklida belgilanadi yoki `-` bilan olinadi. `Qarzlar` va `Muddati o‘tgan qarzlar` bo‘limlari bor. Xodim o‘z qarzli sotuvlarini, direktor barchasini ko‘radi. Muddatga yetgan va kechikkan qarzlar uchun Toshkent vaqti bilan 09:00dan keyin mas’ul xodim va direktorlarga kuniga bir marta eslatma yuboriladi. To‘langan va bekor qilingan qarz eslatilmaydi. Belgilanmagan muddat taxminan to‘ldirilmaydi.
11. **Kunlik xulosa.** `Kunlik xulosa` direktor uchun bugungi holatni ko‘rsatadi. Avtomatik xulosa yangi kun boshlangach avvalgi kun uchun bir marta yuboriladi: faol sotuvlar, savdo summasi, pul tushumi, qaytarilgan pul, sof tushum, jami qarz, qo‘ng‘iroqlar va ochiq vazifalar. Bot qayta ochilishi xulosani takrorlatmaydi. Server ishlamagan kunlar uchun qo‘lda davr hisobotini olish mumkin.
12. **Zaxiradan tiklashni tekshirish.** `backup.py --verify-restore` nusxani alohida vaqtinchalik bazaga tiklaydi, yaxlitligi, tashqi kalitlari va barcha jadvallardagi yozuvlarini solishtiradi. Ishlayotgan bazani almashtirmaydi. systemd kunlik zaxira xizmatiga shu tekshiruv qo‘shilgan. Tiklangan bazada qarz to‘lovi va tugallanmagan dialogni davom ettirish avtomatik sinovda tekshirildi.

## Yangilash tartibi

1. Ishlayotgan botni to‘xtating. Mavjud bazadan zaxira oling.
2. Arxivdagi barcha dastur fayllari va `assets`ni yangilang. Yangi `usability.py` ham kerak. `.env`, `settings.env`, haqiqiy baza, `data` va `.venv`ni o‘chirmang.
3. Mavjud bazani yangi dastur bilan ochganda yangi maydonlar va jadvallar qo‘shiladi. Eski yozuvlar saqlanadi. Minimal qoldiq va qarz muddatlari foydalanuvchi belgilamaguncha qo‘yilmaydi.
4. Windowsda `START-WINDOWS.bat`ni oching; Dockerda image’ni qayta build qiling; systemdda xizmatni qayta ishga tushiring. VPS timeriga tekshirilgan zaxira uchun yangilangan backup service faylini ham o‘rnating.
5. Botda `/start` bosing. Telegram orqali yangi kartalar, tugmalar va ikki tildagi oqimlarni qabul sinovidan o‘tkazing.

107 ta avtomatik test o‘tdi. Telegram serveri va VPSda jonli qabul sinovi bu muhitda bajarilmagan. Avtomatik jarima qoidalari bu yangilanishga kirmaydi: ular buyurtmachi belgilagach qo‘shiladi; qo‘lda direktor jarimasi ishlashda davom etadi.
