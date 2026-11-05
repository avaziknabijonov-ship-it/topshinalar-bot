'use strict';
window.WorkspaceText = (() => {
  const data = window.WorkspaceTextData;
  const index = lang => lang === 'ru' ? 1 : 0;
  const text = (key, lang) => (data.ui[key] || data.ui.extra_field)[index(lang)];
  const field = (key, lang) => (data.fields[key] || data.ui.extra_field)[index(lang)];
  const booleans = new Set(['active','published','has_debt','overdue','price_pending','stock_pending','notified','payment_history_complete']);
  const dates = new Set(['created','date','due','debt_due','started','ended','cancelled_at','accepted_at','closed_at','last_success','as_of']);
  function time(value, lang) {
    if (!value) return '—';
    const raw = String(value);
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw.split('-').reverse().join('.');
    if (!/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(raw)) return raw;
    const date = new Date(raw.replace(' ', 'T') + (/(Z|[+-]\d{2}:\d{2})$/.test(raw) ? '' : '+05:00'));
    if (!Number.isFinite(date.getTime())) return '—';
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(date);
    const values = Object.fromEntries(parts.map(p => [p.type,p.value]));
    return values.day+'.'+values.month+'.'+values.year+' '+values.hour+':'+values.minute;
  }
  function value(key, item, lang) {
    if (item === null || item === undefined || item === '') return '—';
    if (booleans.has(key)) return text(item ? 'yes' : 'no', lang);
    if (key === 'action') return (data.actions[String(item).split(':')[0]] || data.ui.other_action)[index(lang)];
    if (key === 'method' || key === 'payment') {
      if (data.values[key][item]) return data.values[key][item][index(lang)];
      const normalized = String(item).toLowerCase().replace(/[^a-zа-я0-9]/g, '');
      const method = data.method_aliases[normalized];
      return method ? data.values.method[method][index(lang)] : item;
    }
    const choices = data.values[key];
    if (choices) return (choices[item] || data.ui.unknown)[index(lang)];
    if (key === 'last_error') return text('not_available', lang);
    if (dates.has(key)) return time(item, lang);
    if (Array.isArray(item)) return item.map(v => typeof v === 'object' ? text('extra_field',lang) : String(v)).join(', ') || '—';
    if (typeof item === 'object') return text('extra_field', lang);
    return item;
  }
  function error(problem, lang) {
    if (problem && typeof problem !== 'string' && !problem.message) return text('server_error', lang);
    const message = String(problem?.message || problem || '');
    if (/Failed to fetch|NetworkError|Load failed|AbortError|aborted|timeout|timed out/i.test(message)) return text('network_error', lang);
    if (/image.*(decode|format)|FileReader|imagebitmap/i.test(message)) return text('file_error', lang);
    if (/Cannot (read|convert|set)|undefined is not|is not a function|Unexpected token/i.test(message)) return text('server_error', lang);
    if (/^[a-z][a-z0-9_]*$/.test(message) || /^(Server error|Not found|Internal Server Error)$/.test(message)) return text('server_error', lang);
    return message || text('server_error', lang);
  }
  function apply(lang, root = document) {
    root.querySelectorAll('[data-ui]').forEach(el => { el.textContent = text(el.dataset.ui, lang); });
    root.querySelectorAll('[data-ui-placeholder]').forEach(el => { el.placeholder = text(el.dataset.uiPlaceholder, lang); });
    root.querySelectorAll('[data-ui-aria]').forEach(el => { el.setAttribute('aria-label', text(el.dataset.uiAria, lang)); });
    document.documentElement.lang = lang === 'ru' ? 'ru' : 'uz';
  }
  return { text, field, value, time, error, apply };
})();
