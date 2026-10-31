'use strict';
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync('web/app.js','utf8');
const functionSource=source.slice(source.indexOf('async function sendQuotePdf('),source.indexOf('async function download('));
async function test(){
 let count=0,calls=[],messages=[],finish;
 const context={T:(_,ru)=>ru,key:()=>`request-key-${++count}`,toast:text=>messages.push(text),api:async(path,options)=>{calls.push({path,options});return new Promise(resolve=>{finish=resolve})}};
 vm.createContext(context);vm.runInContext(functionSource,context);
 const button={disabled:false,textContent:'PDF в чат',dataset:{pdf:'2'}};
 const first=context.sendQuotePdf(button);assert.equal(button.disabled,true);
 await context.sendQuotePdf(button);assert.equal(calls.length,1);
 assert.equal(calls[0].path,'/api/action');assert.equal(calls[0].options.body.cmd,'pdf');assert.equal(calls[0].options.body.data.ref,2);
 finish({ok:true});await first;
 assert.equal(button.disabled,false);assert.equal(button.textContent,'PDF в чат');assert.equal(button.dataset.requestKey,undefined);assert.match(messages[0],/очередь/);
 context.api=async(path,options)=>{calls.push({path,options});throw Error('offline')};
 await assert.rejects(context.sendQuotePdf(button),/offline/);const retryKey=button.dataset.requestKey;assert.equal(button.disabled,false);
 context.api=async(path,options)=>{calls.push({path,options});return {ok:true}};
 await context.sendQuotePdf(button);assert.equal(calls.at(-1).options.headers['Idempotency-Key'],retryKey);
 await context.sendQuotePdf(button);assert.notEqual(calls.at(-1).options.headers['Idempotency-Key'],retryKey);
 console.log('PDF chat: correct quote, double click guard, queued status, failed retry and intentional resend passed');
}
test().catch(error=>{console.error(error);process.exitCode=1});
