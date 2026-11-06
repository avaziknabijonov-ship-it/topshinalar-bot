'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={tr:(uz,ru)=>uz,esc:x=>String(x)};vm.createContext(context);vm.runInContext(fs.readFileSync('web/director-analytics.js','utf8'),context);
assert.equal(context.analyticsMoney('9007199254740993','USD'),'90071992547409.93 USD');
assert.equal(context.analyticsMoney('12500','USD'),'125.00 USD');assert.equal(context.analyticsMoney('0','UZS'),'0.00 UZS');assert.equal(context.analyticsMoney(null,'USD'),'Ma’lumot yetarli emas');assert.equal(context.analyticsMoney('-125','USD'),'-1.25 USD');assert.equal(context.analyticsMoney(Number.MAX_SAFE_INTEGER+1,'USD'),'—');
vm.runInContext(`directorAnalyticsData={products:[{product:1,product_name:'Big',qty:1,sales_count:1,currency:'USD',revenue:'9007199254740993'},{product:2,product_name:'Bigger',qty:1,sales_count:1,currency:'USD',revenue:'9007199254740994'},{product:3,product_name:'Unknown',qty:2,sales_count:1,currency:'USD',revenue:null},{product:4,product_name:'UZS',qty:20,sales_count:1,currency:'UZS',revenue:'9999999999999999'}],employees:[],review_by_currency:{USD:1}};directorAnalyticsState.products.metric='revenue';`,context);
assert.equal(context.analyticRows('products')[0].product,2);assert.equal(context.analyticRows('products')[2].product,3);assert.equal(context.analyticRows('products').length,3);
vm.runInContext("directorAnalyticsState.products.q='bigger'",context);assert.equal(context.analyticRows('products').length,1);
console.log('Director analytics: exact BigInt cents/ranking, unknown values and currency/search separation passed');
