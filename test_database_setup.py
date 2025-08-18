#!/usr/bin/env python3
"""Test database setup and creation."""

import os
import sys
from pathlib import Path

def test_database_setup():
    """Test if we can create the database successfully."""
    
    print("🔍 Testing database setup...")
    print(f"Python path: {sys.executable}")
    print(f"Current directory: {os.getcwd()}")
    
    # Check if instance directory exists
    instance_dir = Path("instance")
    print(f"Instance directory: {instance_dir.absolute()}")
    print(f"Instance directory exists: {instance_dir.exists()}")
    
    if not instance_dir.exists():
        print("📁 Creating instance directory...")
        instance_dir.mkdir(exist_ok=True)
        print("✅ Instance directory created")
    
    # Test basic imports
    try:
        print("📦 Testing imports...")
        from config.settings import config
        print("✅ Config imported successfully")
        
        from extensions import db
        print("✅ Database models imported successfully")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    
    # Test Flask app creation
    try:
        print("🚀 Testing Flask app creation...")
        from app import create_app
        
        app = create_app('development')
        print("✅ Flask app created successfully")
        
        with app.app_context():
            # Try to create database tables
            print("🗄️ Testing database table creation...")
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Check if database file was created
            db_path = Path("instance/student_database.db")
            if db_path.exists():
                print(f"✅ Database file created: {db_path.absolute()}")
                print(f"Database file size: {db_path.stat().st_size} bytes")
            else:
                print(f"⚠️ Database file not found at: {db_path.absolute()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating app or database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_database_setup()
    if success:
        print("\n🎉 Database setup test completed successfully!")
        print("You can now run: python app.py")
    else:
        print("\n💥 Database setup test failed!")
        print("Please check the errors above and fix them.")
        sys.exit(1)