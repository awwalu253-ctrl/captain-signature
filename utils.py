import os
import secrets
from flask import current_app

def save_picture(form_picture):
    """
    Save uploaded picture to the filesystem with proper error handling
    """
    try:
        # Generate random filename
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_picture.filename)
        picture_fn = random_hex + f_ext
        
        # Determine if running on Vercel
        is_vercel = os.environ.get('VERCEL_ENV') == 'production' or os.environ.get('VERCEL') == '1'
        
        print("\n" + "="*60)
        print("🔍 SAVE_PICTURE DEBUG")
        print(f"is_vercel: {is_vercel}")
        print(f"Original filename: {form_picture.filename}")
        print(f"New filename: {picture_fn}")
        
        if is_vercel:
            # On Vercel, use /tmp directory
            upload_folder = '/tmp/captain_signature_uploads/products'
            print(f"Target upload_folder: {upload_folder}")
            
            # Create directory with full permissions
            os.makedirs(upload_folder, mode=0o777, exist_ok=True)
            print(f"Directory exists: {os.path.exists(upload_folder)}")
            print(f"Directory writable: {os.access(upload_folder, os.W_OK)}")
            
            # List directory before save
            if os.path.exists(upload_folder):
                before_files = os.listdir(upload_folder)
                print(f"Files before save: {before_files}")
        else:
            # Local development
            project_root = os.path.dirname(os.path.abspath(__file__))
            upload_folder = os.path.join(project_root, 'static', 'images', 'products')
            os.makedirs(upload_folder, mode=0o777, exist_ok=True)
            print(f"Local upload_folder: {upload_folder}")
        
        # Full path
        picture_path = os.path.join(upload_folder, picture_fn)
        print(f"Full picture path: {picture_path}")
        
        # IMPORTANT: Save the file and flush immediately
        form_picture.save(picture_path)
        print(f"✓ File saved via form_picture.save()")
        
        # Force flush to disk (important for Vercel)
        with open(picture_path, 'ab') as f:
            f.flush()
            os.fsync(f.fileno())
        print(f"✓ File flushed to disk")
        
        # Verify file exists and get size
        if os.path.exists(picture_path):
            file_size = os.path.getsize(picture_path)
            print(f"✓ File verified at: {picture_path}")
            print(f"  File size: {file_size} bytes")
            
            # List directory after save
            if os.path.exists(upload_folder):
                after_files = os.listdir(upload_folder)
                print(f"Files after save: {after_files}")
                
                if picture_fn in after_files:
                    print(f"✓ File found in directory listing!")
                else:
                    print(f"❌ File NOT found in directory listing!")
        else:
            print(f"❌ File does NOT exist after save!")
            # Try alternative save method
            try:
                with open(picture_path, 'wb') as f:
                    f.write(form_picture.read())
                print(f"✓ File saved via alternative method")
                if os.path.exists(picture_path):
                    file_size = os.path.getsize(picture_path)
                    print(f"✓ Alternative save successful: {file_size} bytes")
                else:
                    raise Exception("Alternative save also failed")
            except Exception as e2:
                print(f"❌ Alternative save failed: {e2}")
                raise Exception("File was not saved properly")
        
        # Return path
        if is_vercel:
            result = f"tmp:{picture_fn}"
        else:
            result = picture_fn
            
        print(f"Returning: {result}")
        print("="*60 + "\n")
        return result
            
    except Exception as e:
        print(f"❌ Error in save_picture: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to save image: {str(e)}")
    
os.chmod(picture_path, 0o644)