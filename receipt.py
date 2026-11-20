"""Sale receipt / delivery note PDF: A4 and 80 mm thermal roll. Reads saved sale data only."""
import io
import os
from decimal import Decimal, ROUND_HALF_UP
from html import escape
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from core import fmt
from quotation import COMPANY_PHONE, COMPANY_ADDRESS

FORMATS = ('a4', '80mm')
ROLL_WIDTH = 80 * 72 / 25.4


def _font():
    font = os.environ.get('PDF_FONT', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not os.path.exists(font):
        raise RuntimeError('Set PDF_FONT to a Unicode TrueType font')
    if 'Unicode' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Unicode', font))


def receipt_data(store, uid, sale):
    row = store.one('sales', sale)
    store.own(uid, row)
    items = []
    for i in store.rows('SELECT name,qty,price,discount FROM sale_items WHERE sale=? ORDER BY id', (sale,)):
        unit = int((Decimal(i['price']) * (100 - i['discount']) / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        items.append(dict(name=i['name'], qty=i['qty'], unit=unit, total=unit * i['qty']))
    payments = store.rows('SELECT amount,method,created FROM payments WHERE sale=? ORDER BY id', (sale,))
    return dict(sale=row, client=store.one('clients', row['client']), seller=store.one('users', row['actor']), items=items, payments=payments)


def _state(sale, ru):
    if sale['status'] == 'cancelled':
        return 'Отменена' if ru else 'Bekor qilingan'
    if sale['paid'] >= sale['total']:
        return 'Оплачено полностью' if ru else 'To‘liq to‘langan'
    if sale['paid'] > 0:
        return 'Оплачено частично' if ru else 'Qisman to‘langan'
    return 'Не оплачено' if ru else 'To‘lanmagan'


def sale_receipt_pdf(store, uid, sale, fmt_name='a4', lang='uz'):
    if fmt_name not in FORMATS:
        raise ValueError('format')
    _font()
    from payments import payment_label
    data = receipt_data(store, uid, sale)
    s = data['sale']
    ru = lang == 'ru'
    cur = s['currency']
    roll = fmt_name == '80mm'
    size = 7.5 if roll else 9
    base = ParagraphStyle('b', fontName='Unicode', fontSize=size, leading=size + 3, spaceAfter=1)
    right = ParagraphStyle('r', parent=base, alignment=2)
    center = ParagraphStyle('c', parent=base, alignment=1)
    title = ParagraphStyle('t', parent=base, fontSize=size + (2 if roll else 9), leading=size + (4 if roll else 13), spaceAfter=4)
    P = lambda t, st=base: Paragraph(escape(str(t)).replace('\n', '<br/>'), st)
    money = lambda v: fmt(v) + ' ' + cur
    out = io.BytesIO()
    width = ROLL_WIDTH if roll else A4[0]
    margin = 8 if roll else 38
    usable = width - 2 * margin
    doc_title = ('Накладная' if ru else 'Yuk xati / chek') + f' #{sale}'
    body = []
    if roll:
        body += [P('TOPSHINALAR', title), P(COMPANY_PHONE, center), HRFlowable(width='100%', thickness=0.6, color=colors.black), Spacer(1, 3)]
    else:
        logo = Image(str(Path(__file__).resolve().parent / 'assets' / 'topshinalar-logo.png'), width=240, height=240 * 195 / 800, hAlign='LEFT')
        body += [logo, Spacer(1, 4), P('«TOPSHINALAR» MCHJ · ' + COMPANY_PHONE), P(COMPANY_ADDRESS),
                 HRFlowable(width='100%', thickness=2, color=colors.HexColor('#E6332A')), Spacer(1, 6), P(doc_title, title)]
    when = str(s['created'])[:16].replace('T', ' ')
    meta = [(('Дата' if ru else 'Sana'), when), (('Клиент' if ru else 'Mijoz'), data['client']['name']), (('Менеджер' if ru else 'Menejer'), data['seller']['name'])]
    if roll:
        body.append(P(doc_title, base))
        body += [P(f'{k}: {v}') for k, v in meta]
    else:
        t = Table([[P(k), P(v)] for k, v in meta], colWidths=[90, usable - 90])
        t.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
        body.append(t)
    body.append(Spacer(1, 6))
    head = ['№', 'Товар' if ru else 'Mahsulot', 'Кол.' if ru else 'Soni', 'Цена' if ru else 'Narx', 'Сумма' if ru else 'Summa']
    if roll:
        rows = [[P(head[1]), P(head[2], right), P(head[4], right)]]
        for i in data['items']:
            rows.append([P(i['name']), P(f"{i['qty']} × {fmt(i['unit'])}", right), P(fmt(i['total']), right)])
        widths = [usable * 0.5, usable * 0.28, usable * 0.22]
    else:
        rows = [[P(h) for h in head]]
        for n, i in enumerate(data['items'], 1):
            rows.append([P(n), P(i['name']), P(i['qty'], right), P(fmt(i['unit']), right), P(fmt(i['total']), right)])
        widths = [24, usable - 24 - 50 - 90 - 100, 50, 90, 100]
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, colors.HexColor('#E6332A') if not roll else colors.black), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('LINEBELOW', (0, 1), (-1, -1), 0.25, colors.HexColor('#cccccc')), ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2)]))
    body += [table, Spacer(1, 6)]
    debt = s['total'] - s['paid']
    sums = [(('Итого' if ru else 'Jami'), money(s['total'])), (('Оплачено' if ru else 'To‘langan'), money(s['paid'])), (('Долг' if ru else 'Qarz'), money(debt)), (('Статус' if ru else 'Holati'), _state(s, ru))]
    st = Table([[P(k), P(v, right)] for k, v in sums], colWidths=[usable * 0.5, usable * 0.5], hAlign='RIGHT')
    st.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2), ('LINEABOVE', (0, 0), (-1, 0), 0.8, colors.black)]))
    body.append(st)
    if data['payments']:
        body += [Spacer(1, 6), P('Оплаты' if ru else 'To‘lovlar')]
        for p in data['payments']:
            try:
                label = payment_label(p['method'], 'ru' if ru else 'uz')
            except ValueError:
                label = p['method']
            body.append(P(f"{str(p['created'])[:10]} · {label} · {money(p['amount'])}"))
    body += [Spacer(1, 10), P('Спасибо за покупку!' if ru else 'Xaridingiz uchun rahmat!', center)]
    if not roll:
        body += [Spacer(1, 18), Table([[P(('Продавец' if ru else 'Sotuvchi') + ': ____________'), P(('Покупатель' if ru else 'Xaridor') + ': ____________', right)]], colWidths=[usable / 2, usable / 2])]
    if roll:
        # Continuous roll: measure the content, then size the single page to fit.
        height = 40 + 4 * len(body)
        for flow in body:
            _, h = flow.wrap(usable, 10000)
            height += h + flow.getSpaceAfter() + flow.getSpaceBefore()
        page = (width, max(120, height))
        doc = SimpleDocTemplate(out, pagesize=page, leftMargin=margin, rightMargin=margin, topMargin=10, bottomMargin=10, title=doc_title)
    else:
        doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=40, bottomMargin=40, title=doc_title)
    doc.build(body)
    return out.getvalue()
