'use strict';
const messages = {
  empty: ['Manzilni kiriting.', 'Введите адрес.'],
  invalid: ['Manzil noto‘g‘ri.', 'Адрес указан неверно.'],
  https: ['Faqat https:// manzil qabul qilinadi.', 'Принимается только адрес https://.'],
  credentials: ['Manzilda login yoki parol bo‘lmasin.', 'В адресе не должно быть логина или пароля.'],
};
const input = document.getElementById('url'), error = document.getElementById('error');
window.desktopConfig.get().then(config => { if (config.serverUrl) input.value = config.serverUrl.replace(/^https:\/\//, ''); });
document.getElementById('form').addEventListener('submit', async event => {
  event.preventDefault();
  error.textContent = '';
  const raw = input.value.trim();
  const result = await window.desktopConfig.save(/^https?:\/\//i.test(raw) ? raw : 'https://' + raw);
  if (!result.ok) { const m = messages[result.error] || messages.invalid; error.textContent = m[0] + ' / ' + m[1]; }
});
