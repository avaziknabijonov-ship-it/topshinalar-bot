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


def product_image(reference):
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
        scale=min(100/image.imageWidth,120/image.imageHeight)
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
    styles.add(ParagraphStyle(name='BodyUnicode',fontName='Unicode',fontSize=9,leading=14,spaceAfter=8))
    styles.add(ParagraphStyle(name='TitleUnicode',fontName='Unicode',fontSize=20,leading=26,textColor=colors.HexColor('#0B0B0A'),spaceAfter=10))
    p=lambda text: Paragraph(escape(str(text)).replace('\n','<br/>'),styles['BodyUnicode'])
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=42,bottomMargin=40,title=f'TOPSHINALAR - KP #{ref}')
    logo=Image(str(Path(__file__).resolve().parent/'assets'/'topshinalar-logo.png'),width=260,height=260*195/800,hAlign='LEFT')
    header=Table([[logo,company_contact_qr()]],colWidths=[doc.width-90,90])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    body=[header,Spacer(1,14),HRFlowable(width='100%',thickness=2,color=colors.HexColor('#E6332A')),Spacer(1,18),Paragraph('Коммерческое предложение' if ru else 'Tijorat taklifi',styles['TitleUnicode']),p(f'#{ref} | '+q['created'][:10]),Spacer(1,10),Spacer(1,14)]
    creator=store.one('users',q['actor'])
    creator_name=q.get('creator_name') or creator['name']
    creator_phone=q.get('creator_phone') or store.contact_phone(q['actor'])
    if creator_phone.startswith('+998') and len(creator_phone)==13:
        creator_phone=creator_phone[:4]+' '+creator_phone[4:6]+' '+creator_phone[6:9]+' '+creator_phone[9:11]+' '+creator_phone[11:]
    body += [p(('Составил: ' if ru else 'Tuzdi: ')+creator_name)]
    body += [p(('Для связи: ' if ru else 'Aloqa uchun: ')+creator_phone)] if creator_phone else [p('Личный номер не указан' if ru else 'Shaxsiy raqam kiritilmagan')]
    body += [Spacer(1,8)]
    headers=['Фото','Товар','Цена за 1 шт.'] if ru else ['Rasm','Mahsulot','1 dona narxi']
    data=[[p(h) for h in headers]]
    from decimal import Decimal, ROUND_HALF_UP
    image_cache={}
    for i in lines:
        unit_price=(Decimal(i['price'])*(100-i['discount'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
        reference=i.get('photo','')
        if reference not in image_cache:image_cache[reference]=product_image(reference)
        picture=image_cache[reference] or p('Нет фото' if ru else 'Rasm mavjud emas')
        data.append([picture,p(i['name']),p(fmt(unit_price))])
    table=Table(data,colWidths=[120,260,doc.width-380],repeatRows=1,hAlign='LEFT')
    # Available A4 width is about 519 points.
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f2f2f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),0.8,colors.HexColor('#E6332A')),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#dedede')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),8)]))
    payment='Любая форма оплаты' if ru else 'Istalgan to‘lov usuli'
    fulfillment='Доставка по согласованию' if ru else 'Yetkazib berish kelishilgan holda'
    body += [table,Spacer(1,20),p('Способ оплаты' if ru else 'To‘lov usuli'),p(payment),Spacer(1,10),p('Условия доставки' if ru else 'Yetkazib berish shartlari'),p(fulfillment)]
    def footer(canvas,doc):
        canvas.setFont('Unicode',8);canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(38,23,'TOPSHINALAR | '+('Коммерческое предложение' if ru else 'Tijorat taklifi'))
        canvas.drawRightString(A4[0]-38,23,str(doc.page))
    doc.build(body,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
