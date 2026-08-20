import os
import zipfile
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, url_for, session
from werkzeug.utils import secure_filename
from PIL import Image
from image_processor import process_twibbon
from storage import create_storage
from pillow_heif import register_heif_opener

# Pastikan opener terdaftar di proses utama Flask
register_heif_opener()
print("Auto-Twibbon Studio: Dukungan HEIC Aktif")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')

# ========== KONFIGURASI STORAGE ==========
# Pilih storage backend berdasarkan environment variable
# STORAGE_TYPE=local (default) atau STORAGE_TYPE=google_drive
STORAGE_TYPE = os.environ.get('STORAGE_TYPE', 'local')

if STORAGE_TYPE == 'google_drive':
    # Konfigurasi Google Drive
    storage = create_storage(
        'google_drive',
        credentials_file=os.environ.get('GOOGLE_CREDENTIALS', 'credentials.json'),
        token_file=os.environ.get('GOOGLE_TOKEN', 'token.pickle'),
        root_folder_id=os.environ.get('GOOGLE_DRIVE_FOLDER_ID', 'root')
    )
    print("Storage Backend: Google Drive")
else:
    # Konfigurasi Local Storage (default)
    storage = create_storage(
        'local',
        base_path=os.environ.get('LOCAL_STORAGE_PATH', 'storage')
    )
    print("Storage Backend: Local Filesystem")

# Riwayat per-browser-session, disimpan HANYA di memori proses
USER_HISTORY = {}


def get_uid():
    """Ambil id unik untuk sesi browser ini, buat baru kalau belum ada."""
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
    get_uid()
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

    batch_id = str(uuid.uuid4())
    session_upload_path = f"{uid}/{batch_id}"
    session_output_path = f"{uid}/{batch_id}"
    
    try:
        # Buat folder untuk session ini di storage
        storage.create_folder(session_upload_path)
        storage.create_folder(session_output_path)

        # Simpan Twibbon ke storage
        twibbon_filename = secure_filename(twibbon_file.filename)
        twibbon_path = f"{session_upload_path}/{twibbon_filename}"
        storage.save_file(twibbon_path, twibbon_file.stream)

        processed_files = []

        # Proses foto pengguna
        for idx, user_image in enumerate(user_images):
            if user_image.filename:
                user_filename = secure_filename(user_image.filename)
                input_filename = f"input_{idx}_{user_filename}"
                user_path = f"{session_upload_path}/{input_filename}"
                
                # Simpan user image ke storage
                storage.save_file(user_path, user_image.stream)

                # Buat preview JPEG dari foto asli
                preview_filename = f"preview_{idx}.jpg"
                try:
                    # Get file dari storage untuk diproses
                    user_file = storage.get_file(user_path)
                    with Image.open(user_file) as src_im:
                        preview_data = src_im.convert("RGB")
                        preview_io = io.BytesIO()
                        preview_data.save(preview_io, "JPEG", quality=88)
                        preview_io.seek(0)
                        preview_path = f"{session_upload_path}/{preview_filename}"
                        storage.save_file(preview_path, preview_io)
                except Exception:
                    preview_filename = None

                # Proses image untuk twibbon
                file_root = user_filename.rsplit('.', 1)[0]
                output_filename = f"result_{file_root}.png"
                output_path = f"{session_output_path}/{output_filename}"

                # Untuk process_twibbon, kita perlu file path lokal
                # Jadi kita download ke temporary path, process, lalu upload hasil
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Download files ke temp
                    user_temp = os.path.join(tmpdir, input_filename)
                    twibbon_temp = os.path.join(tmpdir, twibbon_filename)
                    output_temp = os.path.join(tmpdir, output_filename)
                    
                    with open(user_temp, 'wb') as f:
                        f.write(storage.get_file(user_path).read())
                    
                    with open(twibbon_temp, 'wb') as f:
                        f.write(storage.get_file(twibbon_path).read())
                    
                    # Process twibbon
                    success = process_twibbon(user_temp, twibbon_temp, output_temp)
                    
                    if success:
                        # Upload hasil ke storage
                        with open(output_temp, 'rb') as f:
                            storage.save_file(output_path, f)
                        
                        download_url = storage.get_download_url(output_path)
                        processed_files.append({
                            'original': user_filename,
                            'result_url': download_url,
                            'filename': output_filename,
                            'user_input': input_filename,
                            'preview_input': preview_filename,
                            'pos_x': 0.5,
                            'pos_y': 0.5,
                            'zoom': 1.0,
                        })

        zip_url = None
        # Buat ZIP jika diproses > 1 gambar
        if len(processed_files) > 1:
            import io
            zip_filename = f"twibbon_batch_{batch_id}.zip"
            zip_path = f"{uid}/{zip_filename}"
            
            # Buat ZIP di memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                for pf in processed_files:
                    file_to_zip_path = f"{session_output_path}/{pf['filename']}"
                    file_data = storage.get_file(file_to_zip_path).read()
                    zipf.writestr(pf['filename'], file_data)
            
            zip_buffer.seek(0)
            storage.save_file(zip_path, zip_buffer)
            zip_url = storage.get_download_url(zip_path)

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
    """Render ulang satu hasil dengan posisi crop / zoom baru."""
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

    session_upload_path = f"{uid}/{batch_id}"
    session_output_path = f"{uid}/{batch_id}"
    user_path = f"{session_upload_path}/{file_record['user_input']}"
    twibbon_path = f"{session_upload_path}/{batch['twibbon_filename']}"
    output_path = f"{session_output_path}/{filename}"

    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download files ke temp
            user_temp = os.path.join(tmpdir, file_record['user_input'])
            twibbon_temp = os.path.join(tmpdir, batch['twibbon_filename'])
            output_temp = os.path.join(tmpdir, filename)
            
            with open(user_temp, 'wb') as f:
                f.write(storage.get_file(user_path).read())
            
            with open(twibbon_temp, 'wb') as f:
                f.write(storage.get_file(twibbon_path).read())
            
            # Process ulang dengan parameter baru
            success = process_twibbon(user_temp, twibbon_temp, output_temp, zoom=zoom, pos_x=pos_x, pos_y=pos_y)
            
            if not success:
                return jsonify({'error': 'Gagal memproses ulang posisi gambar.'}), 500
            
            # Upload hasil yang sudah diproses
            with open(output_temp, 'rb') as f:
                storage.save_file(output_path, f)
        
        file_record['pos_x'] = pos_x
        file_record['pos_y'] = pos_y
        file_record['zoom'] = zoom

        # Dapatkan URL download dengan cache-bust
        download_url = storage.get_download_url(output_path)
        if '?' not in download_url:
            download_url += f"?v={uuid.uuid4().hex[:8]}"

        return jsonify({'result_url': download_url, 'pos_x': pos_x, 'pos_y': pos_y, 'zoom': zoom}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
    
    try:
        file_path = f"{uid}/{batch_id}/{secure_filename(filename)}"
        file_data = storage.get_file(file_path)
        return send_file(file_data, mimetype='image/jpeg')
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


@app.route('/source_twibbon/<uid>/<batch_id>')
def source_twibbon(uid, batch_id):
    """Menyajikan file Twibbon asli untuk overlay di editor posisi."""
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    
    batch = _find_batch(uid, batch_id)
    if not batch:
        return "Sesi tidak ditemukan.", 404
    
    try:
        file_path = f"{uid}/{batch_id}/{batch['twibbon_filename']}"
        file_data = storage.get_file(file_path)
        return send_file(file_data, mimetype='image/png')
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


@app.route('/download/<uid>/<batch_id>/<filename>')
def download_file(uid, batch_id, filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    
    try:
        file_path = f"{uid}/{batch_id}/{secure_filename(filename)}"
        file_data = storage.get_file(file_path)
        return send_file(file_data, as_attachment=True, download_name=filename)
    except FileNotFoundError:
        return "File tidak ditemukan.", 404


@app.route('/download_zip/<uid>/<zip_filename>')
def download_zip(uid, zip_filename):
    if not _check_owner(uid):
        return "Akses ditolak.", 403
    
    try:
        file_path = f"{uid}/{secure_filename(zip_filename)}"
        file_data = storage.get_file(file_path)
        return send_file(file_data, as_attachment=True, download_name=zip_filename)
    except FileNotFoundError:
        return "File Zip tidak ditemukan.", 404


if __name__ == '__main__':
    app.run(debug=True, port=8000)
