import os
import io
import threading
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

# ── HEIC/HEIF support ────────────────────────────────────────────────────────
# register_heif_opener() memodifikasi global registry Pillow (Image.OPEN).
# Di ThreadPoolExecutor, worker thread bisa jalan sebelum registry ter-update,
# sehingga Image.open() gagal dengan UnidentifiedImageError pada file .heic.
# Solusi: panggil register_heif_opener() di SETIAP entry-point yang membuka
# gambar, dilindungi lock agar tidak ada race condition.

_heif_lock = threading.Lock()

def _ensure_heif():
    """Pastikan HEIC/HEIF opener terdaftar di thread yang sedang berjalan."""
    with _heif_lock:
        register_heif_opener()

_ensure_heif()


# ── optimize_image ────────────────────────────────────────────────────────────

def optimize_image(img_input, max_dimension=None, quality=95):
    """
    Buka dan optimasi gambar input (termasuk HEIC).
    Jika max_dimension=None, ukuran asli dipertahankan 100%.
    Selalu mengembalikan BytesIO berisi PNG dengan pointer di posisi 0.
    """
    _ensure_heif()

    if isinstance(img_input, Image.Image):
        img = img_input
    else:
        if hasattr(img_input, 'seek'):
            try:
                img_input.seek(0)
            except Exception:
                pass
        img = Image.open(img_input)

    # Perbaiki orientasi EXIF (foto HP yang berotasi)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    width, height = img.size
    if max_dimension and max(width, height) > max_dimension:
        ratio = max_dimension / float(max(width, height))
        new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    out_buf = io.BytesIO()
    has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)

    if has_alpha:
        img.convert('RGBA').save(out_buf, 'PNG', optimize=True, compress_level=3)
    else:
        img.convert('RGB').save(out_buf, 'PNG', optimize=True, compress_level=3)

    out_buf.seek(0)
    return out_buf


# ── process_twibbon ───────────────────────────────────────────────────────────

def process_twibbon(user_image_path, twibbon_image_path, output_path,
                    zoom=1.0, pos_x=0.5, pos_y=0.5, max_dimension=None):
    """Menggabungkan foto pengguna dengan Twibbon.

    zoom  : faktor skala relatif terhadap ukuran "cover" minimum.
            > 1.0 = perbesar (gambar lebih besar dari canvas, bisa digeser/crop)
            = 1.0 = cover tepat (default, center-crop)
            < 1.0 = perkecil (gambar lebih kecil dari canvas, ada padding di tepi)
    pos_x : posisi horizontal, 0.0 = rata kiri, 1.0 = rata kanan, 0.5 = tengah.
    pos_y : posisi vertikal, 0.0 = rata atas, 1.0 = rata bawah, 0.5 = tengah.
    max_dimension : jika None, mempertahankan 100% resolusi asli twibbon.
    """
    try:
        _ensure_heif()

        user_img = Image.open(user_image_path)
        try:
            user_img = ImageOps.exif_transpose(user_img)
        except Exception:
            pass
        user_img = user_img.convert("RGBA")

        twibbon_img = Image.open(twibbon_image_path).convert("RGBA")

        t_width, t_height = twibbon_img.size
        if max_dimension and max(t_width, t_height) > max_dimension:
            scale = max_dimension / float(max(t_width, t_height))
            t_width = max(1, int(t_width * scale))
            t_height = max(1, int(t_height * scale))
            twibbon_img = twibbon_img.resize((t_width, t_height), Image.Resampling.LANCZOS)

        # Fit user image ke ukuran twibbon (cover mode, pertahankan aspect ratio)
        u_width, u_height = user_img.size
        width_ratio  = t_width  / float(u_width)
        height_ratio = t_height / float(u_height)

        zoom = min(max(float(zoom), 0.3), 3.0)
        cover_ratio = max(width_ratio, height_ratio)
        ratio = cover_ratio * zoom

        new_size = (max(1, int(u_width * ratio)), max(1, int(u_height * ratio)))
        user_img = user_img.resize(new_size, Image.Resampling.LANCZOS)

        canvas = Image.new('RGBA', (t_width, t_height), (0, 0, 0, 0))

        if zoom >= 1.0:
            # Gambar lebih besar/sama dengan canvas → crop sesuai posisi
            slack_x = max(0, user_img.width  - t_width)
            slack_y = max(0, user_img.height - t_height)

            pos_x = min(max(float(pos_x), 0.0), 1.0)
            pos_y = min(max(float(pos_y), 0.0), 1.0)

            left   = int(slack_x * pos_x)
            top    = int(slack_y * pos_y)
            right  = left + t_width
            bottom = top  + t_height

            user_img = user_img.crop((left, top, right, bottom))
            canvas.paste(user_img, (0, 0))
        else:
            # Gambar lebih kecil dari canvas → tempatkan sesuai posisi (ada padding)
            pos_x = min(max(float(pos_x), 0.0), 1.0)
            pos_y = min(max(float(pos_y), 0.0), 1.0)

            pad_x   = t_width  - user_img.width
            pad_y   = t_height - user_img.height
            paste_x = int(pad_x * pos_x)
            paste_y = int(pad_y * pos_y)

            canvas.paste(user_img, (paste_x, paste_y))

        # Tempel twibbon di atas foto pengguna
        canvas.paste(twibbon_img, (0, 0), twibbon_img)

        canvas.save(output_path, "PNG", compress_level=3, optimize=True)
        return True

    except Exception as e:
        print(f"Error processing image: {e}")
        return False
