from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta  # Add timedelta here
from time import time
import random
import string
import secrets


db = SQLAlchemy()

# Nigeria states for dropdown
NIGERIA_STATES = [
    'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue',
    'Borno', 'Cross River', 'Delta', 'Ebonyi', 'Edo', 'Ekiti', 'Enugu',
    'FCT - Abuja', 'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina',
    'Kebbi', 'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo',
    'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto', 'Taraba', 'Yobe', 'Zamfara'
]

def generate_order_number():
    """Generate a unique order number"""
    timestamp = datetime.now().strftime('%Y%m%d')
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"ORD-{timestamp}-{random_chars}"

class Settings(db.Model):
    """Global settings for the application"""
    id = db.Column(db.Integer, primary_key=True)
    delivery_fee = db.Column(db.Float, default=1500.00)
    free_delivery_threshold = db.Column(db.Float, default=0.00)
    currency = db.Column(db.String(10), default='₦')
    site_name = db.Column(db.String(100), default='Captain Signature')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    @staticmethod
    def get_settings():
        """Get or create settings with error handling"""
        try:
            settings = Settings.query.first()
            if not settings:
                settings = Settings()
                db.session.add(settings)
                db.session.commit()
            return settings
        except Exception as e:
            print(f"⚠ Error in get_settings: {e}")
            # Return a dummy settings object if database fails
            from types import SimpleNamespace
            return SimpleNamespace(
                delivery_fee=1500.00,
                free_delivery_threshold=0,
                currency='₦',
                site_name='Captain Signature'
            )

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state = db.Column(db.String(100), nullable=True)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image = db.Column(db.String(200), nullable=True)
    stock = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, default=generate_order_number)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')  # pending, processing, shipped, delivered, cancelled
    subtotal = db.Column(db.Float, default=0.0)
    delivery_fee = db.Column(db.Float, default=1500.00)
    total_amount = db.Column(db.Float, default=0.0)
    
    # Shipping Information (Nigeria only)
    shipping_name = db.Column(db.String(100), nullable=True)
    shipping_address = db.Column(db.Text, nullable=True)
    shipping_city = db.Column(db.String(100), nullable=True)
    shipping_state = db.Column(db.String(100), nullable=True)
    shipping_phone = db.Column(db.String(20), nullable=True)
    shipping_email = db.Column(db.String(120), nullable=True)
    
    # Tracking Information
    tracking_number = db.Column(db.String(100), nullable=True)
    carrier = db.Column(db.String(50), nullable=True)
    estimated_delivery = db.Column(db.DateTime, nullable=True)
    delivered_date = db.Column(db.DateTime, nullable=True)
    
    # Payment Information - SIMPLIFIED for Cash on Delivery only
    payment_method = db.Column(db.String(50), default='cash_on_delivery')
    payment_status = db.Column(db.String(50), default='pending')  # pending, paid
    
    # Notes
    admin_notes = db.Column(db.Text, nullable=True)
    customer_notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')
    tracking_updates = db.relationship('OrderTracking', backref='order', lazy=True, cascade='all, delete-orphan')

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    product_name = db.Column(db.String(100), nullable=True)
    product_image = db.Column(db.String(200), nullable=True)

class OrderTracking(db.Model):
    """Track order status updates"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.String(50), nullable=True)  # 'system', 'admin', 'carrier'
    
class PasswordResetToken(db.Model):
    """Store password reset tokens"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='reset_tokens')
    
    @staticmethod
    def generate_token(user_id):
        """Generate a unique reset token"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)  # Token valid for 24 hours
        return PasswordResetToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at
        )
    
    def is_valid(self):
        """Check if token is still valid"""
        return (not self.used and 
                datetime.utcnow() < self.expires_at)
    
    @staticmethod
    def can_request_new(user_id):
        """Check if user can request a new reset token"""
        # Get the most recent token for this user
        last_token = PasswordResetToken.query.filter_by(
            user_id=user_id
        ).order_by(PasswordResetToken.created_at.desc()).first()
        
        if not last_token:
            return True, None  # No previous tokens
        
        # Check if last token was created within the last 5 minutes
        time_since_last = datetime.utcnow() - last_token.created_at
        if time_since_last.total_seconds() < 300:  # 5 minutes
            wait_time = 300 - int(time_since_last.total_seconds())
            minutes = wait_time // 60
            seconds = wait_time % 60
            return False, f"Please wait {minutes} minute(s) and {seconds} second(s) before requesting another reset link."
        
        return True, None
    
class MaintenanceSettings(db.Model):
    """Maintenance mode settings stored in database"""
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False)
    message = db.Column(db.Text, default='We are currently performing scheduled maintenance. We\'ll be back shortly!')
    estimated_return = db.Column(db.String(100), default='soon')
    allowed_ips = db.Column(db.Text, default='127.0.0.1')  # Comma-separated IPs
    allowed_paths = db.Column(db.Text, default='/static,/admin/maintenance')  # Comma-separated paths
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    @staticmethod
    def get_settings():
        """Get or create maintenance settings"""
        try:
            settings = MaintenanceSettings.query.first()
            if not settings:
                settings = MaintenanceSettings()
                db.session.add(settings)
                db.session.commit()
            return settings
        except Exception as e:
            print(f"⚠ Error in MaintenanceSettings.get_settings: {e}")
            # Return a dummy settings object if database fails
            from types import SimpleNamespace
            return SimpleNamespace(
                enabled=False,
                message='Under Maintenance',
                estimated_return='soon',
                allowed_ips=['127.0.0.1'],
                allowed_paths=['/static', '/admin/maintenance']
            )
    
    def get_allowed_ips_list(self):
        """Convert comma-separated IPs to list"""
        if not self.allowed_ips:
            return ['127.0.0.1']
        return [ip.strip() for ip in self.allowed_ips.split(',') if ip.strip()]
    
    def get_allowed_paths_list(self):
        """Convert comma-separated paths to list"""
        if not self.allowed_paths:
            return ['/static', '/admin/maintenance']
        return [path.strip() for path in self.allowed_paths.split(',') if path.strip()]