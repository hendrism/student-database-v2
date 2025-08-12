#!/usr/bin/env python3
"""Create initial admin user."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, User

def create_admin():
    app = create_app()
    
    with app.app_context():
        # Check if admin already exists
        if User.query.filter_by(username='admin').first():
            print("Admin user already exists!")
            return
        
        # Create admin user
        admin = User(
            username='admin',
            email='admin@yourschool.edu',
            first_name='Admin',
            last_name='User',
            role='admin'
        )
        admin.set_password('AdminPass123!')  # Change this!
        admin.email_verified = True
        
        db.session.add(admin)
        db.session.commit()
        
        print("✅ Admin user created!")
        print("Username: admin")
        print("Password: AdminPass123!")
        print("⚠️  CHANGE THE PASSWORD IMMEDIATELY!")

if __name__ == "__main__":
    create_admin()