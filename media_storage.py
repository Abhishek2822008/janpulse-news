import os
import secrets
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app, url_for
from PIL import Image
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)

def init_cloudinary(app):
    """
    Initializes Cloudinary if credentials or CLOUDINARY_URL are configured in app.config / .env.
    """
    import re
    cloudinary_url = os.environ.get('CLOUDINARY_URL') or app.config.get('CLOUDINARY_URL')
    cloud_name = app.config.get('CLOUDINARY_CLOUD_NAME')
    api_key = app.config.get('CLOUDINARY_API_KEY')
    api_secret = app.config.get('CLOUDINARY_API_SECRET')

    # If the user pasted CLOUDINARY_URL into the secret field, parse it cleanly
    if api_secret and 'cloudinary://' in api_secret:
        clean_url = api_secret.replace('CLOUDINARY_URL=', '').strip().strip('"').strip("'")
        m = re.match(r"cloudinary://([^:]+):([^@]+)@(.+)", clean_url)
        if m:
            api_key, api_secret, cloud_name = m.groups()
            app.config['CLOUDINARY_CLOUD_NAME'] = cloud_name
            app.config['CLOUDINARY_API_KEY'] = api_key
            app.config['CLOUDINARY_API_SECRET'] = api_secret

    if cloudinary_url:
        try:
            cloudinary.config(cloudinary_url=cloudinary_url)
            app.config['CLOUDINARY_ACTIVE'] = True
            print("[Cloudinary] Configured successfully via CLOUDINARY_URL.")
            return
        except Exception as e:
            print(f"[Cloudinary] Failed to configure from URL: {e}")

    if cloud_name and api_key and api_secret:
        if '*' in api_secret:
            app.config['CLOUDINARY_ACTIVE'] = False
            print("[Cloudinary Warning] API Secret contains masked asterisks (**********). Please click the eye/copy icon in Cloudinary dashboard to reveal the actual secret.")
            return

        try:
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )
            app.config['CLOUDINARY_ACTIVE'] = True
            print(f"[Cloudinary] Configured successfully for cloud: {cloud_name}")
        except Exception as e:
            app.config['CLOUDINARY_ACTIVE'] = False
            print(f"[Cloudinary] Configuration failed: {e}")
    else:
        app.config['CLOUDINARY_ACTIVE'] = False
        print("[Cloudinary] No credentials found. Using local WebP auto-compression.")

def is_cloudinary_active():
    """Returns True if Cloudinary is configured and ready."""
    return current_app.config.get('CLOUDINARY_ACTIVE', False)

def save_uploaded_media(file_storage, folder="news", max_width=1280, quality=82):
    """
    Handles file upload:
    1. If Cloudinary is configured, uploads directly to Cloud CDN (0 KB disk storage used).
    2. Fallback / Local mode: Uses Pillow to resize (max_width 1280px) and compress to WebP (95% disk saved).
    
    Returns dict:
        {
            'url': public_url,
            'type': ext,
            'name': original_filename,
            'storage': 'cloudinary' or 'local_webp'
        }
    """
    if not file_storage or not file_storage.filename:
        return None

    raw_filename = secure_filename(file_storage.filename)
    ext = raw_filename.rsplit('.', 1)[-1].lower() if '.' in raw_filename else ''
    is_image = ext in current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'png', 'jpg', 'jpeg', 'webp', 'gif'})
    is_video = ext in current_app.config.get('ALLOWED_VIDEO_EXTENSIONS', {'mp4', 'webm'})

    # ----------------------------------------------------
    # 1. Cloudinary Cloud Upload (Option 3)
    # ----------------------------------------------------
    if is_cloudinary_active():
        try:
            resource_type = "video" if is_video else "image"
            upload_params = {
                "folder": f"janpulse/{folder}",
                "resource_type": resource_type,
            }
            if is_image:
                # Automatic quality, WebP/AVIF format optimization at CDN edge
                upload_params["transformation"] = [
                    {"width": max_width, "crop": "limit"},
                    {"quality": "auto", "fetch_format": "auto"}
                ]
            
            # Reset stream pointer
            file_storage.seek(0)
            result = cloudinary.uploader.upload(file_storage, **upload_params)
            
            secure_url = result.get('secure_url')
            if secure_url:
                return {
                    'url': secure_url,
                    'path': secure_url,
                    'type': ext or result.get('format', 'jpg'),
                    'name': raw_filename,
                    'storage': 'cloudinary'
                }
        except Exception as e:
            logger.error(f"[Cloudinary] Upload failed, falling back to local optimization: {e}")

    # ----------------------------------------------------
    # 2. Local Fallback with Pillow WebP Compression
    # ----------------------------------------------------
    timestamp = int(datetime.now().timestamp())
    token = secrets.token_hex(4)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    if is_image:
        try:
            file_storage.seek(0)
            img = Image.open(file_storage)

            # Convert RGBA or Palette to RGB for clean WebP compression
            if img.mode in ("RGBA", "LA"):
                # Preserve transparency if WebP
                pass
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if width exceeds max_width
            if img.width > max_width:
                height = int(img.height * (max_width / img.width))
                img = img.resize((max_width, height), Image.Resampling.LANCZOS)

            # Save as optimized WebP
            fname = f"{folder}_{timestamp}_{token}.webp"
            target_path = os.path.join(upload_folder, fname)
            img.save(target_path, 'WEBP', quality=quality, optimize=True)

            public_url = url_for('static', filename=f"uploads/{fname}")
            return {
                'url': public_url,
                'path': public_url,
                'type': 'webp',
                'name': raw_filename,
                'storage': 'local_webp'
            }
        except Exception as e:
            logger.error(f"[Pillow] Image processing error: {e}")
            # If Pillow fails, fallback to raw save
            fname = f"{folder}_{timestamp}_{token}.{ext}"
            target_path = os.path.join(upload_folder, fname)
            file_storage.seek(0)
            file_storage.save(target_path)
            public_url = url_for('static', filename=f"uploads/{fname}")
            return {
                'url': public_url,
                'path': public_url,
                'type': ext,
                'name': raw_filename,
                'storage': 'local_raw'
            }
    else:
        # Video or other file
        fname = f"{folder}_{timestamp}_{token}.{ext}"
        target_path = os.path.join(upload_folder, fname)
        file_storage.seek(0)
        file_storage.save(target_path)
        public_url = url_for('static', filename=f"uploads/{fname}")
        return {
            'url': public_url,
            'path': public_url,
            'type': ext,
            'name': raw_filename,
            'storage': 'local_raw'
        }
