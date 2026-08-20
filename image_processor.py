import os
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIF opener for Pillow to handle .heic files
register_heif_opener()


def process_twibbon(user_image_path, twibbon_image_path, output_path, zoom=1.0, pos_x=0.5, pos_y=0.5):
    """Menggabungkan foto pengguna dengan Twibbon.

    zoom  : faktor perbesaran di atas ukuran "cover" minimum (>= 1.0).
    pos_x : posisi horizontal jendela crop, 0.0 = rata kiri, 1.0 = rata kanan, 0.5 = tengah.
    pos_y : posisi vertikal jendela crop, 0.0 = rata atas, 1.0 = rata bawah, 0.5 = tengah.

    Nilai default (zoom=1.0, pos_x=pos_y=0.5) menghasilkan perilaku yang sama
    persis dengan versi sebelumnya (center-crop otomatis).
    """
    try:
        # Panggil lagi di sini untuk memastikan decoder aktif dalam thread/proses ini
        register_heif_opener()

        # Load the user and twibbon images
        user_img = Image.open(user_image_path).convert("RGBA")
        twibbon_img = Image.open(twibbon_image_path).convert("RGBA")

        # Get size of the twibbon
        t_width, t_height = twibbon_img.size

        # Fit user image to the twibbon size (cover, maintaining aspect ratio)
        u_width, u_height = user_img.size
        width_ratio = t_width / u_width
        height_ratio = t_height / u_height

        zoom = max(1.0, float(zoom))  # jangan sampai di bawah ukuran "cover" minimum
        ratio = max(width_ratio, height_ratio) * zoom

        new_size = (max(1, int(u_width * ratio)), max(1, int(u_height * ratio)))
        user_img = user_img.resize(new_size, Image.Resampling.LANCZOS)

        # Sisa ruang yang bisa digeser (slack) di tiap sumbu setelah di-resize
        slack_x = max(0, user_img.width - t_width)
        slack_y = max(0, user_img.height - t_height)

        pos_x = min(max(float(pos_x), 0.0), 1.0)
        pos_y = min(max(float(pos_y), 0.0), 1.0)

        left = slack_x * pos_x
        top = slack_y * pos_y
        right = left + t_width
        bottom = top + t_height

        user_img = user_img.crop((left, top, right, bottom))

        # Create a blank canvas matching twibbon size
        canvas = Image.new('RGBA', (t_width, t_height), (0, 0, 0, 0))

        # Paste user image
        canvas.paste(user_img, (0, 0))

        # Apply twibbon over user image transparently (using it as a mask itself via the third parameter)
        canvas.paste(twibbon_img, (0, 0), twibbon_img)

        # Save result as PNG to maintain quality
        canvas.save(output_path, "PNG", compress_level=6)
        return True

    except Exception as e:
        print(f"Error processing image: {e}")
        return False