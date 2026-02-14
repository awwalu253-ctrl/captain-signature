import os
import sys
import traceback
from flask import Flask, render_template, redirect, url_for, flash, request, abort, send_from_directory, session, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import tempfile

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

app = Flask(__name__)
app.config.from_object(Config)

# Determine if running on Vercel
IS_VERCEL = os.environ.get('VERCEL_ENV') == 'production' or os.environ.get('VERCEL') == '1'

# Function to ensure directories exist with proper permissions
def ensure_directories():
    """Create all necessary directories if they don't exist"""
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # On Vercel, use /tmp for writable directories
    if IS_VERCEL:
        upload_base = '/tmp/captain_signature_uploads'
    else:
        user_home = os.path.expanduser("~")
        upload_base = os.path.join(user_home, 'captain_signature_uploads')
    
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
        upload_base,
        os.path.join(upload_base, 'product_images')
    ]
    
    print("=" * 50)
    print("Checking and creating directories...")
    
    for directory in directories:
        try:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                print(f"✓ Created: {directory}")
            else:
                print(f"✓ Exists: {directory}")
                
            # Check if writable
            if not os.access(directory, os.W_OK):
                print(f"⚠ Warning: Directory not writable: {directory}")
                
        except Exception as e:
            print(f"✗ Error creating {directory}: {e}")
    
    print("=" * 50)
    return project_root, upload_base

# Call the function to create directories
project_root, upload_base = ensure_directories()
upload_folder = os.path.join(upload_base, 'product_images')

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
        # Create tables
        db.create_all()
        
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
            settings = Settings()
            db.session.add(settings)
            db.session.commit()
            print("✓ Default settings created successfully!")
            print(f"  Delivery fee: ₦{settings.delivery_fee}")
    except Exception as e:
        print(f"✗ Database initialization error: {e}")
        print("Make sure your database is properly configured on Vercel.")

# Route to serve uploaded images
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files from upload folder"""
    return send_from_directory(upload_folder, filename)

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
    
    form = SignupForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password
        )
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html', form=form)

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
        payment_method = request.form.get('payment_method')
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
            flash(f'Congratulations! You qualify for FREE delivery!', 'success')
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
        
        flash(f'Order #{order.order_number} placed successfully! We\'ll deliver to {shipping_city}, {shipping_state}.', 'success')
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
        
        # Look up the order
        order = Order.query.filter_by(order_number=order_number).first()
        
        if order and (order.customer.email == email or order.shipping_email == email):
            return redirect(url_for('track_order_result', order_number=order.order_number))
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
                    
                    image_file = save_picture(form.image.data, upload_folder)
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
                    # Try to delete from various possible locations
                    possible_paths = [
                        os.path.join(upload_folder, product.image),
                        os.path.join(project_root, 'static', 'images', 'products', product.image)
                    ]
                    
                    for old_image_path in possible_paths:
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                            print(f"Deleted old image: {old_image_path}")
                
                # Save new image
                product.image = save_picture(form.image.data, upload_folder)
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
            # Try to delete from various possible locations
            possible_paths = [
                os.path.join(upload_folder, product.image),
                os.path.join(project_root, 'static', 'images', 'products', product.image)
            ]
            
            for image_path in possible_paths:
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

# Health check for Vercel
@app.route('/api/health')
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

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
    return render_template('500.html'), 500

# For local development
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

# For Vercel - this is required
app = app