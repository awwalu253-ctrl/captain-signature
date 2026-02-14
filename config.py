import os
import sys

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
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

    print("*******************************************", file=sys.stderr)
    # --- End Database Configuration ---

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload folder configuration (using /tmp on Vercel)
    if IS_VERCEL:
        UPLOAD_FOLDER = '/tmp/captain_signature_uploads'
        print(f"✓ Using Vercel upload folder: {UPLOAD_FOLDER}", file=sys.stderr)
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        UPLOAD_FOLDER = os.path.join(project_root, 'uploads')
        print(f"✓ Using local upload folder: {UPLOAD_FOLDER}", file=sys.stderr)

    # ... (rest of your config variables like MAX_CONTENT_LENGTH, NIGERIA_STATES, etc.) ...
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif'}
    NIGERIA_STATES = [ 'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 'FCT - Abuja', 'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamfara']
    DEFAULT_DELIVERY_FEE = 1500.00
    CURRENCY = '₦'
    SITE_NAME = 'Captain Signature'