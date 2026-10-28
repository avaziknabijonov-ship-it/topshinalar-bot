"""Create a verified SQLite snapshot without stopping the running bot."""
import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from storage import snapshot


def verify_restore(backup):
    """Restore into an isolated database and compare every domain table."""
    from storage import readonly
    backup=Path(backup).resolve()
    with tempfile.TemporaryDirectory(prefix='restore-check-',dir=backup.parent) as directory:
        restored=Path(directory)/'restored.sqlite3'
        snapshot(backup,restored)
        with closing(readonly(backup)) as original,closing(readonly(restored)) as restored_db:
            if restored_db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or restored_db.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Restore integrity check failed')
            tables=[r[0] for r in original.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            result={}
            for table in tables:
                quoted='"'+table.replace('"','""')+'"'
                source=original.execute(f'SELECT * FROM {quoted} ORDER BY rowid')
                target=restored_db.execute(f'SELECT * FROM {quoted} ORDER BY rowid')
                count=0
                while True:
                    a=source.fetchmany(500);b=target.fetchmany(500)
                    if a!=b:raise ValueError('Restore contents differ')
                    if not a:break
                    count+=len(a)
                result[table]=count
            return result


def create_backup(source, directory):
    source=Path(source).resolve()
    directory=Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    name='topshinalar-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex[:8]+'.sqlite3'
    destination=directory/name
    temporary=directory/('.'+name+'.tmp')
    # Create privately before SQLite opens the file, including under a loose umask.
    fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(fd)
    try:
        snapshot(source,temporary)
        # Make the export self-contained even when the live database uses WAL.
        with closing(sqlite3.connect(temporary)) as conn:
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            conn.execute('PRAGMA journal_mode=DELETE')
        os.replace(temporary,destination)
    finally:
        temporary.unlink(missing_ok=True)
        for suffix in ('-wal','-shm'):
            Path(str(temporary)+suffix).unlink(missing_ok=True)
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=os.environ.get('DB_PATH','data/topshinalar.sqlite3'))
    parser.add_argument('--directory',default=None)
    parser.add_argument('--verify-restore',action='store_true',help='Restore into an isolated temporary database and compare all tables')
    args=parser.parse_args()
    directory=args.directory or str(Path(args.source).resolve().parent/'backups')
    try:
        result=create_backup(args.source,directory)
        if args.verify_restore:verify_restore(result)
    except (OSError,ValueError,sqlite3.Error):
        parser.exit(1,'Backup failed; source and earlier backups were not replaced.\n')
    print(result)


if __name__=='__main__':main()
