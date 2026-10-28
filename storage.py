"""Stable local data and explicit, backed-up migration from older Windows folders."""
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime
from uuid import uuid4

DB_NAME='topshinalar.sqlite3'
TABLES=('points','products','clients','sales','quotes','movements')

def data_home():
    base=os.environ.get('LOCALAPPDATA') or os.environ.get('XDG_DATA_HOME')
    return (Path(base) if base else Path.home()/'.local'/'share')/'TOPSHINALAR'/'staff-bot'

def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=5)

def inspect_db(path):
    try:
        with closing(readonly(path)) as conn:
            if conn.execute('PRAGMA quick_check').fetchone()[0]!='ok':return None
            tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'users','points','products','stock','sales'}.issubset(tables):return None
            counts={t:conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in TABLES if t in tables}
            counts['stock']=conn.execute('SELECT COALESCE(SUM(qty),0) FROM stock').fetchone()[0]
            return counts
    except (OSError,sqlite3.Error):return None

def active_ids(path):
    with closing(readonly(path)) as conn:
        rows=conn.execute('SELECT id,role FROM users WHERE active=1 ORDER BY id').fetchall()
    return {role:','.join(str(uid) for uid,r in rows if r==role) for role in ('director','employee')}

def candidate_roots(root):
    home=Path.home()
    roots=[root,root.parent]
    # Older copies may have been launched straight from a ZIP/WinRAR window.
    temp=os.environ.get('TEMP') or os.environ.get('TMP')
    if temp:roots.append(Path(temp))
    return roots+[home/'Downloads',home/'Desktop',home/'OneDrive'/'Desktop']

def discover_databases(root,bot_id,roots=None):
    result=set();visited=set();scanned=0
    for base in roots if roots is not None else candidate_roots(root):
        base=Path(base)
        if not base.is_dir():continue
        for directory,dirs,files in os.walk(base,followlinks=False):
            current=Path(directory)
            if current in visited:dirs[:]=[];continue
            visited.add(current);scanned+=1
            if scanned>5000:return sorted(result,key=str)
            depth=len(current.relative_to(base).parts)
            dirs[:]=[d for d in dirs if not d.startswith('.') and d not in {'node_modules','__pycache__','backups'} and not (current/d).is_symlink()] if depth<4 else []
            if DB_NAME not in files:continue
            path=current/DB_NAME
            # Ignore a known deployment belonging to another bot.
            config=path.parent.parent/'.env'
            if config.is_file():
                try:
                    tokens=[line.split('=',1)[1].strip() for line in config.read_text(encoding='utf-8').splitlines() if line.startswith('BOT_TOKEN=')]
                    if tokens and tokens[0] and tokens[0].split(':',1)[0]!=str(bot_id):continue
                except (OSError,UnicodeError):continue
            if inspect_db(path) is not None:result.add(path.resolve())
    return sorted(result,key=str)

def snapshot(source,destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    src=readonly(source)
    try:
        dest=sqlite3.connect(destination)
        try:src.backup(dest)
        finally:dest.close()
    finally:src.close()
    if inspect_db(destination) is None:
        destination.unlink(missing_ok=True)
        raise ValueError('Database copy could not be verified')

def migrate_database(source,target):
    source=Path(source).resolve();target=Path(target).resolve()
    if source==target:return
    if inspect_db(source) is None:raise ValueError('Source database is not valid')
    target.parent.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8]
    backups=target.parent/'backups'
    # Keep an immutable snapshot of the chosen source and of an existing target.
    snapshot(source,backups/f'import-{stamp}.sqlite3')
    if target.exists():
        snapshot(target,backups/f'before-restore-{stamp}.sqlite3')
        # Read-only inspection can leave empty WAL sidecars. A writable connection
        # safely checkpoints them; files held by another process remain detectable.
        conn=sqlite3.connect(target,timeout=1)
        try:
            if conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
                raise ValueError('Stop all bot windows before restoring the database')
        finally:conn.close()
    fd,temp=tempfile.mkstemp(prefix='.migration-',suffix='.sqlite3',dir=target.parent)
    os.close(fd);temp=Path(temp)
    try:
        snapshot(source,temp)
        # The launcher holds SingleInstance; old bot windows must be stopped before restore.
        for suffix in ('-wal','-shm'):
            if Path(str(target)+suffix).exists():
                raise ValueError('Stop all bot windows before restoring the database')
        os.replace(temp,target)
    finally:temp.unlink(missing_ok=True)

def resolve_database(root,bot_id,configured='',ask=input,emit=print,base=None,recover=False,roots=None):
    target=(Path(base) if base else data_home())/str(bot_id)/DB_NAME
    if target.exists() and not recover:
        if inspect_db(target) is None:raise ValueError('Existing database is damaged; it was not replaced')
        return target,False
    candidates=discover_databases(root,bot_id,roots)
    if configured:
        preferred=Path(configured)
        if not preferred.is_absolute():preferred=Path(root)/preferred
        if preferred.exists() and inspect_db(preferred) is not None:candidates.append(preferred.resolve())
    candidates=list(dict.fromkeys(p for p in candidates if p!=target.resolve()))
    if not candidates:
        if not recover:
            target.parent.mkdir(parents=True,exist_ok=True)
            return target,False
        emit('Eski baza avtomatik topilmadi. Faylga to‘liq yo‘lni kiriting yoki q bilan to‘xtating.')
    if candidates:emit('\nEski bot bazalari topildi. Asosiy ombor va qoldig‘i bor bazani tanlang:')
    for index,path in enumerate(candidates,1):
        c=inspect_db(path)
        emit(f"{index}. {path}\n   Ombor: {c['points']} | Mahsulot: {c['products']} | Qoldiq: {c['stock']} dona | Mijoz: {c['clients']} | Sotuv: {c['sales']}")
    while True:
        answer=ask('Baza raqami yoki sqlite3 fayliga to‘liq yo‘l (q — to‘xtatish): ').strip()
        if answer.lower()=='q':raise SystemExit('To‘xtatildi. Bazalar o‘zgartirilmadi.')
        try:index=int(answer)-1
        except ValueError:
            manual=Path(answer.strip('"')).expanduser()
            if manual.is_file() and inspect_db(manual) is not None and manual.resolve()!=target.resolve():
                candidates.append(manual.resolve());index=len(candidates)-1
            else:
                emit('Baza fayli topilmadi yoki yaroqsiz. Boshqa yo‘lni kiriting.')
                continue
        if 0<=index<len(candidates):break
    migrate_database(candidates[index],target)
    emit('Baza zaxira nusxasi bilan tiklandi. Asl eski baza o‘zgartirilmadi.')
    return target,True

class SingleInstance:
    def __init__(self,path):self.path=Path(path);self.file=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        self.file.seek(0,2)
        if self.file.tell()==0:self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();self.file=None
            raise SystemExit('Bot allaqachon ochiq. Avvalgi qora oynani yoping.') from None
        return self
    def __exit__(self,*args):
        if self.file:
            self.file.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(),fcntl.LOCK_UN)
            self.file.close()
