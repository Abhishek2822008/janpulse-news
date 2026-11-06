"""
JanPulse Administration CLI Tool
Usage:
  python manage.py create-admin
  python manage.py run
"""

import sys
import getpass
from werkzeug.security import generate_password_hash
import db
from app import app
from init_db import init_database

def create_admin_interactive():
    print("=" * 55)
    print("  JanPulse Newsroom - Secure Admin Provisioning CLI")
    print("=" * 55)
    
    name = input("Enter Admin Full Name [Chief Editor]: ").strip() or "Chief Editor"
    email = input("Enter Admin Email [admin@janpulse.com]: ").strip().lower() or "admin@janpulse.com"
    
    password = getpass.getpass("Enter Secure Admin Password: ")
    if not password:
        print("Password cannot be empty!")
        return

    confirm = getpass.getpass("Confirm Admin Password: ")
    if password != confirm:
        print("Error: Passwords do not match!")
        return

    with app.app_context():
        # Check if user already exists
        existing = db.query_db("SELECT id, role FROM users WHERE email = %s", (email,), one=True)
        pw_hash = generate_password_hash(password, method='scrypt')
        
        if existing:
            db.execute_db("UPDATE users SET name = %s, password_hash = %s, role = 'admin', is_active = 1 WHERE id = %s", (name, pw_hash, existing['id']))
            print(f"\nSuccessfully elevated existing account '{email}' to newsroom Administrator!")
        else:
            res = db.execute_db("""
                INSERT INTO users (name, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, 'admin', 1)
            """, (name, email, pw_hash))
            print(f"\nSuccessfully created new Newsroom Administrator: {email} (User ID #{res['lastrowid']})")
        print("Admin can now log in at /admin/login securely.")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'create-admin':
        create_admin_interactive()
    elif len(sys.argv) > 1 and sys.argv[1] == 'init-db':
        init_database()
    elif len(sys.argv) > 1 and sys.argv[1] == 'run':
        app.run(host='127.0.0.1', port=5000, debug=True)
    else:
        print("Usage:")
        print("  python manage.py create-admin    - Provision new administrator account")
        print("  python manage.py init-db         - Initialize MySQL tables and seed data")
        print("  python manage.py run             - Start local development server")
