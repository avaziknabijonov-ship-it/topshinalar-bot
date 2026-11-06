'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const context={window:{},Intl,Date};vm.createContext(context);require('./localization_helpers')(context);
const ui=context.WorkspaceText,data=JSON.parse(fs.readFileSync('locales/uz-ru.json','utf8'));
for(const lang of ['uz','ru']){
 for(const [key,words] of Object.entries(data.fields))assert.equal(ui.field(key,lang),words[lang==='ru'?1:0]);
 for(const [key,choices] of Object.entries(data.values)){
  for(const [code,words] of Object.entries(choices))assert.equal(ui.value(key,code,lang),words[lang==='ru'?1:0]);
 }
 assert.equal(ui.value('name','active',lang),'active');
 assert.equal(ui.value('note','English customer note',lang),'English customer note');
 assert.equal(ui.value('amount',12500,lang),12500);
 assert.equal(ui.time('2026-11-04T23:30:00+00:00',lang),'05.11.2026 04:30');
 assert.equal(ui.time('2026-11-05',lang),'05.11.2026');
 assert.equal(ui.time('2026-11-05T00:30',lang),'05.11.2026 00:30');
 assert.ok(!ui.field('future_field_name',lang).includes('future_field_name'));
 assert.ok(!ui.value('status','future_state',lang).includes('future_state'));
 assert.ok(!ui.value('action','supplier_edit:{"token":"secret"}',lang).includes('secret'));
 assert.ok(!ui.error(new TypeError('Failed to fetch'),lang).includes('fetch'));
 assert.ok(!ui.error(new Error('The source image could not be decoded.'),lang).includes('decoded'));
 assert.ok(!ui.error(new TypeError('Cannot read properties of undefined'),lang).includes('undefined'));
}
assert.equal(ui.value('role','employee','ru'),'Сотрудник');
assert.equal(ui.value('method','ОПЛАТА КАРТОЙ','uz'),'Karta');
assert.equal(ui.value('method','Custom legacy method','ru'),'Custom legacy method');
assert.equal(ui.error('shu nuqtada mahsulot yetarli emas','uz'),'shu nuqtada mahsulot yetarli emas');
console.log('UZ/RU: all catalogue fields and enums, names/notes preserved, aliases, safe fallback and Tashkent dates passed');
