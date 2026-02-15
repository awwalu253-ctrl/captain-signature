import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
from flask import current_app

def init_cloudinary():
    """Initialize Cloudinary with app config"""
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET')
    )

def save_picture_cloudinary(form_picture):
    """
    Save uploaded picture to Cloudinary
    Returns: secure URL of uploaded image
    """
    try:
        # Initialize Cloudinary
        init_cloudinary()
        
        # Upload to Cloudinary
        result = cloudinary.uploader.upload(
            form_picture,
            folder="captain_signature/products",
            use_filename=True,
            unique_filename=True
        )
        
        print(f"✓ Image uploaded to Cloudinary: {result['secure_url']}")
        return result['secure_url']  # Return the full URL
        
    except Exception as e:
        print(f"❌ Cloudinary upload error: {e}")
        raise Exception(f"Failed to upload image: {str(e)}")