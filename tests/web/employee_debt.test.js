'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');const ctx={window:{}};vm.createContext(ctx);vm.runInContext(fs.readFileSync('web/employee-debt.js','utf8'),ctx);const d=ctx.window.EmployeeDebt;
assert.equal(d.cents('50.25'),5025n);assert.equal(d.cents('1 250,05'),125005n);assert.equal(d.cents('0.01'),1n);assert.equal(d.cents('1'),100n);
for(const v of ['1.001','-1','NaN','Infinity','1e3','1,2.3','', '9'.repeat(100)])assert.equal(d.cents(v),null);
assert.equal(d.format(5025n,'USD'),'50.25 USD');assert.equal(d.format(20000n-d.cents('50.25'),'USD'),'149.75 USD');assert.equal(d.format('9007199254740993','USD'),'90071992547409.93 USD');console.log('Employee debt: exact cents parsing, validation and remaining balance passed');
