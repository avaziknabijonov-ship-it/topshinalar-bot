# TOPSHINALAR Telegram Mini App

Mini App xodimlar va direktor uchun mavjud bot ichida ochiladi. Sotuv, qoldiq, mijozlar va qarzlar chat-bot bilan umumiy bazada saqlanadi. MasterCoffee bilan integratsiya yo‘q.

## Foydalanish

Xodim: katalogda razmer/nom/brendni qidiradi, mahsulot va miqdorni savatga qo‘shadi, mijoz/ombor/to‘lovni tanlaydi, ko‘rib tasdiqlaydi. Qarz, КП, mijozlar, qo‘ng‘iroq, vazifa, Labo, davomat va hisobotlar mavjud.

Direktor: umumiy sotuvlar, tushum, qarzlar va minimal qoldiqni ko‘radi; mahsulot, rasm, ombor, minimal qoldiq, jarima va vazifalarni boshqaradi. Sotuvni to‘liq bekor qilishda sabab hamda tovar/pul qaytarilganini tasdiqlaydi. Bankdan pul avtomatik qaytarilmaydi.

Mijoz va mahsulotlar nomi orqali tanlanadi. O‘zbek/rus tillari almashtiriladi. Rasm bo‘lmasa «Rasm yuklanmagan» chiqadi; direktor haqiqiy mahsulot rasmini kartadan yuklaydi. Kerakli amal Mini Appda ko‘rinmasa, mavjud chat menyusi ham ishlaydi.

## VPSga ulash

Avval `deploy/VPS-UZ.md` bo‘yicha bot, direktor/xodim IDlari, doimiy baza, zaxira va Python muhiti sozlanadi. Yangilashdan oldin mavjud bazadan zaxira oling. Bo‘sh bazani mavjud bazaning o‘rniga ko‘chirmang.

1. Subdomen DNS A yozuvini VPS IP manziliga yo‘naltiring. Masalan, `bot.example.uz` o‘rniga o‘z domeningizni ishlating.
2. `web/`, `miniapp.py` va qolgan yangilangan kodni `/opt/topshinalar`ga joylashtiring. Bot va Mini App aynan bitta bazani ochishi kerak.
3. `/etc/topshinalar.env`ga `PUBLIC_APP_URL=https://SIZNING-DOMEN` qo‘shing. URL faqat origin bo‘lsin, oxirida sahifa yo‘li bo‘lmasin. Tokenni shu maxfiy faylda saqlang.
4. `deploy/topshinalar-miniapp.service`ni `/etc/systemd/system/`ga o‘rnating. `systemctl daemon-reload`, keyin `systemctl enable --now topshinalar-miniapp` buyrug‘ini bajaring. Xizmat 127.0.0.1:8080da ishlaydi.
5. Nginx o‘rnating; `deploy/miniapp.nginx.conf`dagi namunaviy domenni o‘zgartiring, konfiguratsiyani yoqing va `nginx -t` bilan tekshiring. Certbot bilan haqiqiy domenga HTTPS sertifikati oling. Faqat 80/443 portlar ochiladi; 8080ni tashqariga ochmang.
6. Chat-bot xizmatini qayta ishga tushiring. `/start` yoki `/app`dan Mini App tugmasi chiqadi. Ixtiyoriy: BotFather Menu Button URL manziliga shu HTTPS URLni belgilang.
7. Har bir ruxsatli xodim o‘z Telegram hisobida ochib tekshiradi. Ruxsatsiz odam ilovadagi ma’lumotni ko‘ra olmaydi. Ilova ochiq holda bir soatdan oshsa, qayta ochish kerak bo‘lishi mumkin.

Docker varianti: `.env`ni to‘ldirib `docker compose up -d --build` bajaring. `bot` va `miniapp` bir `bot-data` volume ishlatadi. Hostdagi Nginx 127.0.0.1:8080ga uzatadi. systemd va Docker nusxalarini bir vaqtda ishga tushirmang.

## Qabul sinovi

VPSda xodim va direktor bilan: kirish ruxsati, rasm, razmer qidirish, sotuv/qoldiq, qisman to‘lov/qarz, КП PDF, Excel, eslatma va tilni tekshiring. Telegramdagi haqiqiy telefonlarda tugmalar va klaviatura qulayligini tekshiring. Bot/VPS qayta ishga tushganda ma’lumot saqlanishini va xizmatlar avtomatik ko‘tarilishini tekshiring.

Avtomatik sinovlar: `python -m unittest discover -s tests -v`. Batafsil natijalar `TEST-HOLATI.md`da. Bu paketda token, haqiqiy savdo bazasi va brauzer sinovi uchun kirish yordamchilari yo‘q.
