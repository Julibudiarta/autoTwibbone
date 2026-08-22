import os
import io
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

# Register HEIF opener for Pillow to handle .heic files
register_heif_opener()


def optimize_image(img_input, max_dimension=None, quality=95):
    """
    Optimasi gambar input. Jika max_dimension diset, gambar akan di-resize.
    Jika max_dimension=None, gambar dipertahankan 100% pada ukuran asli tanpa resize.
    """
    register_heif_opener()
    
    if isinstance(img_input, Image.Image):
        img = img_input
    else:
        img = Image.open(img_input)

    # Perbaiki orientasi EXIF (misal foto HP berotasi)
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


def process_twibbon(user_image_path, twibbon_image_path, output_path, zoom=1.0, pos_x=0.5, pos_y=0.5, max_dimension=None):
    """Menggabungkan foto pengguna dengan Twibbon secara presisi pada 100% ukuran asli tanpa penurunan kualitas.

    zoom  : faktor perbesaran di atas ukuran "cover" minimum (>= 1.0).
    pos_x : posisi horizontal jendela crop (0.0 - 1.0).
    pos_y : posisi vertikal jendela crop (0.0 - 1.0).
    max_dimension : jika None, mempertahankan 100% resolusi asli twibbon.
    """
    try:
        register_heif_opener()

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

        # Fit user image to the twibbon size (cover mode)
        u_width, u_height = user_img.size
        width_ratio = t_width / float(u_width)
        height_ratio = t_height / float(u_height)

        zoom = max(1.0, float(zoom))
        ratio = max(width_ratio, height_ratio) * zoom

        new_size = (max(1, int(u_width * ratio)), max(1, int(u_height * ratio)))
        user_img = user_img.resize(new_size, Image.Resampling.LANCZOS)

        # Sisa ruang crop (slack)
        slack_x = max(0, user_img.width - t_width)
        slack_y = max(0, user_img.height - t_height)

        pos_x = min(max(float(pos_x), 0.0), 1.0)
        pos_y = min(max(float(pos_y), 0.0), 1.0)

        left = int(slack_x * pos_x)
        top = int(slack_y * pos_y)
        right = left + t_width
        bottom = top + t_height

        user_img = user_img.crop((left, top, right, bottom))

        # Canvas penggabungan
        canvas = Image.new('RGBA', (t_width, t_height), (0, 0, 0, 0))
        canvas.paste(user_img, (0, 0))
        canvas.paste(twibbon_img, (0, 0), twibbon_img)

        canvas.save(output_path, "PNG", compress_level=3, optimize=True)
        return True
    except Exception as e:
        print(f"Error processing image: {e}")
        return False