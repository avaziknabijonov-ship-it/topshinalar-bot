'use strict';
document.getElementById('server').textContent = new URLSearchParams(location.search).get('url') || '';
document.getElementById('retry').addEventListener('click', () => window.desktopConfig.retry());
document.getElementById('change').addEventListener('click', () => { location.href = 'setup.html'; });
// Try again by itself while the window stays open.
setTimeout(() => window.desktopConfig.retry(), 20000);
