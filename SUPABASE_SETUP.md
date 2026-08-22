# Auto-Twibbon Storage Configuration (Supabase)

Dokumentasi setup & penyelesaian error RLS (Row Level Security) untuk Supabase Storage.

---

## ⚡ Solusi Error: "new row violates row-level security policy" (HTTP 403)

Error 403 ini terjadi karena bucket Supabase **membatasi akses UPDATE atau DELETE** untuk pengguna anonim (`anon` role).

### Cara Solusi 1: Atur Policies di Supabase Dashboard (Direkomendasikan)

1. Buka [Supabase Dashboard](https://supabase.com/dashboard) -> pilih project Anda.
2. Masuk ke menu **Storage** (sidebar kiri) -> klik **Policies**.
3. Cari bucket `twibbon-files`.
4. Klik **New policy** -> pilih **For full customization** (atau **Create policy from scratch**).
5. Buat 4 Kebijakan (Policies) berikut:

| Nama Policy | Allowed Operations | Target roles | USING / WITH CHECK expression |
|---|---|---|---|
| `Public Select` | **SELECT** | `anon`, `authenticated` | `bucket_id = 'twibbon-files'` |
| `Public Insert` | **INSERT** | `anon`, `authenticated` | `bucket_id = 'twibbon-files'` |
| `Public Update` | **UPDATE** | `anon`, `authenticated` | `bucket_id = 'twibbon-files'` |
| `Public Delete` | **DELETE** | `anon`, `authenticated` | `bucket_id = 'twibbon-files'` |

---

### Cara Solusi 2: Jalankan Script SQL di Supabase (Paling Cepat ⚡)

Buka menu **SQL Editor** di Supabase Dashboard, lalu paste & jalankan script SQL berikut:

```sql
-- Izinkan SELECT (Download/Lihat)
CREATE POLICY "Allow Public Select" ON storage.objects
FOR SELECT USING (bucket_id = 'twibbon-files');

-- Izinkan INSERT (Upload Baru)
CREATE POLICY "Allow Public Insert" ON storage.objects
FOR INSERT WITH CHECK (bucket_id = 'twibbon-files');

-- Izinkan UPDATE (Simpan Posisi / Overwrite)
CREATE POLICY "Allow Public Update" ON storage.objects
FOR UPDATE USING (bucket_id = 'twibbon-files');

-- Izinkan DELETE (Auto Cleanup Storage)
CREATE POLICY "Allow Public Delete" ON storage.objects
FOR DELETE USING (bucket_id = 'twibbon-files');
```

---

## ⚙️ Fitur Otomatis di Kode Python

Aplikasi sudah dilengkapi **Auto-Fallback**:
- Jika tombol **Simpan Posisi** ditekan saat izin `UPDATE` belum diaktifkan di Supabase, sistem secara otomatis menyimpan posisi sebagai file versi baru (`INSERT`), sehingga tombol **Simpan Posisi** **TETAP BERHASIL & TIDAK GAAL**.
