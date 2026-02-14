import os
import secrets
from flask import current_app

def save_picture(form_picture):
    """
    Save uploaded picture to the filesystem with proper error handling
    Uses /tmp directory on Vercel (writable) and local folder elsewhere
    """
    try:
        # Generate random filename to prevent conflicts
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_picture.filename)
        picture_fn = random_hex + f_ext
        
        # Determine if running on Vercel
        is_vercel = os.environ.get('VERCEL_ENV') == 'production' or os.environ.get('VERCEL') == '1'
        
        if is_vercel:
            # On Vercel, use /tmp directory (writable)
            upload_folder = '/tmp/captain_signature_uploads/products'
            # Also store in a database-friendly path
            db_path = f"uploads/{picture_fn}"
        else:
            # Local development
            project_root = os.path.dirname(os.path.abspath(__file__))
            upload_folder = os.path.join(project_root, 'static', 'images', 'products')
            db_path = picture_fn
        
        print(f"\n--- Image Upload Debug ---")
        print(f"Upload folder: {upload_folder}")
        print(f"Database path: {db_path}")
        
        # Create the directory if it doesn't exist
        os.makedirs(upload_folder, exist_ok=True)
        
        # Construct the full file path
        picture_path = os.path.join(upload_folder, picture_fn)
        print(f"Full picture path: {picture_path}")
        
        # Save the file
        form_picture.save(picture_path)
        print(f"File saved successfully: {picture_fn}")
        
        # Verify file exists
        if os.path.exists(picture_path):
            print(f"✓ File verified at: {picture_path}")
            print(f"  File size: {os.path.getsize(picture_path)} bytes")
        else:
            raise Exception("File was not saved properly")
        
        # Return the appropriate path for database
        if is_vercel:
            return f"tmp:{picture_fn}"  # Mark as temp file
        else:
            return picture_fn
            
    except Exception as e:
        print(f"Error in save_picture: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to save image: {str(e)}")