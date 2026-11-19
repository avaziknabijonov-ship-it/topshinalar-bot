#!/usr/bin/env python3
"""Wipe all business data (test data) and keep only staff and director access.

Kept:   users, staff_access, staff_invites, positions, meta (system markers)
Wiped:  products, stock, receipts, lots, sales, payments, clients, suppliers, warehouses,
        money records, audit, outbox, ... every other table.

Safe by default: without --confirm it only prints what would be deleted.
With --confirm it first writes a verified backup, then wipes inside one transaction.
Stop the bot and Mini App services before running with --confirm.
"""
import argparse
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

KEEP = {'users', 'staff_access', 'staff_invites', 'positions', 'meta'}
# Cursors that point into wiped tables: removed so they restart from the new (empty) state.
RESET_META = ('topic_notice_cursor',)


def tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
    return [r[0] for r in rows]


def plan(conn):
    return [(t, conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]) for t in tables(conn) if t not in KEEP]


def wipe(db_path, backup_dir):
    from backup import create_backup
    backup = create_backup(db_path, backup_dir, verify=True)
    print('Zaxira nusxa tayyor:', backup)
    with closing(sqlite3.connect(db_path, isolation_level=None)) as conn:
        conn.execute('PRAGMA foreign_keys=OFF')
        conn.execute('BEGIN IMMEDIATE')
        try:
            # Catalog triggers may re-queue rows while others are deleted: repeat until everything is empty.
            for _ in range(5):
                left = [table for table, count in plan(conn) if count]
                if not left:
                    break
                for table in left:
                    conn.execute(f'DELETE FROM "{table}"')
            else:
                raise RuntimeError('Tables did not empty after 5 passes: ' + ', '.join(t for t, c in plan(conn) if c))
            if 'sqlite_sequence' in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name='sqlite_sequence'")]:
                conn.execute('DELETE FROM sqlite_sequence')
            for key in RESET_META:
                conn.execute('DELETE FROM meta WHERE key=?', (key,))
            problems = conn.execute('PRAGMA foreign_key_check').fetchall()
            if problems:
                raise RuntimeError(f'Foreign key check failed: {problems[:3]}')
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
        conn.execute('VACUUM')
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=os.environ.get('DB_PATH', '/var/lib/topshinalar/topshinalar.sqlite3'))
    parser.add_argument('--backup-dir', default='/var/lib/topshinalar/backups')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (default: only show the plan)')
    args = parser.parse_args(argv)
    if not Path(args.db).is_file():
        sys.exit(f'Baza topilmadi: {args.db}')
    with closing(sqlite3.connect(f'file:{args.db}?mode=ro', uri=True)) as conn:
        items = plan(conn)
        kept = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in KEEP if t in tables(conn)}
    print('O‘chiriladi:')
    for table, count in items:
        print(f'  {table}: {count}')
    print('Qoladi:', ', '.join(f'{t}={c}' for t, c in sorted(kept.items())))
    if not args.confirm:
        print('\nBu faqat reja. O‘chirish uchun --confirm qo‘shing.')
        return 0
    wipe(args.db, args.backup_dir)
    print('Tayyor: baza tozalandi, xodimlar saqlandi.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
