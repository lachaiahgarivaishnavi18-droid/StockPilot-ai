"""Generate explicit initial DDL from metadata against an empty scratch DB."""
from pathlib import Path
from sqlalchemy import create_engine
from alembic.migration import MigrationContext
from alembic.autogenerate import produce_migrations, render_python_code
from app.database import Base
from app import models

engine=create_engine('sqlite://')
with engine.connect() as connection:
    operations=produce_migrations(MigrationContext.configure(connection),Base.metadata)
    upgrade=render_python_code(operations.upgrade_ops)
    downgrade=render_python_code(operations.downgrade_ops)
    output='''"""Initial schema: explicit, immutable DDL."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
'''+upgrade+'\n\ndef downgrade():\n'+downgrade+'\n'
    Path('alembic/versions/0001_initial.py').write_text(output,encoding='utf-8')
