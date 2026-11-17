'use strict';
const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { normalizeServerUrl, loadConfig, saveUserConfig, classifyUrl } = require('../config');

test('server URL is reduced to an https origin', () => {
  assert.equal(normalizeServerUrl('bot.example.uz'), 'https://bot.example.uz');
  assert.equal(normalizeServerUrl(' https://Bot.Example.uz/director?x=1#y '), 'https://bot.example.uz');
  assert.equal(normalizeServerUrl('https://bot.example.uz:8443/'), 'https://bot.example.uz:8443');
});

test('insecure, credentialed and malformed addresses are rejected', () => {
  assert.throws(() => normalizeServerUrl('http://bot.example.uz'), /https/);
  assert.throws(() => normalizeServerUrl('https://user:pass@bot.example.uz'), /credentials/);
  assert.throws(() => normalizeServerUrl(''), /empty/);
  assert.throws(() => normalizeServerUrl('ftp://bot.example.uz'), /https/);
  assert.throws(() => normalizeServerUrl('intranet'), /invalid/);
  assert.throws(() => normalizeServerUrl('javascript:alert(1)'), /https|invalid/);
});

test('plain http is allowed only for this computer', () => {
  assert.equal(normalizeServerUrl('http://localhost:8080'), 'http://localhost:8080');
  assert.equal(normalizeServerUrl('http://127.0.0.1:8080/x'), 'http://127.0.0.1:8080');
});

test('config priority: environment, then user setting, then installer default', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tsh-'));
  const user = path.join(dir, 'user.json'), def = path.join(dir, 'default.json');
  assert.deepEqual(loadConfig({ env: {}, userFile: user, defaultFile: def }), { serverUrl: '', source: 'none' });
  fs.writeFileSync(def, JSON.stringify({ serverUrl: 'https://installer.example.uz' }));
  assert.deepEqual(loadConfig({ env: {}, userFile: user, defaultFile: def }), { serverUrl: 'https://installer.example.uz', source: 'installer' });
  assert.equal(saveUserConfig(user, 'user.example.uz/path'), 'https://user.example.uz');
  assert.deepEqual(loadConfig({ env: {}, userFile: user, defaultFile: def }), { serverUrl: 'https://user.example.uz', source: 'user' });
  assert.deepEqual(loadConfig({ env: { TOPSHINALAR_SERVER_URL: 'env.example.uz' }, userFile: user, defaultFile: def }), { serverUrl: 'https://env.example.uz', source: 'environment' });
  // an invalid value falls through to the next source instead of breaking the app
  assert.equal(loadConfig({ env: { TOPSHINALAR_SERVER_URL: 'http://evil.example' }, userFile: user, defaultFile: def }).source, 'user');
  assert.throws(() => saveUserConfig(user, 'http://evil.example'), /https/);
  assert.equal(JSON.parse(fs.readFileSync(user, 'utf8')).serverUrl, 'https://user.example.uz');
});

test('config files hold only the server address, never secrets', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tsh-'));
  const user = path.join(dir, 'user.json');
  saveUserConfig(user, 'https://bot.example.uz');
  assert.deepEqual(Object.keys(JSON.parse(fs.readFileSync(user, 'utf8'))), ['serverUrl']);
});

test('navigation: server and own pages stay in the window, https links go to the browser, the rest is blocked', () => {
  const server = 'https://bot.example.uz', pages = 'file:///app/pages/';
  assert.equal(classifyUrl('https://bot.example.uz/director', server, pages), 'internal');
  assert.equal(classifyUrl('file:///app/pages/setup.html?x=1', server, pages), 'internal');
  assert.equal(classifyUrl('https://t.me/somebot', server, pages), 'external');
  assert.equal(classifyUrl('https://bot.example.uz.evil.test/', server, pages), 'external');
  assert.equal(classifyUrl('file:///etc/passwd', server, pages), 'block');
  assert.equal(classifyUrl('file:///app/pages/../secret.html', server, pages), 'block');
  assert.equal(classifyUrl('javascript:alert(1)', server, pages), 'block');
  assert.equal(classifyUrl('http://bot.example.uz/', server, pages), 'block');
  assert.equal(classifyUrl('not a url', server, pages), 'block');
});
