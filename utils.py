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
        print(f"Filename: {picture_fn}")
        
        if is_vercel:
            # On Vercel, use /tmp directory
            upload_folder = '/tmp/captain_signature_uploads/products'
            print(f"Target upload_folder: {upload_folder}")
            
            # Create directory
            os.makedirs(upload_folder, exist_ok=True)
            print(f"Directory exists after creation: {os.path.exists(upload_folder)}")
            
            # Check if we can write to it
            print(f"Directory writable: {os.access(upload_folder, os.W_OK)}")
            
            # List directory contents before save
            if os.path.exists(upload_folder):
                before_files = os.listdir(upload_folder)
                print(f"Files before save: {before_files}")
        else:
            # Local development
            project_root = os.path.dirname(os.path.abspath(__file__))
            upload_folder = os.path.join(project_root, 'static', 'images', 'products')
            os.makedirs(upload_folder, exist_ok=True)
            print(f"Local upload_folder: {upload_folder}")
        
        # Full path
        picture_path = os.path.join(upload_folder, picture_fn)
        print(f"Full picture path: {picture_path}")
        
        # Save the file
        form_picture.save(picture_path)
        print(f"✓ File saved via form_picture.save()")
        
        # Verify file exists
        if os.path.exists(picture_path):
            file_size = os.path.getsize(picture_path)
            print(f"✓ File verified at: {picture_path}")
            print(f"  File size: {file_size} bytes")
            
            # List directory contents after save
            if os.path.exists(upload_folder):
                after_files = os.listdir(upload_folder)
                print(f"Files after save: {after_files}")
        else:
            print(f"❌ File does NOT exist after save!")
            # Try to write a test file to verify directory is writable
            test_file = os.path.join(upload_folder, 'test.txt')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                print(f"✓ Test file written successfully: {test_file}")
                os.remove(test_file)
                print(f"✓ Test file removed")
            except Exception as e:
                print(f"❌ Cannot write test file: {e}")
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