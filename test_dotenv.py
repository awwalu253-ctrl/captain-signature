# test_dotenv.py
import os
from dotenv import load_dotenv

print("Current directory:", os.getcwd())
print("Looking for .env file...")

# Load the .env file
loaded = load_dotenv()
print(f"load_dotenv() returned: {loaded}")

# Check if variables are loaded
print("\nEnvironment variables after load:")
print(f"MAIL_SERVER: {os.environ.get('MAIL_SERVER', 'NOT SET')}")
print(f"MAIL_USERNAME: {os.environ.get('MAIL_USERNAME', 'NOT SET')}")
print(f"MAIL_PASSWORD: {'SET' if os.environ.get('MAIL_PASSWORD') else 'NOT SET'}")
print(f"ADMIN_EMAIL: {os.environ.get('ADMIN_EMAIL', 'NOT SET')}")

# Check if .env file exists
import os.path
env_path = os.path.join(os.getcwd(), '.env')
print(f"\n.env file exists: {os.path.exists(env_path)}")