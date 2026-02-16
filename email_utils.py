import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template
from threading import Thread

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        try:
            print(f"\n=== ATTEMPTING TO SEND EMAIL ===")
            print(f"To: {msg['To']}")
            print(f"Subject: {msg['Subject']}")
            print(f"From: {msg['From']}")
            print(f"Mail Server: {os.environ.get('MAIL_SERVER', 'Not set')}")
            print(f"Mail Port: {os.environ.get('MAIL_PORT', 'Not set')}")
            print(f"Mail Username: {os.environ.get('MAIL_USERNAME', 'Not set')}")
            
            server = smtplib.SMTP(
                os.environ.get('MAIL_SERVER', 'smtp.gmail.com'), 
                int(os.environ.get('MAIL_PORT', 587))
            )
            server.starttls()
            server.login(
                os.environ.get('MAIL_USERNAME'), 
                os.environ.get('MAIL_PASSWORD')
            )
            server.send_message(msg)
            server.quit()
            print(f"✓ Email sent successfully to {msg['To']}")
            return True
        except Exception as e:
            print(f"✗ Email error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

def send_email(app, to_email, subject, template, **kwargs):
    """Send email asynchronously"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@captainsignature.com')
        msg['To'] = to_email
        
        # Create HTML content
        html_content = render_template(f'emails/{template}', **kwargs)
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send asynchronously
        Thread(target=send_async_email, args=(app._get_current_object(), msg)).start()
        return True
    except Exception as e:
        print(f"✗ Error creating email: {e}")
        return False

def send_order_notifications(app, order, user):
    """
    Send notifications to both customer and admin when an order is placed
    """
    print(f"\n=== SENDING ORDER NOTIFICATIONS FOR ORDER #{order.order_number} ===")
    
    # Send to customer
    customer_subject = f"Order Confirmation #{order.order_number} - Captain Signature"
    customer_sent = send_email(app, user.email, customer_subject, 'order_confirmation.html', 
                               order=order, user=user, recipient='customer')
    print(f"Customer email sent: {customer_sent}")
    
    # Send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
    admin_subject = f"🆕 NEW ORDER #{order.order_number} - Captain Signature"
    admin_sent = send_email(app, admin_email, admin_subject, 'admin_new_order.html',
                           order=order, user=user)
    print(f"Admin email sent: {admin_sent}")
    
    return customer_sent and admin_sent

def send_order_status_update(app, order, user, old_status, new_status):
    """
    Send order status update to customer AND admin
    """
    print(f"\n=== SENDING STATUS UPDATE FOR ORDER #{order.order_number} ===")
    print(f"Status changed from {old_status} to {new_status}")
    
    # Send to customer
    customer_subject = f"Order #{order.order_number} Status Updated - Captain Signature"
    customer_sent = send_email(app, user.email, customer_subject, 'order_status_update.html',
                               order=order, user=user, old_status=old_status, new_status=new_status)
    print(f"Customer status email sent: {customer_sent}")
    
    # Send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
    admin_subject = f"📦 ORDER #{order.order_number} {new_status.upper()} - Captain Signature"
    admin_sent = send_email(app, admin_email, admin_subject, 'admin_status_update.html',
                           order=order, user=user, old_status=old_status, new_status=new_status)
    print(f"Admin status email sent: {admin_sent}")
    
    return customer_sent and admin_sent

def send_delivery_notification(app, order, user):
    """
    Send delivery notification to customer AND admin
    """
    print(f"\n=== SENDING DELIVERY NOTIFICATION FOR ORDER #{order.order_number} ===")
    
    # Send to customer
    customer_subject = f"Order #{order.order_number} Out for Delivery - Captain Signature"
    customer_sent = send_email(app, user.email, customer_subject, 'delivery_notification.html',
                               order=order, user=user)
    print(f"Customer delivery email sent: {customer_sent}")
    
    # Send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
    admin_subject = f"🚚 ORDER #{order.order_number} OUT FOR DELIVERY - Captain Signature"
    admin_sent = send_email(app, admin_email, admin_subject, 'admin_delivery_notification.html',
                           order=order, user=user)
    print(f"Admin delivery email sent: {admin_sent}")
    
    return customer_sent and admin_sent

def send_cancellation_notification(app, order, user, cancelled_by='customer'):
    """
    Send cancellation notification to both parties
    """
    print(f"\n=== SENDING CANCELLATION NOTIFICATION FOR ORDER #{order.order_number} ===")
    print(f"Cancelled by: {cancelled_by}")
    
    # Send to customer
    customer_subject = f"Order #{order.order_number} Cancelled - Captain Signature"
    customer_sent = send_email(app, user.email, customer_subject, 'cancellation_notification.html',
                               order=order, user=user, cancelled_by=cancelled_by)
    print(f"Customer cancellation email sent: {customer_sent}")
    
    # Send to admin (if cancelled by customer)
    if cancelled_by == 'customer':
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
        admin_subject = f"⚠️ ORDER #{order.order_number} CANCELLED BY CUSTOMER - Captain Signature"
        admin_sent = send_email(app, admin_email, admin_subject, 'admin_cancellation_notice.html',
                               order=order, user=user)
        print(f"Admin cancellation email sent: {admin_sent}")
        return customer_sent and admin_sent
    
    return customer_sent