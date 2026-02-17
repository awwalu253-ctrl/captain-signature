import smtplib
import os
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template
from threading import Thread

def send_async_email(app, msg, to_email):
    """Send email asynchronously with detailed logging"""
    with app.app_context():
        try:
            print(f"\n{'='*60}")
            print(f"📧 ATTEMPTING TO SEND EMAIL")
            print(f"{'='*60}")
            print(f"To: {to_email}")
            print(f"Subject: {msg['Subject']}")
            print(f"From: {msg['From']}")
            print(f"Mail Server: {os.environ.get('MAIL_SERVER', 'Not set')}")
            print(f"Mail Port: {os.environ.get('MAIL_PORT', 'Not set')}")
            print(f"Mail Username: {os.environ.get('MAIL_USERNAME', 'Not set')}")
            print(f"Mail Password: {'✅ Set' if os.environ.get('MAIL_PASSWORD') else '❌ NOT SET'}")
            
            # Connect to server
            print("\n🔌 Connecting to SMTP server...")
            server = smtplib.SMTP(
                os.environ.get('MAIL_SERVER', 'smtp.gmail.com'), 
                int(os.environ.get('MAIL_PORT', 587))
            )
            server.set_debuglevel(1)  # This will show SMTP conversation
            print("✅ Connected")
            
            # Start TLS
            print("\n🔒 Starting TLS...")
            server.starttls()
            print("✅ TLS started")
            
            # Login
            print("\n🔑 Logging in...")
            server.login(
                os.environ.get('MAIL_USERNAME'), 
                os.environ.get('MAIL_PASSWORD')
            )
            print("✅ Login successful")
            
            # Send email
            print("\n📤 Sending message...")
            server.send_message(msg)
            print("✅ Message sent")
            
            # Quit
            print("\n👋 Closing connection...")
            server.quit()
            print("✅ Connection closed")
            
            print(f"\n✅✅✅ EMAIL SENT SUCCESSFULLY TO {to_email} ✅✅✅")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"\n❌❌❌ AUTHENTICATION FAILED ❌❌❌")
            print(f"Error: {str(e)}")
            print("\nPossible causes:")
            print("1. Wrong App Password")
            print("2. 2-Factor Authentication not enabled")
            print("3. App password has spaces (remove them)")
            return False
            
        except smtplib.SMTPException as e:
            print(f"\n❌❌❌ SMTP ERROR ❌❌❌")
            print(f"Error: {str(e)}")
            return False
            
        except Exception as e:
            print(f"\n❌❌❌ EMAIL FAILED ❌❌❌")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print("\nFull traceback:")
            traceback.print_exc()
            return False

def send_email(app, to_email, subject, template, **kwargs):
    """Send email asynchronously with error handling"""
    try:
        print(f"\n{'='*60}")
        print(f"📨 PREPARING EMAIL FOR {to_email}")
        print(f"{'='*60}")
        print(f"Subject: {subject}")
        print(f"Template: {template}")
        
        # Check if template exists by trying to render it
        try:
            # Try to render the template to see if it exists
            test_render = render_template(f'emails/{template}', **kwargs)
            print(f"✅ Template found and rendered successfully")
        except Exception as e:
            print(f"❌ Template '{template}' not found or error: {e}")
            print("Make sure the template file exists in templates/emails/ folder")
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@captainsignature.com')
        msg['To'] = to_email
        
        # Create HTML content
        html_content = render_template(f'emails/{template}', **kwargs)
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send asynchronously - FIXED: Use app directly, not _get_current_object()
        thread = Thread(target=send_async_email, args=(app, msg, to_email))
        thread.daemon = True
        thread.start()
        print(f"✅ Email thread started for {to_email}")
        return True
        
    except Exception as e:
        print(f"\n❌ Error creating email: {e}")
        traceback.print_exc()
        return False

def send_order_notifications(app, order, user):
    """
    Send notifications to both customer and admin when an order is placed
    """
    print(f"\n{'='*60}")
    print(f"🛒 SENDING ORDER NOTIFICATIONS FOR ORDER #{order.order_number}")
    print(f"{'='*60}")
    print(f"Customer: {user.username} ({user.email})")
    print(f"Order Total: ₦{order.total_amount if hasattr(order, 'total_amount') else 'N/A'}")
    
    results = {}
    
    # Send to customer
    customer_subject = f"Order Confirmation #{order.order_number} - Captain Signature"
    print(f"\n📧 Preparing CUSTOMER email to: {user.email}")
    try:
        customer_sent = send_email(app, user.email, customer_subject, 'order_confirmation.html', 
                                  order=order, user=user, recipient='customer')
        results['customer'] = customer_sent
        print(f"✅ Customer email result: {customer_sent}")
    except Exception as e:
        print(f"❌ Customer email error: {e}")
        traceback.print_exc()
        results['customer'] = False
    
    # Send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'awwalu253@gmail.com')
    admin_subject = f"🆕 NEW ORDER #{order.order_number} - Captain Signature"
    print(f"\n📧 Preparing ADMIN email to: {admin_email}")
    try:
        admin_sent = send_email(app, admin_email, admin_subject, 'admin_new_order.html',
                               order=order, user=user)
        results['admin'] = admin_sent
        print(f"✅ Admin email result: {admin_sent}")
    except Exception as e:
        print(f"❌ Admin email error: {e}")
        traceback.print_exc()
        results['admin'] = False
    
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS: {results}")
    print(f"{'='*60}")
    
    return results.get('customer', False) and results.get('admin', False)

def send_order_status_update(app, order, user, old_status, new_status):
    """
    Send order status update to customer AND admin
    """
    print(f"\n{'='*60}")
    print(f"📦 SENDING STATUS UPDATE FOR ORDER #{order.order_number}")
    print(f"{'='*60}")
    print(f"Status changed from {old_status} to {new_status}")
    
    results = {}
    
    # Send to customer
    customer_subject = f"Order #{order.order_number} Status Updated - Captain Signature"
    print(f"\n📧 Preparing CUSTOMER status email to: {user.email}")
    try:
        customer_sent = send_email(app, user.email, customer_subject, 'order_status_update.html',
                                  order=order, user=user, old_status=old_status, new_status=new_status)
        results['customer'] = customer_sent
        print(f"✅ Customer status email result: {customer_sent}")
    except Exception as e:
        print(f"❌ Customer status email error: {e}")
        results['customer'] = False
    
    # Send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'awwalu253@gmail.com')
    admin_subject = f"📦 ORDER #{order.order_number} {new_status.upper()} - Captain Signature"
    print(f"\n📧 Preparing ADMIN status email to: {admin_email}")
    try:
        admin_sent = send_email(app, admin_email, admin_subject, 'admin_status_update.html',
                               order=order, user=user, old_status=old_status, new_status=new_status)
        results['admin'] = admin_sent
        print(f"✅ Admin status email result: {admin_sent}")
    except Exception as e:
        print(f"❌ Admin status email error: {e}")
        results['admin'] = False
    
    return results.get('customer', False) and results.get('admin', False)

def send_delivery_notification(app, order, user):
    """
    Send delivery notification to customer AND admin
    """
    print(f"\n{'='*60}")
    print(f"🚚 SENDING DELIVERY NOTIFICATION FOR ORDER #{order.order_number}")
    print(f"{'='*60}")
    
    results = {}
    
    # Send to customer
    customer_subject = f"Order #{order.order_number} Out for Delivery - Captain Signature"
    print(f"\n📧 Preparing CUSTOMER delivery email to: {user.email}")
    try:
        customer_sent = send_email(app, user.email, customer_subject, 'delivery_notification.html',
                                  order=order, user=user)
        results['customer'] = customer_sent
        print(f"✅ Customer delivery email result: {customer_sent}")
    except Exception as e:
        print(f"❌ Customer delivery email error: {e}")
        results['customer'] = False
    
    # Send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'awwalu253@gmail.com')
    admin_subject = f"🚚 ORDER #{order.order_number} OUT FOR DELIVERY - Captain Signature"
    print(f"\n📧 Preparing ADMIN delivery email to: {admin_email}")
    try:
        admin_sent = send_email(app, admin_email, admin_subject, 'admin_delivery_notification.html',
                               order=order, user=user)
        results['admin'] = admin_sent
        print(f"✅ Admin delivery email result: {admin_sent}")
    except Exception as e:
        print(f"❌ Admin delivery email error: {e}")
        results['admin'] = False
    
    return results.get('customer', False) and results.get('admin', False)

def send_cancellation_notification(app, order, user, cancelled_by='customer'):
    """
    Send cancellation notification to both parties
    """
    print(f"\n{'='*60}")
    print(f"⚠️ SENDING CANCELLATION NOTIFICATION FOR ORDER #{order.order_number}")
    print(f"{'='*60}")
    print(f"Cancelled by: {cancelled_by}")
    
    results = {}
    
    # Send to customer
    customer_subject = f"Order #{order.order_number} Cancelled - Captain Signature"
    print(f"\n📧 Preparing CUSTOMER cancellation email to: {user.email}")
    try:
        customer_sent = send_email(app, user.email, customer_subject, 'cancellation_notification.html',
                                  order=order, user=user, cancelled_by=cancelled_by)
        results['customer'] = customer_sent
        print(f"✅ Customer cancellation email result: {customer_sent}")
    except Exception as e:
        print(f"❌ Customer cancellation email error: {e}")
        results['customer'] = False
    
    # Send to admin (if cancelled by customer)
    if cancelled_by == 'customer':
        admin_email = os.environ.get('ADMIN_EMAIL', 'awwalu253@gmail.com')
        admin_subject = f"⚠️ ORDER #{order.order_number} CANCELLED BY CUSTOMER - Captain Signature"
        print(f"\n📧 Preparing ADMIN cancellation email to: {admin_email}")
        try:
            admin_sent = send_email(app, admin_email, admin_subject, 'admin_cancellation_notice.html',
                                   order=order, user=user)
            results['admin'] = admin_sent
            print(f"✅ Admin cancellation email result: {admin_sent}")
        except Exception as e:
            print(f"❌ Admin cancellation email error: {e}")
            results['admin'] = False
        return results.get('customer', False) and results.get('admin', False)
    
    return results.get('customer', False)

def send_password_reset_email(app, user, reset_url):
    """Send password reset email"""
    print(f"\n{'='*60}")
    print(f"📧 SENDING PASSWORD RESET EMAIL TO {user.email}")
    print(f"{'='*60}")
    
    subject = "Reset Your Password - Captain Signature"
    
    try:
        # Check if template exists
        from flask import render_template_string
        import os
        
        # Try to render the template to see if it exists
        template_path = os.path.join('templates', 'email', 'password_reset.html')
        print(f"Looking for template at: {template_path}")
        print(f"Template exists: {os.path.exists(template_path)}")
        
        result = send_email(app, user.email, subject, 'password_reset.html', 
                           user=user, reset_url=reset_url)
        print(f"send_email returned: {result}")
        return result
    except Exception as e:
        print(f"❌ Error in send_password_reset_email: {e}")
        traceback.print_exc()
        return False