import requests
import os
import base64
import secrets
from datetime import datetime
from flask import url_for

class Monnify:
    def __init__(self):
        self.api_key = os.environ.get('MONNIFY_API_KEY')
        self.secret_key = os.environ.get('MONNIFY_SECRET_KEY')
        self.contract_code = os.environ.get('MONNIFY_CONTRACT_CODE')
        self.base_url = 'https://sandbox.monnify.com'  # Sandbox URL for testing
        
        # Debug: Check if keys are loaded
        print("=== MONNIFY DEBUG ===")
        print(f"API Key present: {'YES' if self.api_key else 'NO'}")
        print(f"Secret Key present: {'YES' if self.secret_key else 'NO'}")
        print(f"Contract Code present: {'YES' if self.contract_code else 'NO'}")
        print("=====================")
    
    def get_access_token(self):
        """Get authentication token from Monnify"""
        if not self.api_key or not self.secret_key:
            raise Exception("Monnify API keys not configured")
        
        # Create Basic Auth header
        auth_string = f"{self.api_key}:{self.secret_key}"
        auth_bytes = auth_string.encode('ascii')
        base64_auth = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            'Authorization': f'Basic {base64_auth}'
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/api/v1/auth/login',
                headers=headers
            )
            
            print(f"Token Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                return data['responseBody']['accessToken']
            else:
                print(f"Token Error: {response.text}")
                return None
        except Exception as e:
            print(f"Error getting token: {e}")
            return None
    
    def initialize_transaction(self, email, amount, reference=None, callback_url=None, customer_name=None):
        """Initialize a Monnify transaction"""
        try:
            token = self.get_access_token()
            if not token:
                return {
                    'status': False,
                    'message': 'Failed to authenticate with Monnify'
                }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            if not reference:
                reference = f"CAPTAIN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}"
            
            if not customer_name:
                customer_name = email.split('@')[0]
            
            data = {
                'amount': amount,
                'customerName': customer_name,
                'customerEmail': email,
                'paymentReference': reference,
                'paymentDescription': 'Captain Signature Order',
                'currencyCode': 'NGN',
                'contractCode': self.contract_code,
                'redirectUrl': callback_url or 'http://127.0.0.1:5000/monnify-callback',
                'paymentMethods': ['CARD', 'ACCOUNT_TRANSFER']  # All payment methods
            }
            
            print(f"\n=== INITIALIZING MONNIFY PAYMENT ===")
            print(f"URL: {self.base_url}/api/v1/merchant/transactions/init-transaction")
            print(f"Email: {email}")
            print(f"Amount: {amount} NGN")
            print(f"Reference: {reference}")
            print(f"Customer: {customer_name}")
            
            response = requests.post(
                f'{self.base_url}/api/v1/merchant/transactions/init-transaction',
                headers=headers,
                json=data
            )
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text[:200]}...")
            
            if response.status_code == 200:
                result = response.json()
                if result['requestSuccessful']:
                    # Format to match Paystack structure for easier integration
                    return {
                        'status': True,
                        'data': {
                            'reference': reference,
                            'authorization_url': result['responseBody']['checkoutUrl']
                        }
                    }
                else:
                    return {
                        'status': False,
                        'message': result['responseMessage']
                    }
            else:
                print(f"Error Response: {response.text}")
                return {
                    'status': False,
                    'message': f'HTTP Error: {response.status_code}'
                }
                
        except Exception as e:
            print(f"❌ Monnify initialization error: {e}")
            return {'status': False, 'message': str(e)}
    
    def verify_transaction(self, reference):
        """Verify a Monnify transaction"""
        try:
            token = self.get_access_token()
            if not token:
                return {'status': False, 'message': 'Failed to authenticate'}
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            print(f"\n=== VERIFYING MONNIFY PAYMENT ===")
            print(f"Reference: {reference}")
            
            response = requests.get(
                f'{self.base_url}/api/v1/merchant/transactions/query?paymentReference={reference}',
                headers=headers
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result['requestSuccessful']:
                    payment_data = result['responseBody']
                    # Format to match Paystack structure
                    return {
                        'status': True,
                        'data': {
                            'status': 'success' if payment_data['paymentStatus'] == 'PAID' else 'failed',
                            'amount': payment_data['amount'],
                            'reference': reference
                        }
                    }
                else:
                    return {
                        'status': False,
                        'message': result['responseMessage']
                    }
            else:
                return {
                    'status': False,
                    'message': f'HTTP Error: {response.status_code}'
                }
                
        except Exception as e:
            print(f"❌ Monnify verification error: {e}")
            return {'status': False, 'message': str(e)}

monnify = Monnify()