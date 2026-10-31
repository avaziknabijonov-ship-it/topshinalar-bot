/* Keep the focused field and keyboard controls inside the mobile visual viewport. */
(()=>{
 const viewport=window.visualViewport;
 const telegram=window.Telegram?.WebApp;
 const root=document.documentElement;
 const toolbar=document.createElement('div');toolbar.className='keyboard-toolbar';toolbar.hidden=true;
 const done=document.createElement('button');done.type='button';toolbar.append(done);document.body.append(toolbar);
 let fullHeight=Math.max(window.innerHeight,viewport?.height||0,telegram?.viewportStableHeight||0);
 const editing=()=>{const field=document.activeElement;return field&&((field.tagName==='INPUT'&&!['button','submit','checkbox','radio','file','hidden'].includes(field.type))||field.tagName==='TEXTAREA')};
 function update(){
  const height=viewport?.height||telegram?.viewportHeight||window.innerHeight;
  const offset=viewport?.offsetTop||0;
  if(!editing())fullHeight=Math.max(window.innerHeight,height,telegram?.viewportStableHeight||0);
  const keyboard=Boolean(editing()&&fullHeight-height>100);
  document.body.classList.toggle('keyboard-open',keyboard);
  toolbar.hidden=!keyboard;
  if(keyboard){
   done.textContent=document.getElementById('language')?.textContent.trim()==='RU'?'Готово':'Tayyor';
   toolbar.style.top=Math.max(0,offset+height-44)+'px';
   root.style.setProperty('--visual-height',height+'px');
   root.style.setProperty('--visual-top',offset+'px');
   root.style.setProperty('--keyboard-space',Math.max(0,fullHeight-height)+44+'px');
  }else root.style.setProperty('--keyboard-space','0px');
 }
 toolbar.addEventListener('pointerdown',event=>event.preventDefault());
 done.addEventListener('click',()=>{
  document.activeElement?.blur();update();
  window.setTimeout(()=>{if(!document.body.classList.contains('modal-open'))document.querySelector('.cart-actions')?.scrollIntoView({block:'nearest',inline:'nearest'})},250);
 });
 document.addEventListener('focusin',()=>{update();window.setTimeout(()=>{if(editing())document.activeElement.scrollIntoView({block:'nearest',inline:'nearest'})},300)});
 document.addEventListener('focusout',()=>window.setTimeout(update,0));
 document.addEventListener('keydown',event=>{if(event.key==='Enter'&&editing()&&document.activeElement.closest('.cart-fields')){event.preventDefault();document.activeElement.blur();update()}});
 viewport?.addEventListener('resize',update);viewport?.addEventListener('scroll',update);
 window.addEventListener('resize',update);telegram?.onEvent?.('viewportChanged',update);
 update();
})();
