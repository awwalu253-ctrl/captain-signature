import os
import secrets
from flask import current_app

def save_picture(form_picture):
    """
    Save uploaded picture to a local folder outside OneDrive
    """
    try:
        # Generate random filename to prevent conflicts
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_picture.filename)
        picture_fn = random_hex + f_ext
        
        # Get the user's home directory (C:\Users\awwal)
        user_home = os.path.expanduser("~")
        
        # Create a folder in the user's home directory (outside OneDrive)
        upload_base = os.path.join(user_home, 'captain_signature_uploads')
        upload_folder = os.path.join(upload_base, 'product_images')
        
        print(f"\n--- Debug Path Information ---")
        print(f"User home: {user_home}")
        print(f"Upload folder: {upload_folder}")
        
        # Create the directory if it doesn't exist
        if not os.path.exists(upload_base):
            os.makedirs(upload_base)
            print(f"Created base directory: {upload_base}")
        
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            print(f"Created upload folder: {upload_folder}")
        
        # Verify directory is writable
        if not os.access(upload_folder, os.W_OK):
            raise Exception(f"Upload folder is not writable: {upload_folder}")
        
        # Construct the full file path
        picture_path = os.path.join(upload_folder, picture_fn)
        print(f"Full picture path: {picture_path}")
        
        # Save the file
        form_picture.save(picture_path)
        print(f"File saved successfully: {picture_fn}")
        
        # Return the relative path for database
        # We'll use a special marker to know it's in the user folder
        return f"user_uploads:{picture_fn}"
            
    except Exception as e:
        print(f"Error in save_picture: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to save image: {str(e)}")