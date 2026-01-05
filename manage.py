#!/usr/bin/env python
import os
import sys
import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Only override on Heroku
if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=True)


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'system.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        raise
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
