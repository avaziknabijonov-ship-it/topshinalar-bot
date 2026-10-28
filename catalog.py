"""Idempotent import of the owner's tyre list, without supplier prices or stock."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'assets' / 'tyres.json'


def local_photo(reference):
    if not isinstance(reference, str) or not reference.startswith('catalog:'):
        return None
    name = reference.removeprefix('catalog:')
    if not re.fullmatch(r'[a-z0-9-]+\.jpg', name):
        raise ValueError('photo')
    path = ROOT / 'assets' / 'catalog' / name
    if not path.is_file():
        raise ValueError('photo')
    return path


def import_catalog(store, manifest=MANIFEST):
    """Insert only missing SKUs. Never reset edits, prices, photos or stock."""
    rows = json.loads(Path(manifest).read_text(encoding='utf-8'))
    seen = set()
    for row in rows:
        sku = row['sku']
        if not re.fullmatch(r'TYRE-[A-F0-9]{16}', sku) or sku in seen:
            raise ValueError('catalog_sku')
        seen.add(sku)
        if row.get('price') is not None or row.get('quantity') is not None:
            raise ValueError('catalog_price_stock')
        if row.get('photo'):
            local_photo(row['photo'])
        if not all(isinstance(row[k], str) and row[k].strip() for k in ('brand','model','size','name')):
            raise ValueError('catalog_text')
    added = 0
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        for row in rows:
            existing_sku = store.db.execute('SELECT id,photo FROM products WHERE catalog_sku=?',(row['sku'],)).fetchone()
            if existing_sku:
                if not existing_sku['photo'] and row.get('photo'):
                    store.db.execute('UPDATE products SET photo=? WHERE id=?',(row['photo'],existing_sku['id']))
                continue
            # Reuse an exact existing card without changing its commercial data.
            existing = store.db.execute('SELECT id FROM products WHERE name=? AND catalog_sku IS NULL',(row['name'],)).fetchall()
            if len(existing) == 1:
                store.db.execute('UPDATE products SET catalog_sku=? WHERE id=?',(row['sku'],existing[0]['id']))
                continue
            store.add('products',name=row['name'],brand=row['brand'],size=row['size'],price=0,
                      price_pending=1,catalog_sku=row['sku'],photo=row.get('photo'))
            added += 1
    return added
