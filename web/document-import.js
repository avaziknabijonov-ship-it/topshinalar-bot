'use strict';
function documentImportMenu(){
 state.modal=null;
 modal(T('Boshqa usulda qo‘shish','Добавить другим способом'),`<p class="help">${T('Kirim hujjatini qanday yuklaysiz?','Как вы хотите загрузить документ прихода?')}</p><div class="actions-grid"><button data-action="excel-import">Excel (.xlsx)</button><button data-action="document-pdf">PDF</button><button data-action="document-photo">${T('Rasm / surat','Фото / изображение')}</button></div><button class="secondary full" data-action="income">${T('Qo‘lda kirimga qaytish','Вернуться к ручному приходу')}</button>`);
}
function documentUploadForm(pdf){
 form(pdf?T('PDF orqali kirim','Приход из PDF'):T('Rasm orqali kirim','Приход по фото'),'document_extract',
 select('point',T('Ombor','Склад'),state.points.map(p=>[p.id,p.name]))+
 `<label>${pdf?'PDF':T('Hujjat surati','Фото документа')}<input id="document-file" type="file" accept="${pdf?'.pdf,application/pdf':'image/*'}" required></label><p class="help">${T('4 MB gacha. PDF: 1–5 sahifa. Hujjatdagi nom, kelgan dona va narx o‘qiladi. Keyingi oynada hamma qatorni tekshiring. Narxlar USD bo‘lishi kerak; so‘m narxlari avtomatik aylantirilmaydi.','До 4 МБ. PDF: 1–5 страниц. Распознаются название, количество и цена. На следующем шаге проверьте все строки. Цены должны быть в USD; суммы в сумах автоматически не конвертируются.')}</p>`,{pdf});
}
async function encodeDocumentFile(file,pdf){
 if(!file||file.size>4*1024*1024)throw Error(T('4 MB gacha fayl tanlang','Выберите файл до 4 МБ'));
 if(pdf){
  const b=new Uint8Array(await file.arrayBuffer());if(String.fromCharCode(...b.slice(0,5))!=='%PDF-')throw Error(T('PDF fayl tanlang','Выберите файл PDF'));
 }else{
  // Normalize mobile image formats/orientation and bound OCR image dimensions.
  const bitmap=await createImageBitmap(file);
  try{
   const scale=Math.min(1,3200/Math.max(bitmap.width,bitmap.height));
   const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
   const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
   const encoded=canvas.toDataURL('image/jpeg',.95).split(',')[1];if(encoded.length>4*1024*1024*4/3)throw Error(T('Rasm juda katta','Фото слишком большое'));return encoded;
  }finally{bitmap.close()}
 }
 return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file)});
}
async function reviewDocumentUpload(formElement){
 const m=state.modal,button=formElement.querySelector('button.primary');button.disabled=true;button.textContent=T('Hujjat o‘qilmoqda…','Распознавание документа…');
 try{
  const data={...Object.fromEntries(new FormData(formElement)),file:await encodeDocumentFile($('document-file').files[0],m.data.pdf)};
  const result=await api('/api/action',{method:'POST',headers:{'Idempotency-Key':key()},body:{cmd:'document_extract',data}});
  if(state.modal!==m)return;
  state.documentDraft={point:data.point,rows:result.id.rows.length?result.id.rows:[{name:'',qty:'',price:''}],text:result.id.text};
  documentRowsEditor();
 }catch(error){if(state.modal===m){$('form-error').textContent=error.message;button.disabled=false;button.textContent=T('Qayta urinish','Повторить')}}
}
function documentRowsEditor(){
 const d=state.documentDraft;
 const rows=d.rows.map((row,index)=>`<article class="list-card doc-row"><h3>${index+1}. ${T('Mahsulot','Товар')}</h3><label>${T('Mavjud tovar yoki yangi','Существующий или новый товар')}<select data-doc-field="id"><option value="">${T('Yangi / nomi bo‘yicha moslashtirish','Новый / сопоставить по названию')}</option>${(row.matches||[]).map(p=>`<option value="${p.id}" ${String(row.id)===String(p.id)?'selected':''}>${E(p.name)}</option>`).join('')}</select></label><label>${T('Hujjatdagi nom','Название из документа')}<input data-doc-field="name" value="${E(row.name)}" required maxlength="200"></label><div class="two"><label>${T('Kelgan dona','Поступило, шт.')}<input data-doc-field="qty" type="number" min="0" step="1" value="${E(row.qty)}" required></label><label>${T('Bir dona narxi, USD','Цена за шт., USD')}<input data-doc-field="price" type="number" min="0" step="0.01" value="${E(String(row.price??'').replace(/\s/g,'').replace(',','.'))}" required></label></div><button type="button" class="secondary danger" data-doc-remove="${index}">${T('Qatorni olib tashlash','Удалить строку')}</button></article>`).join('');
 form(T('O‘qilgan qatorlarni tekshirish','Проверка распознанных строк'),'document_rows',
 `<p class="help">${T('Har bir nom, dona va USD narxini asl hujjat bilan solishtiring. Kam qator bo‘lsa qo‘shing, xatosini tuzating. Jami, QQS va xizmat qatorlarini mahsulot sifatida kiritmang.','Сверьте каждое название, количество и цену USD с оригиналом. Добавьте пропущенные строки, исправьте ошибки. Не добавляйте итоги, НДС и услуги как товары.')}</p><details><summary>${T('Hujjatdan o‘qilgan matn','Распознанный текст')}</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">${E(d.text)}</pre></details>${rows}<button type="button" class="secondary full" data-doc-add>+ ${T('Qator qo‘shish','Добавить строку')}</button>`);
}
function collectDocumentRows(){
 return [...$('modal').querySelectorAll('.doc-row')].map((node,index)=>({...state.documentDraft.rows[index],...Object.fromEntries([...node.querySelectorAll('[data-doc-field]')].map(el=>[el.dataset.docField,el.value]))}));
}
async function reviewDocumentRows(formElement){
 const m=state.modal,button=formElement.querySelector('button.primary');button.disabled=true;
 try{
  const d=state.documentDraft;d.rows=collectDocumentRows();
  const data={point:d.point,rows:d.rows.map(r=>({id:r.id,name:r.name,qty:r.qty,price:r.price}))};
  const result=await api('/api/action',{method:'POST',headers:{'Idempotency-Key':key()},body:{cmd:'document_preview',data}});
  if(state.modal!==m)return;
  const preview=result.id;
  state.modal={title:T('Kirimni tasdiqlash','Подтвердить приход'),cmd:'document_import',key:key(),pending:{...data,fingerprint:preview.fingerprint}};
  modal(state.modal.title,`<p>${T('Qatorlar','Строки')}: ${preview.count} · ${T('Yangi tovarlar','Новых товаров')}: ${preview.new_count}</p><p class="help">${T('Kelgan dona qoldiqqa qo‘shiladi. USD narxi barcha omborlarda yangilanadi.','Количество добавляется к остатку. Цена USD обновится для всех складов.')}</p>${preview.rows.map(r=>`<div class="list-card"><h3>${E(r.name)}</h3><p>${r.id?T('Mavjud tovar','Существующий товар'):T('Yangi tovar','Новый товар')} · ${T('Qoldiq','Остаток')}: ${r.old_qty??0} + ${r.qty} = ${r.new_qty}<br>USD: ${r.old_price===null||r.old_price_pending?'—':money(r.old_price)} → ${money(r.price)}</p></div>`).join('')}<label class="check"><input id="excel-confirm" type="checkbox">${T('Asl hujjat bilan barcha qator va USD narxlarni tekshirdim','Я сверил все строки и цены USD с оригиналом')}</label><div id="form-error"></div><button class="secondary full" data-doc-edit>${T('Qatorlarni tahrirlash','Редактировать строки')}</button><button class="primary full" data-confirm>${T('Omborga kirim qilish','Оприходовать на склад')}</button>`);
 }catch(error){if(state.modal===m){$('form-error').textContent=error.message;button.disabled=false}}
}
document.addEventListener('click',event=>{
 const button=event.target.closest('button');if(!button)return;
 if(button.hasAttribute('data-doc-add')){const rows=collectDocumentRows();if(rows.length>=100){toast(T('100 tagacha qator','До 100 строк'));return}state.documentDraft.rows=[...rows,{name:'',qty:'',price:''}];documentRowsEditor()}
 if(button.hasAttribute('data-doc-remove')){const rows=collectDocumentRows();rows.splice(Number(button.dataset.docRemove),1);state.documentDraft.rows=rows;documentRowsEditor()}
 if(button.hasAttribute('data-doc-edit'))documentRowsEditor();
});
