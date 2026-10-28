"""Interactive local startup. Secrets stay on the user's computer."""
import getpass
import os
from pathlib import Path
import re
import secrets
import sys
import time
import tempfile
import webbrowser
from bot import API, Bot, main
from core import Store
from storage import data_home, resolve_database, active_ids, SingleInstance


def load_config(path):
    config={}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if line and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1)
                config[key.strip()]=value.strip()
    return config


def save_config(path,config):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.settings-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:
            out.write(''.join(k+'='+v+'\n' for k,v in config.items()))
        Path(temp).chmod(0o600)
        os.replace(temp,path)
    finally:Path(temp).unlink(missing_ok=True)


def persist_config(path,config):
    save_config(path,config)
    bot_id=config['BOT_TOKEN'].split(':',1)[0]
    save_config(data_home()/bot_id/'settings.env',config)


def saved_config():
    files=sorted(data_home().glob('*/settings.env'))
    if not files:return {}
    if len(files)==1:return load_config(files[0])
    print('Saqlangan botlar:')
    for i,file in enumerate(files,1):print(f'{i}. Bot ID: {file.parent.name}')
    while True:
        answer=input('Bot raqami (q — to‘xtatish): ').strip()
        if answer.lower()=='q':raise SystemExit('To‘xtatildi.')
        if answer.isdigit() and 1<=int(answer)<=len(files):return load_config(files[int(answer)-1])


def start():
    root=Path(__file__).resolve().parent
    os.chdir(root)
    path=root/'.env'
    config=load_config(path)
    if not config.get('BOT_TOKEN'):
        restored=saved_config()
        if restored:config=restored
    token=config.get('BOT_TOKEN','')
    if not token:
        print('TOPSHINALAR: bot tokenini kiriting. Yozayotganingiz ekranda ko‘rinmaydi.')
        token=getpass.getpass('BotFather token: ').strip()
    if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token):
        raise SystemExit('Token formati noto‘g‘ri. Qayta oching.')
    api=API(token)
    try:
        me=api.call('getMe',{})
        webhook=api.call('getWebhookInfo',{})
    except Exception:
        raise SystemExit('Telegram bilan bog‘lanib bo‘lmadi. Internet va tokenni tekshiring. Token oshkor qilinmadi.')
    if webhook.get('url'):
        raise SystemExit('Bu token webhook bilan band. Boshqa nusxani avval to‘xtating; uning sozlamalari o‘zgartirilmadi.')
    config['BOT_TOKEN']=token
    config.setdefault('EMPLOYEE_IDS','')
    print('Bot: @'+me['username'],flush=True)
    try:
        with SingleInstance(data_home()/str(me['id'])/'startup.lock'):
            db,migrated=resolve_database(root,me['id'],config.get('DB_PATH',''),recover='--recover' in sys.argv)
            config['DB_PATH']=str(db.resolve())
            if db.exists() and (migrated or not config.get('DIRECTOR_IDS')):
                users=active_ids(db)
                config['DIRECTOR_IDS']=users['director']
                config['EMPLOYEE_IDS']=users['employee']
            print('Baza: '+str(db),flush=True)
            run_configured(path,config,api,me)
    except ValueError as error:
        raise SystemExit(str(error)) from None


def run_configured(path,config,api,me):
    # Windows ships Arial with Cyrillic and Uzbek glyphs.
    font=config.get('PDF_FONT','')
    if not font or not Path(font).exists():
        candidates=[Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'arial.ttf',Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
        font=next((str(p) for p in candidates if p.exists()),'')
        if not font:raise SystemExit('Unicode TTF shrift topilmadi. .env faylida PDF_FONT ni to‘g‘ri belgilang.')
        config['PDF_FONT']=font
    print('Bot: @'+me['username'],flush=True)
    if not config.get('DIRECTOR_IDS'):
        challenge=secrets.token_urlsafe(18)
        url='https://t.me/'+me['username']+'?start='+challenge
        print('\nDirektor sifatida kirish uchun shu shaxsiy havolani oching va START bosing:\n'+url+'\nHavolani boshqa odamga yubormang. Ctrl+C — to‘xtatish.\n',flush=True)
        try:webbrowser.open(url)
        except Exception:pass
        offset=0
        while not config.get('DIRECTOR_IDS'):
            try:
                updates=api.call('getUpdates',{'offset':offset,'timeout':20,'allowed_updates':['message']})
                for update in updates:
                    offset=update['update_id']+1
                    m=update.get('message',{})
                    if m.get('chat',{}).get('type')!='private' or m.get('from',{}).get('is_bot'):continue
                    if m.get('text','').strip()!='/start '+challenge:continue
                    config['DIRECTOR_IDS']=str(m['from']['id'])
                    persist_config(path,config)
                    Path(config['DB_PATH']).parent.mkdir(parents=True,exist_ok=True)
                    s=Store(config['DB_PATH']);s.configure([m['from']['id']],[])
                    Bot(s).process(update)
                    with s.db:
                        s.db.execute("INSERT INTO meta VALUES('offset',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(offset),))
                    s.db.close()
                    print('Direktor qo‘shildi. Bot ishga tushmoqda.',flush=True)
                    break
            except KeyboardInterrupt:raise SystemExit('To‘xtatildi.')
            except Exception:
                print('Ulanish kutilmoqda. Internetni tekshiring; boshqa polling nusxasi ishlamasin.',flush=True)
                time.sleep(5)
    persist_config(path,config)
    for key,value in config.items():os.environ[key]=value
    print('Bot ishlayapti. Bu oynani ochiq qoldiring. Ctrl+C bilan to‘xtatasiz.',flush=True)
    main()

if __name__=='__main__':
    try:start()
    except KeyboardInterrupt:print('\nTo‘xtatildi.')
