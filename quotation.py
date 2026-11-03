import io
import os
from pathlib import Path
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from core import fmt
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing, Rect


COMPANY_WEBSITE='https://topshinalar.uz'
COMPANY_PHONE='+998974788606'
COMPANY_ADDRESS="Toshkent viloyati, Zangiota tumani, Erkin, Tariq-Teshar MFY, M39 yo'li, 54A"

def company_contact_payload():
    from urllib.parse import urlsplit
    origin=os.environ.get('PUBLIC_APP_URL','').rstrip('/')
    parsed=urlsplit(origin)
    if parsed.scheme=='https' and parsed.netloc and not parsed.path and not parsed.query and not parsed.fragment:
        return origin+'/company'
    # CLI installations without a Mini App keep an offline contact card.
    return '\r\n'.join([
        'BEGIN:VCARD',
        'VERSION:3.0',
        'FN:TOPSHINALAR',
        'ORG:TOPSHINALAR',
        'TEL;TYPE=WORK,VOICE:'+COMPANY_PHONE,
        'URL:'+COMPANY_WEBSITE,
        'ADR;TYPE=WORK:;;'+COMPANY_ADDRESS.replace(',',r'\,')+';;;;Uzbekistan',
        'END:VCARD',
    ])

def company_contact_qr(size=84):
    widget=QrCodeWidget(company_contact_payload(),barBorder=4,barLevel='M')
    x0,y0,x1,y1=widget.getBounds()
    drawing=Drawing(size,size,transform=[size/(x1-x0),0,0,size/(y1-y0),-x0*size/(x1-x0),-y0*size/(y1-y0)])
    drawing.add(Rect(0,0,size,size,fillColor=colors.white,strokeColor=None))
    drawing.add(widget)
    return drawing


def product_image(reference,max_height=120):
    """Read the selected product's saved reference; never substitute another model."""
    from catalog import local_photo
    import json
    import re
    import urllib.request
    import urllib.parse
    if not reference:
        return None
    try:
        path=local_photo(reference)
        if path:
            payload=path.read_bytes()
        else:
            token=os.environ.get('BOT_TOKEN','')
            if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token):return None
            request=urllib.request.Request('https://api.telegram.org/bot'+token+'/getFile',data=urllib.parse.urlencode({'file_id':reference}).encode())
            with urllib.request.urlopen(request,timeout=5) as response:
                info=json.loads(response.read(65536))
            file_path=info.get('result',{}).get('file_path','')
            if not re.fullmatch(r'[A-Za-z0-9_./-]+',file_path) or '..' in file_path:return None
            with urllib.request.urlopen('https://api.telegram.org/file/bot'+token+'/'+file_path,timeout=5) as response:
                payload=response.read(8*1024*1024+1)
        if len(payload)>8*1024*1024:return None
        image=Image(io.BytesIO(payload))
        scale=min(100/image.imageWidth,max_height/image.imageHeight)
        image.drawWidth=image.imageWidth*scale
        image.drawHeight=image.imageHeight*scale
        return image
    except Exception:
        # One unavailable photo must not prevent the proposal from being sent.
        return None


def quotation_pdf(store,uid,ref):
    q=store.one('quotes',ref); store.own(uid,q)
    lines=store.rows('SELECT * FROM quote_items WHERE quote=? ORDER BY id',(ref,))
    font=os.environ.get('PDF_FONT','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not os.path.exists(font):
        raise RuntimeError('Set PDF_FONT to a Unicode TrueType font')
    if 'Unicode' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Unicode',font))
    ru=q['lang']=='ru'
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyUnicode',fontName='Unicode',fontSize=9,leading=13,spaceAfter=4))
    styles.add(ParagraphStyle(name='IntroUnicode',fontName='Unicode',fontSize=8.5,leading=11,alignment=1,spaceAfter=4))
    styles.add(ParagraphStyle(name='TermsUnicode',fontName='Unicode',fontSize=8.5,leading=10.5,spaceAfter=1))
    styles.add(ParagraphStyle(name='TitleUnicode',fontName='Unicode',fontSize=20,leading=26,textColor=colors.HexColor('#0B0B0A'),spaceAfter=8))
    styles.add(ParagraphStyle(name='CompanyUnicode',fontName='Unicode',fontSize=8.5,leading=10.5,alignment=1,spaceAfter=0))
    p=lambda text: Paragraph(escape(str(text)).replace('\n','<br/>'),styles['BodyUnicode'])
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=42,bottomMargin=40,title=f'TOPSHINALAR - KP #{ref}')
    logo=Image(str(Path(__file__).resolve().parent/'assets'/'topshinalar-logo.png'),width=260,height=260*195/800,hAlign='LEFT')
    header=Table([[logo,company_contact_qr(64)]],colWidths=[doc.width-70,70])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    company_lines=[
        Paragraph('«TOPSHINALAR» MAS\'ULIYATI CHEKLANGAN JAMIYAT',styles['CompanyUnicode']),
        Paragraph('ТОШКЕНТ ВИЛОЯТИ, ЗАНГИОТА тумани',styles['CompanyUnicode']),
        Paragraph('Тарик-Тешар МФЙ, М39 Автомагистрал йўли кўчаси, 54A-уй',styles['CompanyUnicode']),
        Paragraph('ИНН: 310676411',styles['CompanyUnicode']),
    ]
    company_table=Table([[company_lines]],colWidths=[doc.width])
    company_table.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    intro=('Уважаемые партнеры! Выражаем Вам огромное уважение и имеем честь предложить наше коммерческое предложение по ниже показанным актуальным ценам:' if ru else 'Hurmatli hamkorlar! Sizlarga chuqur hurmatimizni bildiramiz va quyida ko‘rsatilgan amaldagi narxlar bo‘yicha tijorat taklifimizni taqdim etamiz:')
    body=[header,Spacer(1,6),company_table,Spacer(1,6),HRFlowable(width='100%',thickness=2,color=colors.HexColor('#E6332A')),Spacer(1,7),Paragraph('Коммерческое предложение.' if ru else 'Tijorat taklifi.',styles['TitleUnicode']),p(f'#{ref} | '+q['created'][:10]),Paragraph(escape(intro),styles['IntroUnicode']),Spacer(1,2)]
    body += [p('Тел. 1: +99899-053-83-03' if ru else 'Tel. 1: +99899-053-83-03')]
    body += [p('Тел. 2: +99899-674-10-10' if ru else 'Tel. 2: +99899-674-10-10')]
    body += [p('С уважением,' if ru else 'Hurmat bilan,')]
    body += [p('Менеджер' if ru else 'Menejer')]
    body += [Spacer(1,6)]
    headers=['Фото','Товар','Цена за 1 шт. с НДС'] if ru else ['Rasm','Mahsulot','1 dona narxi (QQS bilan)']
    data=[[p(h) for h in headers]]
    from decimal import Decimal, ROUND_HALF_UP
    image_cache={}
    # Reserve room for author and terms on a four/five-product A4 proposal.
    photo_height=min(90, max(36, 260/len(lines)-16)) if lines and len(lines)<=8 else 64
    for i in lines:
        unit_price=(Decimal(i['price'])*(100-i['discount'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
        reference=i.get('photo','')
        if reference not in image_cache:image_cache[reference]=product_image(reference,max_height=photo_height)
        picture=image_cache[reference] or p('Нет фото' if ru else 'Rasm mavjud emas')
        data.append([picture,p(i['name']),p(fmt(unit_price))])
    table=Table(data,colWidths=[120,260,doc.width-380],repeatRows=1,hAlign='LEFT')
    # Available A4 width is about 519 points.
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f2f2f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),0.8,colors.HexColor('#E6332A')),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#dedede')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    from payments import normalize_fulfillment
    payment='Любая форма оплаты' if ru else 'Istalgan to‘lov usuli'
    fulfillment_value=q.get('fulfillment','')
    try:
        fulfillment_key=normalize_fulfillment(fulfillment_value)
    except ValueError:
        fulfillment_key=''
    if fulfillment_key=='pickup':
        fulfillment='самовывоз со склада продавца' if ru else 'sotuvchi omboridan olib ketish'
    elif fulfillment_key=='delivery':
        fulfillment='доставка (условия согласуются отдельно)' if ru else 'yetkazib berish (shartlari alohida kelishiladi)'
    else:
        fulfillment='Доставка по согласованию' if ru else 'Yetkazib berish kelishilgan holda'
    term=lambda text: Paragraph(escape(str(text)),styles['TermsUnicode'])
    terms=[
        term(('1. Способ доставки — ' if ru else '1. Yetkazib berish usuli — ')+fulfillment),
        term('2. Срок действия цены — 3 дня со дня даты исходящего письма.' if ru else '2. Narx amal qilish muddati — xat sanasidan boshlab 3 kun.'),
        term('3. Гарантия на товар — 1 месяц с даты счёта-фактуры при правильной эксплуатации товара.' if ru else '3. Tovar kafolati — to‘g‘ri ishlatilganda hisob-faktura sanasidan boshlab 1 oy.'),
        term('4. Приложение к гарантии вручается при покупке товара и является официальным документом компании.' if ru else '4. Kafolat ilovasi tovar xarid qilinganda beriladi va kompaniyaning rasmiy hujjati hisoblanadi.'),
        term('Надеемся на долгосрочное и доверительное сотрудничество.' if ru else 'Uzoq muddatli va ishonchli hamkorlikka umid qilamiz.'),
        term('Для дополнительной информации обращайтесь по номерам:' if ru else 'Qo‘shimcha ma’lumot uchun quyidagi raqamlarga murojaat qiling:'),
        term('Тел. 1: +99899-053-83-03' if ru else 'Tel. 1: +99899-053-83-03'),
        term('Тел. 2: +99899-674-10-10' if ru else 'Tel. 2: +99899-674-10-10'),
        term('С уважением,' if ru else 'Hurmat bilan,'),
        term('Менеджер' if ru else 'Menejer'),
        term('A A'),
    ]
    fulfillment='Доставка по согласованию' if ru else 'Yetkazib berish kelishilgan holda'
    body += [table,Spacer(1,5),p('Способ оплаты' if ru else 'To‘lov usuli'),term(payment),Spacer(1,3),p('Условия доставки' if ru else 'Yetkazib berish shartlari'),term(fulfillment),Spacer(1,3),*terms]
    def footer(canvas,doc):
        canvas.setFont('Unicode',8);canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(38,23,'TOPSHINALAR | '+('Коммерческое предложение' if ru else 'Tijorat taklifi'))
        canvas.drawRightString(A4[0]-38,23,str(doc.page))
    doc.build(body,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
