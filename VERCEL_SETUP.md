# Panduan Deploy Auto-Twibbon Studio ke Vercel

Panduan lengkap untuk men-deploy aplikasi **Auto-Twibbon Studio** ke Vercel secara gratis.

---

## 🛠️ Persiapan Sebelum Deploy

Karena Vercel menggunakan Serverless Functions (tanpa penyimpanan harddisk permanen):
- **Opsi Penyimpanan Terbaik di Vercel**:
  1. `STORAGE_TYPE=browser` (Sangat Direkomendasikan: Super Cepat, simpan sementara di RAM memori, tanpa setup cloud).
  2. `STORAGE_TYPE=supabase` (Jika ingin file tersimpan di cloud Supabase).

---
---
## 🚀 Cara 1: Deploy via GitHub (Sangat Mudah & Otomatis)

1. Push repository project Anda ke GitHub:
   ```bash
   git add .
   git commit -m "Setup Vercel deployment"
   git push origin main
   ```
2. Buka [Vercel Dashboard](https://vercel.com/dashboard) dan klik **Add New...** -> **Project**.
3. Pilih repository GitHub Anda.
4. Pada bagian **Environment Variables**, tambahkan variabel berikut:
   - `STORAGE_TYPE`: `browser` (atau `supabase`)
   - `SECRET_KEY`: `random-secret-key-anda`
   - *(Optional jika pakai Supabase)* `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_BUCKET`
5. Klik **Deploy**.
6. Selesai! Aplikasi Anda langsung aktif dan mendapat domain gratis dari Vercel (`https://nama-project.vercel.app`).

---

## ⚡ Cara 2: Deploy via Vercel CLI (Lewat Terminal)

1. Install Vercel CLI (jika belum):
   ```bash
   npm install -g vercel
   ```
2. Jalankan perintah deploy di terminal project:
   ```bash
   vercel
   ```
3. Ikuti petunjuk di layar (pilih `y` untuk mengaitkan ke project Vercel Anda).
4. Untuk deploy ke Production:
   ```bash
   vercel --prod
   ```

---

## 📂 File Konfigurasi Vercel di Project Ini:

- [`vercel.json`](file:///d:/Koding/twibbon/autoTwibbone/vercel.json) — Mengatur routing serverless & file statis (CSS/JS).
- [`api/index.py`](file:///d:/Koding/twibbon/autoTwibbone/api/index.py) — Entry point WSGI Flask untuk Vercel.
- [`requirements.txt`](file:///d:/Koding/twibbon/autoTwibbone/requirements.txt) — Daftar library Python yang diinstall otomatis oleh Vercel.
