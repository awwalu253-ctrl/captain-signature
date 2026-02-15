import os
import sys
import traceback
import logging
from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_from_directory, send_file, session, g, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import text  # Added for proper SQL execution

# Try to import extensions, with helpful error messages
try:
    from flask_sqlalchemy import SQLAlchemy
except ImportError:
    print("Error: Flask-SQLAlchemy not installed. Run: pip install Flask-SQLAlchemy")
    sys.exit(1)

from config import Config
from models import db, User, Product, Order, OrderItem, OrderTracking, Settings, NIGERIA_STATES
from forms import LoginForm, SignupForm, ProductForm
from utils import save_picture
from cart import Cart
from paystack_utils import paystack
import secrets

app = Flask(__name__)
app.config.from_object(Config)

# Setup logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Print environment variables for debugging (remove in production)
print("=== ENVIRONMENT VARIABLES DEBUG ===")
print(f"DATABASE_URL: {'Set' if os.environ.get('DATABASE_URL') else 'NOT SET'}")
print(f"POSTGRES_URL: {'Set' if os.environ.get('POSTGRES_URL') else 'NOT SET'}")
print(f"POSTGRES_PRISMA_URL: {'Set' if os.environ.get('POSTGRES_PRISMA_URL') else 'NOT SET'}")
print(f"VERCEL_ENV: {os.environ.get('VERCEL_ENV', 'not set')}")
print("===================================")

# Function to ensure directories exist with proper permissions
def ensure_directories():
    """Create all necessary directories if they don't exist"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    user_home = os.path.expanduser("~")
    
    directories = [
        os.path.join(project_root, 'static'),
        os.path.join(project_root, 'static', 'css'),
        os.path.join(project_root, 'static', 'js'),
        os.path.join(project_root, 'static', 'images'),
        os.path.join(project_root, 'static', 'images', 'products'),
        os.path.join(project_root, 'templates'),
        os.path.join(project_root, 'templates', 'dashboard'),
        os.path.join(project_root, 'templates', 'admin'),
        os.path.join(project_root, 'instance'),
        os.path.join(user_home, 'captain_signature_uploads'),
        os.path.join(user_home, 'captain_signature_uploads', 'product_images'),
        # Add Vercel tmp directory for production
        '/tmp/captain_signature_uploads/products',
        '/tmp/captain_signature_uploads',
        '/tmp'
    ]
    
    print("=" * 50)
    print("Checking and creating directories...")
    
    for directory in directories:
        try:
            if not os.path.exists(directory):
                os.makedirs(directory, mode=0o777, exist_ok=True)
                print(f"✓ Created: {directory}")
            else:
                print(f"✓ Exists: {directory}")
                # Ensure permissions are set correctly
                os.chmod(directory, 0o777)
                
            # Check if writable
            if directory.startswith('/tmp'):
                print(f"  Note: {directory} is a temp directory")
                if os.path.exists(directory):
                    print(f"  Writable: {os.access(directory, os.W_OK)}")
                    print(f"  Readable: {os.access(directory, os.R_OK)}")
            elif not os.access(directory, os.W_OK):
                print(f"⚠ Warning: Directory not writable: {directory}")
                
        except Exception as e:
            print(f"✗ Error creating {directory}: {e}")
    
    print("=" * 50)
    return project_root

# Call the function to create directories
project_root = ensure_directories()
user_home = os.path.expanduser("~")
upload_folder = os.path.join(user_home, 'captain_signature_uploads', 'product_images')

# Make session, cart, and settings available to all templates
@app.before_request
def before_request():
    """Make cart and settings available to all templates"""
    # Initialize session if needed
    if 'cart' not in session:
        session['cart'] = {}
    
    # Make cart count available to all templates
    try:
        cart = Cart()
        g.cart_count = cart.get_total_items()
    except Exception as e:
        print(f"Error getting cart count: {e}")
        g.cart_count = 0
    
    # Make settings available to all templates
    try:
        # This will create default settings if they don't exist
        g.settings = Settings.get_settings()
    except Exception as e:
        print(f"Error getting settings: {e}")
        # Create a default settings object if there's an error
        from types import SimpleNamespace
        g.settings = SimpleNamespace(
            delivery_fee=1500.00,
            free_delivery_threshold=0,
            currency='₦',
            site_name='Captain Signature'
        )

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables and admin user
with app.app_context():
    try:
        # Create all tables
        db.create_all()
        print("✓ Database tables created/verified")
        
        # Create admin user if not exists
        if not User.query.filter_by(email='admin@captainsignature.com').first():
            admin = User(
                username='admin',
                email='admin@captainsignature.com',
                password=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin user created successfully!")
            print("  Email: admin@captainsignature.com")
            print("  Password: admin123")
        
        # Create default settings if not exists
        settings = Settings.query.first()
        if not settings:
            settings = Settings(
                delivery_fee=1500.00,
                free_delivery_threshold=0,
                currency='₦',
                site_name='Captain Signature'
            )
            db.session.add(settings)
            db.session.commit()
            print("✓ Default settings created successfully!")
            print(f"  Delivery fee: ₦{settings.delivery_fee}")
            
    except Exception as e:
        print(f"✗ Database initialization error: {e}")
        print(traceback.format_exc())

# Route to serve images from user's home directory
@app.route('/user-uploads/<filename>')
def user_uploads(filename):
    user_home = os.path.expanduser("~")
    upload_folder = os.path.join(user_home, 'captain_signature_uploads', 'product_images')
    return send_from_directory(upload_folder, filename)

# FIXED: Route to serve images from /tmp directory using send_file for better reliability
@app.route('/tmp-uploads/<filename>')
def tmp_uploads(filename):
    """Serve images from /tmp directory using send_file for better reliability"""
    directory = '/tmp/captain_signature_uploads/products'
    file_path = os.path.join(directory, filename)
    
    print(f"\n=== TMP UPLOADS DEBUG ===")
    print(f"Attempting to serve: {filename}")
    print(f"Full path: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
    
    if not os.path.exists(file_path):
        print(f"❌ File not found at path: {file_path}")
        # Try to list directory contents for debugging
        if os.path.exists(directory):
            files = os.listdir(directory)
            print(f"Files in directory: {files}")
        return "File not found", 404
    
    try:
        # Check file permissions
        print(f"File readable: {os.access(file_path, os.R_OK)}")
        print(f"File size: {os.path.getsize(file_path)} bytes")
        
        # Use send_file for more reliable serving
        response = make_response(send_file(file_path))
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['Content-Type'] = 'image/jpeg'
        print(f"✓ Successfully serving file: {filename}")
        return response
    except Exception as e:
        print(f"❌ Error serving {filename}: {e}")
        import traceback
        traceback.print_exc()
        return f"Error serving file: {str(e)}", 500

# Public debug route to check file existence (no login required)
@app.route('/public-debug-file/<filename>')
def public_debug_file(filename):
    """Public debug route to check if file exists (no login required)"""
    import os
    file_path = f'/tmp/captain_signature_uploads/products/{filename}'
    
    result = {
        'filename': filename,
        'file_path': file_path,
        'exists': os.path.exists(file_path),
        'tmp_uploads_url': url_for('tmp_uploads', filename=filename, _external=True)
    }
    
    if os.path.exists(file_path):
        result['size'] = os.path.getsize(file_path)
        result['permissions'] = oct(os.stat(file_path).st_mode)[-3:]
        result['readable'] = os.access(file_path, os.R_OK)
    
    return result

# Public route to test image serving (no login required)
@app.route('/public-test-image/<filename>')
def public_test_image(filename):
    """Public route to test image serving (no login required)"""
    directory = '/tmp/captain_signature_uploads/products'
    file_path = os.path.join(directory, filename)
    
    if not os.path.exists(file_path):
        return f"File not found: {file_path}", 404
    
    try:
        return send_file(file_path)
    except Exception as e:
        return f"Error: {str(e)}", 500

# Debug route to check file details
@app.route('/debug-file-check/<filename>')
def debug_file_check(filename):
    """Diagnose why a file isn't being served."""
    import os
    directory = '/tmp/captain_signature_uploads/products'
    full_path = os.path.join(directory, filename)
    
    result = {
        'filename': filename,
        'full_path': full_path,
        'file_exists': os.path.exists(full_path),
        'is_file': os.path.isfile(full_path) if os.path.exists(full_path) else None,
        'readable': os.access(full_path, os.R_OK) if os.path.exists(full_path) else None,
        'writable': os.access(full_path, os.W_OK) if os.path.exists(full_path) else None,
        'file_size': os.path.getsize(full_path) if os.path.exists(full_path) else None,
        'permissions': oct(os.stat(full_path).st_mode)[-3:] if os.path.exists(full_path) else None,
        'dir_exists': os.path.exists(directory),
        'dir_list': os.listdir(directory) if os.path.exists(directory) else [],
    }
    return result

@app.route('/find-all-files')
def find_all_files():
    """Search for image files in all possible tmp locations"""
    import os
    results = {}
    
    # Search common locations
    search_paths = [
        '/tmp',
        '/tmp/captain_signature_uploads',
        '/var/tmp'
    ]
    
    for base_path in search_paths:
        if os.path.exists(base_path):
            results[base_path] = []
            for root, dirs, files in os.walk(base_path):
                for file in files:
                    if file.endswith('.jpg') or file.endswith('.png'):
                        full_path = os.path.join(root, file)
                        results[base_path].append({
                            'file': file,
                            'path': full_path,
                            'size': os.path.getsize(full_path)
                        })
    
    return results

@app.route('/debug-upload-location')
def debug_upload_location():
    """Check where files are being saved by the upload function"""
    import tempfile
    return {
        'temp_dir': tempfile.gettempdir(),
        'cwd': os.getcwd(),
        'upload_folder_in_config': app.config.get('UPLOAD_FOLDER', 'Not set'),
        'project_root': project_root,
    }
    
# Find file in all possible locations
@app.route('/find-file/<filename>')
def find_file(filename):
    """Search for a file in all possible locations"""
    import os
    results = {}
    
    # Possible locations to check
    locations = [
        '/tmp/captain_signature_uploads/products',
        '/tmp/captain_signature_uploads',
        '/tmp',
        os.path.join(project_root, 'static', 'images', 'products'),
        os.path.join(project_root, 'uploads'),
        '/var/task',  # Vercel's working directory
        '/var/task/static/images/products',
        os.path.join(project_root, 'static', 'images'),
        os.path.join(project_root, 'static')
    ]
    
    for location in locations:
        full_path = os.path.join(location, filename)
        exists = os.path.exists(full_path)
        results[location] = {
            'exists': exists,
            'path': full_path if exists else None,
            'dir_exists': os.path.exists(location)
        }
        if exists:
            results[location]['size'] = os.path.getsize(full_path)
    
    return results

# Debug paths
@app.route('/debug-paths')
def debug_paths():
    """Show all relevant paths"""
    import os
    import tempfile
    
    tmp_uploads_dir = '/tmp/captain_signature_uploads/products'
    
    # Ensure directory exists with proper permissions
    os.makedirs(tmp_uploads_dir, mode=0o777, exist_ok=True)
    
    return {
        'cwd': os.getcwd(),
        'temp_dir': tempfile.gettempdir(),
        'project_root': project_root,
        'tmp_uploads': tmp_uploads_dir,
        'tmp_uploads_exists': os.path.exists(tmp_uploads_dir),
        'tmp_uploads_writable': os.access(tmp_uploads_dir, os.W_OK) if os.path.exists(tmp_uploads_dir) else False,
        'tmp_uploads_readable': os.access(tmp_uploads_dir, os.R_OK) if os.path.exists(tmp_uploads_dir) else False,
        'tmp_dir_list': os.listdir('/tmp') if os.path.exists('/tmp') else [],
        'tmp_uploads_list': os.listdir(tmp_uploads_dir) if os.path.exists(tmp_uploads_dir) else []
    }

# Debug route to check configuration
@app.route('/debug-config')
def debug_config():
    """Debug route to check configuration"""
    return {
        'database_uri': str(app.config['SQLALCHEMY_DATABASE_URI'])[:50] + '...',
        'is_vercel': app.config.get('IS_VERCEL', False),
        'database_url_env': 'set' if os.environ.get('DATABASE_URL') else 'not set',
        'postgres_url_env': 'set' if os.environ.get('POSTGRES_URL') else 'not set',
        'postgres_prisma_url_env': 'set' if os.environ.get('POSTGRES_PRISMA_URL') else 'not set',
    }

@app.route('/debug-cloudinary')
def debug_cloudinary():
    """Check Cloudinary configuration"""
    import os
    return {
        'cloud_name': os.environ.get('CLOUDINARY_CLOUD_NAME', 'NOT SET'),
        'api_key': 'SET' if os.environ.get('CLOUDINARY_API_KEY') else 'NOT SET',
        'api_secret': 'SET' if os.environ.get('CLOUDINARY_API_SECRET') else 'NOT SET',
        'is_vercel': app.config.get('IS_VERCEL', False),
    }

# Paystack Routes
@app.route('/initiate-payment/<int:order_id>')
@login_required
def initiate_payment(order_id):
    """Initiate Paystack payment for an order"""
    order = Order.query.get_or_404(order_id)
    
    # Verify order belongs to current user
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    # Check if order is already paid
    if order.payment_status == 'paid':
        flash('This order has already been paid for.', 'info')
        return redirect(url_for('track_order_result', order_number=order.order_number))
    
    # Initialize Paystack transaction
    callback_url = url_for('payment_callback', _external=True)
    
    # Add order details to metadata
    metadata = {
        'order_id': order.id,
        'order_number': order.order_number,
        'customer_name': current_user.username,
        'customer_email': current_user.email
    }
    
    response = paystack.initialize_transaction(
        email=current_user.email,
        amount=order.total_amount,
        reference=f"ORDER-{order.order_number}",
        callback_url=callback_url,
        metadata=metadata
    )
    
    if response['status']:
        # Save payment details to order
        order.payment_reference = response['data']['reference']
        order.payment_access_code = response['data']['access_code']
        order.payment_authorization_url = response['data']['authorization_url']
        order.paystack_response = response
        db.session.commit()
        
        # Redirect to Paystack payment page
        return redirect(response['data']['authorization_url'])
    else:
        flash(f'Payment initiation failed: {response.get("message", "Unknown error")}', 'danger')
        return redirect(url_for('checkout'))

@app.route('/payment-callback')
def payment_callback():
    """Handle Paystack callback after payment"""
    reference = request.args.get('reference')
    
    if not reference:
        flash('No payment reference provided.', 'danger')
        return redirect(url_for('index'))
    
    # Verify transaction
    response = paystack.verify_transaction(reference)
    
    if response['status'] and response['data']['status'] == 'success':
        # Find order by reference
        order = Order.query.filter_by(payment_reference=reference).first()
        
        if order:
            # Update order payment status
            order.payment_status = 'paid'
            order.paid_at = datetime.utcnow()
            order.status = 'processing'  # Auto-mark as processing after payment
            db.session.commit()
            
            flash('Payment successful! Your order is now being processed.', 'success')
            return redirect(url_for('track_order_result', order_number=order.order_number))
        else:
            flash('Payment successful but order not found. Please contact support.', 'warning')
            return redirect(url_for('index'))
    else:
        flash(f'Payment verification failed: {response.get("message", "Unknown error")}', 'danger')
        return redirect(url_for('index'))

@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():
    """Paystack webhook endpoint for real-time notifications"""
    import json
    
    # Get the payload
    payload = request.get_data(as_text=True)
    signature = request.headers.get('x-paystack-signature')
    
    # Verify webhook signature (optional but recommended)
    # You should implement signature verification here
    
    try:
        event = json.loads(payload)
        
        # Handle different event types
        if event['event'] == 'charge.success':
            data = event['data']
            reference = data['reference']
            
            # Find and update order
            order = Order.query.filter_by(payment_reference=reference).first()
            if order and order.payment_status != 'paid':
                order.payment_status = 'paid'
                order.paid_at = datetime.utcnow()
                order.status = 'processing'
                db.session.commit()
                
                print(f"✅ Webhook: Order {order.order_number} marked as paid")
        
        return {'status': 'success'}, 200
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return {'status': 'error'}, 500

@app.route('/payment-cancel/<int:order_id>')
@login_required
def payment_cancel(order_id):
    """Handle cancelled payment"""
    order = Order.query.get_or_404(order_id)
    flash('Payment was cancelled. You can try again.', 'warning')
    return redirect(url_for('checkout'))

# Debug route to check database connection - FIXED with text()
@app.route('/debug-db')
def debug_db():
    try:
        # Test database connection using text() for raw SQL
        result = db.session.execute(text('SELECT 1')).scalar()
        return {
            'status': 'connected',
            'result': result,
            'database_url': os.environ.get('DATABASE_URL', 'not set')[:20] + '...' if os.environ.get('DATABASE_URL') else 'not set'
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }, 500

# Debug route to check uploaded files
@app.route('/debug-uploads')
def debug_uploads():
    """Debug route to check uploaded files"""
    import os
    results = []
    
    # Check Vercel tmp directory
    tmp_path = '/tmp/captain_signature_uploads/products'
    results.append(f"<h3>Checking: {tmp_path}</h3>")
    
    if os.path.exists(tmp_path):
        results.append(f"✓ Directory exists")
        results.append(f"  Permissions: {oct(os.stat(tmp_path).st_mode)[-3:]}")
        results.append(f"  Readable: {os.access(tmp_path, os.R_OK)}")
        results.append(f"  Writable: {os.access(tmp_path, os.W_OK)}")
        
        try:
            files = os.listdir(tmp_path)
            results.append(f"Found {len(files)} files:")
            for f in files[-10:]:  # Show last 10 files
                file_path = os.path.join(tmp_path, f)
                size = os.path.getsize(file_path)
                perms = oct(os.stat(file_path).st_mode)[-3:]
                results.append(f"  - {f} ({size} bytes, permissions: {perms})")
        except Exception as e:
            results.append(f"✗ Error listing files: {e}")
    else:
        results.append(f"✗ Directory does NOT exist")
        # Try to create it
        try:
            os.makedirs(tmp_path, mode=0o777, exist_ok=True)
            results.append(f"✓ Created directory")
        except Exception as e:
            results.append(f"✗ Failed to create: {e}")
    
    # Check local upload folder
    local_path = os.path.join(project_root, 'static', 'images', 'products')
    results.append(f"<h3>Checking local: {local_path}</h3>")
    if os.path.exists(local_path):
        results.append(f"✓ Local directory exists")
        try:
            files = os.listdir(local_path)
            results.append(f"Found {len(files)} files")
        except Exception as e:
            results.append(f"✗ Error: {e}")
    else:
        results.append(f"✗ Local directory does NOT exist")
    
    # Also check database for image paths
    results.append("<h3>Products in Database</h3>")
    try:
        products = Product.query.limit(10).all()
        for p in products:
            results.append(f"Product {p.id}: {p.name} - Image: {p.image}")
    except Exception as e:
        results.append(f"Error querying products: {e}")
    
    return "<br>".join(results)

# Debug product route
@app.route('/debug-product/<int:product_id>')
def debug_product(product_id):
    """Debug a specific product"""
    product = Product.query.get_or_404(product_id)
    
    # Generate the image URL based on type
    if product.image:
        if product.image.startswith('tmp:'):
            filename = product.image.replace('tmp:', '')
            img_url = url_for('tmp_uploads', filename=filename, _external=True)
        elif product.image.startswith('user_uploads:'):
            filename = product.image.replace('user_uploads:', '')
            img_url = url_for('user_uploads', filename=filename, _external=True)
        else:
            img_url = url_for('static', filename='images/products/' + product.image, _external=True)
    else:
        img_url = None
    
    # Check if file exists
    file_exists = None
    if product.image and product.image.startswith('tmp:'):
        filename = product.image.replace('tmp:', '')
        file_path = f'/tmp/captain_signature_uploads/products/{filename}'
        file_exists = os.path.exists(file_path)
    
    return {
        'product_id': product.id,
        'name': product.name,
        'image_path': product.image,
        'generated_url': img_url,
        'file_exists': file_exists,
        'file_readable': os.access(file_path, os.R_OK) if file_exists else None
    }

# Routes
@app.route('/')
def index():
    try:
        products = Product.query.limit(8).all()
    except:
        products = []
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data if hasattr(form, 'remember') else False)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Basic validation
            if not username or not email or not password:
                flash('All fields are required', 'danger')
                return render_template('signup.html', form=SignupForm())
            
            # Check if user exists
            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'danger')
                return render_template('signup.html', form=SignupForm())
            
            if User.query.filter_by(username=username).first():
                flash('Username already taken', 'danger')
                return render_template('signup.html', form=SignupForm())
            
            # Create user
            hashed_password = generate_password_hash(password)
            user = User(
                username=username,
                email=email,
                password=hashed_password
            )
            db.session.add(user)
            db.session.commit()
            
            flash('Account created! You can now log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            print(f"Signup error: {str(e)}")
            print(traceback.format_exc())
            flash('Registration failed. Please try again.', 'danger')
            return render_template('signup.html', form=SignupForm())
    
    form = SignupForm()
    return render_template('signup.html', form=form)

@app.route('/test-write')
def test_write():
    try:
        # Test creating a test user
        test_user = User(
            username=f"test_{datetime.now().timestamp()}",
            email=f"test_{datetime.now().timestamp()}@test.com",
            password=generate_password_hash('test123')
        )
        db.session.add(test_user)
        db.session.commit()
        db.session.delete(test_user)
        db.session.commit()
        return {"status": "success", "message": "Database write test passed"}
    except Exception as e:
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}, 500

@app.route('/init-db')
def init_db():
    try:
        db.create_all()
        return "Database tables created successfully!"
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        # Get current datetime
        now = datetime.now()
        
        # Basic stats
        total_users = User.query.count()
        total_products = Product.query.count()
        total_orders = Order.query.count()
        
        # Today's new users
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        new_users_today = User.query.filter(User.created_at >= today_start).count()
        
        # New products this month
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_products_this_month = Product.query.filter(Product.created_at >= month_start).count()
        
        # Pending orders count
        pending_orders_count = Order.query.filter_by(status='pending').count()
        
        # Total revenue
        total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
        
        # Revenue growth (compare to last month)
        last_month_start = (datetime.now().replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_revenue = db.session.query(db.func.sum(Order.total_amount))\
            .filter(Order.order_date >= last_month_start)\
            .filter(Order.order_date < month_start).scalar() or 0
        revenue_growth = ((total_revenue - last_month_revenue) / last_month_revenue * 100) if last_month_revenue > 0 else 0
        
        # Recent orders (last 5)
        recent_orders = Order.query.order_by(Order.order_date.desc()).limit(5).all()
        
        # Inventory stats
        low_stock_count = Product.query.filter(Product.stock <= 5).filter(Product.stock > 0).count()
        out_of_stock_count = Product.query.filter_by(stock=0).count()
        in_stock_count = Product.query.filter(Product.stock > 5).count()
        
        # Recent activities
        recent_activities = []
        
        # Add recent orders to activity
        for order in recent_orders[:2]:
            recent_activities.append({
                'icon': 'shopping-cart',
                'description': f'New order #{order.order_number}',
                'time': f'{order.order_date.strftime("%H:%M")}'
            })
        
        # Add recent users to activity
        recent_users = User.query.order_by(User.created_at.desc()).limit(2).all()
        for user in recent_users:
            recent_activities.append({
                'icon': 'user',
                'description': f'New user registered: {user.username}',
                'time': f'{user.created_at.strftime("%H:%M")}'
            })
        
        return render_template('dashboard/admin.html',
                             now=now,
                             total_users=total_users,
                             new_users_today=new_users_today,
                             total_products=total_products,
                             new_products_this_month=new_products_this_month,
                             total_orders=total_orders,
                             pending_orders_count=pending_orders_count,
                             total_revenue=total_revenue,
                             revenue_growth=round(revenue_growth, 1),
                             recent_orders=recent_orders,
                             low_stock_count=low_stock_count,
                             out_of_stock_count=out_of_stock_count,
                             in_stock_count=in_stock_count,
                             recent_activities=recent_activities)
    else:
        # Customer dashboard
        orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.order_date.desc()).all()
        return render_template('dashboard/customer.html', orders=orders)
        
@app.route('/products')
def products():
    category = request.args.get('category')
    if category:
        products = Product.query.filter_by(category=category).all()
    else:
        products = Product.query.all()
    return render_template('products.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

# Cart Routes
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    """Add product to cart"""
    product = Product.query.get_or_404(product_id)
    
    # Get quantity from form
    quantity = int(request.form.get('quantity', 1))
    
    # Check stock
    if quantity > product.stock:
        flash(f'Sorry, only {product.stock} items available.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    # Initialize cart
    cart = Cart()
    
    # Add to cart
    cart.add(
        product_id=product.id,
        quantity=quantity,
        price=product.price,
        name=product.name,
        image=product.image
    )
    
    flash(f'{product.name} added to cart!', 'success')
    
    # Redirect to cart page to prevent form resubmission
    return redirect(url_for('view_cart'))

@app.route('/cart')
def view_cart():
    """View cart page"""
    cart = Cart()
    settings = Settings.get_settings()
    
    cart_items = []
    for product_id, item in cart.get_cart().items():
        product = Product.query.get(int(product_id))
        if product:
            cart_items.append({
                'product': product,
                'quantity': item['quantity'],
                'subtotal': item['price'] * item['quantity']
            })
    
    subtotal = cart.get_subtotal()
    
    # Check if order qualifies for free delivery
    if settings.free_delivery_threshold > 0 and subtotal >= settings.free_delivery_threshold:
        delivery_fee = 0
        free_delivery_message = f"FREE DELIVERY (Orders above {settings.currency}{settings.free_delivery_threshold:,.0f})"
    else:
        delivery_fee = settings.delivery_fee
        free_delivery_message = None
    
    total = subtotal + delivery_fee
    
    return render_template('cart.html', 
                         cart_items=cart_items, 
                         subtotal=subtotal,
                         delivery_fee=delivery_fee,
                         total=total,
                         settings=settings,
                         free_delivery_message=free_delivery_message)

@app.route('/update_cart/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    """Update cart item quantity"""
    quantity = int(request.form.get('quantity', 0))
    cart = Cart()
    
    product = Product.query.get_or_404(product_id)
    
    if quantity > product.stock:
        flash(f'Sorry, only {product.stock} items available.', 'danger')
        return redirect(url_for('view_cart'))
    
    cart.update(product_id, quantity)
    
    if quantity == 0:
        flash('Item removed from cart.', 'info')
    else:
        flash('Cart updated successfully.', 'success')
    
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    """Remove item from cart"""
    cart = Cart()
    cart.remove(product_id)
    flash('Item removed from cart.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/clear_cart')
def clear_cart():
    """Clear entire cart"""
    cart = Cart()
    cart.clear()
    flash('Cart has been cleared.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Checkout page"""
    cart = Cart()
    settings = Settings.get_settings()
    
    if cart.get_total_items() == 0:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('view_cart'))
    
    if request.method == 'POST':
        # Get form data
        shipping_name = request.form.get('shipping_name')
        shipping_address = request.form.get('shipping_address')
        shipping_city = request.form.get('shipping_city')
        shipping_state = request.form.get('shipping_state')
        shipping_phone = request.form.get('shipping_phone')
        payment_method = request.form.get('payment_method', 'paystack')
        customer_notes = request.form.get('customer_notes')
        
        # Validate Nigerian state
        if shipping_state not in NIGERIA_STATES:
            flash('Please select a valid Nigerian state.', 'danger')
            return redirect(url_for('checkout'))
        
        # Calculate totals
        subtotal = cart.get_subtotal()
        
        # Check if order qualifies for free delivery
        if settings.free_delivery_threshold > 0 and subtotal >= settings.free_delivery_threshold:
            delivery_fee = 0
        else:
            delivery_fee = settings.delivery_fee
        
        total_amount = subtotal + delivery_fee
        
        # Create order
        order = Order(
            user_id=current_user.id,
            status='pending',
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            total_amount=total_amount,
            shipping_name=shipping_name,
            shipping_address=shipping_address,
            shipping_city=shipping_city,
            shipping_state=shipping_state,
            shipping_phone=shipping_phone,
            shipping_email=current_user.email,
            payment_method=payment_method,
            payment_status='pending',
            customer_notes=customer_notes
        )
        
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Add order items
        for product_id, item in cart.get_cart().items():
            product = Product.query.get(int(product_id))
            
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item['quantity'],
                price=item['price'],
                product_name=product.name,
                product_image=product.image
            )
            db.session.add(order_item)
            
            # Update stock
            product.stock -= item['quantity']
        
        # Add initial tracking update
        tracking = OrderTracking(
            order_id=order.id,
            status='pending',
            description='Order placed successfully',
            updated_by='system'
        )
        db.session.add(tracking)
        
        db.session.commit()
        
        # Clear cart
        cart.clear()
        
        # If payment method is paystack, redirect to payment
        if payment_method == 'paystack':
            return redirect(url_for('initiate_payment', order_id=order.id))
        
        flash(f'Order #{order.order_number} placed successfully!', 'success')
        return redirect(url_for('track_order_result', order_number=order.order_number))
    
    # GET request - show checkout form
    cart_items = []
    for product_id, item in cart.get_cart().items():
        product = Product.query.get(int(product_id))
        if product:
            cart_items.append({
                'product': product,
                'quantity': item['quantity'],
                'subtotal': item['price'] * item['quantity'],
                'image': product.image
            })
    
    subtotal = cart.get_subtotal()
    
    # Check if order qualifies for free delivery
    if settings.free_delivery_threshold > 0 and subtotal >= settings.free_delivery_threshold:
        delivery_fee = 0
        free_delivery_message = f"FREE DELIVERY (Orders above {settings.currency}{settings.free_delivery_threshold:,.0f})"
    else:
        delivery_fee = settings.delivery_fee
        free_delivery_message = None
    
    total = subtotal + delivery_fee
    
    return render_template('checkout.html', 
                         cart_items=cart_items, 
                         subtotal=subtotal,
                         delivery_fee=delivery_fee,
                         total=total, 
                         user=current_user,
                         states=NIGERIA_STATES,
                         settings=settings,
                         free_delivery_message=free_delivery_message)

# Order Tracking Routes
@app.route('/track', methods=['GET', 'POST'])
def track_order_page():
    """Page to enter order tracking information"""
    if request.method == 'POST':
        order_number = request.form.get('order_number')
        email = request.form.get('email')
        
        # Debug print
        print(f"Searching for order: {order_number} with email: {email}")
        
        # Look up the order
        order = Order.query.filter_by(order_number=order_number).first()
        
        if order:
            print(f"Order found: {order.order_number}, Customer email: {order.customer.email if order.customer else 'No customer'}, Shipping email: {order.shipping_email}")
            
            # Check if email matches either customer email or shipping email
            customer_email = order.customer.email if order.customer else None
            if (customer_email and customer_email.lower() == email.lower()) or (order.shipping_email and order.shipping_email.lower() == email.lower()):
                return redirect(url_for('track_order_result', order_number=order.order_number))
            else:
                flash('Email does not match this order.', 'danger')
        else:
            flash('Order not found. Please check your order number and email.', 'danger')
            
        return redirect(url_for('track_order_page'))
    
    return render_template('track_order.html')

@app.route('/track/<order_number>')
def track_order_result(order_number):
    """Display order tracking information"""
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    return render_template('order_tracking_result.html', order=order)

# Admin routes
@app.route('/admin/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        abort(403)
    
    form = ProductForm()
    if form.validate_on_submit():
        image_file = None
        if form.image.data:
            try:
                # Debug information
                print(f"\n--- Image Upload Debug ---")
                print(f"Form image data: {form.image.data}")
                print(f"Filename: {form.image.data.filename}")
                
                # Check if file was uploaded
                if form.image.data.filename:
                    # Validate file extension
                    allowed_extensions = ['jpg', 'jpeg', 'png', 'gif']
                    file_ext = form.image.data.filename.rsplit('.', 1)[1].lower() if '.' in form.image.data.filename else ''
                    
                    if file_ext not in allowed_extensions:
                        flash(f'Invalid file type. Allowed: {", ".join(allowed_extensions)}', 'danger')
                        return render_template('add_product.html', form=form)
                    
                    image_file = save_picture(form.image.data)
                    flash('Image uploaded successfully!', 'success')
                    print(f"Image saved as: {image_file}")
                else:
                    flash('No image selected.', 'warning')
            except Exception as e:
                flash(f'Error uploading image: {str(e)}', 'danger')
                print(f"Image upload error: {str(e)}")
                traceback.print_exc()
                return render_template('add_product.html', form=form)
        
        # Create new product
        product = Product(
            name=form.name.data,
            description=form.description.data,
            price=form.price.data,
            category=form.category.data,
            stock=form.stock.data,
            image=image_file
        )
        
        try:
            db.session.add(product)
            db.session.commit()
            flash(f'Product "{product.name}" has been added successfully!', 'success')
            return redirect(url_for('admin_products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving product: {str(e)}', 'danger')
            print(f"Database error: {e}")
    
    return render_template('add_product.html', form=form)

@app.route('/admin/customers')
@login_required
def admin_customers():
    """View all registered customers"""
    if not current_user.is_admin:
        abort(403)
    
    # Get current datetime for the template
    now = datetime.now()
    
    # Get all users (excluding admins if you want)
    customers = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all()
    
    # Get stats
    total_customers = len(customers)
    new_today = sum(1 for c in customers if c.created_at.date() == datetime.today().date())
    
    return render_template('admin/customers.html', 
                         customers=customers,
                         total_customers=total_customers,
                         new_today=new_today,
                         now=now)

@app.context_processor
def inject_now():
    """Inject current datetime into all templates"""
    return {'now': datetime.now()}

@app.route('/admin/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if not current_user.is_admin:
        abort(403)
    
    product = Product.query.get_or_404(product_id)
    form = ProductForm()
    
    if request.method == 'GET':
        # Populate form with existing product data
        form.name.data = product.name
        form.description.data = product.description
        form.price.data = product.price
        form.category.data = product.category
        form.stock.data = product.stock
    
    if form.validate_on_submit():
        # Update product with form data
        product.name = form.name.data
        product.description = form.description.data
        product.price = form.price.data
        product.category = form.category.data
        product.stock = form.stock.data
        
        # Handle image upload if a new image was provided
        if form.image.data and form.image.data.filename:
            try:
                print(f"\n--- Image Update Debug ---")
                print(f"Updating image for product: {product.name}")
                
                # Delete old image if it exists
                if product.image:
                    if product.image.startswith('user_uploads:'):
                        # Delete from user folder
                        filename = product.image.replace('user_uploads:', '')
                        user_home = os.path.expanduser("~")
                        old_image_path = os.path.join(user_home, 'captain_signature_uploads', 'product_images', filename)
                    elif product.image.startswith('tmp:'):
                        # Delete from tmp folder
                        filename = product.image.replace('tmp:', '')
                        old_image_path = os.path.join('/tmp/captain_signature_uploads/products', filename)
                    else:
                        # Delete from static folder
                        old_image_path = os.path.join(project_root, 'static', 'images', 'products', product.image)
                    
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                        print(f"Deleted old image: {old_image_path}")
                
                # Save new image
                product.image = save_picture(form.image.data)
                flash('New image uploaded successfully!', 'success')
                print(f"New image saved as: {product.image}")
                
            except Exception as e:
                flash(f'Error uploading image: {str(e)}', 'danger')
                print(f"Image upload error: {e}")
                traceback.print_exc()
                return render_template('edit_product.html', form=form, product=product)
        
        try:
            db.session.commit()
            flash(f'Product "{product.name}" has been updated successfully!', 'success')
            return redirect(url_for('admin_products'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
            print(f"Database error: {e}")
    
    return render_template('edit_product.html', form=form, product=product)

@app.route('/admin/products')
@login_required
def admin_products():
    if not current_user.is_admin:
        abort(403)
    
    products = Product.query.all()
    return render_template('admin_products.html', products=products)

@app.route('/admin/delete_product/<int:product_id>')
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
        abort(403)
    
    product = Product.query.get_or_404(product_id)
    product_name = product.name
    
    # Delete the image file if it exists
    if product.image:
        try:
            if product.image.startswith('user_uploads:'):
                # Delete from user folder
                filename = product.image.replace('user_uploads:', '')
                user_home = os.path.expanduser("~")
                image_path = os.path.join(user_home, 'captain_signature_uploads', 'product_images', filename)
            elif product.image.startswith('tmp:'):
                # Delete from tmp folder
                filename = product.image.replace('tmp:', '')
                image_path = os.path.join('/tmp/captain_signature_uploads/products', filename)
            else:
                # Delete from static folder
                image_path = os.path.join(project_root, 'static', 'images', 'products', product.image)
            
            if os.path.exists(image_path):
                os.remove(image_path)
                print(f"Deleted image: {image_path}")
        except Exception as e:
            print(f"Error deleting image file: {e}")
    
    db.session.delete(product)
    db.session.commit()
    flash(f'Product "{product_name}" has been deleted!', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        abort(403)
    
    orders = Order.query.order_by(Order.order_date.desc()).all()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/update_order/<int:order_id>/<status>')
@login_required
def update_order_status(order_id, status):
    if not current_user.is_admin:
        abort(403)
    
    valid_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
    if status not in valid_statuses:
        flash('Invalid status', 'danger')
        return redirect(url_for('admin_orders'))
    
    order = Order.query.get_or_404(order_id)
    old_status = order.status
    order.status = status
    
    # Add tracking update
    tracking = OrderTracking(
        order_id=order.id,
        status=status,
        description=f'Order status updated from {old_status} to {status}',
        updated_by='admin'
    )
    db.session.add(tracking)
    
    if status == 'delivered':
        order.delivered_date = datetime.utcnow()
    
    db.session.commit()
    flash(f'Order #{order_id} status updated to {status}', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/update_tracking/<int:order_id>', methods=['GET', 'POST'])
@login_required
def update_tracking(order_id):
    if not current_user.is_admin:
        abort(403)
    
    order = Order.query.get_or_404(order_id)
    
    if request.method == 'POST':
        # Update tracking information
        order.tracking_number = request.form.get('tracking_number')
        order.carrier = request.form.get('carrier')
        order.status = request.form.get('status')
        
        # Add tracking update
        if request.form.get('tracking_description'):
            tracking = OrderTracking(
                order_id=order.id,
                status=order.status,
                location=request.form.get('location'),
                description=request.form.get('tracking_description'),
                updated_by='admin'
            )
            db.session.add(tracking)
        
        # Update estimated delivery
        if request.form.get('estimated_delivery'):
            try:
                order.estimated_delivery = datetime.strptime(request.form.get('estimated_delivery'), '%Y-%m-%d')
            except:
                pass
        
        db.session.commit()
        flash(f'Tracking information updated for order #{order.order_number}', 'success')
        return redirect(url_for('admin_orders'))
    
    return render_template('update_tracking.html', order=order)

@app.route('/admin/bulk_tracking_update', methods=['POST'])
@login_required
def bulk_tracking_update():
    if not current_user.is_admin:
        abort(403)
    
    order_ids = request.form.getlist('order_ids')
    status = request.form.get('bulk_status')
    
    if order_ids and status:
        updated_count = 0
        for order_id in order_ids:
            order = Order.query.get(order_id)
            if order:
                old_status = order.status
                order.status = status
                # Add tracking update
                tracking = OrderTracking(
                    order_id=order.id,
                    status=status,
                    description=f'Bulk status update from {old_status} to {status}',
                    updated_by='admin'
                )
                db.session.add(tracking)
                updated_count += 1
        
        db.session.commit()
        flash(f'Updated {updated_count} orders to {status}', 'success')
    
    return redirect(url_for('admin_orders'))

# Settings route
@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Admin settings page"""
    if not current_user.is_admin:
        abort(403)
    
    settings = Settings.get_settings()
    
    if request.method == 'POST':
        try:
            # Update settings
            new_delivery_fee = float(request.form.get('delivery_fee', 1500.00))
            new_threshold = float(request.form.get('free_delivery_threshold', 0))
            new_site_name = request.form.get('site_name', 'Captain Signature')
            new_currency = request.form.get('currency', '₦')
            
            settings.delivery_fee = new_delivery_fee
            settings.free_delivery_threshold = new_threshold
            settings.site_name = new_site_name
            settings.currency = new_currency
            settings.updated_by = current_user.id
            
            db.session.commit()
            flash('Settings updated successfully!', 'success')
            
            # Update g object
            g.settings = settings
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating settings: {str(e)}', 'danger')
            print(f"Settings update error: {e}")
        
        return redirect(url_for('admin_settings'))
    
    return render_template('admin/settings.html', settings=settings)

# Test route to verify upload location
@app.route('/admin/test-upload-location')
@login_required
def test_upload_location():
    if not current_user.is_admin:
        abort(403)
    
    user_home = os.path.expanduser("~")
    upload_folder = os.path.join(user_home, 'captain_signature_uploads', 'product_images')
    
    results = []
    results.append(f"<h3>Upload Location Test</h3>")
    results.append(f"<p><strong>User home:</strong> {user_home}</p>")
    results.append(f"<p><strong>Upload folder:</strong> {upload_folder}</p>")
    
    # Check if directory exists
    if os.path.exists(upload_folder):
        results.append(f"<p style='color: green;'>✓ Upload folder exists</p>")
        
        # Check if writable
        if os.access(upload_folder, os.W_OK):
            results.append(f"<p style='color: green;'>✓ Upload folder is writable</p>")
            
            # Try to write a test file
            try:
                test_file = os.path.join(upload_folder, 'test.txt')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                results.append(f"<p style='color: green;'>✓ Write test passed</p>")
            except Exception as e:
                results.append(f"<p style='color: red;'>✗ Write test failed: {e}</p>")
        else:
            results.append(f"<p style='color: red;'>✗ Upload folder is NOT writable</p>")
    else:
        results.append(f"<p style='color: red;'>✗ Upload folder does NOT exist</p>")
        # Try to create it
        try:
            os.makedirs(upload_folder, exist_ok=True)
            results.append(f"<p style='color: green;'>✓ Successfully created upload folder</p>")
        except Exception as e:
            results.append(f"<p style='color: red;'>✗ Failed to create upload folder: {e}</p>")
    
    return "<br>".join(results)

@app.route('/debug-full')
def debug_full():
    """Comprehensive database diagnostic"""
    results = []
    
    # 1. Check environment variables
    results.append("=== ENVIRONMENT VARIABLES ===")
    results.append(f"DATABASE_URL: {'SET' if os.environ.get('DATABASE_URL') else 'NOT SET'}")
    results.append(f"POSTGRES_URL: {'SET' if os.environ.get('POSTGRES_URL') else 'NOT SET'}")
    
    # 2. Check config
    results.append("\n=== DATABASE CONFIG ===")
    results.append(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')[:50]}...")
    
    # 3. Test raw connection
    results.append("\n=== TESTING RAW CONNECTION ===")
    try:
        from sqlalchemy import create_engine
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            results.append(f"✓ Raw connection successful: {result}")
    except Exception as e:
        results.append(f"✗ Raw connection failed: {str(e)}")
    
    # 4. Test SQLAlchemy connection
    results.append("\n=== TESTING SQLALCHEMY CONNECTION ===")
    try:
        result = db.session.execute(text("SELECT 1")).scalar()
        results.append(f"✓ SQLAlchemy connection successful: {result}")
    except Exception as e:
        results.append(f"✗ SQLAlchemy connection failed: {str(e)}")
    
    # 5. Check if tables exist
    results.append("\n=== CHECKING TABLES ===")
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        results.append(f"Tables in database: {tables}")
    except Exception as e:
        results.append(f"✗ Could not get tables: {str(e)}")
    
    # 6. Test creating a user
    results.append("\n=== TESTING USER CREATION ===")
    try:
        test_username = f"test_{datetime.now().timestamp()}"
        test_email = f"{test_username}@test.com"
        
        test_user = User(
            username=test_username,
            email=test_email,
            password=generate_password_hash('test123')
        )
        db.session.add(test_user)
        db.session.commit()
        results.append(f"✓ Test user created successfully")
        
        # Clean up
        db.session.delete(test_user)
        db.session.commit()
        results.append(f"✓ Test user cleaned up")
    except Exception as e:
        db.session.rollback()
        results.append(f"✗ User creation failed: {str(e)}")
        results.append(f"Traceback: {traceback.format_exc()}")
    
    return "<br>".join(results)

# Debug route to check images
@app.route('/admin/debug-images')
@login_required
def debug_images():
    if not current_user.is_admin:
        abort(403)
    
    products = Product.query.all()
    result = "<h2>Product Image Debug</h2>"
    result += "<table border='1' cellpadding='10'>"
    result += "<tr><th>ID</th><th>Name</th><th>Image Path in DB</th><th>Image Type</th><th>Expected URL</th></tr>"
    
    for product in products:
        if product.image:
            if product.image.startswith('user_uploads:'):
                filename = product.image.replace('user_uploads:', '')
                img_type = "User Uploads"
                img_url = url_for('user_uploads', filename=filename, _external=True)
            elif product.image.startswith('tmp:'):
                filename = product.image.replace('tmp:', '')
                img_type = "Temp Uploads"
                img_url = url_for('tmp_uploads', filename=filename, _external=True)
            else:
                img_type = "Static"
                img_url = url_for('static', filename='images/products/' + product.image, _external=True)
        else:
            img_type = "No Image"
            img_url = "None"
        
        result += f"<tr>"
        result += f"<td>{product.id}</td>"
        result += f"<td>{product.name}</td>"
        result += f"<td>{product.image}</td>"
        result += f"<td>{img_type}</td>"
        result += f"<td>{img_url}</td>"
        result += f"</tr>"
    
    result += "</table>"
    return result

# Debug route to check order images
@app.route('/admin/debug-order/<int:order_id>')
@login_required
def debug_order(order_id):
    if not current_user.is_admin:
        abort(403)
    
    order = Order.query.get_or_404(order_id)
    
    result = "<h2>Order Debug Information</h2>"
    result += f"<p><strong>Order #:</strong> {order.order_number}</p>"
    result += f"<p><strong>Customer:</strong> {order.customer.username}</p>"
    
    result += "<h3>Order Items:</h3>"
    result += "<table border='1' cellpadding='10'>"
    result += "<tr><th>Item ID</th><th>Product Name</th><th>Image Path in DB</th><th>Image Type</th><th>Expected URL</th></tr>"
    
    for item in order.items:
        if item.product_image:
            if item.product_image.startswith('user_uploads:'):
                filename = item.product_image.replace('user_uploads:', '')
                img_type = "User Uploads"
                img_url = url_for('user_uploads', filename=filename, _external=True)
            elif item.product_image.startswith('tmp:'):
                filename = item.product_image.replace('tmp:', '')
                img_type = "Temp Uploads"
                img_url = url_for('tmp_uploads', filename=filename, _external=True)
            else:
                img_type = "Static"
                img_url = url_for('static', filename='images/products/' + item.product_image, _external=True)
        else:
            img_type = "No Image"
            img_url = "None"
        
        result += f"<tr>"
        result += f"<td>{item.id}</td>"
        result += f"<td>{item.product_name}</td>"
        result += f"<td>{item.product_image}</td>"
        result += f"<td>{img_type}</td>"
        result += f"<td>{img_url}</td>"
        result += f"</tr>"
    
    result += "</table>"
    
    return result

# Simple test upload page
@app.route('/test-upload', methods=['GET', 'POST'])
def test_upload():
    """Simple test upload page"""
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file part"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"
        
        try:
            # Save using your function
            filename = save_picture(file)
            return f"File saved! DB path: {filename}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    return '''
    <form method="post" enctype="multipart/form-data">
        <input type="file" name="file">
        <input type="submit">
    </form>
    '''

# Test filesystem write access
@app.route('/debug-filesystem')
def debug_filesystem():
    """Test filesystem write access"""
    import tempfile
    results = []
    
    # Test /tmp directory
    try:
        test_file = '/tmp/captain_signature_test.txt'
        with open(test_file, 'w') as f:
            f.write('test')
        results.append(f"✓ Wrote to /tmp: {test_file}")
        os.remove(test_file)
        results.append(f"✓ Removed test file")
    except Exception as e:
        results.append(f"✗ Cannot write to /tmp: {e}")
    
    # Test your specific directory
    try:
        test_dir = '/tmp/captain_signature_uploads/products'
        os.makedirs(test_dir, mode=0o777, exist_ok=True)
        test_file = os.path.join(test_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        results.append(f"✓ Wrote to {test_file}")
        os.remove(test_file)
        results.append(f"✓ Removed test file")
    except Exception as e:
        results.append(f"✗ Cannot write to {test_dir}: {e}")
    
    return "<br>".join(results)

# Simple test for file serving
@app.route('/test-simple-image/<filename>')
def test_simple_image(filename):
    """Absolute simplest image serving test"""
    file_path = f'/tmp/captain_signature_uploads/products/{filename}'
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"500 error occurred: {error}")
    logger.error(traceback.format_exc())
    return render_template('500.html'), 500

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🚀 Captain Signature Nigeria - Starting...")
    print("=" * 60)
    print("📍 Access the website at: http://127.0.0.1:5000")
    print("👤 Admin login: admin@captainsignature.com / admin123")
    print("📁 Upload folder: " + upload_folder)
    print("💰 Current delivery fee: ₦1,500 (configurable in Settings)")
    print("📍 Shipping: Nigeria only")
    print("=" * 60 + "\n")
    
    # Run the app
    app.run(debug=True, host='127.0.0.1', port=5000)