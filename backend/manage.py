"""Database maintenance. Backup is safe while the app is running."""
import argparse
import os
import sqlite3
import datetime as dt
from contextlib import closing
from pathlib import Path
from .store import Store

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['backup', 'check', 'restore'])
    parser.add_argument('destination', nargs='?')
    args = parser.parse_args()
    store = Store(os.environ.get('DATABASE_PATH', '/data/inventory.sqlite3'))
    if args.command == 'backup':
        if not args.destination:
            parser.error('Specify a new backup path')
        store.backup(args.destination)
        print('Backup integrity: ok')
    elif args.command == 'restore':
        if not args.destination:
            parser.error('Specify a backup path; app must be stopped')
        source_path = Path(args.destination).resolve()
        if source_path == store.path.resolve() or not source_path.is_file():
            parser.error('Backup must be a different existing file')
        with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source:
            if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or source.execute('PRAGMA foreign_key_check').fetchall() or source.execute('PRAGMA user_version').fetchone()[0] != 1:
                raise RuntimeError('Invalid backup integrity or schema')
            # Validate all stored collections before changing the live database.
            from .store import validate
            validate(store._read(source)['data'])
            stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
            store.backup(store.path.parent / 'backups' / f'before-restore-{stamp}.sqlite3')
            with closing(sqlite3.connect(store.path)) as destination:
                source.backup(destination)
        print('Restore complete; pre-restore backup created')
    else:
        with store.connect() as db:
            print('Integrity:', db.execute('PRAGMA integrity_check').fetchone()[0])
            print('Foreign key errors:', db.execute('PRAGMA foreign_key_check').fetchall())
        print('Revision:', store.read()['revision'])
