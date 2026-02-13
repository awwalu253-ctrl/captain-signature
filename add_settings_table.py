# add_settings_table.py
import sqlite3
import os
from app import app, db
from models import Settings

def add_settings_table():
    """Add settings table to existing database"""
    db_path = os.path.join('instance', 'database.db')
    
    if not os.path.exists(db_path):
        print("Database doesn't exist. It will be created when you run the app.")
        return
    
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
        
        print("✓ Settings table added successfully")
        print(f"  Default delivery fee: ₦{settings.delivery_fee}")

if __name__ == '__main__':
    add_settings_table()