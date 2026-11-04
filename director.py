"""Director views reuse the bot's business model and immutable journals."""
import json
from accounting import atomic,quantity,clean_note,accounting_date
from core import now


@atomic
def transfer(s,uid,d):
    s.director(uid)
    product=quantity(d.get('product'));source=quantity(d.get('source'));target=quantity(d.get('target'));qty=quantity(d.get('qty'));note=clean_note(d.get('reason'),True)
    s.one('products',product);s.one('points',source);s.one('points',target)
    if source==target:raise ValueError('same point')
    if not s.db.execute('UPDATE stock SET qty=qty-? WHERE product=? AND point=? AND qty>=?',(qty,product,source,qty)).rowcount:raise ValueError('stock')
    remaining=qty
    for lot in s.rows('SELECT * FROM inventory_lots WHERE product=? AND point=? AND qty>0 ORDER BY receipt IS NOT NULL,receipt,id',(product,source)):
        take=min(remaining,lot['qty'])
        s.db.execute('UPDATE inventory_lots SET qty=qty-? WHERE id=?',(take,lot['id']))
        s.add('inventory_lots',receipt=lot['receipt'],product=product,point=target,qty=take,created=now())
        remaining-=take
        if not remaining:break
    if remaining:raise ValueError('stock_provenance')
    s.db.execute('INSERT INTO stock VALUES(?,?,?) ON CONFLICT(product,point) DO UPDATE SET qty=qty+excluded.qty',(product,target,qty))
    for point,change in [(source,-qty),(target,qty)]:
        s.add('movements',product=product,point=point,qty=change,kind='transfer',actor=uid,note=note,created=now());s.rearm_stock(product,point)
    s.log(uid,'stock_transfer:'+json.dumps({'product':product,'source':source,'target':target,'qty':qty,'reason':note}),product)
    return product


@atomic
def count_stock(s,uid,d):
    s.director(uid)
    product=quantity(d.get('product'));point=quantity(d.get('point'));actual=quantity(d.get('actual'),zero=True);expected=quantity(d.get('expected'),zero=True);note=clean_note(d.get('reason'),True)
    s.one('products',product);s.one('points',point)
    row=s.db.execute('SELECT qty FROM stock WHERE product=? AND point=?',(product,point)).fetchone()
    current=row['qty'] if row else 0
    if expected!=current:raise ValueError('Stock changed; refresh count')
    delta=actual-current
    if delta:s.move(uid,product,point,abs(delta),'in' if delta>0 else 'writeoff',note)
    elif not row:s.opening_stock(uid,product,point,0,note)
    s.log(uid,'inventory_count:'+json.dumps({'product':product,'point':point,'before':current,'actual':actual,'difference':delta,'reason':note}),product)
    return product


def page(rows,q):
    search=q.get('q','').casefold().strip()[:200]
    if search:rows=[r for r in rows if search in json.dumps(r,ensure_ascii=False).casefold()]
    index=max(0,min(100000,int(q.get('page',0))));size=25
    return {'items':rows[index*size:(index+1)*size],'total':len(rows),'page':index,'page_size':size}


def read(service,uid,kind,q):
    s=service.s;s.director(uid)
    start=accounting_date(q.get('start',now()[:10]));end=accounting_date(q.get('end',now()[:10]))
    if start>end:raise ValueError('date')
    if kind=='overview':
        result=service.dashboard(uid,start,end)
        result['lowstock']=[r for r in result['lowstock'] if s.db.execute('SELECT 1 FROM stock WHERE product=? AND point=?',(r['product'],r['point'])).fetchone()]
        result['supplier_balances']=s.suppliers(uid)['balances'];result['recent']=s.rows('SELECT a.*,u.name actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 15')
        result['profit']=None;result['cash_balance']=None;result['financial_note']='Hisoblash uchun ma’lumot yetarli emas / Недостаточно данных для расчёта'
        return result
    if kind in ('payments','refunds'):
        return page(s.rows(f'SELECT p.*,s.client,c.name client_name,u.name actor_name FROM {kind} p JOIN sales s ON s.id=p.sale JOIN clients c ON c.id=s.client JOIN users u ON u.id=p.actor WHERE substr(p.created,1,10) BETWEEN ? AND ? ORDER BY p.id DESC',(start,end)),q)
    if kind in ('debts','overdue'):
        return page(s.debts(uid,kind=='overdue'),q)
    if kind=='sales':
        rows=s.rows('''SELECT s.*,c.name client_name,u.name manager_name,(s.total-s.paid) debt FROM sales s JOIN clients c ON c.id=s.client JOIN users u ON u.id=s.actor WHERE substr(s.created,1,10) BETWEEN ? AND ? ORDER BY s.id DESC''',(start,end))
        for row in rows:
            row['items']=[{**item,'currency':row['currency']} for item in s.rows('SELECT * FROM sale_items WHERE sale=?',(row['id'],))];row['payments']=s.rows('SELECT * FROM payments WHERE sale=? ORDER BY id',(row['id'],))
        for key,column in [('client','client'),('manager','actor')]:
            if q.get(key):rows=[r for r in rows if str(r[column])==q[key]]
        if q.get('product'):rows=[r for r in rows if any(str(i['product'])==q['product'] for i in r['items'])]
        if q.get('payment_status')=='debt':rows=[r for r in rows if r['status']=='active' and r['debt']>0]
        if q.get('payment_status')=='paid':rows=[r for r in rows if r['status']=='active' and r['debt']==0]
        return page(rows,q)
    if kind=='stock':return page(s.inventory_report(uid)['stock'],q)
    if kind=='lots':return page(s.rows('SELECT l.*,p.name product_name,t.name point_name,r.supplier,r.cost,r.currency FROM inventory_lots l JOIN products p ON p.id=l.product JOIN points t ON t.id=l.point LEFT JOIN receipts r ON r.id=l.receipt ORDER BY l.id DESC'),q)
    if kind=='receipts':return page(s.rows('SELECT r.*,p.name product_name,v.name supplier_name,u.name actor_name FROM receipts r JOIN products p ON p.id=r.product JOIN suppliers v ON v.id=r.supplier JOIN users u ON u.id=r.actor WHERE r.date BETWEEN ? AND ? ORDER BY r.id DESC',(start,end)),q)
    if kind=='quotes':return page(s.rows('SELECT q.*,c.name client_name,u.name actor_name FROM quotes q JOIN clients c ON c.id=q.client JOIN users u ON u.id=q.actor WHERE substr(q.created,1,10) BETWEEN ? AND ? ORDER BY q.id DESC',(start,end)),q)
    if kind=='clients':
        if q.get('id'):
            ref=quantity(q['id']);result=s.client_card(uid,ref)
            result['payments']=s.rows('SELECT p.* FROM payments p JOIN sales s ON s.id=p.sale WHERE s.client=? ORDER BY p.id DESC',(ref,))
            result['debts']=[r for r in s.debts(uid) if r['client']==ref];return result
        return page(s.rows('SELECT c.*,u.name owner_name FROM clients c JOIN users u ON u.id=c.owner ORDER BY c.id DESC'),q)
    if kind=='suppliers':
        if q.get('id'):return s.supplier_ledger(uid,quantity(q['id']))
        result=s.suppliers(uid);paged=page(result['suppliers'],q);result['suppliers']=paged.pop('items');result.update(paged);return result
    if kind=='managers':
        import manager_money
        with manager_money.read_snapshot(s):
            result=s.manager_account(uid)
            result['days']=manager_money.days(s,uid,start,end)
        result['pending_handovers']=[r for r in result['entries'] if r['kind']=='return' and r['receipt_status']=='pending']
        result['entries']=[r for r in result['entries'] if start<=r['date']<=end]
        paged=page(result['entries'],q);result['entries']=paged.pop('items');result.update(paged);return result
    if kind=='staff':
        result=__import__('staff').StaffAccess(s).team(uid)
        paged=page(result['employees'],q);result['employees']=paged.pop('items');result.update(paged)
        result['sales_performance']=s.rows("SELECT actor,currency,COUNT(*) sales,SUM(total) total FROM sales WHERE status='active' AND substr(created,1,10) BETWEEN ? AND ? GROUP BY actor,currency",(start,end))
        return result
    if kind=='audit':return page(s.rows('SELECT a.*,u.name actor_name FROM audit a LEFT JOIN users u ON u.id=a.actor WHERE substr(a.created,1,10) BETWEEN ? AND ? ORDER BY a.id DESC',(start,end)),q)
    if kind=='website':
        rows=s.rows('SELECT p.id,p.name,p.brand,p.size,p.catalog_sku,p.currency,p.price,p.price_pending,w.*,o.version,o.delivered_version,o.attempts,o.last_success,o.last_error FROM products p LEFT JOIN website_products w ON w.product=p.id JOIN catalog_outbox o ON o.product=p.id ORDER BY p.id')
        for r in rows:
            r['points']=json.loads(r.get('points') or '[]');r['photos']=json.loads(r.get('photos') or '[]')
            r['sync_status']='synced' if r['version']==r['delivered_version'] else 'retry_required' if r['attempts']>=10 else 'pending'
            r['gallery']=s.rows('SELECT file_id,position FROM product_photos WHERE product=? ORDER BY position',(r['id'],))
        return page(rows,q)
    if kind=='count-preview':
        product=quantity(q.get('product'));point=quantity(q.get('point'));s.one('products',product);s.one('points',point)
        row=s.db.execute('SELECT qty FROM stock WHERE product=? AND point=?',(product,point)).fetchone()
        return {'qty':row['qty'] if row else 0,'known':bool(row)}
    if kind=='lookups':return {'points':s.rows('SELECT id,name,kind FROM points'),'products':s.rows('SELECT id,name FROM products'),'clients':s.rows('SELECT id,name FROM clients'),'staff':s.rows('SELECT id,name,active,role FROM users'),'suppliers':s.rows('SELECT id,name FROM suppliers')}
    raise ValueError('route')


def handle_http(handler,path,write):
    """Called only for dedicated director/auth routes; auth always precedes data."""
    import director_auth as auth
    from core import Store
    from miniapp import MiniService,AuthError
    from urllib.parse import parse_qsl,urlsplit
    import secrets
    s=None
    try:
        s=Store(handler.server.db_path)
        if write:
            if not handler.server.origin or handler.headers.get('Origin')!=handler.server.origin:raise PermissionError('origin')
            length=int(handler.headers.get('Content-Length','0'))
            if not 0<length<=64000:raise ValueError('payload')
            body=json.loads(handler.rfile.read(length))
            if not isinstance(body,dict):raise ValueError('payload')
        else:body={}
        values=auth.cookies(handler.headers.get('Cookie'))
        if path=='/director-auth/start' and write:
            browser=secrets.token_urlsafe(32)
            code=auth.start(s,browser,handler.client_address[0])
            handler.extra_cookies=[auth.cookie(auth.PRECOOKIE,browser,180)]
            handler.send(200,{'command':'/cabinet_login '+code,'expires_in':180});return
        if path=='/director-auth/poll' and write:
            browser=values.get(auth.PRECOOKIE,'')
            if not browser:raise PermissionError()
            auth.limit(s,'poll:'+auth.digest(browser),100)
            token=auth.poll(s,browser)
            if token:handler.extra_cookies=[auth.cookie(auth.COOKIE,token,auth.TTL),auth.cookie(auth.PRECOOKIE,'',0)]
            handler.send(200,{'approved':bool(token)});return
        if path=='/director-auth/telegram' and write:
            auth.limit(s,'telegram:'+handler.client_address[0],20)
            token=auth.telegram(s,body.get('initData',''),handler.server.bot_token)
            handler.extra_cookies=[auth.cookie(auth.COOKIE,token,auth.TTL)]
            handler.send(200,{'ok':True});return
        telegram_raw=handler.headers.get('X-Telegram-Init-Data','')
        if telegram_raw:
            user=auth.telegram_identity(s,telegram_raw,handler.server.bot_token,handler.headers.get('X-Director-Nonce',''));token=None
        else:user,token=auth.identity(s,handler.headers.get('Cookie'),handler.headers.get('X-CSRF-Token'),write)
        uid=user['id']
        if path=='/director-auth/me' and not write:
            handler.send(200,{'name':user['name'],'lang':user['lang'],'csrf':auth.csrf(token) if token else 'telegram-init-data'});return
        if path=='/director-auth/logout' and write:
            with s.db:
                if token:s.db.execute('DELETE FROM director_sessions WHERE token_hash=?',(auth.digest(token),))
                if telegram_raw:s.db.execute('UPDATE director_telegram_sessions SET revoked=1 WHERE hash=?',(auth.digest(telegram_raw),))
                # Revoke any accompanying browser cookie too.
                cookie_token=values.get(auth.COOKIE)
                if cookie_token:s.db.execute('DELETE FROM director_sessions WHERE token_hash=?',(auth.digest(cookie_token),))
                s.log(uid,'director_logout',None)
            handler.extra_cookies=[auth.cookie(auth.COOKIE,'',0)];handler.send(200,{'ok':True});return
        if not path.startswith('/director-api/'):raise ValueError('route')
        kind=path.rsplit('/',1)[-1];service=MiniService(s,handler.server.bot_token)
        if write:
            if kind!='action':raise ValueError('route')
            result=service.write(uid,handler.headers.get('Idempotency-Key',''),body.get('cmd'),body.get('data'))
        else:
            q=dict(parse_qsl(urlsplit(handler.path).query))
            if kind=='photo':
                handler.send(200,service.photo(uid,quantity(q.get('product')),quantity(q.get('index',0),zero=True)),'image/jpeg');return
            if kind=='quote':
                from quotation import quotation_pdf
                ref=quantity(q.get('id'));s.one('quotes',ref)
                handler.send(200,quotation_pdf(s,uid,ref),'application/pdf',f'TOPSHINALAR-KP-{ref}.pdf');return
            if kind=='report':
                from reports import workbook
                start=q.get('start',now()[:10]);end=q.get('end',now()[:10])
                data=s.report(uid,start,end);data.update(s.inventory_report(uid))
                sale_ids={row['id'] for row in data['sales']}
                data['debts']=[row for row in s.debts(uid) if row['id'] in sale_ids]
                if 'manager_entries' not in data:
                    manager=s.manager_account(uid);supplier=s.supplier_report(uid,start,end)
                    data['manager_days']=__import__('manager_money').days(s,uid,start,end)
                    data.update(manager_entries=[r for r in manager['entries'] if start<=r['date']<=end],manager_balances=manager['balances'],supplier_stock=supplier['stock'],supplier_sold=supplier['sold'],supplier_entries=supplier['entries'],supplier_balances=supplier['balances'],supplier_lots=supplier['lots'])
                handler.send(200,workbook(service.b.enrich(data),user['lang']),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','TOPSHINALAR-director.xlsx');return
            result=read(service,uid,kind,q)
        handler.send(200,result)
    except (PermissionError,AuthError):handler.send(403,{'error':'Kirish rad etildi / Доступ запрещён'})
    except (ValueError,TypeError,KeyError,__import__('sqlite3').IntegrityError) as exc:
        from i18n import ERRORS
        messages=ERRORS.get(str(exc),('Ma’lumotni tekshiring','Проверьте данные'))
        handler.send(400,{'error':messages[0]+' / '+messages[1]})
    except Exception:
        __import__('logging').exception('Director request failed: %s',path)
        handler.send(503,{'error':'Vaqtincha mavjud emas / Временно недоступно'})
    finally:
        if s:s.db.close()
