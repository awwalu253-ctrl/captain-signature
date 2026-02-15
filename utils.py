import os
import secrets
from flask import current_app
import cloudinary
import cloudinary.uploader
import cloudinary.api

def init_cloudinary():
    """Initialize Cloudinary with app config"""
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
    
    if not cloud_name or not api_key or not api_secret:
        print("⚠ WARNING: Cloudinary credentials not found in environment variables!")
        print("  Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET")
        return False
    
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True
    )
    print(f"✓ Cloudinary initialized with cloud name: {cloud_name}")
    return True

def save_picture_cloudinary(form_picture):
    """
    Save uploaded picture to Cloudinary
    Returns: secure URL of uploaded image
    """
    try:
        # Initialize Cloudinary
        if not init_cloudinary():
            raise Exception("Cloudinary not configured properly")
        
        print(f"\n--- Cloudinary Upload Debug ---")
        print(f"Original filename: {form_picture.filename}")
        print(f"Content type: {form_picture.content_type}")
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            form_picture,
            folder="captain_signature/products",
            public_id=None,  # Let Cloudinary generate a unique ID
            use_filename=True,
            unique_filename=True,
            overwrite=False,
            resource_type="auto"
        )
        
        print(f"✓ Image uploaded to Cloudinary successfully!")
        print(f"  Public ID: {result.get('public_id')}")
        print(f"  Format: {result.get('format')}")
        print(f"  Width: {result.get('width')}")
        print(f"  Height: {result.get('height')}")
        print(f"  Size: {result.get('bytes')} bytes")
        print(f"  URL: {result.get('secure_url')}")
        
        # Return the secure URL
        return result.get('secure_url')
        
    except Exception as e:
        print(f"❌ Cloudinary upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to upload image to Cloudinary: {str(e)}")

def save_picture_local(form_picture):
    """
    Save uploaded picture locally (for development only)
    """
    try:
        # Generate random filename to prevent conflicts
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form_picture.filename)
        picture_fn = random_hex + f_ext
        
        # Local development path
        project_root = os.path.dirname(os.path.abspath(__file__))
        upload_folder = os.path.join(project_root, 'static', 'images', 'products')
        
        print(f"\n--- Local Upload Debug ---")
        print(f"Upload folder: {upload_folder}")
        print(f"Filename: {picture_fn}")
        
        # Create the directory if it doesn't exist
        os.makedirs(upload_folder, exist_ok=True)
        print(f"Directory exists: {os.path.exists(upload_folder)}")
        
        # Construct the full file path
        picture_path = os.path.join(upload_folder, picture_fn)
        print(f"Full picture path: {picture_path}")
        
        # Save the file
        form_picture.save(picture_path)
        print(f"✓ File saved successfully")
        
        # Verify file exists
        if os.path.exists(picture_path):
            file_size = os.path.getsize(picture_path)
            print(f"✓ File verified at: {picture_path}")
            print(f"  File size: {file_size} bytes")
            
            # Set proper permissions
            os.chmod(picture_path, 0o644)
            print(f"✓ File permissions set")
        else:
            raise Exception("File was not saved properly")
        
        return picture_fn
        
    except Exception as e:
        print(f"❌ Error in local save: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to save image locally: {str(e)}")

def save_picture(form_picture):
    """
    Main function to save uploaded picture
    Uses Cloudinary on Vercel, local storage for development
    """
    try:
        # Determine if running on Vercel
        is_vercel = os.environ.get('VERCEL_ENV') == 'production' or os.environ.get('VERCEL') == '1'
        
        print("\n" + "="*60)
        print("🔍 SAVE_PICTURE - Main Function")
        print(f"Environment: {'Vercel' if is_vercel else 'Local'}")
        print(f"Filename: {form_picture.filename}")
        print(f"Content Type: {form_picture.content_type}")
        print(f"Content Length: {form_picture.content_length}")
        
        if is_vercel:
            # On Vercel, use Cloudinary
            print("📤 Using Cloudinary for production upload...")
            result = save_picture_cloudinary(form_picture)
            print(f"✓ Cloudinary upload complete: {result[:50]}...")
            print("="*60 + "\n")
            return result
        else:
            # Local development - save to disk
            print("💻 Using local storage for development...")
            result = save_picture_local(form_picture)
            print(f"✓ Local save complete: {result}")
            print("="*60 + "\n")
            return result
            
    except Exception as e:
        print(f"❌ Error in save_picture: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to save image: {str(e)}")

# Optional: Function to delete image from Cloudinary
def delete_picture_cloudinary(image_url):
    """
    Delete an image from Cloudinary using its URL
    """
    try:
        if not init_cloudinary():
            return False
        
        # Extract public_id from URL
        # URL format: https://res.cloudinary.com/cloud_name/image/upload/v1234567/folder/public_id.jpg
        import re
        match = re.search(r'/upload/(?:v\d+/)?(.+?)\.(jpg|jpeg|png|gif)$', image_url)
        if match:
            public_id = match.group(1)
            print(f"Extracted public_id: {public_id}")
            
            result = cloudinary.uploader.destroy(public_id)
            print(f"Delete result: {result}")
            return result.get('result') == 'ok'
        else:
            print(f"Could not extract public_id from URL: {image_url}")
            return False
            
    except Exception as e:
        print(f"Error deleting from Cloudinary: {e}")
        return False

# Optional: Function to get image info from Cloudinary
def get_image_info_cloudinary(public_id):
    """
    Get information about an image from Cloudinary
    """
    try:
        if not init_cloudinary():
            return None
        
        result = cloudinary.api.resource(public_id)
        return result
    except Exception as e:
        print(f"Error getting image info: {e}")
        return None