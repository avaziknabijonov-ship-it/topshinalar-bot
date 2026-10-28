# TOPSHINALAR: oxirgi tekshiruv

**131 ta avtomatik test muvaffaqiyatli o‘tdi.** Barcha sinovlar vaqtinchalik bazalar va soxta Telegram javoblari bilan bajarildi. Foydalanuvchining haqiqiy botiga yozuv yuborilmadi.

## Shinalar katalogi tekshiruvi, 24.10.2026

11 ta yangi test: 250 manba qatoridan 247 takrorlanmaydigan variant, narx/qoldiqni import qilmaslik, qayta importda qo‘lda kiritilgan ma’lumotni saqlash, mavjud kartani takrorlamaslik, rasmlarning fayllari va xavfsiz yo‘llari, lokal rasmni API/chat orqali yuborish, narx/qoldiq kiritilmaganini ajratish, metrik/dyuymli/diagonal razmer qidiruvi va xato importni rad etish. Boshlang‘ich qoldiqni 0 yoki musbat son bilan bir marta kiritish, takroriy so‘rov, rollar va noto‘g‘ri sonlar ham tekshirildi.

Brauzerda 247 variant, `12,00 R20` qidiruvining 36 natijasi, haqiqiy lokal rasm va narx/qoldiq belgisi tekshirildi. Sinov bazasi sun’iy. Haqiqiy Telegramga ommaviy katalog xabarlari yuborilmadi.

## Mini App tekshiruvi

- 12 ta yangi test: Telegram imzosi va amal muddati, ruxsatlar, takroriy so‘rovni bir marta bajarish, tranzaksiya xatosida to‘liq qaytarish, butun dona, haqiqiy kattalikdagi Telegram ID, API/chat orasida umumiy qoldiq, КП navbati, rasm yuklash ruxsatlari va HTTP API.
- Modeldagi raqamni razmer deb qabul qilmaslik uchun 1 ta regressiya testi.
- Brauzerda ajratilgan sun’iy bazada: `315 80` qidiruvi, savat, mijoz/ombor tanlash, yakuniy tasdiqlash, sotuvni saqlash, 2 450 000 UZS qarzning paydo bo‘lishi, direktor paneli va rus tiliga o‘tish tekshirildi. Sinov bazasi va kirish yordamchisi tarqatiladigan arxivga kiritilmagan.
- JavaScript sintaksisi tekshirildi. Haqiqiy Telegram ichida telefon sinovi, haqiqiy rasm yuklash/yuklab olish, HTTPS va server qayta yoqilishi hali VPSga joylashgach tekshiriladi.

## Tekshirilgan oqimlar

- Oldingi 76 ta test: ruxsatlar, tranzaksiyalar, ombor, qarz/to‘lov, davomat, eslatmalar navbati, Labo, ikki til, Excel/PDF, eski bazalarni tiklash va Linux nusxa bloki.
- 31 ta yangi test: oddiy va muqobil razmerlar, katta-kichik harf bilan qidirish, rasmli kartalar va sahifalash, kartadan sotuv/КП, nom orqali mijoz/ombor/mahsulot tanlash, mahsulot savati, Orqaga, Bekor qilish va yakuniy tasdiqlash.
- Direktor tahriri eski sotuv yozuvlarini va qoldiqni o‘zgartirmasligi; o‘zga xodim va eskirgan tugmalar orqali yozuvni o‘zgartirishni bloklash; tanlash dialogi va tugmalarning qayta ishga tushganda saqlanishi.
- To‘liq sotuvni bekor qilish: qoldiqni tiklash, dastlabki to‘lovlarni saqlash, alohida pul qaytarish hisobi, ikkinchi marta bekor qilishni bloklash, qaytarishda xato bo‘lsa butun tranzaksiyani orqaga qaytarish, tasdiqlash paytida to‘lov o‘zgarganini aniqlash.
- Bekor qilingan qarzning hisobotda 0 bo‘lishi; qaytarilgan pulning aynan qaytarilgan sanadagi hisobotga tushishi.
- Minimal qoldiq, takroriy xabarni to‘xtatish, qoldiq tiklangach qayta xabar berish, bo‘sh nuqtadagi 0 qoldiq va bildirishnomani o‘chirish.
- Qarz muddatini belgilash/formatlash, faqat o‘z qarzini boshqarish, muddati o‘tgan qarzlar, kunlik eslatma, faol bo‘lmagan xodimga yubormaslik, to‘liq to‘langan qarzni eslatmaslik.
- Direktorning kunlik xulosasi qayta ishga tushganda takrorlanmasligi.
- Eski v1 sxemasidan ma’lumot va ruxsatlarni saqlab ko‘chish; zaxiradagi barcha jadvallarni alohida tiklangan nusxa bilan solishtirish; buzilgan tashqi kalitni aniqlash; tiklangan bazada qarz to‘lovi va tugallanmagan dialogni davom ettirish.

## Tayyor, lekin serverda hali bajarilmagan

systemd xizmatlari va timer sintaksisi tekshirildi. Haqiqiy VPSda o‘rnatish, SSH yopilgandagi ish, VPS qayta yoqilishi, Telegram tugmalari va rasmlarining haqiqiy qurilmalardagi ko‘rinishi hali qabul sinovini talab qiladi. Docker bu muhitda mavjud emas, image build bajarilmadi. Windowsda jonli sinov bu muhitda takrorlanmadi.

Arxivda haqiqiy baza yoki token yo‘q. Avtomatik jarima qoidalari buyurtmachidan olinmagan. Sotuvni bekor qilish butun sotuv uchun; haqiqiy tovar va pulning qaytarilishi direktor tomonidan tasdiqlanadi, bot bank operatsiyasini bajarmaydi.
