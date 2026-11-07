"""Vercel entrypoint: FastAPI API and the compiled React SPA on one origin."""
from backend.app.main import app

# Register during discovery too, before the frontend build directory exists.
# Vercel promotes this directory to its CDN and removes it from the function.
app.frontend('/', directory='frontend/dist', fallback='index.html', check_dir=False)
