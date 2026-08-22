import os
import sys

# Tambahkan root directory ke sys.path agar Vercel Serverless Function dapat membaca app.py & modul lainnya
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
os.chdir(root_dir)

from app import app

class VercelPathFix:
    """
    Middleware WSGI untuk memperbaiki PATH_INFO di Vercel Serverless Function.
    Memastikan route Flask seperti / , /upload, /static/... selalu cocok
    meskipun Vercel menambahkan prefix /api/index.py pada PATH_INFO.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/api/index.py'):
            environ['PATH_INFO'] = path[len('/api/index.py'):] or '/'
        elif path.startswith('/api/index'):
            environ['PATH_INFO'] = path[len('/api/index'):] or '/'
        return self.app(environ, start_response)

# Export WSGI application instance untuk Vercel Serverless
app = VercelPathFix(app)
