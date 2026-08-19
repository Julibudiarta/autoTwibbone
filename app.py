import os
import zipfile
import uuid
from flask import Flask, render_template, request, jsonify, send_file, url_for
from werkzeug.utils import secure_filename
from image_processor import process_twibbon
import shutil
from pillow_heif import register_heif_opener

# Pastikan opener terdaftar di proses utama Flask
register_heif_opener()
print("Auto-Twibbon Studio: Dukungan HEIC Aktif")

app = Flask(__name__)
# Maximum Upload Size 100 MB
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def handle_upload():
    if 'twibbon' not in request.files or 'user_images' not in request.files:
        return jsonify({'error': 'Pastikan Anda mengunggah File Twibbon dan juga File Foto Pengguna.'}), 400

    twibbon_file = request.files['twibbon']
    user_images = request.files.getlist('user_images')

    if twibbon_file.filename == '':
        return jsonify({'error': 'File Twibbon kosong atau tidak terpilih.'}), 400
    
    if len(user_images) == 0 or user_images[0].filename == '':
        return jsonify({'error': 'Tidak ada kumpulan file foto pengguna yang diunggah.'}), 400

    # Buat session ID sementara untuk folder
    session_id = str(uuid.uuid4())
    session_upload_path = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    session_output_path = os.path.join(app.config['OUTPUT_FOLDER'], session_id)
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
                user_path = os.path.join(session_upload_path, f"input_{idx}_{user_filename}")
                user_image.save(user_path)

                # Definisi output PNG
                file_root = user_filename.rsplit('.', 1)[0]
                output_filename = f"result_{file_root}.png"
                output_path = os.path.join(session_output_path, output_filename)

                # Mulai gabungkan via PIL
                success = process_twibbon(user_path, twibbon_path, output_path)
                if success:
                    download_url = url_for('download_file', session_id=session_id, filename=output_filename)
                    processed_files.append({
                        'original': user_filename,
                        'result_url': download_url,
                        'filename': output_filename
                    })

        zip_url = None
        # Buat ZIP jika diproses > 1 gambar
        if len(processed_files) > 1:
            zip_filename = f"twibbon_batch_{session_id}.zip"
            zip_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for pf in processed_files:
                    file_to_zip = os.path.join(session_output_path, pf['filename'])
                    zipf.write(file_to_zip, arcname=pf['filename'])
            zip_url = url_for('download_zip', zip_filename=zip_filename)

        return jsonify({
            'message': f'Berhasil memproses {len(processed_files)} gambar!',
            'files': processed_files,
            'zip_url': zip_url
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<session_id>/<filename>')
def download_file(session_id, filename):
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], session_id, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File tidak ditemukan.", 404

@app.route('/download_zip/<zip_filename>')
def download_zip(zip_filename):
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File Zip tidak ditemukan.", 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
