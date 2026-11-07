"""One-way public catalog replica. SQLite triggers invalidate snapshots atomically.
No network access occurs inside a business transaction. All new products are hidden.
"""
import argparse
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import time
import urllib.request
from urllib.parse import urlsplit
from accounting import transaction


def migrate(store):
    with store.db, transaction(store):
        for sql in (
            '''CREATE TABLE IF NOT EXISTS website_products(product INTEGER PRIMARY KEY REFERENCES products(id), published INTEGER NOT NULL DEFAULT 0 CHECK(published IN (0,1)), price_cents INTEGER CHECK(price_cents>=0 AND price_cents<=100000000000000), category TEXT NOT NULL DEFAULT 'TBR' CHECK(category IN ('TBR','OTR','AGRO','PCR')), model TEXT NOT NULL DEFAULT '', description_uz TEXT NOT NULL DEFAULT '', description_ru TEXT NOT NULL DEFAULT '', stock_mode TEXT NOT NULL DEFAULT 'availability' CHECK(stock_mode IN ('exact','availability')), points TEXT NOT NULL DEFAULT '[]', photos TEXT NOT NULL DEFAULT '[]')''',
            '''CREATE TABLE IF NOT EXISTS catalog_outbox(product INTEGER PRIMARY KEY REFERENCES products(id), version INTEGER NOT NULL DEFAULT 1, delivered_version INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, next_attempt INTEGER NOT NULL DEFAULT 0, last_success TEXT, last_error TEXT NOT NULL DEFAULT '')''',
            '''CREATE TABLE IF NOT EXISTS catalog_images(ref_hash TEXT PRIMARY KEY, public_path TEXT NOT NULL)''',
        ):store.db.execute(sql)
        if 'price_mode' not in {r[1] for r in store.db.execute('PRAGMA table_info(website_products)')}:
            store.db.execute("ALTER TABLE website_products ADD COLUMN price_mode TEXT NOT NULL DEFAULT 'website' CHECK(price_mode IN ('website','bot'))")
        # Trigger writes participate in the caller's transaction, including legacy imports.
        for table, column in [('products','id'),('stock','product'),('product_photos','product'),('website_products','product')]:
            for event in ('INSERT','UPDATE','DELETE'):
                if table=='products' and event=='DELETE':continue  # FK prevents deleting business history.
                ref=('OLD' if event=='DELETE' else 'NEW')+'.'+column
                store.db.execute(f'''CREATE TRIGGER IF NOT EXISTS catalog_{table}_{event.lower()} AFTER {event} ON {table} BEGIN
                    INSERT INTO catalog_outbox(product) VALUES({ref}) ON CONFLICT(product) DO UPDATE SET version=version+1,attempts=0,next_attempt=0;
                    END''')
        if not store.db.execute("SELECT 1 FROM meta WHERE key='catalog_outbox_seed_v1'").fetchone():
            store.db.execute('INSERT OR IGNORE INTO catalog_outbox(product) SELECT id FROM products')
            store.db.execute("INSERT INTO meta(key,value) VALUES('catalog_outbox_seed_v1','1')")


def save_settings(s,uid,d):
    from accounting import clean_note, quantity
    from core import money
    s.director(uid)
    product=quantity(d.get('product'));s.one('products',product)
    if type(d.get('published')) is not bool:raise ValueError('published')
    points=d.get('points');photos=d.get('photos')
    if not isinstance(points,list) or len(points)>200 or any(type(x) is not int for x in points) or len(set(points))!=len(points):raise ValueError('points')
    for p in points:s.one('points',p)
    valid={r['file_id'] for r in s.rows('SELECT file_id FROM product_photos WHERE product=?',(product,))}
    if not isinstance(photos,list) or len(photos)>20 or any(not isinstance(x,str) or x not in valid for x in photos) or len(set(photos))!=len(photos):raise ValueError('photo')
    category=d.get('category');mode=d.get('stock_mode')
    if category not in ('TBR','OTR','AGRO','PCR') or mode not in ('exact','availability'):raise ValueError('category')
    price_mode=d.get('price_mode','website')
    if price_mode not in ('website','bot'):raise ValueError('price mode')
    price=None if d.get('price') in ('',None) else money(d['price'])
    s.db.execute('''INSERT INTO website_products(product,published,price_cents,category,model,description_uz,description_ru,stock_mode,points,photos) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(product) DO UPDATE SET published=excluded.published,price_cents=excluded.price_cents,category=excluded.category,model=excluded.model,description_uz=excluded.description_uz,description_ru=excluded.description_ru,stock_mode=excluded.stock_mode,points=excluded.points,photos=excluded.photos''',(product,int(d['published']),price,category,clean_note(d.get('model',''),False,160),clean_note(d.get('description_uz',''),False,3000),clean_note(d.get('description_ru',''),False,3000),mode,json.dumps(points),json.dumps(photos)))
    s.db.execute('UPDATE website_products SET price_mode=? WHERE product=?',(price_mode,product))
    s.log(uid,'website_settings',product)
    return product


def snapshot(s,product):
    p=s.one('products',product)
    rows=s.rows('SELECT * FROM website_products WHERE product=?',(product,))
    w=rows[0] if rows else {}
    points=json.loads(w.get('points','[]'));approved=json.loads(w.get('photos','[]'))
    stock={r['point']:r['qty'] for r in s.rows('SELECT point,qty FROM stock WHERE product=?',(product,))}
    qty=sum(stock[x] for x in points) if points and all(x in stock for x in points) else None
    existing={r['file_id'] for r in s.rows('SELECT file_id FROM product_photos WHERE product=?',(product,))}
    price=p['price'] if w.get('price_mode')=='bot' and p['currency']=='USD' and not p['price_pending'] else None if w.get('price_mode')=='bot' else w.get('price_cents')
    return dict(source_product_id=str(product),catalog_sku=p['catalog_sku'],name=p['name'],brand=p['brand'],model=w.get('model',''),size=p['size'],category=w.get('category','TBR'),description=w.get('description_uz',''),descriptionRu=w.get('description_ru',''),currency='USD',price_unit='cent',price_cents=price,stock=qty if w.get('stock_mode')=='exact' else None,available=None if qty is None else qty>0,published=bool(w.get('published') and p['active']),images=[],_photos=[x for x in approved if x in existing])


def signed_request(url,secret,payload):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('HTTPS sync endpoint required')
    body=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    stamp=str(int(time.time()));nonce=secrets.token_hex(16)
    signature=hmac.new(secret.encode(),stamp.encode()+b'\n'+nonce.encode()+b'\n'+body,hashlib.sha256).hexdigest()
    request=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','X-Sync-Time':stamp,'X-Sync-Nonce':nonce,'X-Sync-Signature':signature})
    # Never follow a redirect carrying authentication to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as response:
        return json.loads(response.read(1024*1024))


def image_payload(data):
    from PIL import Image, UnidentifiedImageError
    import base64
    if not data or len(data)>4*1024*1024:raise ValueError('image size')
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ('JPEG','PNG','WEBP') or im.width*im.height>16000000:raise ValueError('image format')
            im.verify()
        # Decode and re-encode to remove metadata and ensure real image content.
        with Image.open(io.BytesIO(data)) as im:
            im.load();out=io.BytesIO();im.convert('RGB').save(out,format='JPEG',quality=88)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('image content') from None
    result=out.getvalue()
    if len(result)>4*1024*1024:raise ValueError('image size')
    return {'type':'image','sha256':hashlib.sha256(result).hexdigest(),'data':base64.b64encode(result).decode()}


def run_once(s,send,photo):
    from core import now
    row=s.db.execute('SELECT * FROM catalog_outbox WHERE version>delivered_version AND attempts<10 AND next_attempt<=? ORDER BY next_attempt,product LIMIT 1',(int(time.time()),)).fetchone()
    if not row:return False
    product,version=row['product'],row['version']
    try:
        with s.db, transaction(s):
            # Read version and snapshot under the same lock; release before HTTPS.
            version=s.db.execute('SELECT version FROM catalog_outbox WHERE product=?',(product,)).fetchone()[0]
            payload=snapshot(s,product);payload['source_version']=version
        for index,ref in enumerate(payload.pop('_photos')):
            key=hashlib.sha256(ref.encode()).hexdigest()
            cached=s.db.execute('SELECT public_path FROM catalog_images WHERE ref_hash=?',(key,)).fetchone()
            if cached:path=cached[0]
            else:
                # Photo resolver only accepts existing gallery references, never URLs.
                path=send(image_payload(photo(product,ref)))['path']
                if not isinstance(path,str) or not __import__('re').fullmatch(r'/media/[a-f0-9]{64}\.jpg',path):raise ValueError('image response')
                with s.db:s.db.execute('INSERT OR REPLACE INTO catalog_images VALUES(?,?)',(key,path))
            payload['images'].append(path)
        send({'type':'product',**payload})
        with s.db:s.db.execute("UPDATE catalog_outbox SET delivered_version=MAX(delivered_version,?),last_success=?,last_error='',attempts=CASE WHEN version=? THEN 0 ELSE attempts END,next_attempt=0 WHERE product=?",(version,now(),version,product))
    except Exception:
        # Do not log URLs, tokens, Telegram file identifiers or exception bodies.
        with s.db:s.db.execute("UPDATE catalog_outbox SET attempts=attempts+1,next_attempt=?,last_error='Sync failed; check receiver availability and configuration' WHERE product=? AND version=?",(int(time.time())+min(3600,5*2**min(row['attempts'],9)),product,version))
    return True


def inventory(conn):
    conn.row_factory=sqlite3.Row
    products=[dict(r) for r in conn.execute('SELECT id,name,catalog_sku,currency,price,price_pending,active FROM products')]
    website=[]
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='website_products'").fetchone():
        class ReadOnlyStore:
            db=conn
            def one(self,table,key):return dict(conn.execute('SELECT * FROM '+table+' WHERE id=?',(key,)).fetchone())
            def rows(self,sql,params=()):return [dict(r) for r in conn.execute(sql,params)]
        reader=ReadOnlyStore()
        for product in products:
            p=snapshot(reader,product['id']);p.pop('_photos');website.append(p)
    return {'website_snapshots':website,'products':products,'legacy_price_review':[p for p in products if p['currency']!='USD'],'stock':[dict(r) for r in conn.execute('SELECT product,point,qty FROM stock')], 'mapping_policy':'source_product_id only; no name/size matching'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--db',required=True);parser.add_argument('command',choices=['dry-run','once','requeue']);args=parser.parse_args()
    if args.command=='dry-run':
        from pathlib import Path
        conn=sqlite3.connect(Path(args.db).resolve().as_uri()+'?mode=ro',uri=True)
        data=inventory(conn);conn.close()
        if os.environ.get('CATALOG_SYNC_URL') and os.environ.get('CATALOG_SYNC_SECRET'):
            data['website']=signed_request(os.environ['CATALOG_SYNC_URL'],os.environ['CATALOG_SYNC_SECRET'],{'type':'inventory'})
            source={str(p['id']) for p in data['products']}
            remote=data['website']['products']
            data['unlinked_website']=[x for x in remote if x.get('source_product_id') not in source]
            data['duplicates']=[{'source_product_id':key,'count':sum(x.get('source_product_id')==key for x in remote)} for key in source if sum(x.get('source_product_id')==key for x in remote)>1]
            data['differences']=[]
            for local in data['website_snapshots']:
                matched=[x for x in remote if x.get('source_product_id')==local['source_product_id']]
                if len(matched)!=1:
                    data['differences'].append({'source_product_id':local['source_product_id'],'state':'missing' if not matched else 'ambiguous'});continue
                changes={k:{'bot':local[k],'website':matched[0].get(k)} for k in ('name','size','price_cents','stock','available','published') if local[k]!=matched[0].get(k)}
                if changes:data['differences'].append({'source_product_id':local['source_product_id'],'fields':changes})
        print(json.dumps(data,ensure_ascii=False,indent=2));return
    from core import Store
    s=Store(args.db)
    if args.command=='requeue':
        with s.db:s.db.execute('UPDATE catalog_outbox SET version=version+1,attempts=0,next_attempt=0')
    else:
        from miniapp import MiniService
        service=MiniService(s,os.environ['BOT_TOKEN'])
        def photo(product,ref):
            refs=s.rows('SELECT file_id FROM product_photos WHERE product=? ORDER BY position',(product,))
            index=next(i for i,r in enumerate(refs) if r['file_id']==ref)
            directors=s.rows("SELECT id FROM users WHERE active=1 AND role='director' ORDER BY id LIMIT 1")
            if not directors:raise PermissionError()
            return service.photo(directors[0]['id'],product,index)
        send=lambda p:signed_request(os.environ['CATALOG_SYNC_URL'],os.environ['CATALOG_SYNC_SECRET'],p)
        for _ in range(100):
            if not run_once(s,send,photo):break
    s.db.close()

if __name__=='__main__':main()
