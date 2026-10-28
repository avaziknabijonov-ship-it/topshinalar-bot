# TOPSHINALAR shinalar katalogi, 24.10.2026

Buyurtmachi bergan ikki Excel fayldan 250 qator o‘qildi. Asosiy TBR ro‘yxatidagi 3 mahsulot ikkinchi varaqda ham bor edi: ular takrorlanmadi. Jami 247 variant, 166 brend/model guruhi saqlandi. Razmer yoki PR farqi alohida mahsulotdir. `APLUS/COMPASAL D860/SPD86` yetkazib beruvchi ko‘rsatgan birlashtirilgan yozuv sifatida saqlandi; tasdiqsiz ikkita alohida mahsulotga aylantirilmadi.

## Narx va qoldiq

Yetkazib beruvchi fayllaridagi narxlar, bonuslar va sonlar import qilinmagan. `KATALOG.csv`dagi Narx_UZS va Qoldiq ustunlari bo‘sh. Bazadagi yangi mahsulotlar uchun ichki texnik narx 0 va `price_pending=1`; kartada «Narx kiritilmagan» ko‘rsatiladi. Ombor yozuvlari yaratilmagan, qoldiq «Qoldiq kiritilmagan» deb chiqadi.

Direktor kartadagi «Tahrirlash» orqali narxni belgilaydi. Mini Appdagi «Boshlang‘ich qoldiq»da mahsulot/omborni tanlab sonni kiritadi; 0 ham qabul qilinadi. Bu amal mahsulot/ombor uchun faqat bir marta ishlaydi. Keyingi kirimlar «Mahsulot kirimi» orqali mavjud qoldiqqa qo‘shiladi. Savatga narxsiz mahsulot qo‘shilganda narx maydoni bo‘sh: sotuv yoki КПni tasdiqlashdan oldin narxni yozish kerak.

CSV ro‘yxat ma’lumot uchun; unga narx yozish bot bazasini avtomatik o‘zgartirmaydi. Hozir narx va qoldiq ilova/chat menyusida kiritiladi.

## Rasmlar

247 variantdan 138 tasiga 71 model rasmi ulangan; 109 variantning aniq rasmi hali kerak.

Rasmlar ishlab chiqaruvchi va sotuvchi sahifalari/kataloglaridan olingan model tasvirlaridir; muayyan ombordagi aynan shu donaning fotosurati emas. Bir brend/modelning turli razmer va PR variantlari bir model rasmi bilan ko‘rsatilishi mumkin. Katalogdan olingan ayrim tasvirlar model nomi va protektor ko‘rinishini o‘z ichiga oladi. Rasm manbalari `assets/catalog-photo-sources.json`da, mahsulotning Excel manba fayli/varag‘i/qatori `assets/tyres.json`da saqlanadi.

Aniq modeli tasdiqlanmagan rasm qo‘yilmagan. Ular `RASMI-KERAK.csv`da ro‘yxatlangan. Ushbu modellarning rasmiy yoki yetkazib beruvchi rasmlari kerak. `W`, `Pro`, `JQ`, `KB`, `MAX`, `+` kabi model farqlari tasdiqsiz tashlab yuborilmadi va o‘xshash model surati bilan almashtirilmadi.

Direktor rasmni mahsulot kartasidan yuklashi mumkin. Lokal rasmlar serverdagi `assets/catalog/`dan olinadi, ko‘rsatish uchun tashqi sotuvchi saytiga bog‘lanmaydi.

## Yangilash va ishga tushirish

Mavjud bazani zaxiralang. Yangilangan kod va `assets/` papkasini to‘liq VPSga ko‘chiring. `bot.py` yoki `miniapp.py` ishga tushganda katalog bir martalik SKUlar bilan import qilinadi. Takroriy ishga tushirish mahsulotlarni ko‘paytirmaydi, qo‘lda kiritilgan nom/narx/qoldiq/rasmni qayta yozmaydi. Keyingi paketda ilgari bo‘sh bo‘lgan rasm qo‘shilsa, bo‘sh rasm to‘ldiriladi.

Paket haqiqiy savdo bazasini o‘z ichiga olmaydi. Haqiqiy VPSga joylash va Telegram ichida ko‘rish hali bajarilmagan. Asosiy sayt va MasterCoffee bazasiga ulanish qo‘shilmagan.
