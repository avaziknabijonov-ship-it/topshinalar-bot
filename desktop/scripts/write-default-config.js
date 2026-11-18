'use strict';
/* Writes build/config.default.json, which the installer carries. The only value is the public
   server address (not a secret). Set TOPSHINALAR_SERVER_URL when building; empty = ask on first start. */
const fs = require('node:fs');
const path = require('node:path');
const { normalizeServerUrl } = require('../config');

const raw = (process.env.TOPSHINALAR_SERVER_URL || '').trim();
let serverUrl = '';
if (raw) {
  try { serverUrl = normalizeServerUrl(raw); } catch (error) {
    console.error('TOPSHINALAR_SERVER_URL noto‘g‘ri (' + error.message + '). Masalan: https://bot.example.uz');
    process.exit(1);
  }
}
const target = path.join(__dirname, '..', 'build', 'config.default.json');
fs.writeFileSync(target, JSON.stringify({ serverUrl }, null, 2) + '\n');
console.log('config.default.json: ' + (serverUrl || '(bo‘sh — birinchi ishga tushishda so‘raladi)'));
