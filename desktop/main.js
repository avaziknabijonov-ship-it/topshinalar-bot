'use strict';
const { app, BrowserWindow, Menu, shell, ipcMain, session, dialog } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { loadConfig, saveUserConfig, classifyUrl, normalizeServerUrl } = require('./config');

const PAGES = path.join(__dirname, 'pages');
const PAGES_PREFIX = decodeURI(pathToFileURL(PAGES).href) + '/';
const userFile = () => path.join(app.getPath('userData'), 'config.json');
const defaultFile = () => path.join(process.resourcesPath || __dirname, 'config.default.json');

let win = null;
let config = { serverUrl: '', source: 'none' };

function page(name, query) {
  const url = pathToFileURL(path.join(PAGES, name));
  if (query) url.search = new URLSearchParams(query).toString();
  return url.href;
}

function open() {
  if (!win) return;
  if (!config.serverUrl) { win.loadURL(page('setup.html')); return; }
  win.loadURL(config.serverUrl + '/');
}

function createWindow() {
  win = new BrowserWindow({
    width: 1366, height: 860, minWidth: 1000, minHeight: 640, show: false,
    backgroundColor: '#f3f5f8', title: 'TOPSHINALAR', icon: path.join(__dirname, 'build', 'icon.ico'),
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, spellcheck: false },
  });
  win.once('ready-to-show', () => win.show());
  win.on('closed', () => { win = null; });
  win.webContents.setWindowOpenHandler(({ url }) => {
    const kind = classifyUrl(url, config.serverUrl, PAGES_PREFIX);
    if (kind === 'internal') win.loadURL(url);
    else if (kind === 'external') shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event, url) => {
    const kind = classifyUrl(url, config.serverUrl, PAGES_PREFIX);
    if (kind === 'internal') return;
    event.preventDefault();
    if (kind === 'external') shell.openExternal(url);
  });
  win.webContents.on('did-fail-load', (event, code, description, url, isMainFrame) => {
    // -3 = navigation replaced by another one; not a real failure.
    if (!isMainFrame || code === -3 || url.startsWith('file:')) return;
    win.loadURL(page('offline.html', { url: config.serverUrl, reason: description }));
  });
  // Switch the window to the app's own language on the offline/setup pages.
  open();
}

function buildMenu() {
  const template = [
    { label: 'Fayl / Файл', submenu: [
      { label: 'Qayta yuklash / Перезагрузить', accelerator: 'CmdOrCtrl+R', click: () => open() },
      { label: 'Server manzili… / Адрес сервера…', click: () => win?.loadURL(page('setup.html')) },
      { type: 'separator' },
      { label: 'Chiqish / Выход', role: 'quit' },
    ] },
    { label: 'Ko‘rinish / Вид', submenu: [
      { label: 'Kattalashtirish / Увеличить', role: 'zoomIn', accelerator: 'CmdOrCtrl+Plus' },
      { label: 'Kichiklashtirish / Уменьшить', role: 'zoomOut' },
      { label: 'Asl o‘lcham / Обычный размер', role: 'resetZoom' },
      { type: 'separator' },
      { label: 'To‘liq ekran / Полный экран', role: 'togglefullscreen' },
      ...(app.isPackaged ? [] : [{ label: 'Dasturchi paneli', role: 'toggleDevTools' }]),
    ] },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// Only the app's own local pages may talk to the main process.
function fromLocalPage(event) {
  return String(event.senderFrame?.url || '').startsWith(PAGES_PREFIX);
}

ipcMain.handle('config:get', event => {
  if (!fromLocalPage(event)) throw new Error('denied');
  return { serverUrl: config.serverUrl, source: config.source };
});
ipcMain.handle('config:save', (event, value) => {
  if (!fromLocalPage(event)) throw new Error('denied');
  try {
    config = { serverUrl: saveUserConfig(userFile(), value), source: 'user' };
  } catch (error) {
    return { ok: false, error: error.message };
  }
  open();
  return { ok: true, serverUrl: config.serverUrl };
});
ipcMain.handle('config:retry', event => {
  if (!fromLocalPage(event)) throw new Error('denied');
  open();
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
  app.whenReady().then(() => {
    config = loadConfig({ userFile: userFile(), defaultFile: defaultFile() });
    // The server (desktop.js) recognises the Windows app by this User-Agent suffix.
    session.defaultSession.setUserAgent(`${session.defaultSession.getUserAgent()} TopshinalarDesktop/${app.getVersion()}`);
    // No camera, microphone, location or notification prompts: the app does not need them.
    session.defaultSession.setPermissionRequestHandler((contents, permission, callback) => callback(false));
    session.defaultSession.setPermissionCheckHandler(() => false);
    buildMenu();
    createWindow();
    app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) createWindow(); });
  });
  app.on('window-all-closed', () => app.quit());
}

// Surface unexpected failures instead of silently dying.
process.on('uncaughtException', error => { dialog.showErrorBox('TOPSHINALAR', String(error?.message || error)); });
module.exports = { normalizeServerUrl };
