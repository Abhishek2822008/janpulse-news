import functools
import secrets
from flask import session, redirect, url_for, flash, request, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from db import query_db

def hash_password(password: str) -> str:
    """Hash password using Werkzeug's secure scrypt/pbkdf2."""
    return generate_password_hash(password, method='scrypt')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored hash."""
    return check_password_hash(password_hash, password)

def generate_csrf_token() -> str:
    """Generate or retrieve a CSRF token stored in session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(24)
    return session['_csrf_token']

def validate_csrf(token: str) -> bool:
    """Validate submitted CSRF token against session."""
    session_token = session.get('_csrf_token')
    if not session_token or not token or session_token != token:
        return False
    return True

def get_current_user():
    """Retrieve full current user record from database based on session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    user = query_db("SELECT id, name, email, role, is_super_admin, branch, avatar, is_active FROM users WHERE id = %s AND is_active = 1", (user_id,), one=True)
    return user

def login_required(view):
    """Decorator to require normal user authentication."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required', 'authenticated': False}), 401
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('auth_login', next=request.url))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    """Decorator to require strict Administrator privileges."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        user_id = session.get('user_id')
        user_role = session.get('user_role')
        if not user_id or user_role != 'admin':
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Administrator access required', 'authorized': False}), 403
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('admin_login', next=request.url))
        return view(**kwargs)
    return wrapped_view
