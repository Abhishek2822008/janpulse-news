import os
import re
import secrets
from datetime import datetime
from urllib.parse import urlparse, urljoin
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, abort, g
)

from config import Config
import db
from auth import (
    hash_password, verify_password, generate_csrf_token,
    validate_csrf, get_current_user, login_required, admin_required
)
from media_storage import init_cloudinary, save_uploaded_media
from mail_service import (
    generate_reset_token, verify_reset_token, send_password_reset_email,
    generate_otp_code, send_password_reset_otp_email
)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Cloudinary (Option 3 Cloud Media CDN)
init_cloudinary(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register db teardown
db.init_app(app)

# Helper for slug creation
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text).strip('-')
    return text or 'news-item'

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

# ---------------------------------------------------------
# Template Context Processors & CSRF
# ---------------------------------------------------------
@app.context_processor
def inject_global_template_data():
    """Inject language, active user, CSRF token, and global categories into all templates."""
    lang = session.get('lang', 'hi')
    user = get_current_user()
    
    # 11 Standard categories
    categories = db.query_db("SELECT id, name_en, name_hi, slug FROM categories ORDER BY id ASC")
    
    # Live breaking news headlines
    breaking = db.query_db("""
        SELECT id, title_en, title_hi, slug, published_at
        FROM news
        WHERE is_breaking = 1 AND status = 'published' AND published_at <= NOW()
        ORDER BY published_at DESC, id DESC
        LIMIT 8
    """)

    return {
        'current_lang': lang,
        'current_user': user,
        'csrf_token': generate_csrf_token,
        'nav_categories': categories,
        'breaking_news_list': breaking,
        'current_category_slug': None
    }

# Language switcher route
@app.route('/set-language/<lang>')
def set_language(lang):
    if lang in ['hi', 'en']:
        session['lang'] = lang
    next_page = request.args.get('next') or request.referrer or url_for('index')
    if not is_safe_url(next_page):
        next_page = url_for('index')
    return redirect(next_page)

# ---------------------------------------------------------
# Public News Routes
# ---------------------------------------------------------

@app.route('/')
def index():
    user_id = session.get('user_id')

    # Latest News Algorithm: ORDER BY published_at DESC, id DESC
    latest_news = db.query_db("""
        SELECT n.*, c.name_en AS cat_name_en, c.name_hi AS cat_name_hi, c.slug AS cat_slug,
               CONCAT(l.city, ', ', l.state) AS location_name,
               (SELECT COUNT(*) FROM likes lk WHERE lk.news_id = n.id) AS likes_count,
               (SELECT COUNT(*) FROM comments cm WHERE cm.news_id = n.id AND cm.status = 'approved') AS comments_count
        FROM news n
        JOIN categories c ON n.category_id = c.id
        LEFT JOIN locations l ON n.location_id = l.id
        WHERE n.status = 'published' AND n.published_at <= NOW()
        ORDER BY n.published_at DESC, n.id DESC
        LIMIT 15
    """)

    # Inject whether current logged-in user has liked / bookmarked each article
    if user_id:
        user_likes = {row['news_id'] for row in db.query_db("SELECT news_id FROM likes WHERE user_id = %s", (user_id,))}
        user_bookmarks = {row['news_id'] for row in db.query_db("SELECT news_id FROM bookmarks WHERE user_id = %s", (user_id,))}
        for item in latest_news:
            item['user_has_liked'] = item['id'] in user_likes
            item['user_has_bookmarked'] = item['id'] in user_bookmarks
    else:
        for item in latest_news:
            item['user_has_liked'] = False
            item['user_has_bookmarked'] = False

    # Lead Featured Story (first featured or newest)
    lead_story = next((x for x in latest_news if x.get('is_featured')), (latest_news[0] if latest_news else None))
    
    # Secondary Stories for Hero Section
    secondary_stories = [x for x in latest_news if lead_story and x['id'] != lead_story['id']][:2]

    # Trending Now Sidebar (sorted by views_count DESC)
    trending_news = sorted(latest_news, key=lambda x: (x.get('views_count', 0), x['id']), reverse=True)[:5]

    # Category Spotlights (India & Tech)
    india_spotlight = [x for x in latest_news if x.get('cat_slug') == 'india'][:3]
    tech_spotlight = [x for x in latest_news if x.get('cat_slug') == 'technology'][:3]

    return render_template(
        'index.html',
        lead_story=lead_story,
        secondary_stories=secondary_stories,
        trending_news=trending_news,
        latest_news=latest_news,
        india_spotlight=india_spotlight,
        tech_spotlight=tech_spotlight
    )

@app.route('/category/<slug>')
def category_view(slug):
    category = db.query_db("SELECT * FROM categories WHERE slug = %s", (slug,), one=True)
    if not category:
        abort(404)

    user_id = session.get('user_id')
    articles = db.query_db("""
        SELECT n.*, c.name_en AS cat_name_en, c.name_hi AS cat_name_hi,
               CONCAT(l.city, ', ', l.state) AS location_name,
               (SELECT COUNT(*) FROM likes lk WHERE lk.news_id = n.id) AS likes_count
        FROM news n
        JOIN categories c ON n.category_id = c.id
        LEFT JOIN locations l ON n.location_id = l.id
        WHERE n.category_id = %s AND n.status = 'published' AND n.published_at <= NOW()
        ORDER BY n.published_at DESC, n.id DESC
    """, (category['id'],))

    if user_id:
        user_likes = {row['news_id'] for row in db.query_db("SELECT news_id FROM likes WHERE user_id = %s", (user_id,))}
        user_bookmarks = {row['news_id'] for row in db.query_db("SELECT news_id FROM bookmarks WHERE user_id = %s", (user_id,))}
        for item in articles:
            item['user_has_liked'] = item['id'] in user_likes
            item['user_has_bookmarked'] = item['id'] in user_bookmarks

    return render_template('category.html', category=category, articles=articles, current_category_slug=slug)

@app.route('/article/<slug>')
def article_detail(slug):
    # Retrieve article
    article = db.query_db("""
        SELECT n.*, c.name_en AS cat_name_en, c.name_hi AS cat_name_hi, c.slug AS cat_slug,
               CONCAT(l.city, ', ', l.district, ', ', l.state) AS location_name,
               u.name AS author_name
        FROM news n
        JOIN categories c ON n.category_id = c.id
        LEFT JOIN locations l ON n.location_id = l.id
        LEFT JOIN users u ON n.created_by = u.id
        WHERE n.slug = %s
    """, (slug,), one=True)

    if not article:
        abort(404)

    # Draft articles can only be seen by admins
    if article['status'] != 'published':
        user = get_current_user()
        if not user or user['role'] != 'admin':
            abort(404)

    # Increment view counter
    db.execute_db("UPDATE news SET views_count = views_count + 1 WHERE id = %s", (article['id'],))
    article['views_count'] += 1

    # Likes & Bookmarks info
    likes_count = db.query_db("SELECT COUNT(*) AS total FROM likes WHERE news_id = %s", (article['id'],), one=True)['total']
    
    user_id = session.get('user_id')
    user_has_liked = False
    user_has_bookmarked = False
    if user_id:
        user_has_liked = bool(db.query_db("SELECT id FROM likes WHERE news_id = %s AND user_id = %s", (article['id'], user_id), one=True))
        user_has_bookmarked = bool(db.query_db("SELECT id FROM bookmarks WHERE news_id = %s AND user_id = %s", (article['id'], user_id), one=True))

    # Approved comments
    comments = db.query_db("""
        SELECT c.*, u.name AS user_name, u.avatar AS user_avatar
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.news_id = %s AND c.status = 'approved'
        ORDER BY c.created_at DESC
    """, (article['id'],))

    # Tags
    tags = db.query_db("""
        SELECT t.name_en, t.name_hi, t.slug
        FROM tags t
        JOIN news_tags nt ON t.id = nt.tag_id
        WHERE nt.news_id = %s
    """, (article['id'],))

    # Related news in same category
    related_articles = db.query_db("""
        SELECT n.id, n.title_en, n.title_hi, n.slug, n.image_url, n.published_at, n.views_count,
               c.name_en AS cat_name_en, c.name_hi AS cat_name_hi
        FROM news n
        JOIN categories c ON n.category_id = c.id
        WHERE n.category_id = %s AND n.id != %s AND n.status = 'published' AND n.published_at <= NOW()
        ORDER BY n.published_at DESC
        LIMIT 3
    """, (article['category_id'], article['id']))

    return render_template(
        'article.html',
        article=article,
        likes_count=likes_count,
        user_has_liked=user_has_liked,
        user_has_bookmarked=user_has_bookmarked,
        comments=comments,
        tags=tags,
        related_articles=related_articles,
        current_category_slug=article['cat_slug']
    )

@app.route('/local-news')
def local_news_view():
    """Hyper-local news filter: State -> District -> City"""
    selected_state = request.args.get('state', '').strip()
    selected_district = request.args.get('district', '').strip()
    selected_city = request.args.get('city', '').strip()

    # Get distinct states for dropdown
    states = [r['state'] for r in db.query_db("SELECT DISTINCT state FROM locations ORDER BY state ASC")]

    # Get districts for selected state
    districts = []
    if selected_state:
        districts = [r['district'] for r in db.query_db("SELECT DISTINCT district FROM locations WHERE state = %s ORDER BY district ASC", (selected_state,))]

    # Get cities for selected district
    cities = []
    if selected_state and selected_district:
        cities = [r['city'] for r in db.query_db("SELECT DISTINCT city FROM locations WHERE state = %s AND district = %s ORDER BY city ASC", (selected_state, selected_district))]

    # Build dynamic filter query
    query = """
        SELECT n.*, c.name_en AS cat_name_en, c.name_hi AS cat_name_hi,
               l.state, l.district, l.city,
               (SELECT COUNT(*) FROM likes lk WHERE lk.news_id = n.id) AS likes_count
        FROM news n
        JOIN categories c ON n.category_id = c.id
        JOIN locations l ON n.location_id = l.id
        WHERE n.status = 'published' AND n.published_at <= NOW()
    """
    params = []

    if selected_state:
        query += " AND l.state = %s"
        params.append(selected_state)
    if selected_district:
        query += " AND l.district = %s"
        params.append(selected_district)
    if selected_city:
        query += " AND l.city = %s"
        params.append(selected_city)

    query += " ORDER BY n.published_at DESC, n.id DESC"

    articles = db.query_db(query, tuple(params))

    user_id = session.get('user_id')
    if user_id:
        user_likes = {row['news_id'] for row in db.query_db("SELECT news_id FROM likes WHERE user_id = %s", (user_id,))}
        user_bookmarks = {row['news_id'] for row in db.query_db("SELECT news_id FROM bookmarks WHERE user_id = %s", (user_id,))}
        for item in articles:
            item['user_has_liked'] = item['id'] in user_likes
            item['user_has_bookmarked'] = item['id'] in user_bookmarks

    return render_template(
        'local_news.html',
        articles=articles,
        states=states,
        districts=districts,
        cities=cities,
        selected_state=selected_state,
        selected_district=selected_district,
        selected_city=selected_city
    )

@app.route('/api/locations/districts')
def api_location_districts():
    state = request.args.get('state', '').strip()
    rows = db.query_db("SELECT DISTINCT district FROM locations WHERE state = %s ORDER BY district ASC", (state,))
    return jsonify({'districts': [r['district'] for r in rows]})

@app.route('/api/locations/cities')
def api_location_cities():
    state = request.args.get('state', '').strip()
    district = request.args.get('district', '').strip()
    rows = db.query_db("SELECT DISTINCT city FROM locations WHERE state = %s AND district = %s ORDER BY city ASC", (state, district))
    return jsonify({'cities': [r['city'] for r in rows]})

@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    category_slug = request.args.get('category', '').strip()
    results = []

    if query:
        search_term = f"%{query}%"
        sql = """
            SELECT n.*, c.name_en AS cat_name_en, c.name_hi AS cat_name_hi, c.slug AS cat_slug
            FROM news n
            JOIN categories c ON n.category_id = c.id
            WHERE n.status = 'published' AND n.published_at <= NOW()
              AND (
                  n.title_en LIKE %s OR n.title_hi LIKE %s OR
                  n.excerpt_en LIKE %s OR n.excerpt_hi LIKE %s OR
                  n.content_en LIKE %s OR n.content_hi LIKE %s
              )
        """
        params = [search_term, search_term, search_term, search_term, search_term, search_term]

        if category_slug:
            sql += " AND c.slug = %s"
            params.append(category_slug)

        sql += " ORDER BY n.published_at DESC, n.id DESC LIMIT 50"
        results = db.query_db(sql, tuple(params))

    return render_template(
        'search.html',
        results=results,
        query=query,
        selected_category=category_slug
    )

# ---------------------------------------------------------
# User Engagement Routes (Comments, Likes, Bookmarks)
# ---------------------------------------------------------

@app.route('/api/news/<int:news_id>/like', methods=['POST'])
@login_required
def api_toggle_like(news_id):
    user_id = session['user_id']
    
    # Check if liked already
    existing = db.query_db("SELECT id FROM likes WHERE news_id = %s AND user_id = %s", (news_id, user_id), one=True)
    if existing:
        db.execute_db("DELETE FROM likes WHERE id = %s", (existing['id'],))
        liked = False
    else:
        db.execute_db("INSERT INTO likes (news_id, user_id) VALUES (%s, %s)", (news_id, user_id))
        liked = True

    total_likes = db.query_db("SELECT COUNT(*) AS total FROM likes WHERE news_id = %s", (news_id,), one=True)['total']
    return jsonify({'success': True, 'liked': liked, 'likes_count': total_likes})

@app.route('/api/news/<int:news_id>/bookmark', methods=['POST'])
@login_required
def api_toggle_bookmark(news_id):
    user_id = session['user_id']
    
    existing = db.query_db("SELECT id FROM bookmarks WHERE news_id = %s AND user_id = %s", (news_id, user_id), one=True)
    if existing:
        db.execute_db("DELETE FROM bookmarks WHERE id = %s", (existing['id'],))
        bookmarked = False
    else:
        db.execute_db("INSERT INTO bookmarks (news_id, user_id) VALUES (%s, %s)", (news_id, user_id))
        bookmarked = True

    return jsonify({'success': True, 'bookmarked': bookmarked})

@app.route('/article/<int:news_id>/comment', methods=['POST'])
@login_required
def add_comment(news_id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid CSRF token session. Please try again.', 'danger')
        return redirect(request.referrer or url_for('index'))

    comment_text = request.form.get('comment_text', '').strip()
    if not comment_text or len(comment_text) < 3:
        flash('Comment cannot be empty or too short.', 'warning')
        return redirect(request.referrer or url_for('index'))

    user_id = session['user_id']
    db.execute_db("""
        INSERT INTO comments (news_id, user_id, comment_text, status)
        VALUES (%s, %s, %s, 'approved')
    """, (news_id, user_id, comment_text))

    flash('Your comment has been posted successfully!', 'success')
    news = db.query_db("SELECT slug FROM news WHERE id = %s", (news_id,), one=True)
    if news:
        return redirect(url_for('article_detail', slug=news['slug']) + '#comments-section')
    return redirect(request.referrer or url_for('index'))

# ---------------------------------------------------------
# User Authentication & Profile
# ---------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def auth_login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token. Please try again.', 'danger')
            return redirect(url_for('auth_login'))

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = db.query_db("SELECT * FROM users WHERE email = %s AND is_active = 1", (email,), one=True)
        if user and verify_password(password, user['password_hash']):
            session.permanent = True
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash(f"Welcome back, {user['name']}!", 'success')
            
            next_url = request.args.get('next')
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def auth_register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token. Please try again.', 'danger')
            return redirect(url_for('auth_register'))

        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash('All fields are required.', 'warning')
            return redirect(url_for('auth_register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'warning')
            return redirect(url_for('auth_register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'warning')
            return redirect(url_for('auth_register'))

        # Check existing email
        existing = db.query_db("SELECT id FROM users WHERE email = %s", (email,), one=True)
        if existing:
            flash('An account with this email address already exists.', 'warning')
            return redirect(url_for('auth_register'))

        # SECURITY: Strictly assign role='user'. Never trust client input!
        pw_hash = hash_password(password)
        res = db.execute_db("""
            INSERT INTO users (name, email, password_hash, role, is_active)
            VALUES (%s, %s, %s, 'user', 1)
        """, (name, email, pw_hash))

        session.permanent = True
        session['user_id'] = res['lastrowid']
        session['user_name'] = name
        session['user_role'] = 'user'

        flash('Your account has been created successfully! Welcome to JanPulse.', 'success')
        next_url = request.args.get('next')
        if next_url and is_safe_url(next_url):
            return redirect(next_url)
        return redirect(url_for('index'))

    return render_template('auth/register.html')

@app.route('/logout')
def auth_logout():
    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('index'))

# ---------------------------------------------------------
# Password Recovery / Reset Flow (SMTP Token Based)
# ---------------------------------------------------------

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token. Please try again.', 'danger')
            return redirect(url_for('forgot_password'))

        email = request.form.get('email', '').strip().lower()
        if not email:
            flash('Please enter your registered email address.', 'warning')
            return redirect(url_for('forgot_password'))

        user = db.query_db("SELECT id, name, email, is_active FROM users WHERE email = %s", (email,), one=True)
        if not user:
            flash('No account found with this email. Please check your spelling or register a new account.', 'warning')
            return redirect(url_for('forgot_password'))

        if not user.get('is_active'):
            flash('This account is currently deactivated. Please contact administrator.', 'danger')
            return redirect(url_for('forgot_password'))

        # Generate 6-digit OTP
        otp_code = generate_otp_code()
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(minutes=10)

        # Invalidate old OTPs for this email
        db.execute_db("UPDATE password_otps SET is_used = 1 WHERE email = %s AND is_used = 0", (email,))

        # Save new OTP to database
        db.execute_db("""
            INSERT INTO password_otps (user_id, email, otp_code, expires_at, is_used)
            VALUES (%s, %s, %s, %s, 0)
        """, (user['id'], email, otp_code, expires_at))

        # Store in session for OTP verification
        session['reset_email'] = email
        session['reset_user_id'] = user['id']
        session['otp_verified'] = False

        # Send OTP Email via SMTP
        mail_res = send_password_reset_otp_email(user['email'], user['name'], otp_code)
        if mail_res.get('success'):
            flash(f"A 6-digit verification OTP has been sent to {user['email']}. Please check your inbox (and spam folder).", 'success')
            return redirect(url_for('verify_otp'))
        else:
            flash(f"Failed to dispatch OTP email: {mail_res.get('error')}", 'danger')
            return redirect(url_for('forgot_password'))

    return render_template('auth/forgot_password.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'user_id' in session:
        return redirect(url_for('index'))

    reset_email = session.get('reset_email')
    reset_user_id = session.get('reset_user_id')
    if not reset_email or not reset_user_id:
        flash('Please enter your email to request an OTP first.', 'warning')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token. Please try again.', 'danger')
            return redirect(url_for('verify_otp'))

        otp_input = request.form.get('otp', '').strip()
        if not otp_input or len(otp_input) != 6:
            flash('Please enter a valid 6-digit OTP code.', 'warning')
            return render_template('auth/verify_otp.html')

        # Check OTP in database
        otp_record = db.query_db("""
            SELECT id FROM password_otps
            WHERE email = %s AND otp_code = %s AND is_used = 0 AND expires_at > NOW()
            ORDER BY id DESC LIMIT 1
        """, (reset_email, otp_input), one=True)

        if not otp_record:
            flash('Invalid or expired OTP code. Please re-check the digits or request a new OTP.', 'danger')
            return render_template('auth/verify_otp.html')

        # Mark OTP as used
        db.execute_db("UPDATE password_otps SET is_used = 1 WHERE id = %s", (otp_record['id'],))

        # Mark session as verified
        session['otp_verified'] = True
        flash('OTP verified successfully! Please create your new password.', 'success')
        return redirect(url_for('reset_password'))

    return render_template('auth/verify_otp.html')

@app.route('/resend-otp', methods=['GET', 'POST'])
def resend_otp():
    if 'user_id' in session:
        return redirect(url_for('index'))

    reset_email = session.get('reset_email')
    reset_user_id = session.get('reset_user_id')
    if not reset_email or not reset_user_id:
        flash('Please request an OTP first.', 'warning')
        return redirect(url_for('forgot_password'))

    user = db.query_db("SELECT id, name, email FROM users WHERE id = %s", (reset_user_id,), one=True)
    if not user:
        flash('User account not found.', 'danger')
        return redirect(url_for('forgot_password'))

    otp_code = generate_otp_code()
    from datetime import datetime, timedelta
    expires_at = datetime.now() + timedelta(minutes=10)

    db.execute_db("UPDATE password_otps SET is_used = 1 WHERE email = %s AND is_used = 0", (reset_email,))
    db.execute_db("""
        INSERT INTO password_otps (user_id, email, otp_code, expires_at, is_used)
        VALUES (%s, %s, %s, %s, 0)
    """, (user['id'], reset_email, otp_code, expires_at))

    session['otp_verified'] = False
    send_password_reset_otp_email(user['email'], user['name'], otp_code)
    flash(f"A fresh 6-digit OTP has been sent to {user['email']}.", 'info')
    return redirect(url_for('verify_otp'))

@app.route('/reset-password', methods=['GET', 'POST'])
@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token=None):
    if 'user_id' in session:
        return redirect(url_for('index'))

    target_user_id = None
    target_user = None

    if token:
        target_user_id = verify_reset_token(token, max_age=900)
        if not target_user_id:
            flash('Password reset link is invalid or has expired (15-minute validity).', 'danger')
            return redirect(url_for('forgot_password'))
        target_user = db.query_db("SELECT id, name, email FROM users WHERE id = %s", (target_user_id,), one=True)
    else:
        # OTP verification flow
        if not session.get('otp_verified') or not session.get('reset_user_id'):
            flash('Please verify your 6-digit OTP first.', 'warning')
            return redirect(url_for('forgot_password'))
        target_user_id = session.get('reset_user_id')
        target_user = db.query_db("SELECT id, name, email FROM users WHERE id = %s", (target_user_id,), one=True)

    if not target_user:
        flash('Account not found.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token. Please try again.', 'danger')
            return redirect(url_for('reset_password', token=token) if token else url_for('reset_password'))

        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
            return render_template('auth/reset_password.html', token=token, user=target_user)

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'warning')
            return render_template('auth/reset_password.html', token=token, user=target_user)

        new_hash = hash_password(password)
        db.execute_db("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, target_user['id']))

        # Clear reset session variables
        session.pop('reset_email', None)
        session.pop('reset_user_id', None)
        session.pop('otp_verified', None)

        flash('Your password has been changed successfully! You can now sign in with your new password.', 'success')
        return redirect(url_for('auth_login'))

    return render_template('auth/reset_password.html', token=token, user=target_user)

@app.route('/user/saved')
@login_required
def user_saved():
    user_id = session['user_id']
    saved_articles = db.query_db("""
        SELECT n.*, c.name_en AS cat_name_en, c.name_hi AS cat_name_hi,
               (SELECT COUNT(*) FROM likes lk WHERE lk.news_id = n.id) AS likes_count
        FROM bookmarks b
        JOIN news n ON b.news_id = n.id
        JOIN categories c ON n.category_id = c.id
        WHERE b.user_id = %s
        ORDER BY b.created_at DESC
    """, (user_id,))
    return render_template('user/saved.html', saved_articles=saved_articles)

@app.route('/user/profile')
@login_required
def user_profile():
    user_id = session['user_id']
    user = db.query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    stats = {
        'bookmarks_count': db.query_db("SELECT COUNT(*) AS c FROM bookmarks WHERE user_id = %s", (user_id,), one=True)['c'],
        'likes_count': db.query_db("SELECT COUNT(*) AS c FROM likes WHERE user_id = %s", (user_id,), one=True)['c'],
        'comments_count': db.query_db("SELECT COUNT(*) AS c FROM comments WHERE user_id = %s", (user_id,), one=True)['c']
    }
    return render_template('user/profile.html', user=user, stats=stats)

@app.route('/user/profile/update', methods=['POST'])
@login_required
def user_update_profile():
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid session token.', 'danger')
        return redirect(url_for('user_profile'))

    name = request.form.get('name', '').strip()
    if name:
        db.execute_db("UPDATE users SET name = %s WHERE id = %s", (name, session['user_id']))
        session['user_name'] = name
        flash('Profile updated successfully!', 'success')
    return redirect(url_for('user_profile'))

@app.route('/user/password/update', methods=['POST'])
@login_required
def user_update_password():
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid session token.', 'danger')
        return redirect(url_for('user_profile'))

    curr_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    conf_pw = request.form.get('confirm_new_password', '')

    user = db.query_db("SELECT password_hash FROM users WHERE id = %s", (session['user_id'],), one=True)
    if not verify_password(curr_pw, user['password_hash']):
        flash('Current password was incorrect.', 'danger')
        return redirect(url_for('user_profile'))

    if len(new_pw) < 6 or new_pw != conf_pw:
        flash('New password must be at least 6 characters and match confirmation.', 'warning')
        return redirect(url_for('user_profile'))

    new_hash = hash_password(new_pw)
    db.execute_db("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, session['user_id']))
    flash('Your password has been changed successfully.', 'success')
    return redirect(url_for('user_profile'))

# ---------------------------------------------------------
# Separate Admin CMS Routes (/admin/login & /admin/*)
# ---------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # If already logged in as admin, redirect to admin dashboard
    if session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token. Please try again.', 'danger')
            return redirect(url_for('admin_login'))

        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = db.query_db("SELECT * FROM users WHERE email = %s AND is_active = 1", (email,), one=True)
        
        # STRICT SERVER-SIDE AUTHORIZATION: Verify password AND role == 'admin'
        if user and verify_password(password, user['password_hash']):
            if user['role'] != 'admin':
                flash('Access Denied: You do not possess newsroom administrator credentials.', 'danger')
                return redirect(url_for('admin_login'))

            session.permanent = True
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['is_super_admin'] = bool(user.get('is_super_admin', 0))
            session['user_branch'] = user.get('branch') or 'Headquarters'
            flash(f"Welcome back to Newsroom CMS, {user['name']}!", 'success')
            
            next_url = request.args.get('next')
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid newsroom administrative credentials.', 'danger')

    return render_template('admin/login.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    # Compute dashboard analytics
    stats = {
        'published_count': db.query_db("SELECT COUNT(*) AS c FROM news WHERE status = 'published'", one=True)['c'],
        'drafts_count': db.query_db("SELECT COUNT(*) AS c FROM news WHERE status = 'draft'", one=True)['c'],
        'users_count': db.query_db("SELECT COUNT(*) AS c FROM users WHERE role = 'user'", one=True)['c'],
        'comments_count': db.query_db("SELECT COUNT(*) AS c FROM comments", one=True)['c']
    }

    recent_articles = db.query_db("""
        SELECT n.*, c.name_en AS cat_name_en
        FROM news n
        JOIN categories c ON n.category_id = c.id
        ORDER BY n.id DESC
        LIMIT 8
    """)

    return render_template('admin/dashboard.html', stats=stats, recent_articles=recent_articles)

@app.route('/admin/news')
@admin_required
def admin_news_list():
    query_search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    cat_filter = request.args.get('category', '').strip()

    sql = """
        SELECT n.*, c.name_en AS cat_name_en,
               (SELECT COUNT(*) FROM likes lk WHERE lk.news_id = n.id) AS likes_count
        FROM news n
        JOIN categories c ON n.category_id = c.id
        WHERE 1=1
    """
    params = []

    if query_search:
        sql += " AND (n.title_en LIKE %s OR n.title_hi LIKE %s)"
        params.extend([f"%{query_search}%", f"%{query_search}%"])
    if status_filter:
        sql += " AND n.status = %s"
        params.append(status_filter)
    if cat_filter:
        sql += " AND n.category_id = %s"
        params.append(cat_filter)

    sql += " ORDER BY n.id DESC"
    articles = db.query_db(sql, tuple(params))
    categories = db.query_db("SELECT id, name_en FROM categories ORDER BY name_en ASC")

    return render_template('admin/news_list.html', articles=articles, categories=categories)

@app.route('/admin/news/new', methods=['GET', 'POST'])
@admin_required
def admin_news_new():
    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token.', 'danger')
            return redirect(url_for('admin_news_new'))

        title_en = request.form.get('title_en', '').strip()
        title_hi = request.form.get('title_hi', '').strip()
        excerpt_en = request.form.get('excerpt_en', '').strip()
        excerpt_hi = request.form.get('excerpt_hi', '').strip()
        content_en = request.form.get('content_en', '').strip()
        content_hi = request.form.get('content_hi', '').strip()
        category_id = request.form.get('category_id')
        location_id = request.form.get('location_id') or None
        image_url = request.form.get('image_url', '').strip()
        video_url = request.form.get('video_url', '').strip() or None
        is_breaking = 1 if request.form.get('is_breaking') else 0
        is_featured = 1 if request.form.get('is_featured') else 0
        submit_action = request.form.get('submit_action', 'publish')

        status = 'published' if submit_action == 'publish' else 'draft'

        # Handle image file upload (Cloudinary CDN or WebP Auto-Compression)
        uploaded_media_info = None
        file = request.files.get('image_file')
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext in app.config['ALLOWED_IMAGE_EXTENSIONS']:
                upload_res = save_uploaded_media(file, folder="news")
                if upload_res:
                    image_url = upload_res['url']
                    uploaded_media_info = {'path': image_url, 'type': upload_res['type'], 'name': upload_res['name']}
            else:
                flash('Unsupported image format. Allowed: png, jpg, jpeg, webp.', 'warning')

        if not image_url:
            image_url = 'https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=1200'

        # Generate unique slug
        base_slug = slugify(title_en)
        slug = base_slug
        counter = 1
        while db.query_db("SELECT id FROM news WHERE slug = %s", (slug,), one=True):
            slug = f"{base_slug}-{counter}"
            counter += 1

        published_at = datetime.now() if status == 'published' else None

        res = db.execute_db("""
            INSERT INTO news (
                title_en, title_hi, slug, excerpt_en, excerpt_hi,
                content_en, content_hi, category_id, location_id,
                image_url, video_url, is_breaking, is_featured,
                status, views_count, published_at, created_by
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, 0, %s, %s
            )
        """, (
            title_en, title_hi, slug, excerpt_en, excerpt_hi,
            content_en, content_hi, category_id, location_id,
            image_url, video_url, is_breaking, is_featured,
            status, published_at, session['user_id']
        ))

        news_id = res['lastrowid']

        # Record media upload if file was attached
        if uploaded_media_info:
            db.execute_db("""
                INSERT INTO media (news_id, file_path, file_type, file_name)
                VALUES (%s, %s, %s, %s)
            """, (news_id, uploaded_media_info['path'], uploaded_media_info['type'], uploaded_media_info['name']))

        # Process tags
        raw_tags = request.form.get('tags', '')
        if raw_tags:
            tag_names = [t.strip() for t in raw_tags.split(',') if t.strip()]
            for t_name in tag_names:
                t_slug = slugify(t_name)
                tag_row = db.query_db("SELECT id FROM tags WHERE slug = %s", (t_slug,), one=True)
                if not tag_row:
                    tag_res = db.execute_db("INSERT INTO tags (name_en, name_hi, slug) VALUES (%s, %s, %s)", (t_name, t_name, t_slug))
                    tid = tag_res['lastrowid']
                else:
                    tid = tag_row['id']
                db.execute_db("INSERT IGNORE INTO news_tags (news_id, tag_id) VALUES (%s, %s)", (news_id, tid))

        flash(f"Article '{title_en}' successfully {'published' if status == 'published' else 'saved as draft'}!", 'success')
        return redirect(url_for('admin_news_list'))

    categories = db.query_db("SELECT * FROM categories ORDER BY name_en ASC")
    locations = db.query_db("SELECT * FROM locations ORDER BY state ASC, city ASC")
    return render_template('admin/news_form.html', article=None, categories=categories, locations=locations, article_tags=[])

@app.route('/admin/news/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_news_edit(id):
    article = db.query_db("SELECT * FROM news WHERE id = %s", (id,), one=True)
    if not article:
        abort(404)

    if request.method == 'POST':
        if not validate_csrf(request.form.get('csrf_token')):
            flash('Invalid session token.', 'danger')
            return redirect(url_for('admin_news_edit', id=id))

        title_en = request.form.get('title_en', '').strip()
        title_hi = request.form.get('title_hi', '').strip()
        excerpt_en = request.form.get('excerpt_en', '').strip()
        excerpt_hi = request.form.get('excerpt_hi', '').strip()
        content_en = request.form.get('content_en', '').strip()
        content_hi = request.form.get('content_hi', '').strip()
        category_id = request.form.get('category_id')
        location_id = request.form.get('location_id') or None
        image_url = request.form.get('image_url', '').strip() or article['image_url']
        video_url = request.form.get('video_url', '').strip() or None
        is_breaking = 1 if request.form.get('is_breaking') else 0
        is_featured = 1 if request.form.get('is_featured') else 0
        submit_action = request.form.get('submit_action')

        # Status logic
        if submit_action == 'draft':
            status = 'draft'
        elif submit_action == 'publish':
            status = 'published'
        else:
            status = request.form.get('status', article['status'])

        # Handle image upload (Cloudinary CDN or WebP Auto-Compression)
        uploaded_media_info = None
        file = request.files.get('image_file')
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext in app.config['ALLOWED_IMAGE_EXTENSIONS']:
                upload_res = save_uploaded_media(file, folder="news")
                if upload_res:
                    image_url = upload_res['url']
                    uploaded_media_info = {'path': image_url, 'type': upload_res['type'], 'name': upload_res['name']}
            else:
                flash('Unsupported image format. Allowed: png, jpg, jpeg, webp.', 'warning')

        # If switching from draft to published, set published_at if null
        published_at = article['published_at']
        if status == 'published' and not published_at:
            published_at = datetime.now()

        db.execute_db("""
            UPDATE news SET
                title_en = %s, title_hi = %s, excerpt_en = %s, excerpt_hi = %s,
                content_en = %s, content_hi = %s, category_id = %s, location_id = %s,
                image_url = %s, video_url = %s, is_breaking = %s, is_featured = %s,
                status = %s, published_at = %s
            WHERE id = %s
        """, (
            title_en, title_hi, excerpt_en, excerpt_hi,
            content_en, content_hi, category_id, location_id,
            image_url, video_url, is_breaking, is_featured,
            status, published_at, id
        ))

        # Record media upload if new file was attached
        if uploaded_media_info:
            db.execute_db("""
                INSERT INTO media (news_id, file_path, file_type, file_name)
                VALUES (%s, %s, %s, %s)
            """, (id, uploaded_media_info['path'], uploaded_media_info['type'], uploaded_media_info['name']))

        # Update tags
        db.execute_db("DELETE FROM news_tags WHERE news_id = %s", (id,))
        raw_tags = request.form.get('tags', '')
        if raw_tags:
            tag_names = [t.strip() for t in raw_tags.split(',') if t.strip()]
            for t_name in tag_names:
                t_slug = slugify(t_name)
                tag_row = db.query_db("SELECT id FROM tags WHERE slug = %s", (t_slug,), one=True)
                if not tag_row:
                    tag_res = db.execute_db("INSERT INTO tags (name_en, name_hi, slug) VALUES (%s, %s, %s)", (t_name, t_name, t_slug))
                    tid = tag_res['lastrowid']
                else:
                    tid = tag_row['id']
                db.execute_db("INSERT IGNORE INTO news_tags (news_id, tag_id) VALUES (%s, %s)", (id, tid))

        flash(f"Article #{id} updated successfully!", 'success')
        return redirect(url_for('admin_news_list'))

    categories = db.query_db("SELECT * FROM categories ORDER BY name_en ASC")
    locations = db.query_db("SELECT * FROM locations ORDER BY state ASC, city ASC")
    current_tags = [r['slug'] for r in db.query_db("""
        SELECT t.slug FROM tags t JOIN news_tags nt ON t.id = nt.tag_id WHERE nt.news_id = %s
    """, (id,))]

    return render_template(
        'admin/news_form.html',
        article=article,
        categories=categories,
        locations=locations,
        article_tags=current_tags
    )

@app.route('/admin/news/<int:id>/toggle-status', methods=['POST'])
@admin_required
def admin_news_toggle_status(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid session token.', 'danger')
        return redirect(url_for('admin_news_list'))

    article = db.query_db("SELECT status, published_at FROM news WHERE id = %s", (id,), one=True)
    if not article:
        abort(404)

    if article['status'] == 'published':
        new_status = 'draft'
        db.execute_db("UPDATE news SET status = 'draft' WHERE id = %s", (id,))
        flash(f"Article #{id} unpublished and moved to Drafts.", 'warning')
    else:
        new_status = 'published'
        pub_time = article['published_at'] or datetime.now()
        db.execute_db("UPDATE news SET status = 'published', published_at = %s WHERE id = %s", (pub_time, id))
        flash(f"Article #{id} published live to public readers!", 'success')

    return redirect(request.referrer or url_for('admin_news_list'))

@app.route('/admin/news/<int:id>/delete', methods=['POST'])
@admin_required
def admin_news_delete(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid session token.', 'danger')
        return redirect(url_for('admin_news_list'))

    db.execute_db("DELETE FROM news WHERE id = %s", (id,))
    flash(f"Article #{id} deleted permanently.", 'info')
    return redirect(request.referrer or url_for('admin_news_list'))

@app.route('/admin/news/<int:id>/preview')
@admin_required
def admin_news_preview(id):
    article = db.query_db("SELECT slug FROM news WHERE id = %s", (id,), one=True)
    if not article:
        abort(404)
    return redirect(url_for('article_detail', slug=article['slug']))

# ---------------------------------------------------------
# Admin Categories & Locations
# ---------------------------------------------------------

@app.route('/admin/categories')
@admin_required
def admin_categories():
    categories = db.query_db("""
        SELECT c.*, (SELECT COUNT(*) FROM news n WHERE n.category_id = c.id) AS article_count
        FROM categories c
        ORDER BY c.id ASC
    """)
    return render_template('admin/categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['POST'])
@admin_required
def admin_category_add():
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid token.', 'danger')
        return redirect(url_for('admin_categories'))

    name_en = request.form.get('name_en', '').strip()
    name_hi = request.form.get('name_hi', '').strip()
    slug = slugify(request.form.get('slug', '').strip() or name_en)
    description = request.form.get('description', '').strip()

    if not name_en or not name_hi:
        flash('Both English and Hindi names are required.', 'warning')
        return redirect(url_for('admin_categories'))

    db.execute_db("""
        INSERT INTO categories (name_en, name_hi, slug, description)
        VALUES (%s, %s, %s, %s)
    """, (name_en, name_hi, slug, description))

    flash(f"Category '{name_en}' added successfully!", 'success')
    return redirect(url_for('admin_categories'))

@app.route('/admin/categories/<int:id>/delete', methods=['POST'])
@admin_required
def admin_category_delete(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid token.', 'danger')
        return redirect(url_for('admin_categories'))

    # Check if articles exist
    count = db.query_db("SELECT COUNT(*) AS c FROM news WHERE category_id = %s", (id,), one=True)['c']
    if count > 0:
        flash(f"Cannot delete category: {count} articles are currently assigned to it.", 'danger')
        return redirect(url_for('admin_categories'))

    db.execute_db("DELETE FROM categories WHERE id = %s", (id,))
    flash('Category deleted.', 'info')
    return redirect(url_for('admin_categories'))

@app.route('/admin/locations')
@admin_required
def admin_locations():
    locations = db.query_db("""
        SELECT l.*, (SELECT COUNT(*) FROM news n WHERE n.location_id = l.id) AS news_count
        FROM locations l
        ORDER BY l.state ASC, l.district ASC, l.city ASC
    """)
    return render_template('admin/locations.html', locations=locations)

@app.route('/admin/locations/add', methods=['POST'])
@admin_required
def admin_location_add():
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid token.', 'danger')
        return redirect(url_for('admin_locations'))

    state = request.form.get('state', '').strip()
    district = request.form.get('district', '').strip()
    city = request.form.get('city', '').strip()

    if state and district and city:
        db.execute_db("INSERT INTO locations (state, district, city) VALUES (%s, %s, %s)", (state, district, city))
        flash(f"Location '{city}, {district}' added.", 'success')
    return redirect(url_for('admin_locations'))

@app.route('/admin/locations/<int:id>/delete', methods=['POST'])
@admin_required
def admin_location_delete(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid token.', 'danger')
        return redirect(url_for('admin_locations'))

    db.execute_db("DELETE FROM locations WHERE id = %s", (id,))
    flash('Location deleted.', 'info')
    return redirect(url_for('admin_locations'))

# ---------------------------------------------------------
# Admin Comments & Users
# ---------------------------------------------------------

@app.route('/admin/comments')
@admin_required
def admin_comments():
    comments = db.query_db("""
        SELECT c.*, u.name AS user_name, u.email AS user_email,
               n.title_en AS news_title, n.slug AS news_slug
        FROM comments c
        JOIN users u ON c.user_id = u.id
        JOIN news n ON c.news_id = n.id
        ORDER BY c.created_at DESC
    """)
    return render_template('admin/comments.html', comments=comments)

@app.route('/admin/comments/<int:id>/moderate', methods=['POST'])
@admin_required
def admin_comment_moderate(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid token.', 'danger')
        return redirect(url_for('admin_comments'))

    action = request.args.get('action')
    if action == 'approve':
        db.execute_db("UPDATE comments SET status = 'approved' WHERE id = %s", (id,))
        flash(f"Comment #{id} approved.", 'success')
    elif action == 'reject':
        db.execute_db("UPDATE comments SET status = 'rejected' WHERE id = %s", (id,))
        flash(f"Comment #{id} rejected.", 'warning')
    return redirect(url_for('admin_comments'))

@app.route('/admin/comments/<int:id>/delete', methods=['POST'])
@admin_required
def admin_comment_delete(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid token.', 'danger')
        return redirect(url_for('admin_comments'))

    db.execute_db("DELETE FROM comments WHERE id = %s", (id,))
    flash(f"Comment #{id} deleted.", 'info')
    return redirect(url_for('admin_comments'))

@app.route('/admin/users')
@admin_required
def admin_users():
    users = db.query_db("""
        SELECT id, name, email, role, is_super_admin, branch, is_active, created_at 
        FROM users 
        ORDER BY is_super_admin DESC, (CASE WHEN role='admin' THEN 0 ELSE 1 END), id ASC
    """)
    # Unique cities/locations for branch assignment
    branches = db.query_db("SELECT DISTINCT city, state FROM locations ORDER BY state ASC, city ASC")
    return render_template('admin/users.html', users=users, branches=branches)

@app.route('/admin/users/<int:id>/update-role', methods=['POST'])
@admin_required
def admin_user_update_role(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid session token.', 'danger')
        return redirect(url_for('admin_users'))

    # SECURITY CHECK 1: Only Super Admin (Main Admin) can change roles
    if not session.get('is_super_admin'):
        flash('Access Denied: Only the Main Super Administrator has authority to promote or demote Admin accounts.', 'danger')
        return redirect(url_for('admin_users'))

    target = db.query_db("SELECT * FROM users WHERE id = %s", (id,), one=True)
    if not target:
        abort(404)

    # SECURITY CHECK 2: Main Admin cannot be demoted or changed by anyone
    if target.get('is_super_admin'):
        flash('Security Alert: The Main Super Administrator account is permanently protected and cannot be modified.', 'danger')
        return redirect(url_for('admin_users'))

    action_role = request.form.get('role', 'user').strip()
    branch = request.form.get('branch', '').strip() or None

    if action_role == 'admin':
        db.execute_db("""
            UPDATE users SET role = 'admin', branch = %s WHERE id = %s
        """, (branch or 'General Newsroom', id))
        flash(f"User '{target['name']}' promoted to Newsroom Administrator (Branch: {branch or 'General Newsroom'}).", 'success')
    else:
        db.execute_db("""
            UPDATE users SET role = 'user', branch = NULL WHERE id = %s
        """, (id,))
        flash(f"Administrator privileges revoked for '{target['name']}'. Account reverted to Reader.", 'info')

    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:id>/toggle-status', methods=['POST'])
@admin_required
def admin_user_toggle_status(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid token.', 'danger')
        return redirect(url_for('admin_users'))

    target = db.query_db("SELECT is_active, name, role, is_super_admin FROM users WHERE id = %s", (id,), one=True)
    if not target:
        abort(404)

    # SECURITY CHECK 1: Main Admin cannot be suspended by anyone!
    if target.get('is_super_admin'):
        flash('Security Alert: The Main Super Administrator account cannot be suspended or deactivated.', 'danger')
        return redirect(url_for('admin_users'))

    # SECURITY CHECK 2: User cannot deactivate own active session
    if id == session.get('user_id'):
        flash('You cannot deactivate your own current administrator account.', 'danger')
        return redirect(url_for('admin_users'))

    # SECURITY CHECK 3: Normal admins cannot suspend other admins
    if target['role'] == 'admin' and not session.get('is_super_admin'):
        flash('Permission Denied: Branch administrators cannot suspend other administrator accounts.', 'danger')
        return redirect(url_for('admin_users'))

    new_active = 0 if target['is_active'] else 1
    db.execute_db("UPDATE users SET is_active = %s WHERE id = %s", (new_active, id))
    action_text = "activated" if new_active else "suspended"
    flash(f"User account '{target['name']}' has been {action_text}.", 'info')

    return redirect(url_for('admin_users'))

# ---------------------------------------------------------
# Admin Media Library
# ---------------------------------------------------------

@app.route('/admin/media')
@admin_required
def admin_media():
    media_items = db.query_db("SELECT * FROM media ORDER BY id DESC")
    return render_template('admin/media.html', media_items=media_items)

@app.route('/admin/media/upload', methods=['POST'])
@admin_required
def admin_media_upload():
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid session token.', 'danger')
        return redirect(url_for('admin_media'))

    file = request.files.get('file')
    if file and file.filename != '':
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext in app.config['ALLOWED_IMAGE_EXTENSIONS'] or ext in app.config['ALLOWED_VIDEO_EXTENSIONS']:
            upload_res = save_uploaded_media(file, folder="assets")
            if upload_res:
                db.execute_db("""
                    INSERT INTO media (file_path, file_type, file_name)
                    VALUES (%s, %s, %s)
                """, (upload_res['url'], upload_res['type'], upload_res['name']))
                storage_label = "Cloudinary CDN" if upload_res['storage'] == 'cloudinary' else "Optimized WebP"
                flash(f"Media '{upload_res['name']}' uploaded successfully via {storage_label}!", 'success')
            else:
                flash('Upload failed. Please try again.', 'danger')
        else:
            flash('File format not allowed.', 'warning')
    return redirect(url_for('admin_media'))

@app.route('/admin/media/<int:id>/delete', methods=['POST'])
@admin_required
def admin_media_delete(id):
    if not validate_csrf(request.form.get('csrf_token')):
        flash('Invalid session token.', 'danger')
        return redirect(url_for('admin_media'))

    item = db.query_db("SELECT file_path FROM media WHERE id = %s", (id,), one=True)
    if item:
        fname = os.path.basename(item['file_path'])
        local_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        db.execute_db("DELETE FROM media WHERE id = %s", (id,))
        flash('Media asset deleted.', 'info')
    return redirect(url_for('admin_media'))

# ---------------------------------------------------------
# Custom Error Handlers
# ---------------------------------------------------------

@app.errorhandler(404)
def error_404(e):
    return render_template('base.html'), 404

@app.errorhandler(403)
def error_403(e):
    flash('Forbidden: You lack necessary permissions to access this page.', 'danger')
    return redirect(url_for('index'))

@app.errorhandler(500)
def error_500(e):
    return "500 Internal Server Error: An unexpected error occurred.", 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
