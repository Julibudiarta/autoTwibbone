import os
import zipfile
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, url_for, session
from werkzeug.utils import secure_filename
from PIL import Image
from image_processor import process_twibbon
from pillow_heif import register_heif_opener

# Pastikan opener terdaftar di proses utama Flask
register_heif_opener()
print("Auto-Twibbon Studio: Dukungan HEIC Aktif")

app = Flask(__name__)
# Maximum Upload Size 100 MB
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
# Dibutuhkan untuk menandatangani cookie sesi. Di produksi, ambil dari
# environment variable, jangan hardcode.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Riwayat per-browser-session, disimpan HANYA di memori proses (bukan database).
# Artinya: otomatis terpisah per user (per uid sesi), otomatis "sementara"
# (hilang saat server restart), dan tidak pernah bocor ke sesi/browser lain.
# { uid: [ {batch_id, created_at, message, twibbon_filename, files:[...], zip_url, uid}, ... ] }
USER_HISTORY = {}


def get_uid():
    """Ambil id unik untuk sesi browser ini, buat baru kalau belum ada.
    Disimpan di session cookie yang ditandatangani (bukan baris database
    permanen) sehingga otomatis kedaluwarsa mengikuti sesi/riwayat browser."""
    if 'uid' not in session:
        session['uid'] = str(uuid.uuid4())
        session.permanent = False
    return session['uid']


def _check_owner(uid):
    return session.get('uid') == uid


def _find_batch(uid, batch_id):
    return next((b for b in USER_HISTORY.get(uid, []) if b['batch_id'] == batch_id), None)


@app.route('/')
def index():
    get_uid()  # pastikan setiap pengunjung langsung punya id sesi
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def handle_upload():
    uid = get_uid()

    if 'twibbon' not in request.files or 'user_images' not in request.files:
        return jsonify({'error': 'Pastikan Anda mengunggah File Twibbon dan juga File Foto Pengguna.'}), 400

    twibbon_file = request.files['twibbon']
    user_images = request.files.getlist('user_images')

    if twibbon_file.filename == '':
        return jsonify({'error': 'File Twibbon kosong atau tidak terpilih.'}), 400

    if len(user_images) == 0 or user_images[0].filename == '':
        return jsonify({'error': 'Tidak ada kumpulan file foto pengguna yang diunggah.'}), 400

    # Buat batch ID untuk pemrosesan ini, dinest di bawah folder milik uid
    batch_id = str(uuid.uuid4())
    session_upload_path = os.path.join(app.config['UPLOAD_FOLDER'], uid, batch_id)
    session_output_path = os.path.join(app.config['OUTPUT_FOLDER'], uid, batch_id)
    os.makedirs(session_upload_path, exist_ok=True)
    os.makedirs(session_output_path, exist_ok=True)

    try:
        # Simpan Twibbon
        twibbon_filename = secure_filename(twibbon_file.filename)
        twibbon_path = os.path.join(session_upload_path, twibbon_filename)
        twibbon_file.save(twibbon_path)

        processed_files = []

        # Eksekusi foto pengguna
        for idx, user_image in enumerate(user_images):
            if user_image.filename:
                user_filename = secure_filename(user_image.filename)
                input_filename = f"input_{idx}_{user_filename}"
                user_path = os.path.join(session_upload_path, input_filename)
                user_image.save(user_path)

                # Buat pratinjau JPEG dari foto asli (untuk editor posisi di browser;
                # beberapa format seperti HEIC tidak bisa ditampilkan langsung oleh <img>)
                preview_filename = f"preview_{idx}.jpg"
                try:
                    with Image.open(user_path) as src_im:
                        src_im.convert("RGB").save(
                            os.path.join(session_upload_path, preview_filename), "JPEG", quality=88
                        )
                except Exception:
                    preview_filename = None

                # Definisi output PNG
                file_root = user_filename.rsplit('.', 1)[0]
                output_filename = f"result_{file_root}.png"
                output_path = os.path.join(session_output_path, output_filename)

                # Mulai gabungkan via PIL (posisi default: tengah, tanpa zoom tambahan)
                success = process_twibbon(user_path, twibbon_path, output_path)
                if success:
                    download_url = url_for('download_file', uid=uid, batch_id=batch_id, filename=output_filename)
                    processed_files.append({
                        'original': user_filename,
                        'result_url': download_url,
                        'filename': output_filename,
                        # Disimpan agar /reposition bisa memproses ulang tanpa upload lagi
                        'user_input': input_filename,
                        'preview_input': preview_filename,
                        'pos_x': 0.5,
                        'pos_y': 0.5,
                        'zoom': 1.0,
                    })

        zip_url = None
        # Buat ZIP jika diproses > 1 gambar
        if len(processed_files) > 1:
            zip_filename = f"twibbon_batch_{batch_id}.zip"
            zip_path = os.path.join(app.config['OUTPUT_FOLDER'], uid, zip_filename)
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for pf in processed_files:
                    file_to_zip = os.path.join(session_output_path, pf['filename'])
                    zipf.write(file_to_zip, arcname=pf['filename'])
            zip_url = url_for('download_zip', uid=uid, zip_filename=zip_filename)

        batch_record = {
            'uid': uid,
            'batch_id': batch_id,
            'created_at': datetime.now().strftime('%d %b %Y, %H:%M'),
            'message': f'Berhasil memproses {len(processed_files)} gambar!',
            'twibbon_filename': twibbon_filename,
            'files': processed_files,
            'zip_url': zip_url,
        }
        USER_HISTORY.setdefault(uid, []).insert(0, batch_record)

        return jsonify(batch_record), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/reposition', methods=['POST'])
def reposition():
    """Render ulang satu hasil dengan posisi crop / zoom baru, tanpa upload ulang."""
    uid = get_uid()
    data = request.get_json(silent=True) or {}

    batch_id = data.get('batch_id')
    filename = data.get('filename')

    try:
        pos_x = min(max(float(data.get('pos_x', 0.5)), 0.0), 1.0)
        pos_y = min(max(float(data.get('pos_y', 0.5)), 0.0), 1.0)
        zoom = min(max(float(data.get('zoom', 1.0)), 1.0), 3.0)
    except (TypeError, ValueError):
        return jsonify({'error': 'Parameter posisi/zoom tidak valid.'}), 400

    batch = _find_batch(uid, batch_id)
    if not batch:
        return jsonify({'error': 'Sesi Twibbon ini tidak ditemukan atau sudah kedaluwarsa.'}), 404

    file_record = next((f for f in batch['files'] if f['filename'] == filename), None)
    if not file_record:
        return jsonify({'error': 'File hasil tidak ditemukan pada sesi ini.'}), 404

    session_upload_path = os.path.join(app.config['UPLOAD_FOLDER'], uid, batch_id)
    session_output_path = os.path.join(app.config['OUTPUT_FOLDER'], uid, batch_id)
    user_path = os.path.join(session_upload_path, file_record['user_input'])
    twibbon_path = os.path.join(session_upload_path, batch['twibbon_filename'])
    output_path = os.path.join(session_output_path, filename)

    if not os.path.exists(user_path) or not os.path.exists(twibbon_path):
        return jsonify({'error': 'File sumber sudah tidak tersedia di server.'}), 404

    success = process_twibbon(user_path, twibbon_path, output_path, zoom=zoom, pos_x=pos_x, pos_y=pos_y)
    if not success:
        return jsonify({'error': 'Gagal memproses ulang posisi gambar.'}), 500

    file_record['pos_x'] = pos_x
    file_record['pos_y'] = pos_y
    file_record['zoom'] = zoom

    # cache-bust supaya <img> di browser memuat ulang crop yang baru
    download_url = url_for('download_file', uid=uid, batch_id=batch_id, filename=filename)
    download_url += f"?v={uuid.uuid4().hex[:8]}"

    return jsonify({'result_url': download_url, 'pos_x': pos_x, 'pos_y': pos_y, 'zoom': zoom}), 200


@app.route('/history')
def history():
    uid = get_uid()
    return jsonify({'uid': uid, 'batches': USER_HISTORY.get(uid, [])}), 200


@app.route('/history', methods=['DELETE'])
def clear_history():
    uid = get_uid()
    USER_HISTORY[uid] = []
    return jsonify({'message': 'Riwayat sesi ini sudah dihapus.'}), 200


@app.route('/source_photo/<uid>/<batch_id>/<filename>')
def source_photo(uid, batch_id, filename):
    """Menyajikan foto asli/pratinjau pengguna (dipakai oleh editor posisi)."""
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], uid, batch_id, secure_filename(filename))
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File tidak ditemukan.", 404


@app.route('/source_twibbon/<uid>/<batch_id>')
def source_twibbon(uid, batch_id):
    """Menyajikan file Twibbon asli untuk overlay di editor posisi."""
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    batch = _find_batch(uid, batch_id)
    if not batch:
        return "Sesi tidak ditemukan.", 404
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], uid, batch_id, batch['twibbon_filename'])
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File tidak ditemukan.", 404


@app.route('/download/<uid>/<batch_id>/<filename>')
def download_file(uid, batch_id, filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], uid, batch_id, secure_filename(filename))
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File tidak ditemukan.", 404


@app.route('/download_zip/<uid>/<zip_filename>')
def download_zip(uid, zip_filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], uid, secure_filename(zip_filename))
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File Zip tidak ditemukan.", 404


if __name__ == '__main__':
    app.run(debug=True, port=8000)