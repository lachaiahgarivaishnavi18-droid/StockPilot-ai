"""Stage only application source; never upload local data, logs or credentials."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parent.parent
target=root/'.deployment'
files=['.vercelignore','app.py','pyproject.toml','requirements.txt','vercel.json','backend/requirements-vercel.txt','backend/alembic.ini','backend/deploy_init.py','frontend/package.json','frontend/pnpm-lock.yaml','frontend/tsconfig.json','frontend/vite.config.ts','frontend/index.html','scripts/vercel-build.mjs']
directories=['backend/app','backend/alembic','frontend/src']
for name in files:
    source=root/name
    if source.is_file():
        destination=target/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
for name in directories:
    shutil.copytree(root/name,target/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.test.ts','*.test.tsx'))
print('Prepared source-only Vercel staging directory:',target)
