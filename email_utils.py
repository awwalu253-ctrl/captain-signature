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
            server = smtplib.SMTP(os.environ.get('MAIL_SERVER', 'smtp.gmail.com'), 
                                 int(os.environ.get('MAIL_PORT', 587)))
            server.starttls()
            server.login(os.environ.get('MAIL_USERNAME'), 
                        os.environ.get('MAIL_PASSWORD'))
            server.send_message(msg)
            server.quit()
            print(f"✓ Email sent successfully")
        except Exception as e:
            print(f"✗ Email error: {e}")

def send_email(app, to_email, subject, template, **kwargs):
    """Send email asynchronously"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@captainsignature.com')
    msg['To'] = to_email
    
    # Create HTML content
    html_content = render_template(f'emails/{template}', **kwargs)
    msg.attach(MIMEText(html_content, 'html'))
    
    # Send asynchronously
    Thread(target=send_async_email, args=(app._get_current_object(), msg)).start()

def send_order_notifications(app, order, user):
    """
    Send notifications to both customer and admin when an order is placed
    """
    # Send to customer
    customer_subject = f"Order Confirmation #{order.order_number} - Captain Signature"
    send_email(app, user.email, customer_subject, 'order_confirmation.html', 
              order=order, user=user, recipient='customer')
    
    # ALWAYS send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
    admin_subject = f"🆕 NEW ORDER #{order.order_number} - Captain Signature"
    send_email(app, admin_email, admin_subject, 'admin_new_order.html',
              order=order, user=user)

def send_order_status_update(app, order, user, old_status, new_status):
    """
    Send order status update to customer AND admin
    """
    # Send to customer
    customer_subject = f"Order #{order.order_number} Status Updated - Captain Signature"
    send_email(app, user.email, customer_subject, 'order_status_update.html',
              order=order, user=user, old_status=old_status, new_status=new_status)
    
    # ALWAYS send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
    admin_subject = f"📦 ORDER #{order.order_number} {new_status.upper()} - Captain Signature"
    send_email(app, admin_email, admin_subject, 'admin_status_update.html',
              order=order, user=user, old_status=old_status, new_status=new_status)

def send_delivery_notification(app, order, user):
    """
    Send delivery notification to customer AND admin
    """
    # Send to customer
    customer_subject = f"Order #{order.order_number} Out for Delivery - Captain Signature"
    send_email(app, user.email, customer_subject, 'delivery_notification.html',
              order=order, user=user)
    
    # Send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
    admin_subject = f"🚚 ORDER #{order.order_number} OUT FOR DELIVERY - Captain Signature"
    send_email(app, admin_email, admin_subject, 'admin_delivery_notification.html',
              order=order, user=user)

def send_cancellation_notification(app, order, user, cancelled_by='customer'):
    """
    Send cancellation notification to both parties
    """
    # Send to customer
    customer_subject = f"Order #{order.order_number} Cancelled - Captain Signature"
    send_email(app, user.email, customer_subject, 'cancellation_notification.html',
              order=order, user=user, cancelled_by=cancelled_by)
    
    # ALWAYS send to admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@captainsignature.com')
    admin_subject = f"⚠️ ORDER #{order.order_number} CANCELLED - Captain Signature"
    
    if cancelled_by == 'customer':
        send_email(app, admin_email, admin_subject, 'admin_cancellation_notice.html',
                  order=order, user=user)
    else:
        # Admin already knows they cancelled it
        pass