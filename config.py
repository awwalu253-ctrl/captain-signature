import os
import sys

class Config:
    # Secret key for session security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    # Check if running on Vercel
    IS_VERCEL = os.environ.get('VERCEL_ENV') == 'production' or os.environ.get('VERCEL') == '1'
    
    # --- Database Configuration with Explicit Error Checking ---
    print("********** DATABASE CONFIG DEBUG **********", file=sys.stderr)

    # Try multiple possible environment variable names
    potential_db_urls = [
        os.environ.get('DATABASE_URL'),
        os.environ.get('POSTGRES_URL'),
        os.environ.get('POSTGRES_PRISMA_URL')
    ]

    # Use the first one that is found
    database_url = None
    for url in potential_db_urls:
        if url:
            database_url = url
            print(f"✓ Found database URL from env var", file=sys.stderr)
            break

    if database_url is None:
        print("❌ CRITICAL: No DATABASE_URL, POSTGRES_URL, or POSTGRES_PRISMA_URL found in environment!", file=sys.stderr)
        print("❌ Falling back to SQLite. This WILL FAIL on Vercel.", file=sys.stderr)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
    else:
        # Fix PostgreSQL URL format if necessary
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            print(f"✓ Formatted URL to use 'postgresql://'", file=sys.stderr)

        SQLALCHEMY_DATABASE_URI = database_url
        print(f"✓ Using PostgreSQL database: {database_url.split('@')[-1][:20]}...", file=sys.stderr)
        
        # Add connection pooling and SSL options for Supabase
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 5,
            'max_overflow': 10,
            'pool_timeout': 30,
            'pool_recycle': 1800,
            'connect_args': {
                'sslmode': 'require'
            }
        }

    print("*******************************************", file=sys.stderr)
    # --- End Database Configuration ---

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Cloudinary Configuration for Image Uploads ---
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    
    # Check if Cloudinary is configured
    if IS_VERCEL:
        if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
            print("✓ Cloudinary configured for image uploads", file=sys.stderr)
        else:
            print("⚠ WARNING: Cloudinary not fully configured! Image uploads may fail on Vercel.", file=sys.stderr)
            print("  Please add CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET to Vercel env vars", file=sys.stderr)
    # --- End Cloudinary Configuration ---

    # Upload folder configuration (for local development only)
    if IS_VERCEL:
        # On Vercel, we use Cloudinary instead of local storage
        UPLOAD_FOLDER = '/tmp/captain_signature_uploads'  # Fallback only
        print(f"✓ Using Cloudinary for image uploads on Vercel", file=sys.stderr)
    else:
        # Local development
        project_root = os.path.dirname(os.path.abspath(__file__))
        UPLOAD_FOLDER = os.path.join(project_root, 'uploads')
        print(f"✓ Using local upload folder: {UPLOAD_FOLDER}", file=sys.stderr)

    # Max file size (16MB)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
    
    # Nigeria states for dropdown
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
    
    # Note: Paystack and Monnify configurations have been removed
    # The store now only accepts Cash on Delivery