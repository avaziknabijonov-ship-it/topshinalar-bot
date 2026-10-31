'use strict';
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const events=()=>({listeners:{},addEventListener(name,fn){this.listeners[name]=fn}});
function element(tag='DIV'){
 const names=new Set();return {...events(),tagName:tag,type:'',hidden:false,children:[],style:{values:{},setProperty(k,v){this.values[k]=v}},classList:{toggle(k,on){if(on)names.add(k);else names.delete(k)},contains:k=>names.has(k)},append(child){this.children.push(child)},closest:()=>null,scrollIntoView(){this.scrolled=true}};
}
const viewport={...events(),height:844,offsetTop:0};
const body=element(),root=element(),actions=element(),language={textContent:'RU'};
const document={...events(),body,documentElement:root,activeElement:body,createElement:tag=>element(tag.toUpperCase()),getElementById:()=>language,querySelector:()=>actions};
const window={...events(),visualViewport:viewport,innerHeight:844,setTimeout:callback=>callback(),Telegram:{WebApp:{viewportStableHeight:844,onEvent(){}}}};
vm.runInNewContext(fs.readFileSync('web/mobile.js','utf8'),{window,document});
const toolbar=body.children[0],done=toolbar.children[0];
assert.equal(toolbar.hidden,true);
const field=element('INPUT');field.type='number';field.closest=()=>true;field.blur=()=>{document.activeElement=body};
document.activeElement=field;document.listeners.focusin();
assert.equal(toolbar.hidden,true);assert.equal(field.scrolled,true);
viewport.height=420;viewport.offsetTop=40;viewport.listeners.resize();
assert.equal(body.classList.contains('keyboard-open'),true);assert.equal(toolbar.hidden,false);
assert.equal(done.textContent,'Готово');assert.equal(toolbar.style.top,'416px');
assert.equal(root.style.values['--visual-height'],'420px');
let prevented=false;toolbar.listeners.pointerdown({preventDefault(){prevented=true}});assert.equal(prevented,true);
done.listeners.click();assert.equal(document.activeElement,body);assert.equal(toolbar.hidden,true);assert.equal(actions.scrolled,true);
viewport.height=844;viewport.listeners.resize();assert.equal(body.classList.contains('keyboard-open'),false);
language.textContent='UZ';document.activeElement=field;viewport.height=420;document.listeners.focusin();assert.equal(done.textContent,'Tayyor');
let enterPrevented=false;document.listeners.keydown({key:'Enter',preventDefault(){enterPrevented=true}});
assert.equal(enterPrevented,true);assert.equal(document.activeElement,body);
console.log('Mobile keyboard: visual viewport, offset, close, refocus, language and Enter checks passed');
