import requests
import json
import os
from flask import current_app, url_for
from datetime import datetime
import secrets

class Paystack:
    def __init__(self):
        self.secret_key = os.environ.get('PAYSTACK_SECRET_KEY')
        self.public_key = os.environ.get('PAYSTACK_PUBLIC_KEY')
        self.base_url = 'https://api.paystack.co'
        
    def initialize_transaction(self, email, amount, reference=None, callback_url=None, metadata=None):
        """
        Initialize a Paystack transaction
        Args:
            email: Customer's email
            amount: Amount in kobo (multiply Naira by 100)
            reference: Unique transaction reference (optional)
            callback_url: URL to redirect after payment
            metadata: Additional data to pass to Paystack
        Returns:
            dict: Paystack response
        """
        if not reference:
            # Generate a unique reference
            reference = f"CAPTAIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"
        
        # Convert amount to kobo (Paystack uses smallest currency unit)
        amount_in_kobo = int(amount * 100)
        
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'email': email,
            'amount': amount_in_kobo,
            'reference': reference,
            'callback_url': callback_url or url_for('payment_callback', _external=True),
            'metadata': metadata or {}
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/transaction/initialize',
                headers=headers,
                json=data
            )
            return response.json()
        except Exception as e:
            print(f"Paystack initialization error: {e}")
            return {'status': False, 'message': str(e)}
    
    def verify_transaction(self, reference):
        """
        Verify a Paystack transaction
        Args:
            reference: Transaction reference to verify
        Returns:
            dict: Paystack response
        """
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                f'{self.base_url}/transaction/verify/{reference}',
                headers=headers
            )
            return response.json()
        except Exception as e:
            print(f"Paystack verification error: {e}")
            return {'status': False, 'message': str(e)}
    
    def list_banks(self, country='nigeria'):
        """
        List available banks
        Args:
            country: Country code (nigeria, ghana, etc.)
        Returns:
            list: List of banks
        """
        headers = {
            'Authorization': f'Bearer {self.secret_key}'
        }
        
        try:
            response = requests.get(
                f'{self.base_url}/bank?country={country}',
                headers=headers
            )
            return response.json()
        except Exception as e:
            print(f"Error fetching banks: {e}")
            return {'status': False, 'message': str(e)}
    
    def charge_authorization(self, email, amount, authorization_code, reference=None):
        """
        Charge a previously authorized card (for recurring payments)
        """
        if not reference:
            reference = f"CAPTAIN-CHARGE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        amount_in_kobo = int(amount * 100)
        
        headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'email': email,
            'amount': amount_in_kobo,
            'authorization_code': authorization_code,
            'reference': reference
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/transaction/charge_authorization',
                headers=headers,
                json=data
            )
            return response.json()
        except Exception as e:
            print(f"Paystack charge error: {e}")
            return {'status': False, 'message': str(e)}

# Create a singleton instance
paystack = Paystack()