# JanPulse (जनपल्स) - Full-Stack Bilingual News Platform

**JanPulse** is a responsive, high-performance, bilingual (English & Hindi) digital news portal and newsroom content management system (CMS) built with **Python Flask**, **MySQL**, **Tailwind CSS**, and **Vanilla JavaScript**.

---

## 1. Key Features & Highlights

### Public Portal
- **Bilingual Interface**: Seamlessly switch between **Hindi (हिन्दी)** and **English** with persistent session preferences. Includes bilingual typography tuned for both Devanagari script and Latin fonts.
- **Breaking News Ticker**: Animated marquee ticker highlighting real-time breaking events with live pulsing indicators.
- **11 Curated Categories**:
  1. Latest News (ताज़ा ख़बरें)
  2. Breaking News (ब्रेकिंग न्यूज़)
  3. Local News (स्थानीय समाचार)
  4. India (भारत)
  5. World (विदेश)
  6. Politics (राजनीति)
  7. Business (व्यापार)
  8. Technology (तकनीक)
  9. Sports (खेल)
  10. Entertainment (मनोरंजन)
  11. Health (स्वास्थ्य)
- **Automatic Latest News Algorithm**: Dispatches are ranked automatically by official publication timestamp:
  ```sql
  SELECT * FROM news 
  WHERE status = 'published' AND published_at <= NOW() 
  ORDER BY published_at DESC, id DESC 
  LIMIT 20;
  ```
- **Hyper-Local News Filter**: Dynamic cascade filter allowing readers to narrow down civic dispatches by:
  $$\text{State} \longrightarrow \text{District} \longrightarrow \text{City}$$
- **Reader Engagement**:
  - Unauthenticated visitors can freely browse and read all published articles.
  - Interactive AJAX **Likes** and **Unlikes** with live counters.
  - Interactive AJAX **Bookmarks** to curate a personal reading list.
  - Article **Comments** with user avatar and relative timestamps.
  - One-click social sharing (WhatsApp, X / Twitter, Copy Link).

### User Authentication & Dashboard
- Dedicated, secure Login (`/login`) and Register (`/register`) pages.
- **Strict Role Isolation**: Public registrations are locked to the `user` role on the server, completely ignoring any browser-submitted role modifications.
- Reader Profile management (`/user/profile`): update display name, inspect reading stats (saved articles count, liked count, comments count), and securely change passwords.
- Saved Articles Library (`/user/saved`): manage bookmarked news with direct reading links and instant removal.

### Newsroom Admin CMS (`/admin/login` & `/admin/*`)
- **Completely Isolated Admin Login**: Accessible strictly at `/admin/login`. Normal users never see admin login options anywhere on public pages.
- **Server-Side Authorization**: Every administrative endpoint is guarded by the `@admin_required` server-side decorator.
- **Editorial CMS Capabilities**:
  - Real-time Dashboard with statistics (Published count, Drafts count, Active readers, Comments count).
  - Full CRUD on News Articles: add, edit, delete, publish, and unpublish with one click.
  - **Draft vs. Published Workflow**: Draft articles are completely hidden from public readers until published.
  - **Live Preview**: Editors can preview drafts as they will appear live before publishing.
  - Dual English and Hindi headline, excerpt, and rich HTML content fields.
  - File upload or external image URL support with extension validation and secure naming.
  - Category and Location management (add/delete states, districts, cities).
  - Reader Comments moderation queue (approve, reject, purge).
  - Reader account status management (active / suspended toggle).

---

## 2. Technology Stack

- **Backend**: Python 3.10+ / Flask 3.x
- **Database**: MySQL 8.0+ / PyMySQL
- **Frontend**: HTML5, Tailwind CSS, Lucide Icons, Vanilla JavaScript
- **Security**: Werkzeug secure password hashing (`scrypt`), CSRF token validation, parameterized SQL queries, HttpOnly & Lax cookie flags

---

## 3. Database Schema Overview

The database contains 10 structured tables enforcing foreign keys, unique constraints, and composite indexes:

1. `users`: Stores reader and admin profiles with `scrypt` password hashes and active status.
2. `categories`: 11 news categories with English and Hindi names and unique slugs.
3. `locations`: Geographic index representing State $\rightarrow$ District $\rightarrow$ City hierarchy.
4. `news`: Central articles table indexed by `(status, published_at DESC, id DESC)`.
5. `comments`: Reader comments with foreign key links to news and users.
6. `likes`: Unique composite key `(news_id, user_id)` enforcing single likes.
7. `bookmarks`: Unique composite key `(news_id, user_id)` powering saved articles.
8. `tags`: Tag taxonomy with unique slugs.
9. `news_tags`: Junction table linking articles and tags with composite primary keys.
10. `media`: Media library tracking uploaded images and files.

---

## 4. Default Demonstration Credentials

| Role | Email | Password | Access Route |
|---|---|---|---|
| **Newsroom Admin** | `admin@janpulse.com` | `Admin@JanPulse2026` | `/admin/login` |
| **Normal Reader** | `rahul@example.com` | `User@JanPulse2026` | `/login` |

> *To securely provision a new administrator through the CLI, run:*
> ```bash
> python manage.py create-admin
> ```

---

## 5. Installation & Setup Instructions

### 1. Prerequisites
- Python 3.10+
- MySQL Server 8.0+ running on port `3306`

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize & Seed MySQL Database
Ensure MySQL is running, then execute:
```bash
python init_db.py
```
This script will:
- Create the `janpulse_db` database if not present.
- Execute `schema.sql` to build all 10 tables and indexes.
- Seed all 11 news categories and 25 municipal locations.
- Seed rich bilingual news dispatches (including breaking and local stories).
- Seed the default admin and test user accounts.

### 4. Run the Development Server
```bash
python app.py
```
Or via the CLI tool:
```bash
python manage.py run
```

Access the application in your browser:
- **Public Portal**: `http://127.0.0.1:5000/`
- **Admin CMS**: `http://127.0.0.1:5000/admin/login`
