import os
import secrets
from flask import current_app

def save_picture(form_picture, upload_folder):
    """
    Save uploaded picture to the filesystem with proper error handling
    """
    try:
        # Generate random filename to prevent conflicts
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_picture.filename)
        picture_fn = random_hex + f_ext
        
        print(f"\n--- Debug Path Information ---")
        print(f"Upload folder: {upload_folder}")
        
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
        
        # Return just the filename (not the full path)
        return picture_fn
            
    except Exception as e:
        print(f"Error in save_picture: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to save image: {str(e)}")