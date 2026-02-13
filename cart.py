# cart.py
from flask import session

class Cart:
    def __init__(self):
        self.cart = session.get('cart', {})
        # Clean up any invalid entries
        self._clean_cart()
    
    def _clean_cart(self):
        """Remove any invalid entries from cart"""
        if not isinstance(self.cart, dict):
            self.cart = {}
            session['cart'] = self.cart
            return
        
        # Remove entries with invalid data
        to_remove = []
        for product_id, item in self.cart.items():
            if not isinstance(item, dict) or 'quantity' not in item:
                to_remove.append(product_id)
        
        for product_id in to_remove:
            del self.cart[product_id]
        
        if to_remove:
            session['cart'] = self.cart
            session.modified = True
    
    def add(self, product_id, quantity=1, price=0, name='', image=''):
        """Add item to cart"""
        product_id = str(product_id)
        if product_id in self.cart:
            self.cart[product_id]['quantity'] += quantity
        else:
            self.cart[product_id] = {
                'quantity': quantity,
                'price': float(price),
                'name': name,
                'image': image
            }
        session['cart'] = self.cart
        session.modified = True
        return self.get_total_items()
    
    def update(self, product_id, quantity):
        """Update item quantity"""
        product_id = str(product_id)
        if product_id in self.cart:
            if quantity <= 0:
                del self.cart[product_id]
            else:
                self.cart[product_id]['quantity'] = quantity
        session['cart'] = self.cart
        session.modified = True
    
    def remove(self, product_id):
        """Remove item from cart"""
        product_id = str(product_id)
        if product_id in self.cart:
            del self.cart[product_id]
        session['cart'] = self.cart
        session.modified = True
    
    def get_cart(self):
        """Get cart contents"""
        return self.cart
    
    def get_subtotal(self):
        """Calculate cart subtotal (without delivery)"""
        total = 0
        for item in self.cart.values():
            if isinstance(item, dict) and 'price' in item and 'quantity' in item:
                total += float(item['price']) * int(item['quantity'])
        return total
    
    def get_delivery_fee(self):
        """Get fixed delivery fee for Nigeria"""
        return 1500.00  # Fixed delivery fee in Naira
    
    def get_total(self):
        """Calculate cart total with delivery"""
        return self.get_subtotal() + self.get_delivery_fee()
    
    def get_total_items(self):
        """Get total number of items in cart"""
        total = 0
        for item in self.cart.values():
            if isinstance(item, dict) and 'quantity' in item:
                total += int(item['quantity'])
        return total
    
    def clear(self):
        """Clear the cart"""
        session['cart'] = {}
        session.modified = True
        self.cart = {}
    
    def get_items_count(self):
        """Get count of unique items"""
        return len(self.cart)