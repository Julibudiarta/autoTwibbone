import os
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIF opener for Pillow to handle .heic files
register_heif_opener()

def process_twibbon(user_image_path, twibbon_image_path, output_path):
    try:
        # Panggil lagi di sini untuk memastikan decoder aktif dalam thread/proses ini
        register_heif_opener()
        
        # Load the user and twibbon images
        user_img = Image.open(user_image_path).convert("RGBA")
        twibbon_img = Image.open(twibbon_image_path).convert("RGBA")

        # Get size of the twibbon
        t_width, t_height = twibbon_img.size

        # Fit user image to the twibbon size (center crop to maintain aspect ratio)
        u_width, u_height = user_img.size
        # To fill the twibbon perfectly, we take the max scaling ratio between width and height
        width_ratio = t_width / u_width
        height_ratio = t_height / u_height
        ratio = max(width_ratio, height_ratio)

        new_size = (int(u_width * ratio), int(u_height * ratio))
        user_img = user_img.resize(new_size, Image.Resampling.LANCZOS)

        # Center crop the user image so it exactly matches the twibbon dimensions
        left = (user_img.width - t_width) / 2
        top = (user_img.height - t_height) / 2
        right = (user_img.width + t_width) / 2
        bottom = (user_img.height + t_height) / 2

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
