'use strict';

const accountingKind = kind => ({receipt:T('Kirim','Приход'),payment:T('To‘lov','Оплата'),fund:T('Berilgan pul','Выдано'),expense:T('Xarajat','Расход'),return:T('Qaytarish','Возврат')})[kind]||kind;
const accountingMethod = method => ({cash:T('Naqd','Наличные'),transfer:T('Bank o‘tkazmasi','Банковский перевод'),card:T('Karta','Карта')})[method]||method;
const accountingDate = () => state.dashboard?.date || new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tashkent',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
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
  const total=Math.round(Number(data.cost)*100)*allocations.reduce((sum,row)=>sum+row.qty,0);
  if(!Number.isFinite(total)||payments.reduce((sum,row)=>sum+Math.round(Number(row.amount)*100),0)>total)throw Error(T('To‘lov kirim jami summasidan oshmasin','Оплата не должна превышать сумму прихода'));
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
 modal(T('Yetkazib beruvchilar','Поставщики'),`<button class="primary full" data-action="supplier-new">+ ${T('Yetkazib beruvchi','Поставщик')}</button><button class="secondary full" data-action="supplier-report">${T('Vitrina va saldo hisoboti','Витрина и взаиморасчёты')}</button>${data.suppliers.map(r=>`<article class="list-card"><h3>${E(r.name)}</h3><p>${E(r.phone)}<br>${E(r.note)}</p>${data.balances.filter(b=>b.supplier===r.id).map(b=>`<p>${T('Saldo','Сальдо')}: ${money(b.balance)} ${E(b.currency)}</p>`).join('')}<button class="secondary" data-account-action="supplier-edit" data-id="${r.id}">${T('Tahrirlash','Изменить')}</button></article>`).join('')}`);
}

async function supplierReport(data){
 const report=await api('/api/supplier-report?'+new URLSearchParams(data));state.supplierReport=report;
 const stock=report.stock.map(r=>`<article class="list-card"><h3>${E(r.name)} · ${r.qty}</h3><p>${E(r.supplier_name)} · ${E(r.point_name)}</p></article>`).join('');
 const sold=report.sold.map(r=>`<article class="list-card"><h3>${E(r.name)} · ${r.qty}</h3><p>${E(r.supplier_name)} · ${E(r.point_name)}</p></article>`).join('');
 modal(T('Yetkazib beruvchi hisoboti','Отчёт по поставщикам'),`<p>${E(report.start)} — ${E(report.end)}</p><h3>${T('Vitrinadagi joriy qoldiq','Текущий остаток витрины')}</h3>${stock||empty(T('Qoldiq yo‘q','Нет остатка'))}<h3>${T('Davrda vitrindan sotilgan','Продано с витрины за период')}</h3>${sold||empty(T('Sotuv yo‘q','Нет продаж'))}<h3>${T('Hisob yozuvlari','Операции')}</h3>${accountingHistory(report.entries)}<button class="secondary full" data-action="supplier-report">${T('Davrni o‘zgartirish','Изменить период')}</button>`);
}

async function managerPanel(){
 const data=await api('/api/manager-account');
 modal(T('Menejer pul hisobi','Деньги менеджера'),`<div class="row-actions">${state.me.role==='director'?`<button data-action="manager-fund">${T('Pul berish','Выдать деньги')}</button>`:''}<button data-action="manager-expense">${T('Xarajat','Расход')}</button><button data-action="manager-return">${T('Pul qaytarish','Возврат денег')}</button><button data-action="supplier-payment">${T('Yetkazib beruvchiga to‘lov','Оплатить поставщику')}</button></div>${data.balances.map(b=>`<article class="list-card"><h3>${E(b.manager_name)} · ${money(b.balance)} ${E(b.currency)}</h3><p>${T('Berilgan − xarajat − qaytarilgan','Выдано − расход − возврат')}: ${money(b.given)} − ${money(b.expenses)} − ${money(b.returned)}</p></article>`).join('')}<h3>${T('Yozuvlar','Операции')}</h3>${accountingHistory(data.entries)}`);
}

async function accountingOperations(action,id){
 const director=state.me.role==='director';
 if(action==='suppliers'){await supplierPanel();return true}
 if(action==='manager-account'){await managerPanel();return true}
 if(action==='supplier-new'||action==='supplier-edit'){
  const r=action==='supplier-edit'?state.suppliers.find(r=>r.id===id):{};
  form(T('Yetkazib beruvchi','Поставщик'),'supplier_save',field('name',T('Nomi','Название'),'text',r.name||'')+field('phone',T('Telefon','Телефон'),'text',r.phone||'',false)+field('note',T('Izoh','Примечание'),'text',r.note||'',false),r.id?{supplier:r.id}:{});return true;
 }
 if(action==='income'){
  const [products,suppliers]=await Promise.all([api('/api/catalog'),api('/api/suppliers?picker=1')]);state.productPick=products.items;
  const points=state.points.map(p=>[p.id,p.name+' · '+(p.kind==='vitrina'?T('Vitrina','Витрина'):T('Sklad','Склад'))]);
  const staff=director?(await api('/api/staff')).filter(r=>r.role==='employee'):[];
  form(T('Mahsulot kirimi','Приход товара'),'supplier_income',`<label>${T('Mahsulotni qidirish','Поиск товара')}<input id="picker-product" type="search"></label>`+select('product',T('Mahsulot','Товар'),products.items.map(p=>[p.id,p.name]))+supplierPicker(suppliers)+field('cost',T('Kirim narxi (bir dona)','Закупочная цена за штуку'),'number')+select('first_point',T('Kirim manzili','Место прихода'),points)+field('first_qty',T('Miqdor','Количество'),'number','1')+select('second_point',T('Ikkinchi manzil (ixtiyoriy)','Второе место (необязательно)'),points,'',false)+field('second_qty',T('Ikkinchi manzil miqdori','Количество во втором месте'),'number','0')+field('paid_cash',T('Naqd to‘landi','Оплачено наличными'),'number','0',false)+field('paid_transfer',T('Bank o‘tkazmasi bilan to‘landi','Оплачено банковским переводом'),'number','0',false)+field('paid_card',T('Karta bilan to‘landi','Оплачено картой'),'number','0',false)+(director?select('manager',T('Menejer puli (bo‘sh — direktor puli)','Деньги менеджера (пусто — директора)'),staff.map(r=>[r.id,r.name]),'',false):'')+accountingFields()+`<p class="help">${T('To‘lovlarni usuli bo‘yicha kiriting. To‘lanmagan qismi yetkazib beruvchi qarzi bo‘lib avtomatik hisoblanadi.','Укажите оплату по способам. Неоплаченный остаток автоматически станет долгом поставщику.')}</p>`+(director?`<button type="button" class="secondary full" data-action="other-import">${T('Boshqa usulda qo‘shish','Добавить другим способом')}</button><p class="help">${T('Excel/PDF kirimi yetkazib beruvchisiz saqlanadi.','Приход Excel/PDF сохраняется без поставщика.')}</p><button type="button" class="secondary full" data-action="quick-product">${T('+ Yangi mahsulot','+ Новый товар')}</button><button type="button" class="secondary full" data-action="opening_stock">${T('Boshlang‘ich qoldiq (bir marta)','Начальный остаток (однократно)')}</button>`:''));return true;
 }
 if(action==='supplier-report'){
  const data=await api('/api/suppliers');
  form(T('Yetkazib beruvchi hisoboti','Отчёт по поставщикам'),'supplier-report-view',select('supplier',T('Yetkazib beruvchi (bo‘sh — barchasi)','Поставщик (пусто — все)'),data.suppliers.map(r=>[r.id,r.name]),'',false)+field('start',T('Boshlanish','С даты'),'date',accountingDate())+field('end',T('Tugash','По дату'),'date',accountingDate()));return true;
 }
 if(['manager-fund','manager-expense','manager-return'].includes(action)){
  const kind={'manager-fund':'fund','manager-expense':'expense','manager-return':'return'}[action];
  const staff=director?(await api('/api/staff')).filter(r=>r.role==='employee'):[];
  form(accountingKind(kind),'manager_record',(director?select('manager',T('Menejer','Менеджер'),staff.map(r=>[r.id,r.name])):'')+field('amount',T('Summa','Сумма'),'number')+accountingFields(),{kind,...(!director?{manager:state.me.id}:{})});return true;
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
 if(action==='point-kind'){
  form(T('Saqlash joyi turi','Тип места хранения'),'point_kind',select('point',T('Joy','Место'),state.points.map(r=>[r.id,r.name]))+select('kind',T('Turi','Тип'),[['sklad',T('Sklad','Склад')],['vitrina',T('Vitrina','Витрина')]]));return true;
 }
 if(action==='transfer'){
  const products=await api('/api/catalog');
  form(T('Sklad ↔ Vitrina','Склад ↔ Витрина'),'transfer',`<label>${T('Mahsulotni qidirish','Поиск товара')}<input id="picker-product" type="search"></label>`+select('product',T('Mahsulot','Товар'),products.items.map(r=>[r.id,r.name]))+select('source',T('Qayerdan','Откуда'),state.points.map(r=>[r.id,r.name]))+select('destination',T('Qayerga','Куда'),state.points.map(r=>[r.id,r.name]))+field('qty',T('Dona','Количество'),'number','1')+field('note',T('Izoh','Примечание'),'text','',false));return true;
 }
 return false;
}

document.addEventListener('click',async event=>{
 const button=event.target.closest('[data-account-action]');if(!button)return;
 try{await accountingOperations(button.dataset.accountAction,Number(button.dataset.id))}catch(error){toast(error.message)}
});
