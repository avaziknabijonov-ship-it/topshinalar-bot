import io
import os
from pathlib import Path
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from core import fmt
from payments import payment_label, fulfillment_label


def quotation_pdf(store,uid,ref):
    q=store.one('quotes',ref); store.own(uid,q)
    client=store.one('clients',q['client'])
    lines=store.rows('SELECT * FROM quote_items WHERE quote=? ORDER BY id',(ref,))
    font=os.environ.get('PDF_FONT','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not os.path.exists(font):
        raise RuntimeError('Set PDF_FONT to a Unicode TrueType font')
    if 'Unicode' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Unicode',font))
    ru=q['lang']=='ru'
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyUnicode',fontName='Unicode',fontSize=9,leading=14,spaceAfter=8))
    styles.add(ParagraphStyle(name='TitleUnicode',fontName='Unicode',fontSize=20,leading=26,textColor=colors.HexColor('#0B0B0A'),spaceAfter=10))
    styles.add(ParagraphStyle(name='TotalUnicode',fontName='Unicode',fontSize=13,leading=20,alignment=TA_RIGHT,spaceBefore=12))
    p=lambda text: Paragraph(escape(str(text)).replace('\n','<br/>'),styles['BodyUnicode'])
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=42,bottomMargin=40,title=f'TOPSHINALAR - KP #{ref}')
    logo=Image(str(Path(__file__).resolve().parent/'assets'/'topshinalar-logo.png'),width=260,height=260*195/800,hAlign='LEFT')
    body=[logo,Spacer(1,14),HRFlowable(width='100%',thickness=2,color=colors.HexColor('#E6332A')),Spacer(1,18),Paragraph('Коммерческое предложение' if ru else 'Tijorat taklifi',styles['TitleUnicode']),p(f'#{ref} | '+q['created'][:10]),Spacer(1,10),p(('Клиент: ' if ru else 'Mijoz: ')+client['name']),p(client['phone']+' | '+client['address']),Spacer(1,14)]
    headers=['Товар','Шт.','Цена, UZS','Сумма, UZS'] if ru else ['Mahsulot','Dona','Narx, UZS','Jami, UZS']
    data=[[p(h) for h in headers]]
    from decimal import Decimal
    for i in lines:
        total=int((Decimal(i['price'])*i['qty']*(100-i['discount'])/100).quantize(Decimal('1')))
        data.append([p(i['name']),p(i['qty']),p(fmt(Decimal(total)/i['qty'])),p(fmt(total))])
    table=Table(data,colWidths=[240,45,108,126.28],repeatRows=1,hAlign='LEFT')
    # Available A4 width is about 519 points.
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f2f2f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),0.8,colors.HexColor('#E6332A')),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#dedede')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),8)]))
    unset='Не выбран' if ru else 'Tanlanmagan'
    payment=payment_label(q['payment'],q['lang']) if q['payment'] else unset
    fulfillment=fulfillment_label(q['fulfillment'],q['lang']) if q['fulfillment'] else (q['terms'] or unset)
    body += [table,Paragraph(('Итого: ' if ru else 'Jami: ')+fmt(q['total'])+' UZS',styles['TotalUnicode']),Spacer(1,20),p('Способ оплаты' if ru else 'To‘lov usuli'),p(payment),Spacer(1,10),p('Условия' if ru else 'Shartlar'),p(fulfillment)]
    def footer(canvas,doc):
        canvas.setFont('Unicode',8);canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(38,23,'TOPSHINALAR | '+('Коммерческое предложение' if ru else 'Tijorat taklifi'))
        canvas.drawRightString(A4[0]-38,23,str(doc.page))
    doc.build(body,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
