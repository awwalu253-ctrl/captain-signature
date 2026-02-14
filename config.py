import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    
    # Use PostgreSQL on Vercel, SQLite locally
    if os.environ.get('VERCEL_ENV') == 'production':
        # Get database URL from environment (Vercel Postgres)
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '').replace('postgres://', 'postgresql://')
        if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    else:
        # Local development with SQLite
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = '/tmp'  # Use /tmp on Vercel (writable)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size