"""
Auto-Twibbon Studio — server tunggal teroptimasi & cepat.
Jalankan: python app.py

Fitur Otomatisasi & Optimasi:
  1. STORAGE_TYPE=supabase | local
  2. Auto Cleanup Storage: Jika total file > 900MB, otomatis menghapus file terlama hingga tersisa 500MB
  3. Pemrosesan Paralel (Multi-threading) untuk upload & render batch foto
  4. Pre-kompresi & resizing cerdas tanpa mengurangi ketajaman visual (tajam & hemat ruang)
"""

import os

# ── 1. Muat .env SEBELUM apapun (termasuk storage init) ──────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
    print("[.env] Konfigurasi berhasil dimuat dari file .env")
except ImportError:
    print("[.env] python-dotenv tidak terinstall — lewati")

# ── 2. Import standar & concurrency ──────────────────────────────────────────
import io
import uuid
import base64
import zipfile
import tempfile
import threading
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, render_template, request, jsonify, send_file, url_for, session
from werkzeug.utils import secure_filename
from PIL import Image

from image_processor import process_twibbon, optimize_image
from storage import create_storage

# ── 3. HEIC support ───────────────────────────────────────────────────────────
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    print("[HEIC] Dukungan HEIC/HEIF aktif")
except ImportError:
    print("[HEIC] pillow-heif tidak terinstall — format HEIC tidak didukung")

# ── 4. Flask app ──────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, 'templates'),
    static_folder=os.path.join(ROOT_DIR, 'static')
)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024   # 100 MB max upload
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')

# ── 5. Storage backend ────────────────────────────────────────────────────────
STORAGE_TYPE = os.environ.get('STORAGE_TYPE', 'local').strip().lower()

if STORAGE_TYPE in ('browser', 'memory', 'ram', 'temp'):
    storage = create_storage('browser')
    print("[Storage] Backend: BROWSER (RAM Memori)  |  File tidak disimpan ke Disk / Cloud!")

elif STORAGE_TYPE == 'supabase':
    supabase_url = os.environ.get('SUPABASE_URL', '').strip()
    supabase_key = os.environ.get('SUPABASE_KEY', '').strip()
    bucket_name  = os.environ.get('SUPABASE_BUCKET', 'twibbon-files').strip()

    if not supabase_url or not supabase_key:
        raise RuntimeError(
            "STORAGE_TYPE=supabase tapi SUPABASE_URL / SUPABASE_KEY belum diisi di .env!"
        )

    storage = create_storage(
        'supabase',
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        bucket_name=bucket_name,
    )
    print(f"[Storage] Backend: Supabase  |  bucket: {bucket_name}")

else:
    local_path = os.environ.get('LOCAL_STORAGE_PATH', 'storage').strip()
    storage = create_storage('local', base_path=local_path)
    print(f"[Storage] Backend: Local Filesystem  |  path: {local_path}/")

# ── 6. Session history (in-memory) ───────────────────────────────────────────
USER_HISTORY: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def get_uid() -> str:
    """Kembalikan uid unik per sesi browser; buat baru jika belum ada."""
    if 'uid' not in session:
        session['uid'] = str(uuid.uuid4())
        session.permanent = False
    return session['uid']


def _check_owner(uid: str) -> bool:
    return session.get('uid') == uid


def _find_batch(uid: str, batch_id: str) -> dict | None:
    return next((b for b in USER_HISTORY.get(uid, []) if b['batch_id'] == batch_id), None)


def _guess_mime(filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp',
        'zip': 'application/zip',
    }.get(ext, 'image/png')


def _storage_url(path: str) -> str:
    """
    Kembalikan URL yang bisa dibuka browser untuk file di storage.
      - Browser  : data:image/png;base64,... (instan & 100% bebas serverless state Vercel!)
      - Supabase : public URL dari bucket Supabase
      - Local    : route internal Flask /serve/<path>
    """
    if STORAGE_TYPE in ('browser', 'memory', 'ram', 'temp'):
        try:
            file_buf = storage.get_file(path)
            data_bytes = file_buf.read()
            mime = _guess_mime(path)
            b64_str = base64.b64encode(data_bytes).decode('utf-8')
            return f"data:{mime};base64,{b64_str}"
        except Exception as e:
            print(f"[b64 storage_url error] {e}")
            return f"/serve/{path}"

    if STORAGE_TYPE == 'supabase':
        return storage.get_download_url(path)

    return f"/serve/{path}"


def trigger_async_cleanup():
    """Jalankan pengecekan & pembersihan storage otomatis di background thread."""
    def _run():
        try:
            # 900MB limit trigger, bersihkan hingga 500MB
            storage.cleanup_if_needed(threshold_bytes=900 * 1024 * 1024, target_bytes=500 * 1024 * 1024)
        except Exception as e:
            print(f"[Async Cleanup Error] {e}")
    threading.Thread(target=_run, daemon=True).start()


def _remove_color(image: Image.Image, target_rgb: tuple, tolerance: int = 30) -> Image.Image:
    """
    Hapus warna target dari gambar lalu jadikan transparan.
    Menggunakan jarak Euclidean di ruang RGB dengan fade anti-aliasing.
    """
    img  = image.convert("RGBA")
    data = np.array(img, dtype=np.float32)      # shape (H, W, 4)

    r, g, b = target_rgb
    diff  = data[:, :, :3] - np.array([r, g, b], dtype=np.float32)
    dist  = np.sqrt(np.sum(diff ** 2, axis=2))  # shape (H, W)

    fade_range   = tolerance * 1.5 + 1e-9
    alpha_factor = np.clip((dist - tolerance) / fade_range, 0.0, 1.0)
    data[:, :, 3] = data[:, :, 3] * alpha_factor

    return Image.fromarray(data.astype(np.uint8), "RGBA")


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

# ── Halaman utama ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    get_uid()
    return render_template('index.html')


# ── Sajikan file lokal (hanya aktif saat STORAGE_TYPE=local) ─────────────────
@app.route('/serve/<path:file_path>')
def serve_storage_file(file_path):
    """Sajikan file dari local storage; tidak dipakai saat Supabase aktif."""
    try:
        f   = storage.get_file(file_path)
        ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''
        mime = {
            'png': 'image/png',
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'zip': 'application/zip',
        }.get(ext, 'application/octet-stream')
        return send_file(f, mimetype=mime)
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


# ── Upload & proses twibbon teroptimasi & paralel ─────────────────────────────
@app.route('/upload', methods=['POST'])
def handle_upload():
    uid = get_uid()

    if 'twibbon' not in request.files or 'user_images' not in request.files:
        return jsonify({'error': 'Pastikan Anda mengunggah File Twibbon dan juga File Foto Pengguna.'}), 400

    twibbon_file = request.files['twibbon']
    user_images  = request.files.getlist('user_images')

    if twibbon_file.filename == '':
        return jsonify({'error': 'File Twibbon kosong atau tidak terpilih.'}), 400
    if not user_images or user_images[0].filename == '':
        return jsonify({'error': 'Tidak ada kumpulan file foto pengguna yang diunggah.'}), 400

    batch_id     = str(uuid.uuid4())
    session_path = f"{uid}/{batch_id}"

    try:
        storage.create_folder(session_path)

        # 1. Simpan & optimasi file Twibbon
        twibbon_filename = secure_filename(twibbon_file.filename) or 'twibbon.png'
        twibbon_storage  = f"{session_path}/{twibbon_filename}"

        # Di mode browser, cukup baca bytes twibbon langsung dari stream
        IS_BROWSER_MODE = STORAGE_TYPE in ('browser', 'memory', 'ram', 'temp')
        # Pertahankan 100% ukuran asli tanpa resize sama sekali
        MAX_DIM = None

        optimized_twibbon_buf = optimize_image(twibbon_file.stream, max_dimension=MAX_DIM)
        optimized_twibbon_buf.seek(0)
        twibbon_bytes = optimized_twibbon_buf.read()

        if IS_BROWSER_MODE:
            b64_twibbon = base64.b64encode(twibbon_bytes).decode('utf-8')
            twibbon_url = f"data:image/png;base64,{b64_twibbon}"
        else:
            storage.save_file(twibbon_storage, optimized_twibbon_buf)
            twibbon_url = _storage_url(twibbon_storage)

        # 2. Fungsi worker paralel per foto pengguna
        def _process_single_image(idx_and_user_image):
            idx, user_image = idx_and_user_image
            if not user_image or not user_image.filename:
                return None

            user_filename  = secure_filename(user_image.filename)
            input_filename = f"input_{idx}_{user_filename}"

            # Optimasi foto pengguna (100% ukuran & ketajaman asli)
            opt_user_buf = optimize_image(user_image.stream, max_dimension=MAX_DIM)
            opt_user_buf.seek(0)
            user_bytes = opt_user_buf.read()

            # Simpan ke storage hanya jika bukan mode browser
            if not IS_BROWSER_MODE:
                user_storage = f"{session_path}/{input_filename}"
                storage.save_file(user_storage, opt_user_buf)

            # Buat Data URL resolusi tinggi untuk preview editor posisi
            preview_filename = f"preview_{idx}.png"
            preview_storage  = f"{session_path}/{preview_filename}"
            if IS_BROWSER_MODE:
                preview_b64_url = "data:image/png;base64," + base64.b64encode(user_bytes).decode('utf-8')
            else:
                preview_b64_url = None
                try:
                    storage.save_file(preview_storage, opt_user_buf)
                except Exception as e:
                    print(f"[preview error] {e}")
                    preview_storage = f"{session_path}/{input_filename}"

            # Render hasil overlay twibbon (100% Resolusi & Kualitas Asli)
            file_root       = user_filename.rsplit('.', 1)[0]
            output_filename = f"result_{file_root}.png"
            output_storage  = f"{session_path}/{output_filename}"

            with tempfile.TemporaryDirectory() as tmpdir:
                user_tmp    = os.path.join(tmpdir, input_filename)
                twibbon_tmp = os.path.join(tmpdir, twibbon_filename)
                out_fname   = f"result_{file_root}.png"
                output_tmp  = os.path.join(tmpdir, out_fname)

                with open(user_tmp, 'wb') as f:
                    f.write(user_bytes)
                with open(twibbon_tmp, 'wb') as f:
                    f.write(twibbon_bytes)

                success = process_twibbon(user_tmp, twibbon_tmp, output_tmp, max_dimension=MAX_DIM)
                if success:
                    if IS_BROWSER_MODE:
                        with open(output_tmp, 'rb') as f:
                            out_bytes = f.read()
                        res_url  = "data:image/png;base64," + base64.b64encode(out_bytes).decode('utf-8')
                        dl_url   = res_url
                        prev_url = preview_b64_url or res_url
                    else:
                        with open(output_tmp, 'rb') as f:
                            storage.save_file(output_storage, f)
                        res_url  = _storage_url(output_storage)
                        dl_url   = f"/download/{uid}/{batch_id}/{out_fname}"
                        prev_url = _storage_url(preview_storage)

                    return {
                        'idx':           idx,
                        'original':      user_filename,
                        'result_url':    res_url,
                        'download_url':  dl_url,
                        'preview_url':   prev_url,
                        'filename':      out_fname,
                        'user_input':    input_filename,
                        'preview_input': preview_filename,
                        'pos_x': 0.5, 'pos_y': 0.5, 'zoom': 1.0,
                    }
            return None

        # 3. Jalankan paralel dengan ThreadPoolExecutor (max 4-8 thread)
        processed_files = []
        max_workers = min(8, max(1, len(user_images)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_process_single_image, (idx, img)) for idx, img in enumerate(user_images)]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    processed_files.append(res)

        # Urutkan sesuai index semula
        processed_files.sort(key=lambda x: x['idx'])
        for pf in processed_files:
            pf.pop('idx', None)

        # 4. Buat ZIP jika > 1 gambar
        zip_url = None
        if len(processed_files) > 1:
            zip_filename = f"twibbon_batch_{batch_id}.zip"
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for pf in processed_files:
                    if IS_BROWSER_MODE:
                        # Ambil bytes dari Base64 data URL yang ada di result_url
                        data_url = pf['result_url']
                        if ',' in data_url:
                            img_bytes = base64.b64decode(data_url.split(',', 1)[1])
                        else:
                            img_bytes = b''
                    else:
                        img_bytes = storage.get_file(f"{session_path}/{pf['filename']}").read()
                    zipf.writestr(pf['filename'], img_bytes)
            zip_buf.seek(0)
            if IS_BROWSER_MODE:
                # ZIP sebagai data URL agar bisa diunduh langsung tanpa server
                zip_url = "data:application/zip;base64," + base64.b64encode(zip_buf.read()).decode()
            else:
                zip_storage = f"{uid}/{zip_filename}"
                storage.save_file(zip_storage, zip_buf)
                zip_url = f"/download_zip/{uid}/{zip_filename}"

        batch_record = {
            'uid':              uid,
            'batch_id':         batch_id,
            'created_at':       datetime.now().strftime('%d %b %Y, %H:%M'),
            'message':          f'Berhasil memproses {len(processed_files)} gambar!',
            'twibbon_filename': twibbon_filename,
            'twibbon_url':      twibbon_url,
            'files':            processed_files,
            'zip_url':          zip_url,
        }
        USER_HISTORY.setdefault(uid, []).insert(0, batch_record)

        # 5. Pemicu pembersihan otomatis di background (hanya untuk storage non-browser)
        if not IS_BROWSER_MODE:
            trigger_async_cleanup()

        return jsonify(batch_record), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ── Reposisi foto dalam twibbon ───────────────────────────────────────────────
@app.route('/reposition', methods=['POST'])
def reposition():
    uid  = get_uid()
    data = request.get_json(silent=True) or {}

    batch_id = data.get('batch_id')
    filename = data.get('filename')
    try:
        pos_x = min(max(float(data.get('pos_x', 0.5)), 0.0), 1.0)
        pos_y = min(max(float(data.get('pos_y', 0.5)), 0.0), 1.0)
        zoom  = min(max(float(data.get('zoom',  1.0)), 1.0), 3.0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Parameter posisi/zoom tidak valid.'}), 400

    batch = _find_batch(uid, batch_id)
    if not batch:
        return jsonify({'error': 'Sesi Twibbon ini tidak ditemukan atau sudah kedaluwarsa.'}), 404

    file_record = next((f for f in batch['files'] if f['filename'] == filename), None)
    if not file_record:
        return jsonify({'error': 'File hasil tidak ditemukan pada sesi ini.'}), 404

    session_path  = f"{uid}/{batch_id}"
    user_path     = f"{session_path}/{file_record['user_input']}"
    twibbon_path  = f"{session_path}/{batch['twibbon_filename']}"
    output_path   = f"{session_path}/{filename}"

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            user_tmp    = os.path.join(tmpdir, file_record['user_input'])
            twibbon_tmp = os.path.join(tmpdir, batch['twibbon_filename'])
            output_tmp  = os.path.join(tmpdir, filename)

            with open(user_tmp, 'wb') as f:
                f.write(storage.get_file(user_path).read())
            with open(twibbon_tmp, 'wb') as f:
                f.write(storage.get_file(twibbon_path).read())

            success = process_twibbon(user_tmp, twibbon_tmp, output_tmp,
                                      zoom=zoom, pos_x=pos_x, pos_y=pos_y, max_dimension=2048)
            if not success:
                return jsonify({'error': 'Gagal memproses ulang posisi gambar.'}), 500

            saved_filename = filename
            saved_output_path = output_path
            try:
                with open(output_tmp, 'rb') as f:
                    storage.save_file(output_path, f)
            except Exception as save_err:
                print(f"[Reposition Save Fallback] {save_err}. Saving as new version...")
                saved_filename = f"v_{uuid.uuid4().hex[:6]}_{filename}"
                saved_output_path = f"{session_path}/{saved_filename}"
                with open(output_tmp, 'rb') as f:
                    storage.save_file(saved_output_path, f)
                file_record['filename'] = saved_filename

        file_record.update({'pos_x': pos_x, 'pos_y': pos_y, 'zoom': zoom})
        result_url = _storage_url(saved_output_path)
        if not result_url.startswith('data:'):
            separator = '&' if '?' in result_url else '?'
            result_url += f"{separator}v={uuid.uuid4().hex[:8]}"
            download_url = f"/download/{uid}/{batch_id}/{saved_filename}"
        else:
            download_url = result_url

        file_record['result_url'] = result_url
        file_record['download_url'] = download_url

        return jsonify({'result_url': result_url, 'download_url': download_url, 'pos_x': pos_x, 'pos_y': pos_y, 'zoom': zoom}), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ── Riwayat sesi ──────────────────────────────────────────────────────────────
@app.route('/history')
def history():
    uid = get_uid()
    return jsonify({'uid': uid, 'batches': USER_HISTORY.get(uid, [])}), 200


@app.route('/history', methods=['DELETE'])
def clear_history():
    uid = get_uid()
    USER_HISTORY[uid] = []
    return jsonify({'message': 'Riwayat sesi ini sudah dihapus.'}), 200


# ── Source files untuk editor posisi ─────────────────────────────────────────
@app.route('/source_photo/<uid>/<batch_id>/<filename>')
def source_photo(uid, batch_id, filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    try:
        f = storage.get_file(f"{uid}/{batch_id}/{secure_filename(filename)}")
        return send_file(f, mimetype='image/jpeg')
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


@app.route('/source_twibbon/<uid>/<batch_id>')
def source_twibbon(uid, batch_id):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    batch = _find_batch(uid, batch_id)
    if not batch:
        return "Sesi tidak ditemukan.", 404
    try:
        f = storage.get_file(f"{uid}/{batch_id}/{batch['twibbon_filename']}")
        return send_file(f, mimetype='image/png')
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


# ── Download langsung ─────────────────────────────────────────────────────────
@app.route('/download/<uid>/<batch_id>/<filename>')
def download_file(uid, batch_id, filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    try:
        f = storage.get_file(f"{uid}/{batch_id}/{secure_filename(filename)}")
        return send_file(f, as_attachment=True, download_name=filename)
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


@app.route('/download_zip/<uid>/<zip_filename>')
def download_zip(uid, zip_filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    try:
        f = storage.get_file(f"{uid}/{secure_filename(zip_filename)}")
        return send_file(f, as_attachment=True, download_name=zip_filename)
    except FileNotFoundError:
        return "File Zip tidak ditemukan.", 404


# ── Hapus warna background twibbon ───────────────────────────────────────────
@app.route('/remove_bg_color', methods=['POST'])
def remove_bg_color():
    try:
        uid = get_uid()

        if 'twibbon' not in request.files:
            return jsonify({'error': 'File twibbon tidak ditemukan di request.'}), 400

        twibbon_file = request.files['twibbon']
        raw_filename = twibbon_file.filename or 'twibbon.png'
        safe_name    = secure_filename(raw_filename) or 'twibbon.png'

        color_hex = request.form.get('color', '').strip().lstrip('#')
        if len(color_hex) != 6:
            return jsonify({'error': 'Format warna tidak valid. Gunakan hex 6 karakter.'}), 400
        try:
            target_rgb = tuple(int(color_hex[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return jsonify({'error': 'Kode warna hex tidak valid.'}), 400

        try:
            tolerance = max(0, min(int(float(request.form.get('tolerance', 30))), 150))
        except (ValueError, TypeError):
            tolerance = 30

        img_data = twibbon_file.stream.read()
        if not img_data:
            return jsonify({'error': 'File twibbon kosong.'}), 400

        img        = Image.open(io.BytesIO(img_data))
        result_img = _remove_color(img, target_rgb, tolerance)

        out_buf = io.BytesIO()
        result_img.save(out_buf, 'PNG', compress_level=6, optimize=True)
        out_buf.seek(0)

        base_name    = safe_name.rsplit('.', 1)[0]
        out_filename = f"converted_{base_name}_{uuid.uuid4().hex[:6]}.png"
        storage_path = f"{uid}/converted/{out_filename}"

        storage.save_file(storage_path, out_buf)
        converted_url = _storage_url(storage_path)

        trigger_async_cleanup()

        return jsonify({
            'converted_url': converted_url,
            'filename':      out_filename,
            'storage_path':  storage_path,
        }), 200

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': f'Gagal memproses gambar: {str(e)}'}), 500


@app.route('/converted_twibbon/<uid>/<filename>')
def serve_converted_twibbon(uid, filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    try:
        f = storage.get_file(f"{uid}/converted/{secure_filename(filename)}")
        return send_file(f, mimetype='image/png')
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    print(f"\n[OK] Auto-Twibbon Studio berjalan di http://localhost:{port}")
    print(f"     Storage : {STORAGE_TYPE.upper()}")
    print(f"     Debug   : {debug}\n")
    app.run(debug=debug, port=port)
