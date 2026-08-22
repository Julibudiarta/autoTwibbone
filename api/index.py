import os
import sys

# Tambahkan root directory ke sys.path agar Vercel Serverless Function dapat membaca app.py & modul lainnya
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
os.chdir(root_dir)

from app import app

# Export WSGI application instance untuk Vercel Serverless
app = app
