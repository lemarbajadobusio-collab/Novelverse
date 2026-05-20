from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import hashlib
import os
import json
from datetime import date, datetime
from functools import wraps
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text as sql_text,
)
from sqlalchemy.exc import IntegrityError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = BASE_DIR

app = Flask(__name__, static_folder=None)
app.secret_key = 'novel_secret_key_2024'
CORS(app, supports_credentials=True)

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

def database_url():
    url = (
        os.environ.get('SUPABASE_DATABASE_URL')
        or os.environ.get('DATABASE_URL')
        or f"sqlite:///{os.path.join(BASE_DIR, 'novels.db')}"
    )
    if url.startswith('postgres://'):
        return 'postgresql+psycopg://' + url[len('postgres://'):]
    if url.startswith('postgresql://') and '+psycopg' not in url:
        return 'postgresql+psycopg://' + url[len('postgresql://'):]
    return url

DB_URL = database_url()
ENGINE_OPTIONS = {'future': True, 'pool_pre_ping': True}
if DB_URL.startswith('sqlite:///'):
    ENGINE_OPTIONS['connect_args'] = {'check_same_thread': False}

engine = create_engine(DB_URL, **ENGINE_OPTIONS)
metadata = MetaData()

users = Table(
    'users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String, nullable=False, unique=True),
    Column('email', String, nullable=False, unique=True),
    Column('password', String, nullable=False),
    Column('role', String, server_default='user'),
    Column('avatar', Text, server_default=''),
    Column('created_at', DateTime, server_default=sql_text('CURRENT_TIMESTAMP')),
)

novels = Table(
    'novels', metadata,
    Column('id', Integer, primary_key=True),
    Column('title', String, nullable=False),
    Column('author', String, nullable=False),
    Column('description', Text),
    Column('cover', Text, server_default=''),
    Column('genre', String, server_default=''),
    Column('status', String, server_default='ongoing'),
    Column('views', Integer, server_default='0'),
    Column('created_at', DateTime, server_default=sql_text('CURRENT_TIMESTAMP')),
    Column('updated_at', DateTime, server_default=sql_text('CURRENT_TIMESTAMP')),
)

chapters = Table(
    'chapters', metadata,
    Column('id', Integer, primary_key=True),
    Column('novel_id', Integer, ForeignKey('novels.id'), nullable=False),
    Column('chapter_number', Integer, nullable=False),
    Column('title', String, nullable=False),
    Column('content', Text, nullable=False),
    Column('created_at', DateTime, server_default=sql_text('CURRENT_TIMESTAMP')),
)

favorites = Table(
    'favorites', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('novel_id', Integer, ForeignKey('novels.id'), nullable=False),
    Column('created_at', DateTime, server_default=sql_text('CURRENT_TIMESTAMP')),
    UniqueConstraint('user_id', 'novel_id'),
)

library = Table(
    'library', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('novel_id', Integer, ForeignKey('novels.id'), nullable=False),
    Column('last_chapter', Integer, server_default='1'),
    Column('created_at', DateTime, server_default=sql_text('CURRENT_TIMESTAMP')),
    UniqueConstraint('user_id', 'novel_id'),
)

comments = Table(
    'comments', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('novel_id', Integer, ForeignKey('novels.id'), nullable=False),
    Column('content', Text, nullable=False),
    Column('created_at', DateTime, server_default=sql_text('CURRENT_TIMESTAMP')),
)

def json_ready(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value

def row_dict(row):
    return {key: json_ready(row[key]) for key in row.keys()}

def fetch_one(query, params=None):
    with engine.connect() as conn:
        row = conn.execute(sql_text(query), params or {}).mappings().fetchone()
        return row_dict(row) if row else None

def fetch_all(query, params=None):
    with engine.connect() as conn:
        rows = conn.execute(sql_text(query), params or {}).mappings().fetchall()
        return [row_dict(row) for row in rows]

def execute(query, params=None):
    with engine.begin() as conn:
        conn.execute(sql_text(query), params or {})

def execute_returning_id(query, params=None):
    with engine.begin() as conn:
        if engine.dialect.name == 'postgresql':
            return conn.execute(sql_text(f"{query} RETURNING id"), params or {}).scalar_one()
        result = conn.execute(sql_text(query), params or {})
        return result.lastrowid

def init_db():
    metadata.create_all(engine)
    novel_columns = {col['name'] for col in inspect(engine).get_columns('novels')}
    if 'cover' not in novel_columns:
        execute("ALTER TABLE novels ADD COLUMN cover TEXT DEFAULT ''")

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
    
    try:
        execute(
            "INSERT INTO users (username, email, password) VALUES (:username, :email, :password)",
            {'username': username, 'email': email, 'password': hash_password(password)}
        )
        user = fetch_one("SELECT * FROM users WHERE email=:email", {'email': email})
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({'message': 'Registered successfully', 'user': {
            'id': user['id'], 'username': user['username'],
            'email': user['email'], 'role': user['role']
        }})
    except IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    user = fetch_one(
        "SELECT * FROM users WHERE email=:email AND password=:password",
        {'email': email, 'password': hash_password(password)}
    )
    
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
    user = fetch_one(
        "SELECT id, username, email, role, created_at FROM users WHERE id=:id",
        {'id': session['user_id']}
    )
    if not user:
        return jsonify({'user': None})
    return jsonify({'user': user})

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
    
    query = "SELECT n.*, COUNT(DISTINCT c.id) as chapter_count FROM novels n LEFT JOIN chapters c ON n.id=c.novel_id"
    params = {}
    
    conditions = []
    if genre:
        conditions.append("n.genre=:genre")
        params['genre'] = genre
    if search:
        conditions.append("(n.title LIKE :search OR n.author LIKE :search)")
        params['search'] = f'%{search}%'
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " GROUP BY n.id ORDER BY n.updated_at DESC"
    
    return jsonify(fetch_all(query, params))

@app.route('/api/novels/<int:novel_id>', methods=['GET'])
def get_novel(novel_id):
    execute("UPDATE novels SET views=views+1 WHERE id=:id", {'id': novel_id})
    novel = fetch_one("SELECT * FROM novels WHERE id=:id", {'id': novel_id})
    if not novel:
        return jsonify({'error': 'Novel not found'}), 404
    
    chapters = fetch_all(
        "SELECT id, chapter_number, title, created_at FROM chapters WHERE novel_id=:novel_id ORDER BY chapter_number",
        {'novel_id': novel_id}
    )
    
    fav_count = fetch_one("SELECT COUNT(*) as c FROM favorites WHERE novel_id=:novel_id", {'novel_id': novel_id})['c']
    
    result = novel
    result['chapters'] = chapters
    result['favorite_count'] = fav_count
    
    if 'user_id' in session:
        fav = fetch_one(
            "SELECT id FROM favorites WHERE user_id=:user_id AND novel_id=:novel_id",
            {'user_id': session['user_id'], 'novel_id': novel_id}
        )
        lib = fetch_one(
            "SELECT id FROM library WHERE user_id=:user_id AND novel_id=:novel_id",
            {'user_id': session['user_id'], 'novel_id': novel_id}
        )
        result['is_favorited'] = fav is not None
        result['in_library'] = lib is not None
    
    return jsonify(result)

@app.route('/api/novels', methods=['POST'])
@admin_required
def create_novel():
    data = request.json
    novel_id = execute_returning_id(
        "INSERT INTO novels (title, author, description, cover, genre, status) VALUES (:title, :author, :description, :cover, :genre, :status)",
        {
            'title': data['title'],
            'author': data['author'],
            'description': data.get('description', ''),
            'cover': data.get('cover', ''),
            'genre': data.get('genre', ''),
            'status': data.get('status', 'ongoing'),
        }
    )
    return jsonify({'message': 'Novel created', 'id': novel_id})

@app.route('/api/novels/<int:novel_id>', methods=['PUT'])
@admin_required
def update_novel(novel_id):
    data = request.json
    execute(
        "UPDATE novels SET title=:title, author=:author, description=:description, cover=:cover, genre=:genre, status=:status, updated_at=CURRENT_TIMESTAMP WHERE id=:id",
        {
            'title': data['title'],
            'author': data['author'],
            'description': data.get('description', ''),
            'cover': data.get('cover', ''),
            'genre': data.get('genre', ''),
            'status': data.get('status', 'ongoing'),
            'id': novel_id,
        }
    )
    return jsonify({'message': 'Novel updated'})

@app.route('/api/novels/<int:novel_id>', methods=['DELETE'])
@admin_required
def delete_novel(novel_id):
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM chapters WHERE novel_id=:novel_id"), {'novel_id': novel_id})
        conn.execute(sql_text("DELETE FROM favorites WHERE novel_id=:novel_id"), {'novel_id': novel_id})
        conn.execute(sql_text("DELETE FROM library WHERE novel_id=:novel_id"), {'novel_id': novel_id})
        conn.execute(sql_text("DELETE FROM comments WHERE novel_id=:novel_id"), {'novel_id': novel_id})
        conn.execute(sql_text("DELETE FROM novels WHERE id=:id"), {'id': novel_id})
    return jsonify({'message': 'Novel deleted'})

# â”€â”€â”€ CHAPTERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/novels/<int:novel_id>/chapters/<int:ch_num>', methods=['GET'])
def get_chapter(novel_id, ch_num):
    chapter = fetch_one(
        "SELECT * FROM chapters WHERE novel_id=:novel_id AND chapter_number=:chapter_number",
        {'novel_id': novel_id, 'chapter_number': ch_num}
    )
    if not chapter:
        return jsonify({'error': 'Chapter not found'}), 404
    
    total = fetch_one("SELECT COUNT(*) as c FROM chapters WHERE novel_id=:novel_id", {'novel_id': novel_id})['c']
    novel = fetch_one("SELECT title FROM novels WHERE id=:id", {'id': novel_id})
    
    result = chapter
    result['total_chapters'] = total
    result['novel_title'] = novel['title']
    return jsonify(result)

@app.route('/api/novels/<int:novel_id>/chapters', methods=['POST'])
@admin_required
def add_chapter(novel_id):
    data = request.json
    with engine.begin() as conn:
        ch_num = conn.execute(
            sql_text("SELECT COALESCE(MAX(chapter_number),0)+1 as n FROM chapters WHERE novel_id=:novel_id"),
            {'novel_id': novel_id}
        ).mappings().fetchone()['n']
        conn.execute(
            sql_text("INSERT INTO chapters (novel_id, chapter_number, title, content) VALUES (:novel_id, :chapter_number, :title, :content)"),
            {'novel_id': novel_id, 'chapter_number': ch_num, 'title': data['title'], 'content': data['content']}
        )
        conn.execute(sql_text("UPDATE novels SET updated_at=CURRENT_TIMESTAMP WHERE id=:id"), {'id': novel_id})
    return jsonify({'message': 'Chapter added', 'chapter_number': ch_num})

@app.route('/api/chapters/<int:chapter_id>', methods=['PUT'])
@admin_required
def update_chapter(chapter_id):
    data = request.json
    execute(
        "UPDATE chapters SET title=:title, content=:content WHERE id=:id",
        {'title': data['title'], 'content': data['content'], 'id': chapter_id}
    )
    return jsonify({'message': 'Chapter updated'})

@app.route('/api/chapters/<int:chapter_id>', methods=['DELETE'])
@admin_required
def delete_chapter(chapter_id):
    execute("DELETE FROM chapters WHERE id=:id", {'id': chapter_id})
    return jsonify({'message': 'Chapter deleted'})

# â”€â”€â”€ FAVORITES & LIBRARY â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/favorites', methods=['GET'])
@login_required
def get_favorites():
    favs = fetch_all('''SELECT n.*, COUNT(DISTINCT c.id) as chapter_count 
                        FROM favorites f JOIN novels n ON f.novel_id=n.id
                        LEFT JOIN chapters c ON n.id=c.novel_id
                        WHERE f.user_id=:user_id GROUP BY n.id''',
                     {'user_id': session['user_id']})
    return jsonify(favs)

@app.route('/api/favorites/<int:novel_id>', methods=['POST'])
@login_required
def toggle_favorite(novel_id):
    existing = fetch_one(
        "SELECT id FROM favorites WHERE user_id=:user_id AND novel_id=:novel_id",
        {'user_id': session['user_id'], 'novel_id': novel_id}
    )
    if existing:
        execute(
            "DELETE FROM favorites WHERE user_id=:user_id AND novel_id=:novel_id",
            {'user_id': session['user_id'], 'novel_id': novel_id}
        )
        return jsonify({'favorited': False})
    else:
        execute(
            "INSERT INTO favorites (user_id, novel_id) VALUES (:user_id, :novel_id)",
            {'user_id': session['user_id'], 'novel_id': novel_id}
        )
        return jsonify({'favorited': True})

@app.route('/api/library', methods=['GET'])
@login_required
def get_library():
    lib = fetch_all('''SELECT n.*, l.last_chapter, COUNT(DISTINCT c.id) as chapter_count
                       FROM library l JOIN novels n ON l.novel_id=n.id
                       LEFT JOIN chapters c ON n.id=c.novel_id
                       WHERE l.user_id=:user_id GROUP BY n.id, l.last_chapter''',
                    {'user_id': session['user_id']})
    return jsonify(lib)

@app.route('/api/library/<int:novel_id>', methods=['POST'])
@login_required
def toggle_library(novel_id):
    existing = fetch_one(
        "SELECT id FROM library WHERE user_id=:user_id AND novel_id=:novel_id",
        {'user_id': session['user_id'], 'novel_id': novel_id}
    )
    if existing:
        execute(
            "DELETE FROM library WHERE user_id=:user_id AND novel_id=:novel_id",
            {'user_id': session['user_id'], 'novel_id': novel_id}
        )
        return jsonify({'in_library': False})
    else:
        execute(
            "INSERT INTO library (user_id, novel_id) VALUES (:user_id, :novel_id)",
            {'user_id': session['user_id'], 'novel_id': novel_id}
        )
        return jsonify({'in_library': True})

# COMMENTS

@app.route('/api/novels/<int:novel_id>/comments', methods=['GET'])
def get_comments(novel_id):
    comments = fetch_all('''SELECT c.id, c.content, c.created_at, u.username
                            FROM comments c JOIN users u ON c.user_id=u.id
                            WHERE c.novel_id=:novel_id
                            ORDER BY c.created_at DESC''',
                         {'novel_id': novel_id})
    return jsonify(comments)

@app.route('/api/novels/<int:novel_id>/comments', methods=['POST'])
@login_required
def add_comment(novel_id):
    data = request.json or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    execute(
        "INSERT INTO comments (user_id, novel_id, content) VALUES (:user_id, :novel_id, :content)",
        {'user_id': session['user_id'], 'novel_id': novel_id, 'content': content}
    )
    return jsonify({'message': 'Comment added'})

# â”€â”€â”€ ADMIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    stats = {
        'total_novels': fetch_one("SELECT COUNT(*) as c FROM novels")['c'],
        'total_chapters': fetch_one("SELECT COUNT(*) as c FROM chapters")['c'],
        'total_users': fetch_one("SELECT COUNT(*) as c FROM users")['c'],
        'total_views': fetch_one("SELECT COALESCE(SUM(views),0) as c FROM novels")['c'],
        'total_favorites': fetch_one("SELECT COUNT(*) as c FROM favorites")['c'],
    }
    return jsonify(stats)

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_users():
    users = fetch_all("SELECT id, username, email, role, created_at FROM users ORDER BY created_at DESC")
    return jsonify(users)

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    with engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM favorites WHERE user_id=:user_id"), {'user_id': user_id})
        conn.execute(sql_text("DELETE FROM library WHERE user_id=:user_id"), {'user_id': user_id})
        conn.execute(sql_text("DELETE FROM comments WHERE user_id=:user_id"), {'user_id': user_id})
        conn.execute(sql_text("DELETE FROM users WHERE id=:id"), {'id': user_id})
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

init_db()

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    print("NovelVerse running at http://localhost:5000")
    app.run(debug=True, port=5000)
