"""Run database migrations during a cloud build, never from a user request."""
import os
from alembic import command
from alembic.config import Config
from app.database import DATABASE_URL

if DATABASE_URL.startswith('sqlite'):
    raise RuntimeError('Cloud deployment requires a persistent PostgreSQL database')
os.environ['DATABASE_URL']=DATABASE_URL
command.upgrade(Config('alembic.ini'),'head')
print('StockPilot database migrations completed.')
