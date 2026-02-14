import os
import tempfile

class Config:
    # Secret key for session security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    # Check if running on Vercel
    IS_VERCEL = os.environ.get('VERCEL_ENV') == 'production' or os.environ.get('VERCEL') == '1'
    
    # Database configuration
    database_url = os.environ.get('DATABASE_URL')
    
    # Fix PostgreSQL URL format (Vercel provides postgres:// but SQLAlchemy needs postgresql://)
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = database_url
        print(f"✓ Using PostgreSQL database")
    else:
        # Local development with SQLite
        SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
        print(f"✓ Using SQLite database for local development")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder configuration
    if IS_VERCEL:
        # On Vercel, use /tmp directory (writable)
        UPLOAD_FOLDER = '/tmp/captain_signature_uploads'
        print(f"✓ Using Vercel upload folder: {UPLOAD_FOLDER}")
    else:
        # Local development
        project_root = os.path.dirname(os.path.abspath(__file__))
        UPLOAD_FOLDER = os.path.join(project_root, 'uploads')
        print(f"✓ Using local upload folder: {UPLOAD_FOLDER}")
    
    # Max file size (16MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
    
    # Nigeria states (keep as is)
    NIGERIA_STATES = [
        'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue',
        'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu',
        'FCT - Abuja', 'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina',
        'Kebbi', 'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo',
        'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamfara'
    ]
    
    # Default delivery fee
    DEFAULT_DELIVERY_FEE = 1500.00
    
    # Default currency
    CURRENCY = '₦'
    
    # Site name
    SITE_NAME = 'Captain Signature'