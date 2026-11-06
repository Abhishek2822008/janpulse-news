import pymysql
import pymysql.cursors
from flask import g, current_app
from config import Config

def get_db():
    """Get a database connection for the current application context."""
    if 'db' not in g:
        g.db = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
    return g.db

def close_db(e=None):
    """Close the current database connection if open."""
    db = g.pop('db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass

def query_db(query, args=(), one=False):
    """Execute a SELECT query with parameters and return dict rows."""
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(query, args)
        rv = cursor.fetchall()
        return (rv[0] if rv else None) if one else rv

def execute_db(query, args=(), commit=True):
    """Execute an INSERT, UPDATE, or DELETE query with parameters."""
    conn = get_db()
    with conn.cursor() as cursor:
        affected = cursor.execute(query, args)
        last_id = cursor.lastrowid
        if commit:
            conn.commit()
        return {'lastrowid': last_id, 'affected_rows': affected}

def init_app(app):
    """Register database teardown with Flask app."""
    app.teardown_appcontext(close_db)
