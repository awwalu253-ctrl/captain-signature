import os
import sys
import traceback
import logging
from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_from_directory, send_file, session, g, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import text

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
from monnify_utils import monnify  # Changed from paystack_utils to monnify_utils
import secrets

app = Flask(__name__)
app.config.from_object(Config)

# Setup logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)

# Print environment variables for debugging
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
                os.chmod(directory, 0o777)
                
            if directory.startswith('/tmp'):
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
    if 'cart' not in session:
        session['cart'] = {}
    
    try:
        cart = Cart()
        g.cart_count = cart.get_total_items()
    except Exception as e:
        print(f"Error getting cart count: {e}")
        g.cart_count = 0
    
    try:
        g.settings = Settings.get_settings()
    except Exception as e:
        print(f"Error getting settings: {e}")
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
        db.create_all()
        print("✓ Database tables created/verified")
        
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

# Image upload routes
@app.route('/user-uploads/<filename>')
def user_uploads(filename):
    user_home = os.path.expanduser("~")
    upload_folder = os.path.join(user_home, 'captain_signature_uploads', 'product_images')
    return send_from_directory(upload_folder, filename)

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
        if os.path.exists(directory):
            files = os.listdir(directory)
            print(f"Files in directory: {files}")
        return "File not found", 404
    
    try:
        response = make_response(send_file(file_path))
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['Content-Type'] = 'image/jpeg'
        print(f"✓ Successfully serving file: {filename}")
        return response
    except Exception as e:
        print(f"❌ Error serving {filename}: {e}")
        return f"Error serving file: {str(e)}", 500

# Public debug routes
@app.route('/public-debug-file/<filename>')
def public_debug_file(filename):
    """Public debug route to check if file exists (no login required)"""
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

# Debug routes
@app.route('/debug-file-check/<filename>')
def debug_file_check(filename):
    """Diagnose why a file isn't being served."""
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
    results = {}
    search_paths = ['/tmp', '/tmp/captain_signature_uploads', '/var/tmp']
    
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

@app.route('/find-file/<filename>')
def find_file(filename):
    """Search for a file in all possible locations"""
    results = {}
    locations = [
        '/tmp/captain_signature_uploads/products',
        '/tmp/captain_signature_uploads',
        '/tmp',
        os.path.join(project_root, 'static', 'images', 'products'),
        os.path.join(project_root, 'uploads'),
        '/var/task',
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

@app.route('/debug-paths')
def debug_paths():
    """Show all relevant paths"""
    import tempfile
    tmp_uploads_dir = '/tmp/captain_signature_uploads/products'
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
    return {
        'cloud_name': os.environ.get('CLOUDINARY_CLOUD_NAME', 'NOT SET'),
        'api_key': 'SET' if os.environ.get('CLOUDINARY_API_KEY') else 'NOT SET',
        'api_secret': 'SET' if os.environ.get('CLOUDINARY_API_SECRET') else 'NOT SET',
        'is_vercel': app.config.get('IS_VERCEL', False),
    }

@app.route('/debug-db')
def debug_db():
    try:
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

@app.route('/debug-uploads')
def debug_uploads():
    """Debug route to check uploaded files"""
    results = []
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
            for f in files[-10:]:
                file_path = os.path.join(tmp_path, f)
                size = os.path.getsize(file_path)
                perms = oct(os.stat(file_path).st_mode)[-3:]
                results.append(f"  - {f} ({size} bytes, permissions: {perms})")
        except Exception as e:
            results.append(f"✗ Error listing files: {e}")
    else:
        results.append(f"✗ Directory does NOT exist")
    
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
    
    results.append("<h3>Products in Database</h3>")
    try:
        products = Product.query.limit(10).all()
        for p in products:
            results.append(f"Product {p.id}: {p.name} - Image: {p.image}")
    except Exception as e:
        results.append(f"Error querying products: {e}")
    
    return "<br>".join(results)

@app.route('/debug-product/<int:product_id>')
def debug_product(product_id):
    """Debug a specific product"""
    product = Product.query.get_or_404(product_id)
    
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

# Monnify Payment Routes (Replacing Paystack)
@app.route('/initiate-monnify-payment/<int:order_id>')
@login_required
def initiate_monnify_payment(order_id):
    """Initiate Monnify payment for an order"""
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if order.payment_status == 'paid':
        flash('This order has already been paid for.', 'info')
        return redirect(url_for('track_order_result', order_number=order.order_number))
    
    callback_url = url_for('monnify_callback', _external=True)
    
    response = monnify.initialize_transaction(
        email=current_user.email,
        amount=order.total_amount,
        reference=f"ORDER-{order.order_number}",
        callback_url=callback_url,
        customer_name=order.shipping_name or current_user.username
    )
    
    if response['status']:
        order.payment_reference = response['data']['reference']
        order.payment_authorization_url = response['data']['authorization_url']
        order.payment_method = 'monnify'
        order.payment_status = 'pending'
        db.session.commit()
        return redirect(response['data']['authorization_url'])
    else:
        flash(f'Payment initiation failed: {response.get("message", "Unknown error")}', 'danger')
        return redirect(url_for('checkout'))

@app.route('/initiate-payment-before-order')
@login_required
def initiate_payment_before_order():
    """Initiate Monnify payment before creating order"""
    checkout_data = session.get('checkout_data')
    
    if not checkout_data:
        flash('Checkout session expired. Please try again.', 'danger')
        return redirect(url_for('checkout'))
    
    reference = f"PRE-ORDER-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"
    callback_url = url_for('monnify_success_callback', _external=True)
    
    response = monnify.initialize_transaction(
        email=current_user.email,
        amount=checkout_data['total_amount'],
        reference=reference,
        callback_url=callback_url,
        customer_name=checkout_data['shipping_name']
    )
    
    if response['status']:
        session['payment_reference'] = response['data']['reference']
        return redirect(response['data']['authorization_url'])
    else:
        flash(f'Payment initiation failed: {response.get("message", "Unknown error")}', 'danger')
        return redirect(url_for('checkout'))

@app.route('/monnify-callback')
def monnify_callback():
    """Handle Monnify callback after payment"""
    reference = request.args.get('paymentReference') or request.args.get('reference')
    
    if not reference:
        flash('No payment reference provided.', 'danger')
        return redirect(url_for('index'))
    
    response = monnify.verify_transaction(reference)
    
    if response['status'] and response['data']['status'] == 'success':
        order = Order.query.filter_by(payment_reference=reference).first()
        
        if order:
            order.payment_status = 'paid'
            order.paid_at = datetime.utcnow()
            order.status = 'processing'
            db.session.commit()
            
            flash('Payment successful! Your order is now being processed.', 'success')
            return redirect(url_for('track_order_result', order_number=order.order_number))
        else:
            flash('Payment successful but order not found. Please contact support.', 'warning')
            return redirect(url_for('index'))
    else:
        flash(f'Payment verification failed: {response.get("message", "Unknown error")}', 'danger')
        return redirect(url_for('index'))

@app.route('/monnify-success-callback')
@login_required
def monnify_success_callback():
    """Handle successful Monnify payment and create order"""
    reference = request.args.get('paymentReference') or request.args.get('reference')
    
    if not reference:
        flash('No payment reference provided.', 'danger')
        return redirect(url_for('index'))
    
    response = monnify.verify_transaction(reference)
    
    if response['status'] and response['data']['status'] == 'success':
        checkout_data = session.get('checkout_data')
        
        if not checkout_data:
            flash('Checkout session expired. Please try again.', 'danger')
            return redirect(url_for('checkout'))
        
        try:
            # Create order
            order = Order(
                user_id=current_user.id,
                status='processing',
                subtotal=checkout_data['subtotal'],
                delivery_fee=checkout_data['delivery_fee'],
                total_amount=checkout_data['total_amount'],
                shipping_name=checkout_data['shipping_name'],
                shipping_address=checkout_data['shipping_address'],
                shipping_city=checkout_data['shipping_city'],
                shipping_state=checkout_data['shipping_state'],
                shipping_phone=checkout_data['shipping_phone'],
                shipping_email=current_user.email,
                payment_method='monnify',
                payment_status='paid',
                payment_reference=reference,
                paid_at=datetime.utcnow(),
                customer_notes=checkout_data.get('customer_notes', '')
            )
            
            db.session.add(order)
            db.session.flush()
            
            # Add order items
            cart = Cart()
            for item_data in checkout_data['cart_items']:
                product = Product.query.get(item_data['product_id'])
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item_data['product_id'],
                    quantity=item_data['quantity'],
                    price=item_data['price'],
                    product_name=item_data['name'],
                    product_image=item_data['image']
                )
                db.session.add(order_item)
                
                if product:
                    product.stock -= item_data['quantity']
            
            tracking = OrderTracking(
                order_id=order.id,
                status='processing',
                description='Order placed and payment received',
                updated_by='system'
            )
            db.session.add(tracking)
            
            db.session.commit()
            
            cart.clear()
            session.pop('checkout_data', None)
            session.pop('payment_reference', None)
            
            flash('Payment successful! Your order has been placed.', 'success')
            return redirect(url_for('track_order_result', order_number=order.order_number))
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating order: {e}")
            print(traceback.format_exc())
            flash('Payment successful but order creation failed. Please contact support.', 'danger')
            return redirect(url_for('index'))
    else:
        flash(f'Payment verification failed: {response.get("message", "Unknown error")}', 'danger')
        return redirect(url_for('checkout'))

@app.route('/payment-cancel/<int:order_id>')
@login_required
def payment_cancel(order_id):
    """Handle cancelled payment"""
    order = Order.query.get_or_404(order_id)
    flash('Payment was cancelled. You can try again.', 'warning')
    return redirect(url_for('checkout'))

# Test route for Monnify
@app.route('/test-monnify-keys')
def test_monnify_keys():
    """Test if Monnify keys are working"""
    try:
        token = monnify.get_access_token()
        if token:
            return {
                'status': 'success',
                'message': '✅ Monnify keys are valid!',
                'keys': {
                    'api_key_present': bool(monnify.api_key),
                    'secret_key_present': bool(monnify.secret_key),
                    'contract_code_present': bool(monnify.contract_code)
                }
            }
        else:
            return {
                'status': 'error',
                'message': '❌ Invalid Monnify keys',
                'keys': {
                    'api_key_present': bool(monnify.api_key),
                    'secret_key_present': bool(monnify.secret_key),
                    'contract_code_present': bool(monnify.contract_code)
                }
            }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

# Main routes
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
            
            if not username or not email or not password:
                flash('All fields are required', 'danger')
                return render_template('signup.html', form=SignupForm())
            
            if User.query.filter_by(email=email).first():
                flash('Email already registered', 'danger')
                return render_template('signup.html', form=SignupForm())
            
            if User.query.filter_by(username=username).first():
                flash('Username already taken', 'danger')
                return render_template('signup.html', form=SignupForm())
            
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
        now = datetime.now()
        
        total_users = User.query.count()
        total_products = Product.query.count()
        total_orders = Order.query.count()
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        new_users_today = User.query.filter(User.created_at >= today_start).count()
        
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        new_products_this_month = Product.query.filter(Product.created_at >= month_start).count()
        
        pending_orders_count = Order.query.filter_by(status='pending').count()
        total_revenue = db.session.query(db.func.sum(Order.total_amount)).scalar() or 0
        
        recent_orders = Order.query.order_by(Order.order_date.desc()).limit(5).all()
        
        low_stock_count = Product.query.filter(Product.stock <= 5).filter(Product.stock > 0).count()
        out_of_stock_count = Product.query.filter_by(stock=0).count()
        in_stock_count = Product.query.filter(Product.stock > 5).count()
        
        recent_activities = []
        
        for order in recent_orders[:2]:
            recent_activities.append({
                'icon': 'shopping-cart',
                'description': f'New order #{order.order_number}',
                'time': f'{order.order_date.strftime("%H:%M")}'
            })
        
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
                             revenue_growth=0,
                             recent_orders=recent_orders,
                             low_stock_count=low_stock_count,
                             out_of_stock_count=out_of_stock_count,
                             in_stock_count=in_stock_count,
                             recent_activities=recent_activities)
    else:
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
    quantity = int(request.form.get('quantity', 1))
    
    if quantity > product.stock:
        flash(f'Sorry, only {product.stock} items available.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))
    
    cart = Cart()
    cart.add(
        product_id=product.id,
        quantity=quantity,
        price=product.price,
        name=product.name,
        image=product.image
    )
    
    flash(f'{product.name} added to cart!', 'success')
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
    """Checkout page - Payment before order creation"""
    try:
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
            payment_method = request.form.get('payment_method', 'monnify')
            customer_notes = request.form.get('customer_notes')
            
            # Validate Nigerian state
            if shipping_state not in NIGERIA_STATES:
                flash('Please select a valid Nigerian state.', 'danger')
                return redirect(url_for('checkout'))
            
            # Calculate totals
            subtotal = cart.get_subtotal()
            
            if settings.free_delivery_threshold > 0 and subtotal >= settings.free_delivery_threshold:
                delivery_fee = 0
            else:
                delivery_fee = settings.delivery_fee
            
            total_amount = subtotal + delivery_fee
            
            # Store checkout data in session
            session['checkout_data'] = {
                'shipping_name': shipping_name,
                'shipping_address': shipping_address,
                'shipping_city': shipping_city,
                'shipping_state': shipping_state,
                'shipping_phone': shipping_phone,
                'payment_method': payment_method,
                'customer_notes': customer_notes,
                'subtotal': subtotal,
                'delivery_fee': delivery_fee,
                'total_amount': total_amount,
                'cart_items': [
                    {
                        'product_id': pid,
                        'quantity': item['quantity'],
                        'price': item['price'],
                        'name': item['name'],
                        'image': item['image']
                    } for pid, item in cart.get_cart().items()
                ]
            }
            
            # If payment method is monnify, redirect to payment
            if payment_method == 'monnify':
                print("Redirecting to initiate_payment_before_order")
                return redirect(url_for('initiate_payment_before_order'))
            
            # For other payment methods (cash on delivery, etc.) - create order immediately
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
            db.session.flush()
            
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
                product.stock -= item['quantity']
            
            tracking = OrderTracking(
                order_id=order.id,
                status='pending',
                description='Order placed successfully',
                updated_by='system'
            )
            db.session.add(tracking)
            
            db.session.commit()
            cart.clear()
            
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
    except Exception as e:
        print(f"Checkout error: {e}")
        print(traceback.format_exc())
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('view_cart'))

# Order Tracking Routes
@app.route('/track', methods=['GET', 'POST'])
def track_order_page():
    """Page to enter order tracking information"""
    if request.method == 'POST':
        order_number = request.form.get('order_number')
        email = request.form.get('email')
        
        print(f"Searching for order: {order_number} with email: {email}")
        order = Order.query.filter_by(order_number=order_number).first()
        
        if order:
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
                print(f"\n--- Image Upload Debug ---")
                print(f"Form image data: {form.image.data}")
                print(f"Filename: {form.image.data.filename}")
                
                if form.image.data.filename:
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

# ... rest of your admin routes remain the same (admin_customers, edit_product, admin_products, delete_product, admin_orders, etc.)

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
    
    app.run(debug=True, host='127.0.0.1', port=5000)