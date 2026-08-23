import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app

def save_uploaded_image(file_storage, folder_name='apartment_images', target_size=(1200, 800)):
    """
    Saves and resizes an uploaded image file securely.
    Returns relative path to static folder.
    """
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    
    unique_filename = f"{uuid.uuid4().hex}.{extension}"
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], folder_name)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, unique_filename)

    # Process and resize image using Pillow
    try:
        img = Image.open(file_storage)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        img.save(file_path, quality=85, optimize=True)
    except Exception as e:
        # Fallback save if PIL processing fails
        file_storage.save(file_path)

    # Relative path for static URL
    return f"/static/uploads/{folder_name}/{unique_filename}"
