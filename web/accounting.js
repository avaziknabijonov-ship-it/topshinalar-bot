'use strict';

const accountingKind = kind => WorkspaceText.value('kind',kind,state.me.lang);
const accountingMethod = method => WorkspaceText.value('method',method,state.me.lang);
const accountingDate = () => state.dashboard?.date || new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tashkent',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const accountingTimestamp = value => {if(!value)return '—';const date=new Date(value);return Number.isNaN(date.getTime())?E(value):new Intl.DateTimeFormat(state.me.lang==='ru'?'ru-RU':'uz-UZ',{timeZone:'Asia/Tashkent',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(date)};
const accountingFields = () => select('currency',T('Valyuta','Валюта'),[['USD','USD'],['UZS','UZS']],'USD')+field('date',T('Sana','Дата'),'date',accountingDate())+field('note',T('Izoh','Примечание'),'text','',false);
const supplierPicker = rows => select('supplier',T('Yetkazib beruvchi','Поставщик'),rows.map(r=>[r.id,r.name]));
const accountingHistory = entries => entries.map(r=>`<article class="list-card"><h3>${E(accountingKind(r.kind))}${r.method?' · '+E(accountingMethod(r.method)):''} · ${money(r.amount)} ${E(r.currency)}</h3><p>${E(r.date)} · ${E(r.actor_name)}${r.manager_name?' · '+E(r.manager_name):''}<br>${E(r.supplier_name||'')} ${E(r.note)}</p></article>`).join('') || empty(T('Yozuvlar yo‘q','Записей нет'));

function accountingPayload(cmd,data){
 if(cmd==='supplier_income'){
  const allocations=[];
  for(const prefix of ['first','second']){
   const qty=Number(data[prefix+'_qty']);
   if(!Number.isInteger(qty)||qty<0)throw Error(T('Dona butun son bo‘lsin','Количество должно быть целым'));
   if(qty)allocations.push({point:Number(data[prefix+'_point']),qty});
   delete data[prefix+'_point'];delete data[prefix+'_qty'];
  }
  if(!allocations.length)throw Error(T('Kirim miqdorini kiriting','Введите количество прихода'));
  data.allocations=allocations;
  const payments=[];
  for(const method of ['cash','transfer','card']){
   const amount=Number(data['paid_'+method]||0);
   if(!Number.isFinite(amount)||amount<0)throw Error(T('To‘lov summasini tekshiring','Проверьте сумму оплаты'));
   payments.push({method,amount:String(amount)});
   delete data['paid_'+method];
  }
  if(data.cost!==undefined&&data.cost!==''){
   const unitCost=Number(data.cost);
   const total=Math.round(unitCost*100)*allocations.reduce((sum,row)=>sum+row.qty,0);
   if(!Number.isFinite(total)||total<0||payments.reduce((sum,row)=>sum+Math.round(Number(row.amount)*100),0)>total)throw Error(T('To‘lov kirim jami summasidan oshmasin','Оплата не должна превышать сумму прихода'));
  }
  data.payments=payments;
 }
 if(cmd==='sell'){
  data.items=data.items.map((item,i)=>({...item,point:Number(data['item_point_'+i])}));
  data.point=data.items[0].point;
  for(let i=0;i<data.items.length;i++)delete data['item_point_'+i];
 }
 return data;
}

async function supplierPanel(){
 const data=await api('/api/suppliers');state.suppliers=data.suppliers;
 modal(T('Yetkazib beruvchilar','Поставщики'),`<button class="primary full" data-action="supplier-new">+ ${T('Yetkazib beruvchi','Поставщик')}</button><button class="secondary full" data-action="supplier-report">${T('Vitrina va saldo hisoboti','Витрина и взаиморасчёты')}</button>${data.suppliers.map(r=>`<article class="list-card"><h3>${E(r.name)}</h3><p>${E(r.phone)}<br>${E(r.note)}</p>${data.balances.filter(b=>b.supplier===r.id).map(b=>`<p>${T('Saldo','Сальдо')}: ${money(b.balance)} ${E(b.currency)}</p>`).join('')}<button class="secondary full" data-account-action="supplier-detail" data-id="${r.id}">${T('Kirim va to‘lovlar tarixi','История поступлений и оплат')}</button><button class="secondary" data-account-action="supplier-edit" data-id="${r.id}">${T('Tahrirlash','Изменить')}</button></article>`).join('')}`);
}


async function supplierDetail(id){
 const data=await api('/api/supplier-ledger?supplier='+encodeURIComponent(id));
 const entries=data.entries.slice().reverse();
 const entryCard=r=>{
  const lines=[];
  if(r.product_name)lines.push(`<p>${T('Mahsulot','Товар')}: ${E(r.product_name)}${r.receipt_qty? ` · ${T('Kirim miqdori','Количество прихода')}: ${r.receipt_qty} ${T('dona','шт.')}`:''}${r.qty&&r.kind==='return'? ` · ${T('Qaytarilgan','Возвращено')}: ${r.qty} ${T('dona','шт.')}`:''}</p>`);
  if(r.unit_cost!==null&&r.unit_cost!==undefined)lines.push(`<p>${T('Bir dona narxi','Цена за штуку')}: ${money(r.unit_cost)} ${E(r.currency)}</p>`);
  if(r.locations)lines.push(`<p>${T('Qabul qilingan joylar','Места поступления')}: ${E(r.locations)}</p>`);
  if(r.receipt_id)lines.push(`<p>${T('Kirim raqami','Номер прихода')}: #${r.receipt_id}</p>`);
  if(r.method)lines.push(`<p>${T('To‘lov usuli','Способ оплаты')}: ${E(accountingMethod(r.method))}</p>`);
  lines.push(`<p>${T('Sana-vaqt','Дата и время')}: ${E(accountingTimestamp(r.created))}<br>${T('Hisob sanasi','Дата учета')}: ${E(r.date)} · ${T('Kiritgan','Внёс')}: ${E(r.actor_name)}</p>`);
  lines.push(`<p><strong>${T('Operatsiyadan keyingi saldo','Баланс после операции')}: ${money(r.balance_after)} ${E(r.currency)}</strong></p>`);
  if(r.note)lines.push(`<p>${E(r.note)}</p>`);
  return `<article class="list-card"><h3>#${r.id} · ${E(accountingKind(r.kind))} · ${money(r.amount)} ${E(r.currency)}</h3>${lines.join('')}</article>`;
 };
 const sections=data.totals.map(r=>{
  const currencyEntries=entries.filter(e=>e.currency===r.currency);
  const debtEntries=currencyEntries.filter(e=>e.kind==='receipt'||e.kind==='return');
  const paymentEntries=currencyEntries.filter(e=>e.kind==='payment');
  const debtHistory=debtEntries.map(entryCard).join('')||empty(T('Kirim yoki qaytarish yozuvi yo‘q','Нет приходов или возвратов'));
  const paymentHistory=paymentEntries.map(entryCard).join('')||empty(T('To‘lov yozuvi yo‘q','Нет записей об оплате'));
  return `<section class="supplier-ledger-currency"><h3>${E(r.currency)}</h3>
   <details class="list-card" open><summary><strong>${T('Qarz','Долг')}: ${money(r.balance)} ${E(r.currency)}</strong></summary>
    <p>${T('Jami kirim','Всего поступило')}: ${money(r.received)} · ${T('To‘landi','Оплачено')}: ${money(r.paid)} · ${T('Qaytarildi','Возвращено')}: ${money(r.returned)}</p>
    <div class="list">${debtHistory}</div>
   </details>
   <details class="list-card"><summary><strong>${T('Berilgan pul','Переданные деньги')}: ${money(r.paid)} ${E(r.currency)}</strong></summary>
    <div class="list">${paymentHistory}</div>
   </details>
  </section>`;
 }).join('');
 modal(`${T('Yetkazib beruvchi','Поставщик')}: ${E(data.supplier.name)}`,`${sections||empty(T('Hozircha hisob yozuvi yo‘q','Пока нет записей'))}<button class="secondary full" data-account-action="suppliers">${T('Yetkazib beruvchilar ro‘yxatiga qaytish','Назад к списку поставщиков')}</button>`);
}

async function supplierReport(data){
 const report=await api('/api/supplier-report?'+new URLSearchParams(data));state.supplierReport=report;
 const stock=report.stock.map(r=>`<article class="list-card"><h3>${E(r.name)} · ${r.qty}</h3><p>${E(r.supplier_name)} · ${E(r.point_name)}</p></article>`).join('');
 const sold=report.sold.map(r=>`<article class="list-card"><h3>${E(r.name)} · ${r.qty}</h3><p>${E(r.supplier_name)} · ${E(r.point_name)}</p></article>`).join('');
 modal(T('Yetkazib beruvchi hisoboti','Отчёт по поставщикам'),`<p>${E(report.start)} — ${E(report.end)}</p><h3>${T('Vitrinadagi joriy qoldiq','Текущий остаток витрины')}</h3>${stock||empty(T('Qoldiq yo‘q','Нет остатка'))}<h3>${T('Davrda vitrindan sotilgan','Продано с витрины за период')}</h3>${sold||empty(T('Sotuv yo‘q','Нет продаж'))}<h3>${T('Hisob yozuvlari','Операции')}</h3>${accountingHistory(report.entries)}<button class="secondary full" data-action="supplier-report">${T('Davrni o‘zgartirish','Изменить период')}</button>`);
}

async function managerPanel(){
 const data=await api('/api/manager-account');
 modal(T('Menejer pul hisobi','Деньги менеджера'),`<div class="row-actions">${state.me.role==='director'?`<button data-action="manager-fund">${T('Pul berish','Выдать деньги')}</button>`:''}<button data-action="manager-expense">${T('Xarajat','Расход')}</button><button data-action="manager-return">${T('Kassaga topshirish','Сдать в кассу')}</button><button data-action="supplier-payment">${T('Yetkazib beruvchiga to‘lov','Оплата поставщику')}</button></div>${data.balances.map(b=>`<article class="list-card"><h3>${E(b.manager_name)}</h3><p><strong>${T('Hozir topshirilmagan qoldiq','Остаток на руках')}: ${money(b.balance)} ${E(b.currency)}</strong></p><p>${T('Hisob','Расчёт')}: ${money(b.given)} + ${money(b.received||0)} − ${money(b.expenses)} − ${money(b.returned)} ${E(b.currency)}<br>${T('Mijozga qaytarilgan','Возвращено клиенту')}: ${money(b.refunds||0)} ${E(b.currency)}<br>${T('Direktor tasdig‘ini kutyapti','Ожидает подтверждения директора')}: ${money(b.pending_return||0)} ${E(b.currency)}</p></article>`).join('')||empty(T('Hozircha menejer pul yozuvlari yo‘q','Пока нет записей по деньгам менеджера'))}<p class="help">${T('Kassaga topshirilgan pul direktor tasdiqlagandan keyin qoldiqdan ayriladi. Har bir valyuta alohida hisoblanadi.','Переданные в кассу деньги уменьшают остаток после подтверждения директора. Валюты считаются отдельно.')}</p><h3>${T('Yozuvlar','Операции')}</h3>${accountingHistory(data.entries)}`);
}
async function accountingOperations(action,id){
 const director=state.me.role==='director';
 if(action==='suppliers'){await supplierPanel();return true}
 if(action==='supplier-detail'){await supplierDetail(id);return true}
 if(action==='supplier-debts'){
  const data=await api('/api/suppliers');
  const balances=(data.balances||[]).filter(r=>Number(r.balance)>0);
  modal(T('Yetkazib beruvchilarga qarz','Долги поставщикам'),`<div class="list">${balances.map(r=>{const supplier=data.suppliers.find(s=>s.id===r.supplier);return `<article class="list-card"><h3>${E(supplier?.name||r.supplier_name||T('Yetkazib beruvchi','Поставщик'))}</h3><p>${T('Qolgan qarz','Остаток долга')}: ${money(r.balance)} ${E(r.currency||'USD')}</p><button class="secondary full" data-account-action="supplier-detail" data-id="${r.supplier}">${T('Tarixni ko‘rish','История')}</button></article>`}).join('')||empty(T('Yetkazib beruvchilarga qarz yo‘q.','Долгов поставщикам нет.'))}</div>`);
  return true;
 }
 if(action==='manager-account'){await managerPanel();return true}
 if(action==='supplier-new'||action==='supplier-edit'){
  const r=action==='supplier-edit'?state.suppliers.find(r=>r.id===id):{};
  form(T('Yetkazib beruvchi','Поставщик'),'supplier_save',field('name',T('Nomi','Название'),'text',r.name||'')+field('phone',T('Telefon','Телефон'),'text',r.phone||'',false)+field('note',T('Izoh','Примечание'),'text',r.note||'',false),r.id?{supplier:r.id}:{});return true;
 }
 if(action==='income'){
  const [products,suppliers]=await Promise.all([api('/api/catalog'),api('/api/suppliers?picker=1')]);state.productPick=products.items;
  const points=state.points.map(p=>[p.id,p.name+' · '+(p.kind==='vitrina'?T('Vitrina','Витрина'):T('Sklad','Склад'))]);
  const staff=director?(await api('/api/staff')).filter(r=>r.role==='employee'):[];
  form(T('Mahsulot kirimi','Приход товара'),'supplier_income',`<label>${T('Mahsulotni qidirish','Поиск товара')}<input id="picker-product" type="search"></label>`+select('product',T('Mahsulot','Товар'),products.items.map(p=>[p.id,p.name]))+supplierPicker(suppliers)+field('cost',T('Kirim narxi (bir dona)','Закупочная цена за штуку'),'number')+select('first_point',T('Kirim manzili','Место прихода'),points)+(director?`<button type="button" class="secondary" data-receipt-point-archive>${T('Tanlangan manzilni o‘chirish','Удалить выбранное место')}</button>`:'')+field('first_qty',T('Miqdor','Количество'),'number','1')+select('second_point',T('Ikkinchi manzil (ixtiyoriy)','Второе место (необязательно)'),points,'',false)+field('second_qty',T('Ikkinchi manzil miqdori','Количество во втором месте'),'number','0')+field('paid_cash',T('Naqd to‘landi','Оплачено наличными'),'number','0',false)+field('paid_transfer',T('Bank o‘tkazmasi bilan to‘landi','Оплачено банковским переводом'),'number','0',false)+field('paid_card',T('Karta bilan to‘landi','Оплачено картой'),'number','0',false)+(director?select('manager',T('Menejer puli (bo‘sh — direktor puli)','Деньги менеджера (пусто — директора)'),staff.map(r=>[r.id,r.name]),'',false):'')+accountingFields()+`<p class="help">${T('To‘lovlarni usuli bo‘yicha kiriting. To‘lanmagan qismi yetkazib beruvchi qarzi bo‘lib avtomatik hisoblanadi.','Укажите оплату по способам. Неоплаченный остаток автоматически станет долгом поставщику.')}</p>`+(director?`<button type="button" class="secondary full" data-action="other-import">${T('Boshqa usulda qo‘shish','Добавить другим способом')}</button><p class="help">${T('Excel/PDF kirimi yetkazib beruvchisiz saqlanadi.','Приход Excel/PDF сохраняется без поставщика.')}</p><button type="button" class="secondary full" data-action="quick-product">${T('+ Yangi mahsulot','+ Новый товар')}</button><button type="button" class="secondary full" data-action="opening_stock">${T('Boshlang‘ich qoldiq (bir marta)','Начальный остаток (однократно)')}</button>`:''));return true;
 }
 if(action==='supplier-report'){
  const data=await api('/api/suppliers');
  form(T('Yetkazib beruvchi hisoboti','Отчёт по поставщикам'),'supplier-report-view',select('supplier',T('Yetkazib beruvchi (bo‘sh — barchasi)','Поставщик (пусто — все)'),data.suppliers.map(r=>[r.id,r.name]),'',false)+field('start',T('Boshlanish','С даты'),'date',accountingDate())+field('end',T('Tugash','По дату'),'date',accountingDate()));return true;
 }
 if(['manager-fund','manager-expense','manager-return'].includes(action)){
  const kind={'manager-fund':'fund','manager-expense':'expense','manager-return':'return'}[action];
  const staff=director?(await api('/api/staff')).filter(r=>r.role==='employee'):[];
  form(action==='manager-return'?T('Kassaga topshirish','Сдать в кассу'):accountingKind(kind),'manager_record',(director?select('manager',T('Menejer','Менеджер'),staff.map(r=>[r.id,r.name])):'')+field('amount',T('Summa','Сумма'),'number')+accountingFields()+(action==='manager-return'?`<p class="help">${T('Topshirilgan summa direktor tasdiqlagandan keyin qoldiqdan ayriladi. Bu amal savdolarni o‘zgartirmaydi.','Сумма вычтется из остатка после подтверждения директором. Продажи эта операция не меняет.')}</p>`:''),{kind,...(!director?{manager:state.me.id}:{})});return true;
 }
 if(action==='supplier-payment'){
  const suppliers=await api('/api/suppliers?picker=1');
  const staff=director?(await api('/api/staff')).filter(r=>r.role==='employee'):[];
  form(T('Yetkazib beruvchiga to‘lov','Оплата поставщику'),'supplier_payment',supplierPicker(suppliers)+(director?select('manager',T('Menejer puli (bo‘sh — direktor puli)','Деньги менеджера (пусто — директора)'),staff.map(r=>[r.id,r.name]),'',false):'')+select('method',T('To‘lov usuli','Способ оплаты'),[['cash',T('Naqd','Наличные')],['transfer',T('Bank o‘tkazmasi','Банковский перевод')],['card',T('Karta','Карта')]])+field('amount',T('Summa','Сумма'),'number')+accountingFields()+`<p class="help">${T('Menejer tanlansa, uning xarajatiga avtomatik yoziladi.','При выборе менеджера расход автоматически спишется с его счёта.')}</p>`,director?{}:{manager:state.me.id});return true;
 }
 if(action==='supplier-return'){
  const r=await api('/api/supplier-report?start='+accountingDate()+'&end='+accountingDate());
  form(T('Yetkazib beruvchiga tovar qaytarish','Возврат товара поставщику'),'supplier_return',select('lot',T('Kirim partiyasi','Партия прихода'),r.lots.map(l=>[l.id,`#${l.receipt} ${l.product_name} · ${l.point_name} · ${l.qty} · ${money(l.cost)} ${l.currency}`]))+field('qty',T('Dona','Количество'),'number','1')+field('date',T('Sana','Дата'),'date',accountingDate())+field('note',T('Izoh','Примечание'),'text','',false));return true;
 }

 return false;
}

async function archiveReceiptPoint(button){
 const form=button.closest('form');
 const first=form.elements.namedItem('first_point');
 const point=state.points.find(p=>String(p.id)===first.value);
 if(!point){toast(T('Avval kirim manzilini tanlang','Сначала выберите место прихода'));return}
 if(!window.confirm(T('Manzil arxivlansinmi? Tarix saqlanadi.','Архивировать место? История сохранится.')+' '+point.name))return;
 button.disabled=true;
 try{
  await api('/api/action',{method:'POST',headers:{'Idempotency-Key':key()},body:{cmd:'point_archive',data:{point:point.id,active:false}}});
  state.points=state.points.filter(p=>p.id!==point.id);
  for(const name of ['first_point','second_point']){
   const select=form.elements.namedItem(name);
   if(select.value===String(point.id))select.value="";
   select.querySelector('option[value="'+point.id+'"]')?.remove();
  }
  toast(T('Manzil arxivlandi','Место архивировано'));
 }finally{button.disabled=false}
}

document.addEventListener('click',async event=>{
 const archive=event.target.closest('[data-receipt-point-archive]');
 if(archive){
  try{await archiveReceiptPoint(archive)}catch(error){toast(WorkspaceText.error(error,state.me?.lang||'uz'))}
  return;
 }
 const button=event.target.closest('[data-account-action]');if(!button)return;
 try{await accountingOperations(button.dataset.accountAction,Number(button.dataset.id))}catch(error){toast(WorkspaceText.error(error,state.me?.lang||'uz'))}
});
