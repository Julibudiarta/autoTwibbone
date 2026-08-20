# Auto-Twibbon Storage Configuration

Dokumentasi setup untuk menggunakan Supabase Storage dengan Auto-Twibbon Studio.

## Setup Supabase

### 1. Buat Project Supabase
- Kunjungi https://supabase.com
- Buat project baru atau login ke project existing
- Catat `Project URL` dan `API Key`

### 2. Buat Storage Bucket
Di Supabase Dashboard:
1. Navigasi ke **Storage** (sidebar kiri)
2. Klik **Create new bucket**
3. Nama bucket: `twibbon-files` (atau sesuai kebutuhan)
4. Pilih **Public** jika ingin file bisa diakses langsung via URL

### 3. Environment Variables (.env)
Buat file `.env` di root project:

```bash
# Storage Configuration
STORAGE_TYPE=supabase

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_BUCKET=twibbon-files

# Flask
SECRET_KEY=your-secret-key-here
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Run Application
```bash
python app_supabase.py
```

## Struktur Penyimpanan

Files akan tersimpan di Supabase dengan struktur:
```
twibbon-files/
├── {user_id}/
│   ├── {batch_id}/
│   │   ├── twibbon_file.png
│   │   ├── input_0_photo.jpg
│   │   ├── preview_0.jpg
│   │   └── result_photo.png
│   └── twibbon_batch_{batch_id}.zip
```

## Keuntungan Supabase Storage

✅ **Cloud Storage** - Tidak perlu worry tentang disk space lokal
✅ **Unlimited Scalability** - Pertumbuhan tanpa batas
✅ **Public URLs** - Link langsung ke file hasil
✅ **Built-in CDN** - Akses cepat dari mana saja
✅ **PostgreSQL Integration** - Bisa tambah database untuk metadata
✅ **Cost Effective** - Harga kompetitif

## URL Download Format

File yang di-upload akan bisa diakses via:
```
https://your-project.supabase.co/storage/v1/object/public/twibbon-files/{user_id}/{batch_id}/{filename}
```

## Switching Storage Backend

Untuk kembali ke Local Storage:
```bash
STORAGE_TYPE=local python app_supabase.py
```

Atau gunakan `app_with_storage.py` yang lebih generic.

## Troubleshooting

### Error: "Supabase dependencies tidak terinstall"
```bash
pip install supabase
```

### Error: "Invalid Supabase URL atau KEY"
- Double check di Supabase Dashboard > Settings > API
- Pastikan menggunakan **anon** key, bukan **service_role** key

### Error: "Bucket not found"
- Pastikan bucket `twibbon-files` sudah dibuat di Supabase Storage
- Atau ubah nama di `SUPABASE_BUCKET` environment variable

### Files tidak bisa diakses
- Pastikan bucket berstatus **Public**
- Di Supabase Dashboard > Storage > Policies bisa adjust permissions
