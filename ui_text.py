"""One presentation catalogue for the web workspaces and Excel exports.

Only application-owned labels/codes are translated. Names, descriptions and notes
remain exactly as recorded. This module has no business database access.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CATALOG=json.loads((ROOT/'locales'/'uz-ru.json').read_text())
FIELDS=CATALOG['fields']
BOOLEANS={'active','published','has_debt','overdue','price_pending','stock_pending','notified','payment_history_complete'}


def language(header=None,fallback='uz'):
    return header if header in ('uz','ru') else ('ru' if fallback=='ru' else 'uz')


def text(key,lang='uz'):
    return CATALOG['ui'].get(key,CATALOG['ui']['extra_field'])[lang=='ru']


def value(key,item,lang='uz'):
    index=lang=='ru'
    if item is None or item=='':return item
    if key in {'payment','method'}:
        if item in CATALOG['values'][key]:return CATALOG['values'][key][item][index]
        from payments import normalize_payment
        try:item=normalize_payment(item)
        except ValueError:return item  # Preserve historical/custom method names.
    if key in BOOLEANS:return text('yes' if item else 'no',lang)
    if key=='action':return CATALOG['actions'].get(str(item).split(':',1)[0],CATALOG['ui']['other_action'])[index]
    choices=CATALOG['values'].get(key)
    if choices and isinstance(item,str):return choices.get(item,CATALOG['ui']['unknown'])[index]
    if key=='last_error' and item:return text('not_available',lang)
    return item


def browser_script():
    """Static trusted catalogue + browser helpers, served as one same-origin asset."""
    data=json.dumps(CATALOG,ensure_ascii=True,separators=(',',':'))
    return 'window.WorkspaceTextData='+data+';\n'+(ROOT/'web'/'ui-text.js').read_text()
