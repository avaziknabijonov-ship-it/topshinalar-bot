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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, PageBreak
from core import fmt
from payments import payment_label, fulfillment_label


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
        scale=min(52/image.imageWidth,62/image.imageHeight)
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
    styles.add(ParagraphStyle(name='TotalUnicode',fontName='Unicode',fontSize=13,leading=20,alignment=TA_RIGHT,spaceBefore=12))
    p=lambda text: Paragraph(escape(str(text)).replace('\n','<br/>'),styles['BodyUnicode'])
    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=38,leftMargin=38,topMargin=42,bottomMargin=40,title=f'TOPSHINALAR - KP #{ref}')
    logo=Image(str(Path(__file__).resolve().parent/'assets'/'topshinalar-logo.png'),width=260,height=260*195/800,hAlign='LEFT')
    body=[logo,Spacer(1,14),HRFlowable(width='100%',thickness=2,color=colors.HexColor('#E6332A')),Spacer(1,18),Paragraph('Коммерческое предложение' if ru else 'Tijorat taklifi',styles['TitleUnicode']),p(f'#{ref} | '+q['created'][:10]),Spacer(1,10),Spacer(1,14)]
    headers=['Фото','Товар','Шт.','Цена','Сумма'] if ru else ['Rasm','Mahsulot','Dona','Narx','Jami']
    data=[[p(h) for h in headers]]
    from decimal import Decimal
    image_cache={}
    for i in lines:
        total=int((Decimal(i['price'])*i['qty']*(100-i['discount'])/100).quantize(Decimal('1')))
        reference=i.get('photo','')
        if reference not in image_cache:image_cache[reference]=product_image(reference)
        picture=image_cache[reference] or p('Нет фото' if ru else 'Rasm mavjud emas')
        data.append([picture,p(i['name']),p(i['qty']),p(fmt(Decimal(total)/i['qty'])),p(fmt(total))])
    table=Table(data,colWidths=[68,192,35,102,122.28],repeatRows=1,hAlign='LEFT')
    # Available A4 width is about 519 points.
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f2f2f2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),0.8,colors.HexColor('#E6332A')),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#dedede')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),8)]))
    payment='Любая форма оплаты' if ru else 'Istalgan to‘lov usuli'
    fulfillment='По договорённости' if ru else 'Kelishuv asosida'
    body += [table,Paragraph(('Итого: ' if ru else 'Jami: ')+fmt(q['total']),styles['TotalUnicode']),Spacer(1,20),p('Способ оплаты' if ru else 'To‘lov usuli'),p(payment),Spacer(1,10),p('Условия доставки' if ru else 'Yetkazib berish shartlari'),p(fulfillment)]
    # Keep the supplied certificates unchanged in appearance and append them
    # after all commercial-proposal pages. No external downloads at runtime.
    attachment_root=Path(__file__).resolve().parent/'assets'/'quotation-attachments'
    for name in ('company-registration','vat-registration'):
        image=Image(str(attachment_root/(name+'.png')))
        scale=min(doc.width/image.imageWidth,(doc.height-12)/image.imageHeight)
        image.drawWidth=image.imageWidth*scale
        image.drawHeight=image.imageHeight*scale
        body += [PageBreak(),image]
    def footer(canvas,doc):
        canvas.setFont('Unicode',8);canvas.setFillColor(colors.HexColor('#666666'))
        canvas.drawString(38,23,'TOPSHINALAR | '+('Коммерческое предложение' if ru else 'Tijorat taklifi'))
        canvas.drawRightString(A4[0]-38,23,str(doc.page))
    doc.build(body,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
