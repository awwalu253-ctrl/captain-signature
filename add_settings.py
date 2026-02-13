# add_settings.py
from app import app, db
from models import Settings

def add_settings_table():
    """Add settings table to database"""
    with app.app_context():
        # Create settings table
        db.create_all()
        
        # Create default settings if they don't exist
        settings = Settings.query.first()
        if not settings:
            settings = Settings()
            db.session.add(settings)
            db.session.commit()
            print("✓ Created default settings")
            print(f"  Default delivery fee: ₦{settings.delivery_fee}")
        else:
            print("✓ Settings already exist")
            print(f"  Current delivery fee: ₦{settings.delivery_fee}")
        
        print("Settings table is ready!")

if __name__ == '__main__':
    add_settings_table()