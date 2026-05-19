from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import sqlite3
import hashlib
import os
import json
from datetime import datetime
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = BASE_DIR

app = Flask(__name__, static_folder=None)
app.secret_key = 'novel_secret_key_2024'
CORS(app, supports_credentials=True)

DB_PATH = os.path.join(BASE_DIR, 'novels.db')

def load_env_file():
    env_path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env_file()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        avatar TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS novels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        description TEXT,
        cover TEXT DEFAULT '',
        genre TEXT DEFAULT '',
        status TEXT DEFAULT 'ongoing',
        views INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL,
        chapter_number INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (novel_id) REFERENCES novels(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        novel_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, novel_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (novel_id) REFERENCES novels(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        novel_id INTEGER NOT NULL,
        last_chapter INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, novel_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (novel_id) REFERENCES novels(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        novel_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (novel_id) REFERENCES novels(id)
    )''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# â”€â”€â”€ AUTH â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not username or not email or not password:
        return jsonify({'error': 'All fields required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                     (username, email, hash_password(password)))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({'message': 'Registered successfully', 'user': {
            'id': user['id'], 'username': user['username'],
            'email': user['email'], 'role': user['role']
        }})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 400
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email=? AND password=?",
                        (email, hash_password(password))).fetchone()
    conn.close()
    
    if not user:
        return jsonify({'error': 'Invalid email or password'}), 401
    
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    return jsonify({'message': 'Login successful', 'user': {
        'id': user['id'], 'username': user['username'],
        'email': user['email'], 'role': user['role']
    }})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})

@app.route('/api/me', methods=['GET'])
def me():
    if 'user_id' not in session:
        return jsonify({'user': None})
    conn = get_db()
    user = conn.execute("SELECT id, username, email, role, created_at FROM users WHERE id=?",
                        (session['user_id'],)).fetchone()
    conn.close()
    if not user:
        return jsonify({'user': None})
    return jsonify({'user': dict(user)})

# â”€â”€â”€ NOVELS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/config/supabase', methods=['GET'])
def supabase_config():
    return jsonify({
        'url': os.environ.get('NEXT_PUBLIC_SUPABASE_URL', ''),
        'publishableKey': os.environ.get('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', ''),
    })

@app.route('/api/novels', methods=['GET'])
def get_novels():
    genre = request.args.get('genre', '')
    search = request.args.get('search', '')
    conn = get_db()
    
    query = "SELECT n.*, COUNT(DISTINCT c.id) as chapter_count FROM novels n LEFT JOIN chapters c ON n.id=c.novel_id"
    params = []
    
    conditions = []
    if genre:
        conditions.append("n.genre=?")
        params.append(genre)
    if search:
        conditions.append("(n.title LIKE ? OR n.author LIKE ?)")
        params.extend([f'%{search}%', f'%{search}%'])
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY n.id ORDER BY n.updated_at DESC"
    
    novels = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(n) for n in novels])

@app.route('/api/novels/<int:novel_id>', methods=['GET'])
def get_novel(novel_id):
    conn = get_db()
    conn.execute("UPDATE novels SET views=views+1 WHERE id=?", (novel_id,))
    conn.commit()
    novel = conn.execute("SELECT * FROM novels WHERE id=?", (novel_id,)).fetchone()
    if not novel:
        return jsonify({'error': 'Novel not found'}), 404
    
    chapters = conn.execute("SELECT id, chapter_number, title, created_at FROM chapters WHERE novel_id=? ORDER BY chapter_number",
                            (novel_id,)).fetchall()
    
    fav_count = conn.execute("SELECT COUNT(*) as c FROM favorites WHERE novel_id=?", (novel_id,)).fetchone()['c']
    
    result = dict(novel)
    result['chapters'] = [dict(c) for c in chapters]
    result['favorite_count'] = fav_count
    
    if 'user_id' in session:
        fav = conn.execute("SELECT id FROM favorites WHERE user_id=? AND novel_id=?",
                           (session['user_id'], novel_id)).fetchone()
        lib = conn.execute("SELECT id FROM library WHERE user_id=? AND novel_id=?",
                           (session['user_id'], novel_id)).fetchone()
        result['is_favorited'] = fav is not None
        result['in_library'] = lib is not None
    
    conn.close()
    return jsonify(result)

@app.route('/api/novels', methods=['POST'])
@admin_required
def create_novel():
    data = request.json
    conn = get_db()
    conn.execute("INSERT INTO novels (title, author, description, genre, status) VALUES (?, ?, ?, ?, ?)",
                 (data['title'], data['author'], data.get('description', ''),
                  data.get('genre', ''), data.get('status', 'ongoing')))
    conn.commit()
    novel_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return jsonify({'message': 'Novel created', 'id': novel_id})

@app.route('/api/novels/<int:novel_id>', methods=['PUT'])
@admin_required
def update_novel(novel_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE novels SET title=?, author=?, description=?, genre=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                 (data['title'], data['author'], data.get('description', ''),
                  data.get('genre', ''), data.get('status', 'ongoing'), novel_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Novel updated'})

@app.route('/api/novels/<int:novel_id>', methods=['DELETE'])
@admin_required
def delete_novel(novel_id):
    conn = get_db()
    conn.execute("DELETE FROM chapters WHERE novel_id=?", (novel_id,))
    conn.execute("DELETE FROM favorites WHERE novel_id=?", (novel_id,))
    conn.execute("DELETE FROM library WHERE novel_id=?", (novel_id,))
    conn.execute("DELETE FROM novels WHERE id=?", (novel_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Novel deleted'})

# â”€â”€â”€ CHAPTERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/novels/<int:novel_id>/chapters/<int:ch_num>', methods=['GET'])
def get_chapter(novel_id, ch_num):
    conn = get_db()
    chapter = conn.execute("SELECT * FROM chapters WHERE novel_id=? AND chapter_number=?",
                           (novel_id, ch_num)).fetchone()
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    total = conn.execute("SELECT COUNT(*) as c FROM chapters WHERE novel_id=?", (novel_id,)).fetchone()['c']
    novel = conn.execute("SELECT title FROM novels WHERE id=?", (novel_id,)).fetchone()
    conn.close()
    
    result = dict(chapter)
    result['total_chapters'] = total
    result['novel_title'] = novel['title']
    return jsonify(result)

@app.route('/api/novels/<int:novel_id>/chapters', methods=['POST'])
@admin_required
def add_chapter(novel_id):
    data = request.json
    conn = get_db()
    ch_num = conn.execute("SELECT COALESCE(MAX(chapter_number),0)+1 as n FROM chapters WHERE novel_id=?", (novel_id,)).fetchone()['n']
    conn.execute("INSERT INTO chapters (novel_id, chapter_number, title, content) VALUES (?, ?, ?, ?)",
                 (novel_id, ch_num, data['title'], data['content']))
    conn.execute("UPDATE novels SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (novel_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Chapter added', 'chapter_number': ch_num})

@app.route('/api/chapters/<int:chapter_id>', methods=['PUT'])
@admin_required
def update_chapter(chapter_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE chapters SET title=?, content=? WHERE id=?",
                 (data['title'], data['content'], chapter_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Chapter updated'})

@app.route('/api/chapters/<int:chapter_id>', methods=['DELETE'])
@admin_required
def delete_chapter(chapter_id):
    conn = get_db()
    conn.execute("DELETE FROM chapters WHERE id=?", (chapter_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Chapter deleted'})

# â”€â”€â”€ FAVORITES & LIBRARY â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/favorites', methods=['GET'])
@login_required
def get_favorites():
    conn = get_db()
    favs = conn.execute('''SELECT n.*, COUNT(DISTINCT c.id) as chapter_count 
                           FROM favorites f JOIN novels n ON f.novel_id=n.id
                           LEFT JOIN chapters c ON n.id=c.novel_id
                           WHERE f.user_id=? GROUP BY n.id''',
                        (session['user_id'],)).fetchall()
    conn.close()
    return jsonify([dict(f) for f in favs])

@app.route('/api/favorites/<int:novel_id>', methods=['POST'])
@login_required
def toggle_favorite(novel_id):
    conn = get_db()
    existing = conn.execute("SELECT id FROM favorites WHERE user_id=? AND novel_id=?",
                            (session['user_id'], novel_id)).fetchone()
    if existing:
        conn.execute("DELETE FROM favorites WHERE user_id=? AND novel_id=?",
                     (session['user_id'], novel_id))
        conn.commit()
        conn.close()
        return jsonify({'favorited': False})
    else:
        conn.execute("INSERT INTO favorites (user_id, novel_id) VALUES (?, ?)",
                     (session['user_id'], novel_id))
        conn.commit()
        conn.close()
        return jsonify({'favorited': True})

@app.route('/api/library', methods=['GET'])
@login_required
def get_library():
    conn = get_db()
    lib = conn.execute('''SELECT n.*, l.last_chapter, COUNT(DISTINCT c.id) as chapter_count
                          FROM library l JOIN novels n ON l.novel_id=n.id
                          LEFT JOIN chapters c ON n.id=c.novel_id
                          WHERE l.user_id=? GROUP BY n.id''',
                       (session['user_id'],)).fetchall()
    conn.close()
    return jsonify([dict(l) for l in lib])

@app.route('/api/library/<int:novel_id>', methods=['POST'])
@login_required
def toggle_library(novel_id):
    conn = get_db()
    existing = conn.execute("SELECT id FROM library WHERE user_id=? AND novel_id=?",
                            (session['user_id'], novel_id)).fetchone()
    if existing:
        conn.execute("DELETE FROM library WHERE user_id=? AND novel_id=?",
                     (session['user_id'], novel_id))
        conn.commit()
        conn.close()
        return jsonify({'in_library': False})
    else:
        conn.execute("INSERT INTO library (user_id, novel_id) VALUES (?, ?)",
                     (session['user_id'], novel_id))
        conn.commit()
        conn.close()
        return jsonify({'in_library': True})

# â”€â”€â”€ ADMIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    conn = get_db()
    stats = {
        'total_novels': conn.execute("SELECT COUNT(*) as c FROM novels").fetchone()['c'],
        'total_chapters': conn.execute("SELECT COUNT(*) as c FROM chapters").fetchone()['c'],
        'total_users': conn.execute("SELECT COUNT(*) as c FROM users").fetchone()['c'],
        'total_views': conn.execute("SELECT COALESCE(SUM(views),0) as c FROM novels").fetchone()['c'],
        'total_favorites': conn.execute("SELECT COUNT(*) as c FROM favorites").fetchone()['c'],
    }
    conn.close()
    return jsonify(stats)

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    conn = get_db()
    users = conn.execute("SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'User deleted'})

# â”€â”€â”€ SERVE FRONTEND â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    allowed_files = {'index.html', 'style.css', 'app.js'}
    if path not in allowed_files:
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(FRONTEND_DIR, path)

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    init_db()
    print("NovelVerse running at http://localhost:5000")
    app.run(debug=True, port=5000)
