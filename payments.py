"""Shared payment choices for Telegram dialogs, reports and quotations."""
import re

PAYMENTS = {
    'naqd': ('NAQD', 'НАЛИЧНЫЕ'),
    'perechisleniya': ('PERECHISLENIYA', 'ПЕРЕЧИСЛЕНИЕ'),
    'karta': ('KARTA ORQALI TO‘LOV', 'ОПЛАТА КАРТОЙ'),
}

def payment_key(value):
    return re.sub(r'[^a-zа-я0-9]', '', str(value).casefold())

ALIASES = {}
for code, names in PAYMENTS.items():
    for name in (code, *names):
        ALIASES[payment_key(name)] = code
for code, names in {
    'naqd': ['naxt', 'naht', 'cash', 'nal', 'нал', 'наличными'],
    'perechisleniya': ['perchesleniya', 'perechesleniya', 'перечислением',
                      'o‘tkazma', "o'tkazma", 'otkazma', 'bank transfer',
                      'bank_transfer', 'bank orqali', 'перевод', 'безнал'],
    'karta': ['card', 'terminal', 'karta orqali tolov', 'karta orqali',
              'карта', 'картой', 'терминал'],
}.items():
    for name in names:
        ALIASES[payment_key(name)] = code

def normalize_payment(value):
    try:
        return ALIASES[payment_key(value)]
    except KeyError:
        raise ValueError('payment') from None

def payment_label(value, lang='uz'):
    try:
        return PAYMENTS[normalize_payment(value)][lang == 'ru']
    except ValueError:
        # Preserve historical/custom text when reading existing records.
        return value

def payment_labels(lang='uz'):
    return [names[lang == 'ru'] for names in PAYMENTS.values()]

FULFILLMENT = {'pickup': ('Olib ketish', 'Самовывоз'),
               'delivery': ('Yetkazib berish', 'Доставка')}

def normalize_fulfillment(value):
    for code,names in FULFILLMENT.items():
        if payment_key(value) in {payment_key(code),*(payment_key(n) for n in names)}:
            return code
    raise ValueError('fulfillment')

def fulfillment_label(value,lang='uz'):
    try:return FULFILLMENT[normalize_fulfillment(value)][lang=='ru']
    except ValueError:return value

def fulfillment_labels(lang='uz'):
    return [names[lang=='ru'] for names in FULFILLMENT.values()]
