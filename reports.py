import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from payments import payment_label, fulfillment_label

# Stable API keys; labels are shared by the summary and export filename.
REPORT_GROUPS = {
    'all': (('Barchasi', 'Все разделы'), None),
    'sales': (('Sotuvlar', 'Продажи'), ('sales', 'sale_items')),
    'payments': (('To‘lovlar va pul qaytarishlar', 'Платежи и возвраты'), ('payments', 'refunds')),
    'debts': (('Davrdagi sotuvlar qarzi (joriy)', 'Долги по продажам периода'), ('debts',)),
    'stock': (('Ombor qoldig‘i (hozir)', 'Остатки склада сейчас'), ('stock', 'warehouses')),
    'movements': (('Ombor kirim-chiqimi', 'Движения склада'), ('movements', 'product_events')),
    'employees': (('Xodimlar: ish kunlari va jarimalar', 'Сотрудники: рабочие дни и штрафы'), ('shifts', 'fines')),
    'calls': (('Qo‘ng‘iroqlar', 'Звонки'), ('calls',)),
    'quotes': (('Tijorat takliflari (KP)', 'Коммерческие предложения (КП)'), ('quotes',)),
    'deliveries': (('Yetkazib berishlar', 'Доставки'), ('deliveries',)),
    'tasks': (('Ochiq vazifalar (hozir)', 'Открытые задачи сейчас'), ('tasks',)),
}

def report_group(section):
    if not isinstance(section, str) or section not in REPORT_GROUPS:
        raise ValueError('report_section')
    return REPORT_GROUPS[section]


COLUMNS={
'creator_name':('KP tuzuvchi','Составитель КП'),'creator_phone':('Tuzuvchi telefoni','Телефон составителя'),
'currency':('Valyuta','Валюта'),'exchange_rate':('USD kursi, so‘m','Курс USD, сум'),'source_total_usd':('Asl jami, USD','Исходная сумма, USD'),
'warehouse_name':('Ombor','Склад'),'stock_value':('Narxi ma’lum qoldiq qiymati','Стоимость остатков с ценой'),'unknown_stock':('Qoldig‘i kiritilmagan mahsulotlar','Товары без остатка'),'unknown_price':('Narxi kiritilmagan qoldiqlar','Остатки без цены'),'as_of':('Qoldiq olingan vaqt','Время снимка остатков'),'stock_status':('Qoldiq holati','Статус остатка'),'kind':('Harakat turi','Тип движения'),'action':('Amal','Действие'),
'brand':('Brend','Бренд'),'size':('Razmer','Размер'),'debt_due':('To‘lov muddati','Срок оплаты'),
'cancel_reason':('Bekor qilish sababi','Причина отмены'),'cancelled_by':('Bekor qilgan direktor ID','ID отменившего директора'),'cancelled_by_name':('Bekor qilgan direktor','Отменивший директор'),'cancelled_at':('Bekor qilingan vaqt','Время отмены'),
'id':('ID','ID'),'name':('Nomi / ism','Название / имя'),'phone':('Telefon','Телефон'),'address':('Manzil','Адрес'),
'note':('Izoh','Примечание'),'owner':('Mas’ul ID','ID ответственного'),'client':('Mijoz ID','ID клиента'),
'client_name':('Mijoz','Клиент'),'actor':('Xodim ID','ID сотрудника'),'employee_name':('Xodim','Сотрудник'),
'owner_name':('Mas’ul xodim','Ответственный сотрудник'),'approved_by_name':('Tasdiqlagan direktor','Утвердивший директор'),
'point':('Nuqta','Точка'),'point_id':('Nuqta ID','ID точки'),'product':('Mahsulot ID','ID товара'),
'price':('Narx','Цена'),'qty':('Dona','Количество'),'discount':('Chegirma, %','Скидка, %'),
'sale':('Sotuv ID','ID продажи'),'quote':('КП ID','ID КП'),'total':('Jami','Итого'),
'paid':('To‘langan','Оплачено'),'debt':('Qarz','Долг'),'payment':('To‘lov turi','Тип оплаты'),
'amount':('Summa','Сумма'),'method':('To‘lov turi','Тип оплаты'),'created':('Sana va vaqt','Дата и время'),
'due':('Eslatma vaqti','Время напоминания'),'status':('Holat','Статус'),'notified':('Eslatma yuborildi','Напоминание отправлено'),
'result':('Natija','Результат'),'started':('Ish boshlandi','Начало работы'),'ended':('Ish tugadi','Конец работы'),
'report':('Kun hisoboti','Отчет за день'),'reason':('Sabab','Причина'),'approved_by':('Tasdiqlagan direktor ID','ID утвердившего директора'),
'driver':('Haydovchi','Водитель'),'fee':('Yetkazish narxi','Стоимость доставки'),
'fulfillment':('Shartlar','Условия'),'lang':('Til','Язык'),'terms':('Avvalgi izoh','Прежнее примечание'),'role':('Lavozim','Роль'),
}
SECTIONS={'manager_days':('Menejer ish kunlari','Рабочие дни менеджеров'),
'supplier_stock':('Yetkazib beruvchi vitrina','Витрина по поставщикам'),
'supplier_sold':('Vitrinadan sotilgan','Продано с витрины'),
'supplier_entries':('Yetkazib beruvchi hisob','Операции поставщиков'),
'supplier_balances':('Yetkazib beruvchi saldo','Сальдо поставщиков'),
'supplier_lots':('Kirim partiyalari','Партии прихода'),
'manager_entries':('Menejer pul jurnali','Денежный журнал менеджера'),
'manager_balances':('Menejer pul saldosi','Денежное сальдо менеджера'),
'debts':('Davrdagi sotuvlar qarzi','Долги по продажам периода'),
'movements':('Ombor harakatlari','Движения склада'),'product_events':('Mahsulot qo‘shish tarixi','История товаров'),'warehouses':('Omborlar hozirgi qoldiq','Склады текущие остатки'),
'refunds':('Pul qaytarishlar','Возвраты денег'),
'sales':('Sotuvlar','Продажи'),'sale_items':('Sotilgan mahsulotlar','Проданные товары'),
'payments':('To‘lovlar','Платежи'),'calls':('Qo‘ng‘iroqlar','Звонки'),'deliveries':('Labo yetkazish','Доставка Labo'),
'shifts':('Ish kunlari','Рабочие дни'),'fines':('Jarimalar','Штрафы'),'quotes':('Tijorat takliflari','Коммерческие предложения'),
'tasks':('Vazifalar','Задачи'),'client':('Mijoz','Клиент'),'stock':('Qoldiqlar','Остатки'),
}
VALUES={'director':('Direktor','Директор'),'employee':('Xodim','Сотрудник'),'open':('Ochiq','Открыта'),'done':('Bajarilgan','Выполнена'),'draft':('Qoralama','Черновик'),'sent':('Yuborilgan','Отправлено'),'accepted':('Qabul qilingan','Принято'),'rejected':('Rad etilgan','Отклонено'),'new':('Yangi','Новая'),'on_way':('Yo‘lda','В пути'),'delivered':('Yetkazildi','Доставлено'),'cancelled':('Bekor qilingan','Отменено')}

def localized(key,val,lang,section=None):
    from ui_text import value,CATALOG,BOOLEANS
    if key=='kind' and section=='manager_entries':return value('manager_kind',val,lang)
    if key=='method' and val=='refund':return value(key,val,lang)
    if key in {'payment','method'}:return payment_label(val,lang)
    if key in CATALOG['values'] or key in BOOLEANS or key in {'action','last_error'}:
        return value(key,val,lang)
    if key in {'receipt_status','day_status'}:
        names={'pending':('Tasdiq kutilmoqda','Ожидает подтверждения'),'accepted':('Qabul qilindi','Принято'),'rejected':('Rad etilgan','Отклонено'),'legacy':('Eski yozuv','Прежняя запись'),'open':('Yopilmagan','Не закрыт'),'closed':('Yopilgan','Закрыт'),'reopened':('Qayta tekshirish','Требуется сверка')}
        if val in names:return names[val][lang=='ru']
    if key in {'kind','action','stock_status'}:
        labels={'excel_income':('Excel/PDF kirimi','Приход Excel/PDF'),'in':('Kirim','Приход'),'opening':('Boshlang‘ich qoldiq','Начальный остаток'),'return':('Qaytarish','Возврат'),'writeoff':('Hisobdan chiqarish','Списание'),'sale':('Sotuv','Продажа'),'product':('Mahsulot qo‘shildi','Товар добавлен'),'product_edit':('Mahsulot tahrirlandi','Товар изменён'),'unknown':('Kiritilmagan','Не указан'),'known':('Kiritilgan','Указан')}
        if val in labels:return labels[val][lang=='ru']
    if key=='status' and val=='active':return 'Faol' if lang=='uz' else 'Активна'
    if key=='method' and val=='refund':return 'Pul qaytarish' if lang=='uz' else 'Возврат денег'
    if key in {'payment','method'}:return payment_label(val,lang)
    if key=='fulfillment':return fulfillment_label(val,lang)
    if key in {'status','role'} and val in VALUES:return VALUES[val][lang=='ru']
    return val

MONEY={'received','received_cash','received_card','received_transfer','received_other','historical_received','pending_return','legacy_returned','refunds','price','total','paid','amount','fee','debt','stock_value','source_total_usd','cost','balance','given','expenses','returned'}
PEOPLE={'accepted_by':'accepted_by_name','actor':'employee_name','owner':'owner_name','approved_by':'approved_by_name','cancelled_by':'cancelled_by_name'}
COLUMNS.update({'day_status':('Kun holati','Статус дня'),'closed_by':('Kunni yopgan','Закрыл день'),'closed_at':('Yopilgan vaqt','Время закрытия'),'refund_review_count':('Tekshirilmagan refundlar','Непроверенные возвраты'),'historical_received':('Avvalgi to‘lovlardan tushum','Поступления по прежним оплатам'),'legacy_returned':('Eski qaytarish yozuvlari','Прежние записи возвратов'),'received_cash':('Naqd tushum','Наличные поступления'),'received_card':('Karta tushumi','Поступления по карте'),'received_transfer':('Bank tushumi','Банковские поступления'),'received_other':('Boshqa tushum','Прочие поступления'),'received':('Qabul qilgan pul','Получено'),'pending_return':('Tasdiq kutilmoqda','Ожидает подтверждения'),'refunds':('Mijozga qaytargan','Возвращено клиенту'),'receipt_status':('Qabul holati','Статус приёма'),'accepted_by':('Qabul qilgan direktor ID','ID принявшего директора'),'accepted_at':('Qabul vaqti','Время приёма'),'source':('Manba','Источник'),'source_id':('Manba ID','ID источника'),
'supplier':('Yetkazib beruvchi ID','ID поставщика'),'supplier_name':('Yetkazib beruvchi','Поставщик'),
'manager':('Menejer ID','ID менеджера'),'manager_name':('Menejer','Менеджер'),
'actor_name':('Yozuvni kiritgan','Кто записал'),'date':('Hisob sanasi','Дата операции'),
'cost':('Bir dona kirim narxi','Закупочная цена за штуку'),'balance':('Saldo','Сальдо'),
'given':('Berilgan pul','Выданные деньги'),'expenses':('Xarajatlar','Расходы'),'returned':('Qaytarilgan pul','Возвращённые деньги'),
'receipt':('Kirim ID','ID прихода'),'lot':('Partiya ID','ID партии'),'point_name':('Saqlash joyi','Место хранения'),
'product_name':('Mahsulot','Товар'),'manager_entry':('Menejer xarajat ID','ID расхода менеджера'),
})

def export_fields(rows):
    """Replace person identifiers in-place and omit duplicate name columns."""
    fields=[]
    for key in dict.fromkeys(key for row in rows for key in row) if rows else ['id']:
        if key=='discount':continue
        key=PEOPLE.get(key,key)
        if key not in fields:fields.append(key)
    return fields

def workbook(sections,lang='uz',hide_ids=False):
    wb=Workbook();wb.remove(wb.active)
    for index,(name,rows) in enumerate(sections.items()):
        ws=wb.create_sheet(SECTIONS.get(name,(name,name))[lang=='ru'][:31])
        defaults={'movements':['created','name','brand','size','warehouse_name','qty','kind','actor','note'],'product_events':['created','name','brand','size','action','actor'],'warehouses':['warehouse_name','qty','stock_value','unknown_stock','unknown_price','as_of']}
        fields=export_fields(rows if rows else [dict.fromkeys(defaults[name])]) if name in defaults else export_fields(rows)
        if hide_ids:
            from director_reports import INTERNAL
            fields=[k for k in fields if k not in INTERNAL and not k.endswith('_id')] or ['note']
        from ui_text import text
        ws.append([COLUMNS[k][lang=='ru'] if k in COLUMNS else text('extra_field',lang) for k in fields])
        for row in rows:
            values=[]
            for key in fields:
                val=localized(key,row.get(key),lang,name)
                if key in PEOPLE.values() and not val:
                    val='Имя не указано' if lang=='ru' else 'Ism kiritilmagan'
                if key in MONEY and val is not None:
                    if isinstance(val,int) and abs(val)>=10**15:
                        absolute=abs(val);val=('-' if val<0 else '')+str(absolute//100)+'.'+str(absolute%100).zfill(2)
                    else:val=val/100
                if isinstance(val,str) and val.lstrip().startswith(('=','+','-','@')):val="'"+val
                values.append(val)
            ws.append(values)
        for c in ws[1]:
            c.font=Font(color='FFFFFF',bold=True);c.fill=PatternFill('solid',fgColor='17394D');c.alignment=Alignment(wrap_text=True,vertical='center')
        ws.row_dimensions[1].height=34;ws.freeze_panes='A2'
        for idx,key in enumerate(fields,1):
            ws.column_dimensions[get_column_letter(idx)].width=40 if key in {'name','note','address','report','terms',*PEOPLE.values()} else 23
            for cells in ws.iter_rows(min_row=2,min_col=idx,max_col=idx):
                c=cells[0];c.alignment=Alignment(wrap_text=True,vertical='top')
                if key in MONEY:c.number_format='#,##0.00'
        if rows:
            tab=Table(displayName=f'Data{index}',ref=f'A1:{get_column_letter(len(fields))}{len(rows)+1}')
            tab.tableStyleInfo=TableStyleInfo(name='TableStyleMedium2',showRowStripes=True)
            ws.add_table(tab)
        ws.sheet_view.showGridLines=False
    if not sections:wb.create_sheet('TOPSHINALAR')
    out=io.BytesIO();wb.save(out);return out.getvalue()


SECTIONS.update({'clients':('Mijozlar · joriy','Клиенты · сейчас'),'client_history':('Mijoz qarzi tarixi','История долга клиентов'),'client_opening':('Mijoz davr boshi qarzi','Долг клиентов на начало'),'suppliers':('Ta’minotchilar','Поставщики'),'supplier_opening':('Ta’minotchi davr boshi','Поставщики на начало'),'receipts':('Kirimlar','Приходы'),'staff':('Xodimlar','Сотрудники'),'website':('Sayt katalogi','Каталог сайта'),'audit':('Amallar tarixi','История действий')})
COLUMNS.update({'change':('Qarz o‘zgarishi','Изменение долга'),'balance_after':('Amaldan keyingi qarz','Долг после операции'),'history_review_count':('Tarixi tekshiriladigan savdolar','Продажи для проверки истории'),'price_cents':('Sayt narxi USD','Цена сайта USD')})
MONEY.update({'change','balance_after','unit_cost','price_cents'})

SECTIONS['current_debts']=('Mijozlar qarzi · joriy','Долги клиентов · сейчас')

SECTIONS.update({'products':('Mahsulotlar · joriy','Товары · сейчас'),'expenses':('Menejer xarajatlari','Расходы менеджеров'),'customer_returns':('Mijozdan qaytarishlar','Возвраты клиентов'),'supplier_returns':('Ta’minotchiga qaytarishlar','Возвраты поставщикам'),'other_incomes':('Boshqa tovar kirimi','Прочий приход товара')})

SECTIONS.update({'product_analytics':('Tovarlar tahlili','Аналитика товаров'),'employee_analytics':('Xodimlar tahlili','Аналитика сотрудников')})
COLUMNS.update({'revenue':('Savdo summasi','Сумма продаж'),'sales_count':('Savdolar soni','Количество продаж'),'client_count':('Mijozlar soni','Количество клиентов'),'paid_to_date':('Hozirgacha to‘langan','Оплачено на сейчас'),'debt_to_date':('Qolgan mijoz qarzi','Остаток долга клиентов'),'unknown_sales_count':('Tekshirish kerak bo‘lgan savdolar','Продажи для проверки')})
MONEY.update({'revenue','paid_to_date','debt_to_date'})

SECTIONS['analytics_review']=('Tovar tahlili tekshiruvi','Проверка аналитики товаров')
COLUMNS['review_sales_count']=('Tekshiriladigan savdolar','Продажи для проверки')

# The same field names/coded values appear in the web cabinet and its exports.
from ui_text import FIELDS
COLUMNS.update(FIELDS)
