# TOPSHINALAR — Windows ilovasi

Windows ilovasi alohida oynada ochiladigan o‘rnatiladigan dastur (Electron). U **hech qanday baza va biznes mantiqini o‘z ichiga olmaydi**: VDS’dagi mavjud Mini App serveriga internet orqali ulanadi va aynan o‘sha frontend (`web/`), API (`/api/*`, `/director-api/*`) va **bitta SQLite bazadan** foydalanadi. Mini App va Windows ilovasida bir xil hisoblar, rollar (direktor/xodim/haydovchi), ruxsatlar va o‘zbek/rus tillari ishlaydi; bir joydagi o‘zgarish boshqasida darhol ko‘rinadi. Offline rejim yo‘q.

## Kirish (login)
Telegram `initData` faqat Telegram ichida bor, shuning uchun oynada bir martalik kod chiqadi. Foydalanuvchi uni **o‘z Telegramidan** botga yuboradi: `/desktop_login KOD`. Bot yuboruvchining hisobini tekshiradi (faqat bazadagi faol xodim/direktor), shundan so‘ng ilova 8 soatlik HttpOnly sessiya oladi. Direktor bitta kod bilan direktor kabinetini ham ochadi. Hisob o‘chirilsa, sessiya ham bekor bo‘ladi.

## Server manzili (maxfiy emas)
Ustuvorlik: `TOPSHINALAR_SERVER_URL` muhit o‘zgaruvchisi → ilovadagi «Fayl → Server manzili» (foydalanuvchi papkasidagi `config.json`) → o‘rnatgichga yozilgan qiymat. Faqat `https://` (sinov uchun `http://localhost`). Token, parol yoki bot tokeni ilovada **yo‘q**.

## `.exe` o‘rnatgichini olish
**A) GitHub Actions (tavsiya):** GitHub → Actions → «Windows installer» → Run workflow (ixtiyoriy: server manzili) → tugagach sahifa pastidagi **Artifacts → TOPSHINALAR-Windows-installer** ichidan `TOPSHINALAR-Setup-1.0.0.exe`.
Manzilni har safar kiritmaslik uchun: Settings → Secrets and variables → Actions → Variables → `TOPSHINALAR_SERVER_URL`.

**B) Windows kompyuterda:** Node.js 22 o‘rnating, so‘ng
```
cd desktop
npm install
set TOPSHINALAR_SERVER_URL=https://SIZNING-DOMEN
npm test
npm run build
```
Natija: `desktop\dist\TOPSHINALAR-Setup-1.0.0.exe`.

## Serverda talab
`PUBLIC_APP_URL=https://SIZNING-DOMEN` allaqachon Mini App uchun sozlangan bo‘lishi kerak (yozish so‘rovlari origin bilan tekshiriladi). Nginx/systemd o‘zgarmaydi. Yangi kod (`desktop_auth.py`, `web/desktop.*`) VDSga faqat siz ruxsat berib deploy qilganingizda chiqadi; shunda bot va Mini App xizmatini qayta ishga tushirish kerak. Baza sxemasiga ikkita yordamchi jadval qo‘shiladi (`desktop_logins`, `desktop_sessions`); mavjud jadvallar o‘zgarmaydi.

## Sinash
`python -m unittest discover -s tests` (jumladan `test_desktop_auth.py`), `node --test desktop/test/*.test.js`, brauzerda: `python tests/browser_desktop.py`.

## Cheklovlar
- O‘rnatgich imzolanmagan: Windows SmartScreen «Noma’lum nashriyotchi» ogohlantirishini ko‘rsatadi (Ko‘proq ma’lumot → Baribir ishga tushirish). Kod imzolash sertifikati kerak.
- Avtomatik yangilanish yo‘q: yangi versiya uchun o‘rnatgich qayta beriladi. Veb qismi (`web/`) esa serverda yangilanishi bilan darhol yangilanadi.
- Windows 10/11 x64.
