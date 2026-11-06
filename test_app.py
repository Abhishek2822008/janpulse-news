"""
Comprehensive Automated Test Suite for JanPulse
Tests all endpoints, database queries, authentication, RBAC,
likes/bookmarks, local news filters, and admin CMS functions.
"""

import unittest
from datetime import datetime
from app import app
import db

class JanPulseTestCase(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_01_public_homepage(self):
        """Test homepage loads and latest news algorithm shows published items."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'JAN', response.data)
        self.assertIn(b'PULSE', response.data)
        # Ensure draft news does NOT show on homepage
        self.assertNotIn(b'Draft Policy on Urban Aerial Drone Corridors', response.data)
        print("[PASS] Public Homepage & Latest News Algorithm verified (Drafts excluded).")

    def test_02_bilingual_toggle(self):
        """Test language toggle between English and Hindi."""
        # Switch to English
        res_en = self.client.get('/set-language/en', follow_redirects=True)
        self.assertEqual(res_en.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('lang'), 'en')

        # Switch to Hindi
        res_hi = self.client.get('/set-language/hi', follow_redirects=True)
        self.assertEqual(res_hi.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('lang'), 'hi')
        print("[PASS] Bilingual session persistence verified.")

    def test_03_category_filtering(self):
        """Test category endpoint."""
        response = self.client.get('/category/technology')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'technology', response.data.lower())
        print("[PASS] Category view verified.")

    def test_04_local_news_filtering(self):
        """Test local news cascade filter by state, district, city."""
        res_state = self.client.get('/local-news?state=Uttar+Pradesh')
        self.assertEqual(res_state.status_code, 200)
        self.assertIn(b'Uttar Pradesh', res_state.data)

        # Test district API
        res_dist = self.client.get('/api/locations/districts?state=Uttar+Pradesh')
        self.assertEqual(res_dist.status_code, 200)
        self.assertIn('Lucknow', res_dist.get_json()['districts'])

        # Test city API
        res_cities = self.client.get('/api/locations/cities?state=Uttar+Pradesh&district=Lucknow')
        self.assertEqual(res_cities.status_code, 200)
        self.assertIn('Lucknow Central', res_cities.get_json()['cities'])
        print("[PASS] Local News cascade filtering (State -> District -> City) verified.")

    def test_05_article_detail_and_view_count(self):
        """Test viewing an article increases views count."""
        with app.app_context():
            art = db.query_db("SELECT id, slug, views_count FROM news WHERE status = 'published' LIMIT 1", one=True)
            initial_views = art['views_count']

        response = self.client.get(f"/article/{art['slug']}")
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            updated = db.query_db("SELECT views_count FROM news WHERE id = %s", (art['id'],), one=True)
            self.assertEqual(updated['views_count'], initial_views + 1)
        print("[PASS] Article detail view & view counter increment verified.")

    def test_06_user_registration_role_enforcement(self):
        """Test user registration always sets role to 'user' even if malicious role sent."""
        test_email = f"test_{int(datetime.now().timestamp())}@example.com"
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        response = self.client.post('/register', data={
            'csrf_token': 'test-token',
            'name': 'Test Reader',
            'email': test_email,
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'admin'  # Malicious attempt to inject admin role
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        with app.app_context():
            created_user = db.query_db("SELECT role FROM users WHERE email = %s", (test_email,), one=True)
            self.assertIsNotNone(created_user)
            self.assertEqual(created_user['role'], 'user', "Security Violation: User role was not forced to 'user'!")
        print("[PASS] Registration strictly forces 'user' role regardless of submitted form data.")

    def test_07_user_login_and_logout(self):
        """Test login with seeded user credentials."""
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        response = self.client.post('/login', data={
            'csrf_token': 'test-token',
            'email': 'rahul@example.com',
            'password': 'User@JanPulse2026'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get('user_role'), 'user')

        # Test logout
        res_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)
        print("[PASS] Normal user authentication and session management verified.")

    def test_08_authenticated_engagement_likes_bookmarks(self):
        """Test liking and bookmarking require login and function properly."""
        with app.app_context():
            art = db.query_db("SELECT id FROM news WHERE status = 'published' LIMIT 1", one=True)
            news_id = art['id']

        # 1. Unauthenticated like returns 401
        res_unauth = self.client.post(f"/api/news/{news_id}/like")
        self.assertEqual(res_unauth.status_code, 401)

        # 2. Login as test user
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_name'] = 'Rahul Sharma'
            sess['user_role'] = 'user'

        # 3. Toggle like
        res_like = self.client.post(f"/api/news/{news_id}/like")
        self.assertEqual(res_like.status_code, 200)
        self.assertIn('likes_count', res_like.get_json())

        # 4. Toggle bookmark
        res_bm = self.client.post(f"/api/news/{news_id}/bookmark")
        self.assertEqual(res_bm.status_code, 200)
        self.assertIn('bookmarked', res_bm.get_json())
        print("[PASS] Interactive Likes & Bookmarks (with 401 protection) verified.")

    def test_09_separate_admin_login_and_rbac(self):
        """Test admin login rejects normal user and permits admin account."""
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        # Attempting admin login with normal user credentials must be rejected
        res_fail = self.client.post('/admin/login', data={
            'csrf_token': 'test-token',
            'email': 'rahul@example.com',
            'password': 'User@JanPulse2026'
        }, follow_redirects=True)
        self.assertIn(b'Access Denied', res_fail.data)

        # Admin login with valid admin credentials
        res_success = self.client.post('/admin/login', data={
            'csrf_token': 'test-token',
            'email': 'admin@janpulse.com',
            'password': 'Admin@JanPulse2026'
        }, follow_redirects=True)
        self.assertEqual(res_success.status_code, 200)
        self.assertIn(b'Newsroom CMS', res_success.data)
        print("[PASS] Separate Admin Login and role rejection verified.")

    def test_10_admin_news_draft_workflow(self):
        """Test creating a draft article, verifying it does NOT show publicly, then publishing it."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Chief Editor'
            sess['user_role'] = 'admin'
            sess['_csrf_token'] = 'test-token'

        # Create draft
        res = self.client.post('/admin/news/new', data={
            'csrf_token': 'test-token',
            'title_en': 'Secret Exclusive Draft Investigation 2026',
            'title_hi': 'गोपनीय विशेष मसौदा जांच 2026',
            'excerpt_en': 'This is a test draft excerpt that must remain private.',
            'excerpt_hi': 'यह एक परीक्षण मसौदा संक्षेप है जिसे निजी रहना चाहिए।',
            'content_en': '<p>Private confidential news draft.</p>',
            'content_hi': '<p>निजी गोपनीय समाचार मसौदा।</p>',
            'category_id': 1,
            'submit_action': 'draft'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with app.app_context():
            draft_art = db.query_db("SELECT id, slug, status FROM news WHERE title_en = %s", ('Secret Exclusive Draft Investigation 2026',), one=True)
            self.assertIsNotNone(draft_art)
            self.assertEqual(draft_art['status'], 'draft')

        # Clear session to act as regular public visitor
        self.client.get('/logout')

        # Check public home does NOT contain draft
        res_public = self.client.get('/')
        self.assertNotIn(b'Secret Exclusive Draft Investigation 2026', res_public.data)

        # Check direct link returns 404 for regular visitor
        res_direct = self.client.get(f"/article/{draft_art['slug']}")
        self.assertEqual(res_direct.status_code, 404)
        print("[PASS] Newsroom Draft vs. Published workflow strictly hides draft from public visitors.")

    def test_11_promote_user_to_admin_and_protect_main_admin(self):
        """Test Promoting a user to Admin, branch assignment, and Main Admin protection rules."""
        # 1. Super Admin logs in
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Chief Editor'
            sess['user_role'] = 'admin'
            sess['is_super_admin'] = True
            sess['_csrf_token'] = 'test-token'

        # 2. Promote test user (ID 2, rahul@example.com) to Branch Admin
        res_promote = self.client.post('/admin/users/2/update-role', data={
            'csrf_token': 'test-token',
            'role': 'admin',
            'branch': 'Lucknow Branch'
        }, follow_redirects=True)
        self.assertEqual(res_promote.status_code, 200)

        with app.app_context():
            promoted_user = db.query_db("SELECT role, branch, is_super_admin FROM users WHERE id = 2", one=True)
            self.assertEqual(promoted_user['role'], 'admin')
            self.assertEqual(promoted_user['branch'], 'Lucknow Branch')
            self.assertEqual(promoted_user['is_super_admin'], 0)

        # 3. Log in as the newly promoted branch admin (ID 2)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_name'] = 'Rahul Sharma'
            sess['user_role'] = 'admin'
            sess['is_super_admin'] = False  # Not Super Admin
            sess['_csrf_token'] = 'test-token'

        # 4. Attempt to demote or suspend the Main Admin (ID 1) -> MUST BE BLOCKED!
        res_attack_demote = self.client.post('/admin/users/1/update-role', data={
            'csrf_token': 'test-token',
            'role': 'user'
        }, follow_redirects=True)
        self.assertIn(b'Access Denied', res_attack_demote.data)

        res_attack_suspend = self.client.post('/admin/users/1/toggle-status', data={
            'csrf_token': 'test-token'
        }, follow_redirects=True)
        self.assertIn(b'Security Alert', res_attack_suspend.data)

        # Verify Main Admin is still active and admin
        with app.app_context():
            main_admin = db.query_db("SELECT role, is_active, is_super_admin FROM users WHERE id = 1", one=True)
            self.assertEqual(main_admin['role'], 'admin')
            self.assertEqual(main_admin['is_active'], 1)
            self.assertEqual(main_admin['is_super_admin'], 1)

        # 5. Super Admin logs back in and demotes ID 2 back to regular reader
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Chief Editor'
            sess['user_role'] = 'admin'
            sess['is_super_admin'] = True
            sess['_csrf_token'] = 'test-token'

        res_demote = self.client.post('/admin/users/2/update-role', data={
            'csrf_token': 'test-token',
            'role': 'user'
        }, follow_redirects=True)
        self.assertEqual(res_demote.status_code, 200)

        with app.app_context():
            reverted_user = db.query_db("SELECT role, branch FROM users WHERE id = 2", one=True)
            self.assertEqual(reverted_user['role'], 'user')
            self.assertIsNone(reverted_user['branch'])
        print("[PASS] User Promotion, Branch Assignment, and Main Admin Immunity verified.")

    def test_12_media_storage_webp_optimization(self):
        """Test that uploaded news image is automatically converted to optimized WebP."""
        import io
        from PIL import Image

        # Create dummy 100x100 PNG in memory
        img_byte_arr = io.BytesIO()
        test_img = Image.new('RGB', (100, 100), color='red')
        test_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_name'] = 'Chief Editor'
            sess['user_role'] = 'admin'
            sess['is_super_admin'] = True
            sess['_csrf_token'] = 'test-token'

        response = self.client.post('/admin/media/upload', data={
            'csrf_token': 'test-token',
            'file': (img_byte_arr, 'test_sample.png')
        }, content_type='multipart/form-data', follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        with app.app_context():
            uploaded_item = db.query_db(
                "SELECT * FROM media WHERE file_name = 'test_sample.png' ORDER BY id DESC LIMIT 1",
                one=True
            )
            self.assertIsNotNone(uploaded_item)
            # The saved file path should end in .webp (optimized) or be a cloudinary url
            self.assertTrue(
                uploaded_item['file_path'].endswith('.webp') or 'cloudinary' in uploaded_item['file_path'],
                f"Expected .webp or cloudinary URL, got {uploaded_item['file_path']}"
            )
            # Clean up test row
            db.execute_db("DELETE FROM media WHERE id = %s", (uploaded_item['id'],))

        print("[PASS] Media upload and automatic WebP compression verified.")

    def test_13_forgot_and_reset_password_flow(self):
        """Test forgot password request, 6-digit OTP email generation, OTP verification, and password reset."""
        from auth import hash_password, verify_password

        # 1. GET /forgot-password
        with self.client.session_transaction() as sess:
            sess['lang'] = 'en'
        res_get = self.client.get('/forgot-password')
        self.assertEqual(res_get.status_code, 200)
        self.assertIn(b'Reset Your Password', res_get.data)

        # 2. POST /forgot-password with valid email
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        res_post = self.client.post('/forgot-password', data={
            'csrf_token': 'test-token',
            'email': 'rahul@example.com'
        }, follow_redirects=True)
        self.assertEqual(res_post.status_code, 200)
        self.assertIn(b'verification OTP has been sent', res_post.data)
        self.assertIn(b'Verify Your OTP', res_post.data)

        # 3. Retrieve generated OTP from DB
        with app.app_context():
            otp_record = db.query_db(
                "SELECT otp_code FROM password_otps WHERE email = 'rahul@example.com' AND is_used = 0 ORDER BY id DESC LIMIT 1",
                one=True
            )
            self.assertIsNotNone(otp_record)
            otp_code = otp_record['otp_code']
            self.assertEqual(len(otp_code), 6)

        # 4. Try submitting invalid OTP
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        res_bad_otp = self.client.post('/verify-otp', data={
            'csrf_token': 'test-token',
            'otp': '000000'
        }, follow_redirects=True)
        self.assertIn(b'Invalid or expired OTP', res_bad_otp.data)

        # 5. Submit valid OTP -> Should proceed to reset password page
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        res_good_otp = self.client.post('/verify-otp', data={
            'csrf_token': 'test-token',
            'otp': otp_code
        }, follow_redirects=True)
        self.assertEqual(res_good_otp.status_code, 200)
        self.assertIn(b'OTP verified successfully', res_good_otp.data)
        self.assertIn(b'Create New Password', res_good_otp.data)

        # 6. POST /reset-password with new password
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        res_reset = self.client.post('/reset-password', data={
            'csrf_token': 'test-token',
            'password': 'NewOtpPass@2026',
            'confirm_password': 'NewOtpPass@2026'
        }, follow_redirects=True)
        self.assertEqual(res_reset.status_code, 200)
        self.assertIn(b'password has been changed successfully', res_reset.data)

        # 7. Authenticate with the new password
        with self.client.session_transaction() as sess:
            sess['_csrf_token'] = 'test-token'

        res_login = self.client.post('/login', data={
            'csrf_token': 'test-token',
            'email': 'rahul@example.com',
            'password': 'NewOtpPass@2026'
        }, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b'Welcome back, Rahul Sharma!', res_login.data)

        # 8. Reset Rahul's password back to 'User@JanPulse2026' for idempotency
        with app.app_context():
            db.execute_db("UPDATE users SET password_hash = %s WHERE id = 2", (hash_password('User@JanPulse2026'),))

        print("[PASS] Forgot Password & 6-Digit Email OTP Verification Flow verified.")

if __name__ == '__main__':
    unittest.main()
