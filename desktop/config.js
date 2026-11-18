'use strict';
/* Pure helpers (no Electron imports) so they can be unit-tested with plain Node. */
const fs = require('node:fs');
const path = require('node:path');

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

/* Returns the server origin ("https://host[:port]") or throws Error with a message code.
   Only https is accepted, except plain http to this computer (for local testing). */
function normalizeServerUrl(input) {
  const raw = String(input ?? '').trim();
  if (!raw) throw new Error('empty');
  let url;
  try { url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(raw) ? raw : 'https://' + raw); } catch (error) { throw new Error('invalid'); }
  if (url.username || url.password) throw new Error('credentials');
  const local = LOCAL_HOSTS.has(url.hostname);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && local)) throw new Error('https');
  if (!url.hostname || (!local && !url.hostname.includes('.'))) throw new Error('invalid');
  return url.origin;
}

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (error) { return {}; }
}

/* Priority: environment > user setting (changed from the app menu) > value baked into the installer. */
function loadConfig({ env = process.env, userFile, defaultFile }) {
  const candidates = [
    ['environment', env.TOPSHINALAR_SERVER_URL],
    ['user', userFile ? readJson(userFile).serverUrl : ''],
    ['installer', defaultFile ? readJson(defaultFile).serverUrl : ''],
  ];
  for (const [source, value] of candidates) {
    if (!value) continue;
    try { return { serverUrl: normalizeServerUrl(value), source }; } catch (error) { /* ignore an invalid value and try the next source */ }
  }
  return { serverUrl: '', source: 'none' };
}

function saveUserConfig(file, serverUrl) {
  const origin = normalizeServerUrl(serverUrl);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const temp = file + '.tmp';
  fs.writeFileSync(temp, JSON.stringify({ serverUrl: origin }, null, 2));
  fs.renameSync(temp, file);
  return origin;
}

/* Decides what the window may do with a URL. Only the configured server and the app's own
   local pages are loaded in the window; ordinary https links go to the default browser. */
function classifyUrl(target, serverOrigin, localPagesPrefix) {
  let url;
  try { url = new URL(target); } catch (error) { return 'block'; }
  if (serverOrigin && url.origin === serverOrigin) return 'internal';
  if (url.protocol === 'file:' && localPagesPrefix && decodeURI(url.href).startsWith(localPagesPrefix)) return 'internal';
  if (url.protocol === 'https:' || url.protocol === 'mailto:' || url.protocol === 'tel:') return 'external';
  return 'block';
}

module.exports = { normalizeServerUrl, loadConfig, saveUserConfig, classifyUrl };
