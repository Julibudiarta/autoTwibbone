import os
from PIL import Image
import pillow_heif
import sys

def diagnose(file_path):
    print(f"--- Diagnosing: {file_path} ---")
    if not os.path.exists(file_path):
        print("Error: File does not exist.")
        return

    print(f"File size: {os.path.getsize(file_path)} bytes")

    # Method 1: Pillow with register_heif_opener and options
    try:
        pillow_heif.register_heif_opener()
        pillow_heif.options.ALLOW_INCORRECT_HEADERS = True
        img = Image.open(file_path)
        print(f"Method 1 (Pillow) Success: Format={img.format}, Size={img.size}")
    except Exception as e:
        print(f"Method 1 (Pillow) Failed: {e}")

    # Method 2: pillow_heif.read_heif directly with options
    try:
        heif_file = pillow_heif.read_heif(file_path)
        print(f"Method 2 (pillow_heif) Success: Size={heif_file.size}, Mode={heif_file.mode}")
    except Exception as e:
        print(f"Method 2 (pillow_heif) Failed: {e}")

if __name__ == "__main__":
    # Find the most recent HEIC file in uploads
    uploads_dir = "uploads"
    heic_files = []
    for root, dirs, files in os.walk(uploads_dir):
        for file in files:
            if file.lower().endswith(".heic"):
                heic_files.append(os.path.join(root, file))
    
    if heic_files:
        # Sort by mtime
        heic_files.sort(key=os.path.getmtime, reverse=True)
        diagnose(heic_files[0])
    else:
        print("No HEIC files found in uploads directory.")
