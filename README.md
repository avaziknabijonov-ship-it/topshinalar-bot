# TOPSHINALAR — xodimlar uchun Telegram bot, v1

## 24.10.2026: haqiqiy shinalar ro‘yxati

Ikkita yuborilgan Excel fayldan 247 variant qo‘shildi. Brend, model, razmer va PR saqlanadi; yetkazib beruvchining narxlari, bonuslari va qoldiqlari olinmadi. Bot/Mini App ishga tushganda katalog avtomatik import qilinadi. Narx/qoldiq kiritilmagani alohida yoziladi. Qayta ishga tushirish qo‘lda kiritilgan narx, qoldiq va kartalarni almashtirmaydi. `KATALOG-UZ.md`, `KATALOG.csv` va `RASMI-KERAK.csv`ga qarang.

## Telegram Mini App

**131 ta avtomatik test o‘tdi.** Bot ichida ochiladigan veb-ilova qo‘shildi: rasmli katalog, razmer/brend/ombor qidiruvi, savat, sotuv va КП, mijozlar, qarzlar hamda direktor/xodim ish paneli. Chat va Mini App bir SQLite bazasidan foydalanadi. Mini Appni ulash uchun VPS, domen/subdomen va HTTPS kerak; tartibi `MINIAPP-UZ.md`da. Hozirgi paket serverga joylashtirilmagan.

## Oldingi yangilanish: 12 ta qulaylik

**107 ta test o‘tdi.** Oddiy razmer qidiruvi, mahsulot kartalari va tugmalar, sahifalangan tanlash, mahsulot savati, Orqaga/Bekor qilish, tushunarli tasdiqlash, direktor uchun sotuvni bekor qilish va pul qaytarish hisobi, mahsulotni tahrirlash, minimal qoldiq, qarz muddatlari/eslatmalari, kunlik xulosa va zaxiradan tiklash tekshiruvi qo‘shildi. Tafsilot va yangilash tartibi: `YANGILANISH-12.md`. Quyidagi sanali bo‘limlar oldingi yangilanishlar tarixidir; eng yangi holat shu bo‘lim va `TEST-HOLATI.md`da.

VPSga systemd orqali joylash va kunlik zaxira uchun `deploy/VPS-UZ.md`ga qarang. Oxirgi tekshiruv chegaralari `TEST-HOLATI.md`da. Asosiy kirish nuqtasi bir baza bilan ikki nusxani bloklaydi.

Bu alohida ichki bot. MasterCoffee sayti, bazasi va Telegram botiga ulanmaydi. TOPSHINALAR saytiga ham avtomatik integratsiya o‘rnatilmagan. Barcha ma’lumot botning o‘z SQLite bazasida saqlanadi. Windows ochish dasturi bazani foydalanuvchining doimiy AppData papkasida saqlaydi; dastur arxivi boshqa papkaga ochilganda ham o‘sha baza ishlatiladi.

## Tayyor bo‘limlar

- 2 tagacha direktor, 4 tagacha xodim; faqat ruxsat berilgan Telegram IDlar kiradi.
- O‘zbekcha va ruscha menyu, dialog, eslatma, PDF va Excel hisobotlari.
- Ish kunini boshlash/tugatish va kunlik yozma hisobot. Direktorlarga boshlanish/tugash xabari, tugashda Excel hisoboti.
- Mijozlar bazasi, qidirish, aloqa ma’lumotlari va mijozning qo‘ng‘iroq, sotuv, КП, vazifa va yetkazib berish tarixi.
- Mahsulot va savdo nuqtalarini direktor kiritadi. Shina nomida brend, o‘lcham va o‘q turini yozish mumkin. Telegram orqali rasm qo‘shish va ko‘rish.
- Nuqta bo‘yicha kirim, qaytarish, direktor uchun hisobdan chiqarish, mavjud qoldiq va assortiment qidiruvi.
- Bir sotuvda bir nechta mahsulot, miqdor, narx, to‘lov turi va qisman to‘lov. Sotuv tasdiqlanganda qoldiq kamayadi; yetarli bo‘lmasa butun sotuv bekor qilinadi.
- Qarzning keyingi to‘lovlari va barcha to‘lovlarning tarixi.
- КП PDF: mahsulotlar, jami summa, mijoz, tanlangan to‘lov usuli va olib ketish/yetkazib berish sharti. Qoldiq kamaymaydi. КП holatini o‘zgartirish va qayta yuklab olish.
- Sovuq qo‘ng‘iroqlar: mijoz, natija va izoh. Qayta qo‘ng‘iroqni alohida eslatma qilib belgilash.
- CRM vazifalari, Toshkent vaqti bo‘yicha eslatmalar va bajarilganini belgilash. Direktor xodimga vazifa topshirishi mumkin.
- Labo: mijoz, bog‘langan sotuv (ixtiyoriy), haydovchi, manzil, yetkazish narxi, yetkazish uchun to‘langan summa, holat. Transport to‘lovi mahsulot to‘lovidan alohida.
- Kun/hafta/oy yoki istalgan sana oralig‘i bo‘yicha Excel hisobotlari: sotuvlar, sotilgan mahsulotlar, to‘lovlar, qo‘ng‘iroqlar, yetkazish, ish kunlari, jarimalar, КП, ochiq vazifalar va joriy qoldiq.
- Xodim hisobotida o‘z operatsiyalari; direktor hisobotida barcha xodimlar. Mijozlar bazasi va assortiment jamoa uchun umumiy.
- Jarimalar faqat direktor tomonidan sabab va summa bilan qo‘lda kiritiladi. Avtomatik jarima va kechikish qoidalari yo‘q — buyurtmachi keyin belgilaydi.

## Ishga tushirish uchun kerak

1. TOPSHINALAR xodimlari uchun **alohida Telegram bot tokeni**. MasterCoffee tokenini ishlatmang.
2. 2 direktor va 4 xodimning raqamli Telegram IDlari.
3. Doimiy ishlaydigan server, Docker va doimiy disk. Chat-bot polling orqali ishlaydi. Mini App uchun alohida HTTPS domen/subdomen kerak.
4. Real mahsulotlar, narxlar, savdo nuqtalari va boshlang‘ich qoldiqlar. Paketda haqiqiy savdo ma’lumotlari yo‘q.

Tokenni serverdagi `.env` fayliga kiriting; kodga yozmang va Gitga qo‘shmang. Token tarqatishga mo‘ljallangan arxivda yo‘q.

### Windowsda tez ochish

1. Arxivni to‘liq oching. ZIP ichidan to‘g‘ridan-to‘g‘ri ishga tushirmang.
2. `START-WINDOWS.bat`ni ikki marta bosing. Python 3.11+ kerak; yo‘q bo‘lsa ochilgan oynada manzil ko‘rsatiladi.
3. Birinchi ochishda kutubxonalar internetdan o‘rnatiladi, keyin bot tokeni so‘raladi. Token kiritilishi ekranda ko‘rinmaydi; ma’lumot faqat shu kompyuterdagi `.env`da saqlanadi.
4. Oynada chiqqan shaxsiy Telegram havolasini ochib START bosing. Shu Telegram hisob direktor sifatida qo‘shiladi. IDni qo‘lda topish shart emas.
5. Oynani ochiq qoldiring. Kompyuter yoqilgan va internet ulangan bo‘lishi kerak. Keyingi safar shu BATni yana ochasiz. Bir vaqtda ikki marta ochmang.

Bu paket ichida token yo‘q. `.env` yoki `data` papkasini boshqa odamlarga yubormang. Ikkinchi direktor va xodimlar keyin `.env`dagi ID ro‘yxatlariga qo‘shiladi. Telefon orqali tasdiqlash va jonli Telegram sinovi ushbu muhitda tarmoq cheklovi sabab yakunlanmagan. Windows launcher kodi tayyor; Windows kompyuterida jonli sinov hali bajarilmagan.

### Docker bilan

```sh
cp .env.example .env
# .env faylida BOT_TOKEN, DIRECTOR_IDS, EMPLOYEE_IDS ni to‘ldiring.
docker compose up -d --build
docker compose logs -f --tail=50 bot
```

Misol IDlar haqiqiy odamlar emas: `DIRECTOR_IDS=111111,222222`, `EMPLOYEE_IDS=333333,444444,555555,666666`.

Bot faqat shaxsiy chatda ishlaydi. Har bir xodim botni ochib `/start` bosishi kerak; bot suhbat boshlamagan odamga xabar yubora olmaydi. Begona foydalanuvchi `/start` bosganda uning IDsi ko‘rinadi, lekin ichki ma’lumotlar ochilmaydi. IDni direktor tekshiradi va `.env`dagi tegishli ro‘yxatga kiritadi. Ro‘yxat o‘zgarsa botni qayta yarating:

```sh
docker compose up -d --force-recreate bot
```

Bot allaqachon webhook bilan ishlayotgan tokenni aniqlasa to‘xtaydi; boshqa bot ishini buzish uchun webhookni avtomatik o‘chirmaydi. Bir token uchun faqat bitta bot nusxasini ishlating.

### Python bilan

Python 3.11+ va Unicode TrueType shrift kerak. Linux uchun Docker ichida DejaVu o‘rnatiladi. Windows/macOSda `PDF_FONT`ni mos shrift fayliga yo‘naltiring. `Asia/Tashkent` vaqt bazasi tizimda mavjud bo‘lishi kerak; Windowsda `pip install tzdata` kerak bo‘lishi mumkin.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
set -a
. ./.env
set +a
python bot.py
```

Yuqoridagi muhitni yuklash buyruqlari Bash uchun. Docker `.env`ni o‘zi o‘qiydi.

## Birinchi sozlash

Direktor: `/start` → tilni tanlash → «Nuqta qo‘shish» → «Shina qo‘shish». Keyin xodim yoki direktor «Mahsulot kirimi» orqali boshlang‘ich qoldiqni kiritadi. Nuqta va mahsulot IDlari `/points` va `/stock`da ko‘rinadi.

Har bir yozuv kiritish dialogi ma’lumotlarni ketma-ket so‘raydi. Yakunda ma’lumotlarni tekshirib **Tasdiqlash** bosing. Tasdiqlanguncha sotuv yoki kirim saqlanmaydi. `/cancel` operatsiyani bekor qiladi. Dialog paytida `/clients`, `/stock` yoki `/points` ko‘rish joriy qadamni yo‘qotmaydi.

Sotuv/КПda har bir mahsulot alohida qatorda:

```text
ID | dona | bir dona narxi UZS
1|4|2400000
1-4-2400000
1 4 2400000
```

Uchala ajratish usuli ham sotuv va КПda ishlaydi; misollar bitta mahsulotni yozishning uch xil usuli, ularni bir paytda yubormang. Bir nechta mahsulotni alohida qatorlarda yozing; har qator o‘z formatida bo‘lishi mumkin. Bo‘shliq bilan ajratganda narxni 2400000 shaklida yozing, 2 400 000 shaklida emas. Birinchi sarlavha qatorini kiritmang. Miqdor butun dona, narx va to‘lov so‘mda, ko‘pi bilan 2 kasr xonasi. Chegirma funksiyasi olib tashlangan; jami summa dona × narx asosida hisoblanadi. Noto‘g‘ri tasdiqlangan yozuvlarni o‘chirish/tahrirlash v1 menyusida yo‘q; bazani to‘g‘ridan-to‘g‘ri o‘zgartirmang, tuzatish tartibi kelishiladi. Mahsulot qaytarish miqdorni oshiradi; u avtomatik pul qaytarish yoki oldingi sotuv summasini o‘zgartirish amali emas.

## Qo‘shimcha buyruqlar

| Buyruq | Vazifa |
|---|---|
| `/stock 315/80` | O‘lcham/nom/nuqta bo‘yicha qidirish |
| `/clients transport` | Mijoz nomi yoki telefoni bo‘yicha qidirish |
| `/points` | Nuqtalar va IDlar |
| `/card` | Mijozning umumiy tarixini Excelda olish |
| `/done` | Vazifani bajarilgan deb belgilash |
| `/pdf` | O‘z КПsini qayta yuklash; direktor barcha КПni ko‘ra oladi |
| `/quote_status` | draft / sent / accepted / rejected |
| `/delivery_status` | new / on_way / delivered / cancelled |
| `/photo` | Mahsulot rasmini ko‘rish |
| `/return` | Omborga qaytarish |
| `/writeoff` | Hisobdan chiqarish, faqat direktor |
| `/cancel` | Joriy dialogni bekor qilish |

ID so‘ralganda faqat raqam kiriting. Eslatma sanasi `YYYY-MM-DD HH:MM`, hisobot sanalari `YYYY-MM-DD`; Toshkent vaqti. Eslatmada mas’ul sifatida `0` kiritilsa vazifa o‘zingizga yoziladi.

## Hisobot talqini

Hisobotdagi sotuvlar sana oralig‘ida yaratilgan sotuvlardir. «Shu sotuvlardan to‘langan» — ularning hozirgacha to‘langan summasi, keyinroq kelgan to‘lovlarni ham hisoblaydi. «Davrda kelib tushgan to‘lovlar» — aynan tanlangan davrdagi pul tushumi, shu jumladan oldingi sotuvlarning qarz to‘lovlari. Ularni ikki marta qo‘shmang. Excelning «Qoldiqlar» varag‘i va «Vazifalar» varag‘i joriy holatni ko‘rsatadi; tarixiy sana holati emas. Summalar Excelda UZS, ichki bazada aniqlik uchun tiyinlarda saqlanadi.

## Saqlash va ishonchlilik

`bot-data` Docker volume bazani qayta ishga tushganda saqlaydi. Volumeni o‘chirmang. Zaxira nusxasi uchun bot ishlayotgan paytda ham SQLite backup API orqali izchil nusxa olish mumkin:

```sh
docker compose exec bot python -c "import sqlite3; s=sqlite3.connect('/app/data/topshinalar.sqlite3'); d=sqlite3.connect('/app/data/backup.sqlite3'); s.backup(d); d.close(); s.close()"
```

Zaxirani serverdan tashqariga ham saqlang. Bitta baza bilan bitta polling nusxa ishlaydi. Yangi Telegram update takror kelsa moliyaviy yozuv ikki marta saqlanmaydi. Tarmoq uzilsa xabarlar bazadagi navbatda qoladi va qayta yuboriladi. Xabar yuborilib, navbatni belgilashdan oldin server to‘xtasa xabar takror yetishi mumkin; sotuvning o‘zi takror yaratilmaydi. Bekor qilingan foydalanuvchiga navbatdagi ichki hisobotlar yuborilmaydi.

Mavjud yozuvlar audit jurnalida qayd etiladi. V1 da Excelga chiqarish mavjud; Excel/import, avtomatik veb-sayt sinxronizatsiyasi, GPS va avtomatik jarima qo‘shilmagan.

## Tekshiruv va holat

```sh
python -m unittest discover -s tests -v
```

69 ta funksional test o‘tgan: huquqlar, takroriy update, atomar sotuv, qoldiq, qarz/to‘lov, CRM, bildirishnoma navbati, ish kuni, Labo, ikki til, Excel va КП PDF yaratish. Logotipli o‘zbekcha va ko‘p sahifali ruscha КП alohida yaratilgan; summa va kirill matni tekshirilgan, birinchi va oxirgi sahifalari tasvirga aylantirib ko‘rilgan.

**Telegram serveri bilan jonli sinov va joylashtirish hali bajarilmagan:** TOPSHINALAR uchun alohida token, real Telegram IDlar va server berilmagan. Real xodimlar bilan qabul sinovi ishga tushirilgandan keyin o‘tkaziladi. Bu arxiv mustaqil dastur kodi va ishga tushirish sozlamalaridir.

## Kiritish formatlari yangilanishi — 2026-10-16

Sotuv va КП uchun mahsulot qatorlarida `|`, `-` yoki bo‘shliqdan foydalanish mumkin. Tartib: mahsulot IDsi, dona soni, bir dona narxi. Masalan: `1-4-2400000` = mahsulot 1, 4 dona, narx 2 400 000 UZS. Jami 9 600 000 UZS. Manfiy qiymatlar, ortiqcha yoki yetishmayotgan maydonlar qabul qilinmaydi. Alohida ID, narx yoki dona so‘raladigan qadamlarda bitta qiymat kiritiladi.

Ishlayotgan Windows nusxasini yangilash:
1. Botning qora oynasida Ctrl+C bosing va oynani yoping.
2. Arxivni alohida oching. Undagi `bot.py`, `core.py`, `i18n.py` fayllarini amaldagi bot papkasiga nusxalab, eskilarini almashtiring.
3. Amaldagi `.env`, `data` va `.venv`ni saqlang; ularni o‘chirmang. Baza formati o‘zgarmagan, ombor va mijozlarni qayta kiritish shart emas.
4. Eski papkadagi `START-WINDOWS.bat`ni yana oching.

Bu format yangilanishi lokal testlarda tekshirildi; kompyuterdagi nusxaga barcha yangilangan dastur fayllari va assets papkasi ko‘chirilgach qo‘llanadi.

## Logotip va to‘lov turlari yangilanishi — 2026-10-16

КП PDFining yuqori qismida asl TOPSHINALAR logotipi qo‘yildi. Logo buyurtmachining TOPSHINALAR_Brandbook.pdf hujjatidagi asosiy gorizontal logotipdan olingan, qayta chizilmagan. Bir sahifali o‘zbekcha va ikki sahifali ruscha namunalar ko‘rib tekshirildi. `KP-NAMUNA.pdf` ichida sinov ma’lumotlari bor.

Sotuv va qarz to‘lovi uchun uchta tanlov tugmasi: **NAQD**, **PERECHISLENIYA**, **KARTA ORQALI TO‘LOV**. Rus tilida mos ravishda НАЛИЧНЫЕ, ПЕРЕЧИСЛЕНИЕ, ОПЛАТА КАРТОЙ. NAXT, PERCHESLENIYA, terminal, o‘tkazma kabi yozuvlar ham tegishli turga keltiriladi. Excel hisobotlarida to‘lov turi tanlangan tilda chiqadi, oldingi yozuvlarning asl ma’lumoti o‘zgartirilmaydi. PDFda faqat tanlangan to‘lov usuli va tanlangan olib ketish/yetkazib berish sharti ko‘rsatiladi. Bu to‘lovni qayd qilish funksiyasi; bankdan avtomatik pul yechish yoki ekvayring integratsiyasi emas.

Ushbu yangilanish uchun arxivdagi **barcha dastur fayllari va `assets` papkasini** amaldagi bot papkasiga ko‘chiring. Faqat uchta faylni almashtirish yetmaydi — yangi `payments.py`, yangilangan `quotation.py`, `reports.py` va logo kerak. Botni avval Ctrl+C bilan to‘xtating. **Amaldagi `.env`, `data`, `.venv`ni o‘chirmang.** Keyin START-WINDOWS.bat orqali qayta oching.

## Chegirma olib tashlandi

Yangi sotuv va КП faqat **ID, dona, narx** orqali kiritiladi. Chegirma so‘ralmaydi, tasdiqlash oynasida, Excel va PDFda chegirma ustuni chiqmaydi. Jami = dona × narx. Eski to‘rt maydonli qatorni yubormang. Ichki bazada avval saqlangan chegirmali yozuvlar o‘zgartirilmaydi; eski КПni qayta yuklaganda tarixiy jami saqlanadi va dona narxi sof narxda ko‘rsatiladi. Yangilash vaqtida chegirmali tugallanmagan sotuv/КП bo‘lsa, bot uni saqlamasdan bekor qiladi va qayta kiritishni so‘raydi.

## Doimiy baza va tiklash — 2026-10-16

Windows launcher endi bazani `%LOCALAPPDATA%/TOPSHINALAR/staff-bot/<bot-ID>/topshinalar.sqlite3`da saqlaydi. Bot tokeni va ruxsat berilgan IDlar shu joydagi `settings.env`da ham saqlanadi. Bu faylni ulashmang. Har bir bot ID uchun alohida joy ajratiladi. Keyingi yangi arxiv papkasi saqlangan sozlamalarni o‘qiydi va doimiy bazadan davom etadi. Docker uchun avvalgi doimiy volume tartibi o‘zgarmagan.

**Hozirgi «Assortiment bo‘sh» holatini tuzatish:**
1. Barcha eski bot oynalarini Ctrl+C bilan to‘xtating.
2. Arxivdagi dastur fayllari va `assets`ni ishlatayotgan bot papkangizga almashtiring; `.env`, `data`, `.venv`ni o‘chirmang.
3. `RESTORE-DATA.bat`ni oching. Zarur bo‘lsa tokenni faqat qora oynada kiriting.
4. Eski bazalar yonida ombor, mahsulot, umumiy qoldiq, mijoz va sotuvlar soni ko‘rsatiladi. Oldingi **Asosiy ombor / 15 dona** yozuvi bor bazani ro‘yxat raqami orqali tanlang.
5. Bot ishga tushgach `/points` va `/stock` bilan tekshiring.

Avtomatik qidiruv dastur papkasi va yonidagi papkalar, Downloads, Desktop, OneDrive/Desktop, Windows vaqtinchalik papkasida ishlaydi. Qidiruv chuqurligi va papkalar soni cheklangan. Agar eski baza boshqa joyda bo‘lsa, ro‘yxat raqami o‘rniga `topshinalar.sqlite3` fayliga to‘liq yo‘l kiritish mumkin. ZIP ichidagi fayllar avtomatik qidirilmaydi; arxivni alohida papkaga oching.

Tiklash eski faylni o‘zgartirmasdan SQLite backup API orqali izchil nusxa oladi, shu jumladan WAL jurnalidagi saqlangan yozuvlarni ham oladi. Tanlangan manba va mavjud doimiy bazaning zaxiralari `backups`da saqlanadi. Bazalar avtomatik birlashtirilmaydi: tanlangan bazaning holati olinadi, boshqa fayllar va oldingi holatlar zaxirada qoladi. Bekor qilish uchun `q`. Eski baza o‘chirilgan bo‘lsa, dastur uning ma’lumotlarini yo‘qdan tiklay olmaydi.

Doimiy baza yaratilgach oddiy ochish `START-WINDOWS.bat` orqali; qayta tanlash kerak bo‘lsa `RESTORE-DATA.bat`. Bir botning ikki yangi nusxasi bir vaqtda ochilishiga blok qo‘yilgan. Avvalgi eski versiyadagi botlarni alohida to‘xtatish kerak.

Ombor hali yaratilmagan bo‘lsa ham, saqlangan mahsulotlar endi assortimentda ko‘rinadi. Bot yo‘q ombor uchun «0 dona» deb taxmin qilmaydi; ombor yaratish yoki eski bazani tanlashni aniq tushuntiradi.

60 ta testda baza tanlash, zaxira, tiklash, yangi dastur papkasidan doimiy bazani ochish, buzilgan faylni almashtirmaslik, parallel ochishni bloklash, WAL va ruxsatlarni saqlash tekshirildi. Haqiqiy Windows kompyuteridagi tiklash hali foydalanuvchi bilan tekshirilishi kerak.

## КПda tanlangan to‘lov usuli va yetkazish sharti

Yangi КП dialogi: mijoz → mahsulotlar → **NAQD / PERECHISLENIYA / KARTA ORQALI TO‘LOV** tugmalaridan bittasi → **Olib ketish / Yetkazib berish** tugmalaridan bittasi → Tasdiqlash. PDFda faqat tanlangan bitta to‘lov usuli va bitta shart ko‘rsatiladi. Uchta to‘lov usuli birgalikda chiqarilmaydi. Shartlar endi erkin matn yoki raqam orqali kiritilmaydi. Ruscha dialogda НАЛИЧНЫЕ / ПЕРЕЧИСЛЕНИЕ / ОПЛАТА КАРТОЙ va Самовывоз / Доставка ishlaydi.

**Oldingi КПni yangilash:** botda `/quote_options` yoki «КП to‘lov va shartlari»ni tanlang, КП raqamini kiriting, to‘lov va shartni tanlab tasdiqlang. Shu КПning PDFi qayta yuboriladi; yangi КП, sotuv yoki ombor harakati yaratilmaydi, summasi o‘zgarmaydi. Xodim faqat o‘z КПsini, direktor barcha КПni o‘zgartira oladi.

Baza yangilanganda mavjud КПlarga ikkita bo‘sh maydon qo‘shiladi. Avvalgi yozuvlarga to‘lov usuli yoki yetkazish sharti taxminan belgilanmaydi. Eski КПdagi tanlanmagan to‘lov PDFda «Tanlanmagan» bo‘ladi; yuqoridagi buyruq bilan tanlang. Avvalgi erkin izoh saqlanadi, biroq tanlangan yangi shart PDFda ustun turadi. Yangilanish vaqtida eski КП dialogi tugallanmagan bo‘lsa, mijoz va mahsulotlar saqlanib, bot yangi to‘lov tanlash qadamiga qaytadi.

65 ta test o‘tdi; PDFning ikki til × uchta to‘lov × ikki shart bo‘yicha 12 kombinatsiyasi alohida tekshirildi. Logotip, chegirmasiz jadval, uch xil mahsulot kiritish formati va doimiy baza/tiklash imkoniyati saqlangan.

## Excelda xodim ismlari

Excelning barcha tegishli varaqlarida Telegram xodim IDlari o‘rniga xodimlarning ismlari chiqariladi. Sotuvlar, sotilgan mahsulotlar, to‘lovlar, qo‘ng‘iroqlar, Labo, ish kunlari, jarimalar, КП va vazifalarda «Xodim» ustuni bor. Mijoz kartasida «Mas’ul xodim», jarimalarda «Tasdiqlagan direktor» ham ism bilan chiqadi. Takroriy ism ustuni chiqarilmaydi, ruscha hisobotdagi ustunlar ham moslashtirilgan. Ism xodimning Telegram profilidan olinadi va botga murojaat qilganda yangilanadi. Hali botga Start bosmagan xodimning ismi ma’lum bo‘lmasa «Ism kiritilmagan» yoziladi; ID ism sifatida ko‘rsatilmaydi.

Bazadagi IDlar, ruxsatlar, sotuv va to‘lov summalari o‘zgarmaydi. Oldin yuklangan Excel fayli avtomatik o‘zgarmaydi: dastur yangilangach botdan hisobotni qayta oling. Ushbu yangilanishda 69 ta test o‘tdi.

## Assortimentda rasmlar

Razmer yoki nom bo‘yicha `/stock` qidirilganda qoldiqlar ro‘yxati va har bir mos mahsulotning yuklangan rasmi alohida Telegram foto sifatida yuboriladi. Bir mahsulot bir nechta nuqtada bo‘lsa ham rasmi bir marta yuboriladi. Rasm ostida nom, ID va narx bor. Surat qo‘shishda Telegramdagi eng katta mavjud variant saqlanadi; manba xira bo‘lsa uning sifatini bot avtomatik yaxshilamaydi. Rasm yuklanmagan mahsulot matnli ro‘yxatda qoladi. 76 ta test o‘tdi.
