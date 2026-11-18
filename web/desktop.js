'use strict';
/* Windows desktop mode.
   The Electron shell appends "TopshinalarDesktop/<version>" to the User-Agent. In the Telegram
   Mini App and in ordinary browsers this file does nothing at all, so their behaviour is unchanged.
   Identity still comes from Telegram: the window shows a one-use code, the person sends it to the
   bot, and the server then sets an HttpOnly session cookie (see desktop_auth.py). */
(() => {
 if (!/\bTopshinalarDesktop\//.test(navigator.userAgent)) return;
 document.documentElement.classList.add('desktop-app');
 const sheet = document.createElement('link');
 sheet.rel = 'stylesheet';
 sheet.href = '/desktop.css';
 document.head.appendChild(sheet);

 const session = { active: true, csrf: '', user: null };
 // Nobody is signed in yet, so the login screen shows both languages of the product.
 const text = (uz, ru) => `<span lang="uz">${uz}</span><small class="desktop-ru" lang="ru">${ru}</small>`;
 const post = async path => {
  const response = await fetch(path, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf }, body: '{}' });
  if (!response.ok) throw new Error(String(response.status));
  return response.json();
 };

 async function current() {
  try {
   const response = await fetch('/desktop-auth/me', { credentials: 'same-origin', cache: 'no-store' });
   if (!response.ok) return null;
   const me = await response.json();
   session.csrf = me.csrf;
   session.user = me;
   return me;
  } catch (error) { return null; }
 }

 // Called by app.js after a 403: true when it was a normal permission error, false when the session is gone.
 session.stillSignedIn = async () => Boolean(await current());
 session.relogin = () => location.reload();
 session.logout = async () => {
  try { if (await current()) await post('/desktop-auth/logout'); } catch (error) { /* the cookie expires on its own */ }
  location.href = '/';
 };

 function renderLogin(root, resolve) {
  let attempt = 0, timer = 0, polling = false;
  root.innerHTML = `<div class="empty desktop-login">
   <h2>${text('Telegram orqali kirish', 'Вход через Telegram')}</h2>
   <p>${text('Quyidagi buyruqni Telegramdagi TOPSHINALAR botiga yuboring.', 'Отправьте эту команду боту TOPSHINALAR в Telegram.')}</p>
   <pre id="desktop-code" tabindex="0" aria-live="polite">…</pre>
   <div class="desktop-login-actions"><button type="button" class="secondary" id="desktop-copy">${text('Nusxalash', 'Копировать')}</button><button type="button" class="secondary" id="desktop-new">${text('Yangi kod', 'Новый код')}</button></div>
   <p class="help" id="desktop-state" role="status"></p>
   <p class="help">${text('Faqat shu oynada chiqqan kodni yuboring. Boshqa odam bergan kodni yubormang.', 'Отправляйте только код из этого окна. Не отправляйте код, который прислал кто-то другой.')}</p>
  </div>`;
  const code = root.querySelector('#desktop-code'), state = root.querySelector('#desktop-state');
  const say = (uz, ru) => { state.innerHTML = text(uz, ru); };
  async function start() {
   clearInterval(timer);
   const mine = ++attempt;
   say('Kod olinmoqda…', 'Получаем код…');
   try {
    const data = await post('/desktop-auth/start');
    if (mine !== attempt) return;
    code.textContent = data.command;
    say('Telegram tasdig‘i kutilmoqda…', 'Ожидается подтверждение Telegram…');
    const until = Date.now() + data.expires_in * 1000;
    timer = setInterval(async () => {
     if (mine !== attempt || polling) return;
     if (Date.now() > until) { clearInterval(timer); say('Kod muddati tugadi. «Yangi kod»ni bosing.', 'Код истёк. Нажмите «Новый код».'); return; }
     polling = true;
     try {
      const result = await post('/desktop-auth/poll');
      if (mine !== attempt) return;
      if (result.approved) { clearInterval(timer); if (await current()) resolve(); else say('Kirish bajarilmadi. Yangi kod oling.', 'Вход не выполнен. Получите новый код.'); }
     } catch (error) {
      if (mine === attempt) { clearInterval(timer); say('Aloqa yoki kod xatosi. «Yangi kod»ni bosing.', 'Ошибка связи или кода. Нажмите «Новый код».'); }
     } finally { polling = false; }
    }, 2500);
   } catch (error) {
    if (mine === attempt) say('Server bilan aloqa yo‘q yoki urinishlar ko‘p. Birozdan so‘ng qayta urinib ko‘ring.', 'Нет связи с сервером или слишком много попыток. Повторите чуть позже.');
   }
  }
  root.querySelector('#desktop-new').onclick = start;
  root.querySelector('#desktop-copy').onclick = async () => {
   try { await navigator.clipboard.writeText(code.textContent); say('Nusxalandi. Telegramga qo‘yib yuboring.', 'Скопировано. Вставьте в Telegram.'); }
   catch (error) { say('Nusxalab bo‘lmadi. Buyruqni qo‘lda yozing.', 'Не удалось скопировать. Введите команду вручную.'); }
  };
  start();
 }

 // Resolves once the window holds a valid session, asking for the Telegram code only when needed.
 session.require = async root => {
  if (await current()) return session.user;
  document.documentElement.classList.add('desktop-signed-out');
  await new Promise(resolve => renderLogin(root, resolve));
  document.documentElement.classList.remove('desktop-signed-out');
  return session.user;
 };

 window.DesktopSession = session;
})();
