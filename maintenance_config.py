# maintenance_config.py
import json
import os

class MaintenanceConfig:
    def __init__(self, config_file='maintenance.json'):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """Load maintenance configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                return self.get_default_config()
        return self.get_default_config()
    
    def save_config(self):
        """Save maintenance configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_default_config(self):
        """Get default configuration"""
        return {
            'enabled': False,
            'message': 'We are currently performing scheduled maintenance.',
            'estimated_return': '24 hours',
            'allowed_ips': ['127.0.0.1'],
            'allowed_paths': ['/static', '/admin/maintenance'],
            'social_links': {
                'facebook': '#',
                'instagram': '#',
                'twitter': '#',
                'email': 'support@captainsignature.com'
            }
        }
    
    @property
    def enabled(self):
        return self.config.get('enabled', False)
    
    @enabled.setter
    def enabled(self, value):
        self.config['enabled'] = value
        self.save_config()
    
    @property
    def message(self):
        return self.config.get('message', 'Under Maintenance')
    
    @message.setter
    def message(self, value):
        self.config['message'] = value
        self.save_config()