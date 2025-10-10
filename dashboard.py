from flask import Flask, jsonify, render_template_string, request, session, redirect, url_for, flash
import os  # Env vars
import sqlite3  # Sync DB (error-free)
import json  # Safe entities
from datetime import datetime, timedelta  # Premium/events
import traceback  # Error logging

app = Flask(__name__)
app.secret_key = os.getenv('DASHBOARD_SECRET', 'nexusverse12')  # Session secret
DB_FILE = 'nexusverse.db'
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# Sync DB Helpers (Full – Matches bot schema, auto-init)
def init_dashboard_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER DEFAULT 100,
                entities TEXT DEFAULT '[]',
                level INTEGER DEFAULT 1,
                pity INTEGER DEFAULT 0,
                premium_until TEXT DEFAULT NULL,
                streak INTEGER DEFAULT 0,
                last_daily TEXT DEFAULT NULL,
                is_official_member BOOLEAN DEFAULT 0
            )
        ''')
        # Guilds (official servers)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                is_official BOOLEAN DEFAULT 0,
                spawn_multiplier REAL DEFAULT 1.0,
                admins TEXT DEFAULT '[]'
            )
        ''')
        # Bans
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                issuer_id INTEGER,
                timestamp TEXT,
                guild_id INTEGER DEFAULT NULL
            )
        ''')
        # Audits/Logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                issuer_id INTEGER,
                target_id INTEGER,
                guild_id INTEGER,
                timestamp TEXT
            )
        ''')
        # Global Events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS global_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                start_time TEXT,
                end_time TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("✅ Dashboard DB initialized (all tables ready).")
    except Exception as e:
        print(f"DB init error: {e}")
        traceback.print_exc()

def get_user_data_sync(user_id: int) -> dict:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            keys = ['user_id', 'credits', 'entities', 'level', 'pity', 'premium_until', 'streak', 'last_daily', 'is_official_member']
            data = dict(zip(keys, row))
            data['entities'] = json.loads(data['entities'] or '[]')
            data['is_premium'] = bool(data['premium_until'] and datetime.fromisoformat(data['premium_until']) > datetime.now())
            return data
        return {'user_id': user_id, 'credits': 100, 'entities': [], 'level': 1, 'is_premium': False, 'streak': 0, 'last_daily': None, 'is_official_member': False}
    except Exception as e:
        print(f"get_user_data error: {e}")
        return {'error': str(e)}

def update_user_data_sync(user_id: int, **kwargs):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        set_parts = ', '.join([f"{k} = ?" for k in kwargs])
        values = list(kwargs.values()) + [user_id]
        if 'entities' in kwargs:
            values[list(kwargs.keys()).index('entities')] = json.dumps(kwargs['entities'])
        if 'premium_until' in kwargs:
            idx = list(kwargs.keys()).index('premium_until')
            values[idx] = kwargs['premium_until'].isoformat() if kwargs['premium_until'] else None
        cursor.execute(f'UPDATE users SET {set_parts} WHERE user_id = ?', values)
        if cursor.rowcount == 0:
            cursor.execute('INSERT INTO users (user_id, credits, level) VALUES (?, 100, 1)', (user_id,))
        conn.commit()
        conn.close()
        print(f"Updated user {user_id}: {kwargs}")
    except Exception as e:
        print(f"update_user_data error: {e}")

def get_guild_data_sync(guild_id: int) -> dict:
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM guilds WHERE guild_id = ?', (guild_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            keys = ['guild_id', 'is_official', 'spawn_multiplier', 'admins']
            data = dict(zip(keys, row))
                        data['admins'] = json.loads(data['admins'] or '[]')
            return data
        return {'guild_id': guild_id, 'is_official': False, 'spawn_multiplier': 1.0, 'admins': []}
    except Exception as e:
        print(f"get_guild_data error: {e}")
        return {'error': str(e)}

def update_guild_data_sync(guild_id: int, **kwargs):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        set_parts = ', '.join([f"{k} = ?" for k in kwargs])
        values = list(kwargs.values()) + [guild_id]
        if 'admins' in kwargs:
            idx = list(kwargs.keys()).index('admins')
            values[idx] = json.dumps(kwargs['admins'])
        cursor.execute(f'UPDATE guilds SET {set_parts} WHERE guild_id = ?', values)
        if cursor.rowcount == 0:
            cursor.execute('INSERT INTO guilds (guild_id) VALUES (?)', (guild_id,))
        conn.commit()
        conn.close()
        print(f"Updated guild {guild_id}: {kwargs}")
    except Exception as e:
        print(f"update_guild_data error: {e}")

def ban_user_sync(user_id: int, reason: str, issuer_id: int = OWNER_ID, guild_id: int = None):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO bans (user_id, reason, issuer_id, timestamp, guild_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, reason, issuer_id, datetime.now().isoformat(), guild_id))
        conn.commit()
        conn.close()
        log_audit_sync('ban_user', issuer_id, user_id, guild_id)
        print(f"Banned {user_id}: {reason}")
    except Exception as e:
        print(f"ban_user error: {e}")

def unban_user_sync(user_id: int, guild_id: int = None):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        params = [user_id]
        where = 'guild_id = ?' if guild_id else 'guild_id IS NULL'
        if guild_id:
            params.append(guild_id)
        cursor.execute(f'DELETE FROM bans WHERE user_id = ? AND {where}', params)
        conn.commit()
        conn.close()
        log_audit_sync('unban_user', OWNER_ID, user_id, guild_id)
        print(f"Unbanned {user_id}")
    except Exception as e:
        print(f"unban_user error: {e}")

def start_global_event_sync(event_type: str, duration_hours: int = 24):
    try:
        end_time = datetime.now() + timedelta(hours=duration_hours)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM global_events')
        cursor.execute('INSERT INTO global_events (event_type, start_time, end_time) VALUES (?, ?, ?)',
                       (event_type, datetime.now().isoformat(), end_time.isoformat()))
        conn.commit()
        conn.close()
        log_audit_sync('start_event', OWNER_ID, None, None, extra=event_type)
        print(f"Started event: {event_type} for {duration_hours}h")
    except Exception as e:
        print(f"start_event error: {e}")

def get_global_event_sync():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT event_type FROM global_events WHERE end_time > ? LIMIT 1', (datetime.now().isoformat(),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"get_global_event error: {e}")
        return None

def get_total_users_sync():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"total_users error: {e}")
        return 0

def get_banned_users_sync():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, reason, timestamp FROM bans')
        rows = cursor.fetchall()
        conn.close()
        return [{'user_id': r[0], 'reason': r[1], 'timestamp': r[2]} for r in rows]
    except Exception as e:
        print(f"banned_users error: {e}")
        return []

def get_audit_logs_sync(limit: int = 10):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT action, issuer_id, target_id, timestamp FROM audits ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [{'action': r[0], 'issuer': r[1], 'target': r[2], 'timestamp': r[3]} for r in rows]
    except Exception as e:
        print(f"audit_logs error: {e}")
        return []

def log_audit_sync(action: str, issuer_id: int, target_id: int = None, guild_id: int = None):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execut(        'INSERT INTO audits (action, issuer_id, target_id, guild_id, timestamp) VALUES (?, ?, ?, ?, ?)',
                       (action, issuer_id, target_id, guild_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"log_audit error: {e}")

def get_top_entities_sync():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT entities FROM users WHERE entities IS NOT NULL AND entities != "[]"')
        rows = cursor.fetchall()
        conn.close()
        all_entities = []
        for row in rows:
            try:
                entities = json.loads(row[0])
                all_entities.extend(entities)
            except json.JSONDecodeError:
                pass
        if not all_entities:
            return []
        # Top 5 by power
        top = sorted(all_entities, key=lambda e: e.get('power', 0), reverse=True)[:5]
        return top
    except Exception as e:
        print(f"get_top_entities error: {e}")
        return []

# Permission Decorator (Secret Key + Owner ID Check)
def login_required(f):
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Login required.', 'warning')
            return redirect(url_for('login'))
        if session['user_id'] != OWNER_ID:
            flash('Access denied – Owner only.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        secret = request.form.get('secret')
        if secret == app.secret_key:
            session['logged_in'] = True
            session['user_id'] = OWNER_ID
            log_audit_sync('login', OWNER_ID)
            flash('Login successful – Welcome, Owner! 🌌', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid secret – Access denied. 🔒', 'error')
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Owner Login - NexusVerse</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: linear-gradient(135deg, #0D1117 0%, #1a1a2e 50%, #16213e 100%); color: #fff; }
            .neon-glow { box-shadow: 0 0 20px #00D4FF; border: 1px solid #00D4FF; }
            .btn-neon { background: linear-gradient(45deg, #00D4FF, #8B00FF); color: white; }
        </style>
    </head>
    <body class="d-flex justify-content-center align-items-center vh-100">
        <div class="card neon-glow p-4" style="width: 400px;">
            <h2 class="text-center mb-4">🔐 Owner Login</h2>
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }}">{{ message }}</div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <form method="post">
                <div class="mb-3">
                    <input type="password" name="secret" class="form-control" placeholder="Enter Secret Key" required>
                </div>
                <button type="submit" class="btn btn-neon w-100">Login</button>
            </form>
            <p class="text-center mt-3 small">Secret: DASHBOARD_SECRET env var (default: nexusverse12)</p>
        </div>
    </body>
    </html>
    '''

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NexusVerse Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style> body { background: linear-gradient(135deg, #0D1117, #1a1a2e); color: #fff; } .neon-glow { box-shadow: 0 0 20px #00D4FF; } .btn-neon { background: linear-gradient(45deg, #00D4FF, #8B00FF); color: white; } </style>
    </head>
    <body class="d-flex justify-content-center align-items-center vh-100">
        <div class="text-center">
            <h1 class="neon-glow mb-4">🌌 NexusVerse Control Center</h1>
            <p class="lead">Ultimate Admin Panel for Bot Commands & Servers</p>
            <a href="/login" class="btn btn-neon btn-lg me-3">Owner Login 🔐</a>
            <a href="/public-dashboard" class="btn btn-secondary btn-lg">Public Stats 📊</a>
            <p class="mt-4">Bot Online – Commands populate data!</p>
        </div>
    </body>
    </html>
    '''

@app.route('/public-dashboard')
def public_dashboard():
    total_users = get_total_users_sync()
    event = get_global_event_sync() or 'None'
    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Public Stats - NexusVerse</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style> body { background: linear-gradient(135deg, #0D1117, #1a1a2e); color: #fff; } .card { background: rgba(13,17,23,0.8); } .neon-glow { box-shadow: 0 0 20px #00D4FF; } </style>
    </head>
    <body class="p-5">
        <div class="container">
            <h1 class="text-center neon-glow mb-4">Public NexusVerse Stats</h1>
            <div class="row">
                <div class="col-md-6">
                    <div class="card neon-glow p-3">
                        <h5>Total Users</h5>
                        <h2>{total_users}</h2>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card p-3">
                        <h5>Active Global Event</h5>
                        <h2>{event}</h2>
                    </div>
                </div>
            </div>
            <div class="text-center mt-4">
                <a href="/login" class="btn btn-neon">Owner Controls</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        total_users = get_total_users_sync()
        owner_data = get_user_data_sync(OWNER_ID)
        top_entities = get_top_entities_sync()
        event = get_global_event_sync() or 'None'
        banned_users = get_banned_users_sync()
        audit_logs = get_audit_logs_sync(5)
        return render_template_string(ADMIN_TEMPLATE,  # Template below
                                     total_users=total_users, owner_data=owner_data,
                                     top_entities=top_entities, event=event,
                                     banned_users=banned_users, audit_logs=audit_logs)
    except Exception as e:
        print(f"Dashboard error: {e}")
        traceback.print_exc()
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect(url_for('login'))

# Admin POST Routes (All Commands Control)
@app.route('/admin/premium', methods=['POST'])
@login_required
def admin_premium():
    try:
        user_id = int(request.form['user_id'])
        duration = int(request.form.get('duration', 1))
        end_time = datetime.now() + timedelta(days=30 * duration)
        update_user_data_sync(user_id, premium_until=end_time)
        log_audit_sync('grant_premium', OWNER_ID, user_id)
        flash(f'Premium granted to user {user_id} for {duration} months! 💎', 'success')
    except Exception as e:
        flash(f'Premium grant error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/ban', methods=['POST'])
@login_required
def admin_ban():
    try:
        user_id = int(request.form['user_id'])
        reason = request.form['reason']
        guild_id = int(request.form.get('guild_id', 0)) or None
        ban_user_sync(user_id, reason, OWNER_ID, guild_id)
        flash(f'User {user_id} banned: {reason}', 'success')
    except Exception as e:
        flash(f'Ban error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/unban', methods=['POST'])
@login_required
def admin_unban():
    try:
        user_id = int(request.form['user_id'])
        guild_id = int(request.form.get('guild_id', 0)) or None
        unban_user_sync(user_id, guild_id)
        flash(f'User {user_id} unbanned!', 'success')
    except Exception as e:
        flash(f'Unban error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/event', methods=['POST'])
@login_required
def admin_event():
    try:
        event_type = request.form['event_type']
        duration = int(request.form['duration'])
        start_global_event_sync(event_type, duration)
        flash(f'Global event "{event_type}" started for {duration}h! 🌟', 'success')
    except Exception as e:
        flash(f'Event error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/official-server', methods=['POST'])
@login_required
def admin_official_server():
    try:
        guild_id = int(request.form['guild_id'])
        multiplier = float(request.form.get('multiplier', 3.0))
        update_guild_data_sync(guild_id, is_official=True, spawn_multiplier=multiplier)
        log_audit_sync('set_official_server', OWNER_ID, None, guild_id)
        flash(f'Guild {guild_id} set as official server (spawn x{multiplier})! 🏛️', 'success')
    except Exception as e:
        flash(f'Official server error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/daily', methods=['POST'])
@login_required
def admin_daily():
    try:
        user_id = int(request.form['user_id'])
        credits = int(request.form.get('credits', 100))
        update_user_data_sync(user_id, credits=kwargs['credits'] + credits, last_daily=datetime.now().isoformat())
        flash(f'Daily reward granted to {user_id}: +{credits} credits! 🎁', 'success')
    except Exception as e:
        flash(f'Daily error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/shop', methods=['POST'])
@login_required
def admin_shop():
    try:
        user_id = int(request.form['user_id'])
        item = request.form['item']  # e.g., 'boost', 'entity'
        cost = int(request.form.get('cost', 50))
        update_user_data_sync(user_id, credits=kwargs['credits'] - cost)
        if item == 'entity':
            # Add entity to user
            new_entity = {'name': 'Admin Gift', 'rarity': 'Legendary', 'power': 100}
            data = get_user_data_sync(user_id)
            data['entities'].append(new_entity)
            update_user_data_sync(user_id, entities=data['entities'])
        flash(f'Shop buy for {user_id}: {item} for {cost} credits! 🛒', 'success')
    except Exception as e:
        flash(f'Shop error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/pull', methods=['POST'])
@login_required
def admin_pull():
    try:
        user_id = int(request.form['user_id'])
        num_pulls = int(request.form.get('num_pulls', 1))
        # Simulate pull (add random entities)
        data = get_user_data_sync(user_id)
        for _ in range(num_pulls):
            entity = {'name': 'Pulled Entity', 'rarity': 'Rare', 'power': 50}  # Randomize in full
            data['entities'].append(entity)
            data['pity'] = 0
        update_user_data_sync(user_id, entities=data['entities'], pity=0)
        flash(f'{num_pulls} pulls granted to {user_id}! 🎰', 'success')
    except Exception as e:
        flash(f'Pull error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/catch-boost', methods=['POST'])
@login_required
def admin_catch_boost():
    try:
        user_id = int(request.form['user_id'])
        boost = float(request.form.get('boost', 2.0))
        # Temporary boost (add to user data or global)
        update_user_data_sync(user_id, spawn_boost=boost)  # Add column if needed
        flash(f'Catch boost x{boost} granted to {user_id}! 🎣', 'success')
    except Exception as e:
        flash(f'Catch boost error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/battle-setup', methods=['POST'])
@login_required
def admin_battle_setup():
    try:
        user1_id = int(request.form['user1_id'])
        user2_id = int(request.form['user2_id'])
        # Setup battle (log or update DB for bot to handle)
        log_audit_sync('battle_setup', OWNER_ID, user1_id, None, extra=f'vs {user2_id}')
        flash(f'Battle setup: {user1_id} vs {user2_id}! ⚔️', 'success')
    except Exception as e:
        flash(f'Battle setup error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/profile-edit', methods=['POST'])
@login_required
def admin_profile_edit():
    try:
        user_id = int(request.form['user_id'])
        credits = int(request.form.get('credits', 0))
        level = int(request.form.get('level', 1))
        update_user_data_sync(user_id, credits=credits, level=level)
        flash(f'Profile edited for {user_id}: Credits {credits}, Level {level}! 📊', 'success')
    except Exception as e:
        flash(f'Profile edit error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

# Attractive Admin Template (Neon Theme – Tabs for All Sections)
ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Dashboard - NexusVerse</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: linear-gradient(135deg, #0D1117 0%, #1a1a2e 50%, #16213e 100%); color: #fff; font-family: 'Arial', sans-serif; }
        .neon-glow { box-shadow: 0 0 20px #00D4FF, inset 0 0 10px rgba(0,212,255,0.1); border: 1px solid #00D4FF; }
        .neon-purple { box-shadow: 0 0 20px #8B00FF, inset 0 0 10px rgba(139,0,255,0.1); border: 1px solid #8B00FF; }
        .card { background: rgba(13,17,23,0.8); border-radius: 15px; backdrop-filter: blur(10px); }
        .btn-neon { background: linear-gradient(45deg, #00D4FF, #8B00FF); border: none; color: white; box-shadow: 0 0 15px rgba(0,212,255,0.5); }
        .btn-neon:hover { box-shadow: 0 0 25px rgba(0,212,255,0.8); transform: scale(1.05); }
        h1 { text-shadow: 0 0 10px #00D4FF; } .chart-container { background: rgba(0,0,0,0.5); border-radius: 10px; padding: 20px; } .modal-content { background: rgba(13,17,23,0.9); color: white; } .tab-pane { padding: 20px; } </style>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark">
            <div class="container">
                <a class="navbar-brand neon-glow" href="#">🌌 NexusVerse Admin</a>
                <div>
                    <a href="/dashboard" class="btn btn-outline-light me-2">Dashboard</a>
                    <a href="/logout" class="btn btn-outline-danger">Logout</a>
                </div>
            </div>
        </nav>
        <div class="container mt-4">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' if category == 'error' else 'warning' }} alert-dismissible fade show" role="alert">
                            {{ message }}
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="alert"></button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            <h1 class="text-center mb-4 neon-glow">Ultimate Control Center</h1>
            <ul class="nav nav-tabs neon-glow" id="adminTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="stats-tab" data-bs-toggle="tab" data-bs-target="#stats" type="button" role="tab">📊 Stats</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="commands-tab" data-bs-toggle="tab" data-bs-target="#commands" type="button" role="tab">⚡ Commands</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="servers-tab" data-bs-toggle="tab" data-bs-target="#servers" type="button" role="tab">🏛️ Servers</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="bans-tab" data-bs-toggle="tab" data-bs-target="#bans" type="button" role="tab">🚫 Bans</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="logs-tab" data-bs-toggle="tab" data-bs-target="#logs" type="button" role="tab">📝 Logs</button>
                </li>
            </ul>
            <div class="tab-content" id="adminTabsContent">
                <!-- Stats Tab -->
                <div class="tab-pane fade show active" id="stats" role="tabpanel">
                    <div class="row mt-3">
                        <div class="col-md-3">
                            <div class="card neon-glow p-3">
                                <h5>Total Users</h5>
                                <h2>{{ total_users }}</h2>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card neon-purple p-3">
                                <h5>Owner Level</h5>
                                <h2>{{ owner_data.level }}</h2>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card neon-glow p-3">
                                <h5>Total Credits</h5>
                                <h2>{{ owner_data.credits }}</h2>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card neon-purple p-3">
                                <h5>Premium Status</h5>
                                <h2>{% if owner_data.is_premium %}💎 Active{% else %}Inactive{% endif %}</h2>
                            </div>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-6">
                            <div class="card p-3">
                                <h5>Owner Profile</h5>
                                <p>Entities: {{ owner_data.entities|length }} (Power: {{ owner_data.entities|sum(attribute='power') }})</p>
                                <p>Streak: {{ owner_data.streak }}</p>
                                <p>Last Daily: {{ owner_data.last_daily or 'None' }}</p>
                                <a href="/api/profile/{{ OWNER_ID }}" class="btn btn-neon">JSON Profile</a>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card chart-container">
                                <h5>Top Entities Chart</h5>
                                <canvas id="entitiesChart"></canvas>
                            </div>
                        </div>
                    </div>
                    <script>
                        const ctx = document.getElementById('entitiesChart').getContext('2d');
                        new Chart(ctx, {{
                            type: 'bar',
                            data: {{
                                labels: {{ top_entities|map(attribute='name')|list|tojson }},
                                datasets: [{{
                                    label: 'Power',
                                    data: {{ top_entities|map(attribute='power')|list|tojson }},
                                    backgroundColor: 'rgba(0, 212, 255, 0.6)',
                                    borderColor: '#00D4FF',
                                    borderWidth: 2
                                }}]
                            }},
                            options: {{
                                scales: {{ y: {{ beginAtZero: true }} }},
                                plugins: {{ legend: {{ labels: {{ color: '#fff' }} }} }}
                            }}
                        }});
                    </script>
                </div>
                <!-- Commands Tab (All Bot Commands Control) -->
                <div class="tab-pane fade" id="commands" role="tabpanel">
                    <h5 class="mt-3">Execute Bot Commands from Dashboard</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <button class="btn btn-neon w-100 mb-2" data-bs-toggle="modal" data-bs-target="#premiumModal">Grant Premium 💎</button>
                            <button class="btn btn-neon w-100 mb-2" data-bs-toggle="modal" data-bs-target="#dailyModal">Give Daily 🎁</button>
                            <button class="btn btn-neon w-100 mb-2" data-bs-toggle="modal" data-bs-target="#shopModal">Shop Buy 🛒</button>
                            <button class="btn btn-neon w-100 mb-2" data-bs-toggle="modal" data-bs-target="#pullModal">Gacha Pull 🎰</button>
                            <button class="btn btn-neon w-100 mb-2" data-bs-toggle="modal" data-bs-target="#catchBoostModal">Catch Boost 🎣</button>
                            <button class="btn btn-neon w-100 mb-2" data-bs-toggle="modal" data-bs-target="#battleModal">Battle Setup ⚔️</button>
                            <button class="btn btn-neon w-100 mb-2" data-bs-toggle="modal" data-bs-target="#profileEditModal">Edit Profile 📊</button>
                        </div>
                    </div>
                    <!-- Modals for Commands -->
                    <!-- Premium Modal -->
                    <div class="modal fade" id="premiumModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Grant Premium</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/premium">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="number" name="duration" class="form-control" placeholder="Months (1 default)" value="1">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Grant 💎</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Daily Modal -->
                    <div class="modal fade" id="dailyModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Give Daily Reward</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/daily">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="number" name="credits" class="form-control" placeholder="Credits (100 default)" value="100">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Give 🎁</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Shop Modal -->
                    <div class="modal fade" id="shopModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Shop Buy</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/shop">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="text" name="item" class="form-control mb-2" placeholder="Item (e.g., boost, entity)" required>
                                        <input type="number" name="cost" class="form-control" placeholder="Cost (50 default)" value="50">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Buy 🛒</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Pull Modal -->
                    <div class="modal fade" id="pullModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Gacha Pull</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/pull">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="number" name="num_pulls" class="form-control" placeholder="Number of Pulls (1 default)" value="1">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Pull 🎰</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Catch Boost Modal -->
                    <div class="modal fade" id="catchBoostModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Catch Boost</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/catch-boost">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="number" step="0.1" name="boost" class="form-control" placeholder="Boost Multiplier (2.0 default)" value="2.0">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Boost 🎣</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Battle Setup Modal -->
                    <div class="modal fade" id="battleModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Battle Setup</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/battle-setup">
                                    <div class="modal-body">
                                        <input type="number" name="user1_id" class="form-control mb-2" placeholder="User 1 ID" required>
                                        <input type="number" name="user2_id" class="form-control" placeholder="User 2 ID" required>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Setup Battle ⚔️</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Profile Edit Modal -->
                    <div class="modal fade" id="profileEditModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Edit Profile</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/profile-edit">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="number" name="credits" class="form-control mb-2" placeholder="Credits (0 to set)" value="0">
                                        <input type="number" name="level" class="form-control" placeholder="Level (1 default)" value="1">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Edit 📊</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
                <!-- Servers Tab (Official Server Setup) -->
                <div class="tab-pane fade" id="servers" role="tabpanel">
                    <h5 class="mt-3">Official Server Management</h5>
                    <p>Set servers as official for 3x spawn rates in /catch, premium perks, etc.</p>
                    <button class="btn btn-neon mb-3" data-bs-toggle="modal" data-bs-target="#officialModal">Add Official Server 🏛️</button>
                    <div class="row">
                        <div class="col-md-6">
                            <h6>Official Servers List</h6>
                            <ul class="list-group">
                                {% for guild in official_guilds %}
                                <li class="list-group-item bg-dark text-white d-flex justify-content-between">
                                    Guild ID: {{ guild.guild_id }} (x{{ guild.spawn_multiplier }})
                                    <button class="btn btn-sm btn-outline-danger" onclick="removeOfficial({{ guild.guild_id }})">Remove</button>
                                </li>
                                {% endfor %}
                            </ul>
                        </div>
                    </div>
                    <!-- Official Server Modal -->
                    <div class="modal fade" id="officialModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Set Official Server</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/official-server">
                                    <div class="modal-body">
                                        <input type="number" name="guild_id" class="form-control mb-2" placeholder="Guild ID (Right-click server > Copy ID)" required>
                                        <input type="number" step="0.1" name="multiplier" class="form-control" placeholder="Spawn Multiplier (3.0 default)" value="3.0">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-neon">Set Official 🏛️</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <script>
                        function removeOfficial(guild_id) {
                            if (confirm('Remove official status?')) {
                                // POST to remove (add route if needed)
                                fetch('/admin/remove-official', { method: 'POST', body: new FormData({guild_id: guild_id}) });
                                location.reload();
                            }
                        }
                    </script>
                </div>
                <!-- Bans Tab -->
                <div class="tab-pane fade" id="bans" role="tabpanel">
                    <h5 class="mt-3">Ban Management</h5>
                    <button class="btn btn-danger mb-3" data-bs-toggle="modal" data-bs-target="#banModal">Ban User 🚫</button>
                    <button class="btn btn-success mb-3" data-bs-toggle="modal" data-bs-target="#unbanModal">Unban User</button>
                    <h6>Banned Users</h6>
                    <table class="table table-dark">
                        <thead><tr><th>ID</th><th>Reason</th><th>Timestamp</th><th>Actions</th></tr></thead>
                        <tbody>
                            {% for ban in banned_users %}
                            <tr>
                                <td>{{ ban.user_id }}</td>
                                <td>{{ ban.reason }}</td>
                                <td>{{ ban.timestamp }}</td>
                                <td><button class="btn btn-sm btn-success" onclick="unban({{ ban.user_id }})">Unban</button></td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    <!-- Ban Modal -->
                    <div class="modal fade" id="banModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Ban User</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/ban">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="text" name="reason" class="form-control mb-2" placeholder="Reason" required>
                                        <input type="number" name="guild_id" class="form-control" placeholder="Guild ID (optional for global ban)">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-danger">Ban 🚫</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <!-- Unban Modal -->
                    <div class="modal fade" id="unbanModal" tabindex="-1">
                        <div class="modal-dialog">
                            <div class="modal-content bg-dark text-white">
                                <div class="modal-header">
                                    <h5 class="modal-title">Unban User</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                </div>
                                <form method="post" action="/admin/unban">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                        <input type="number" name="guild_id" class="form-control" placeholder="Guild ID (optional for global unban)">
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-success">Unban</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                    <script>
                        function unban(user_id) {
                            if (confirm('Unban this user?')) {
                                fetch('/admin/unban', { method: 'POST', body: new FormData({user_id: user_id}) });
                                location.reload();
                            }
                        }
                    </script>
                </div>
                <!-- Logs Tab -->
                <div class="tab-pane fade" id="logs" role="tabpanel">
                    <h5 class="mt-3">Audit Logs (Recent Actions)</h5>
                    <table class="table table-dark">
                        <thead><tr><th>Action</th><th>Issuer ID</th><th>Target ID</th><th>Timestamp</th></tr></thead>
                        <tbody>
                            {% for log in audit_logs %}
                            <tr>
                                <td>{{ log.action }}</td>
                                <td>{{ log.issuer }}</td>
                                <td>{{ log.target or 'N/A' }}</td>
                                <td>{{ log.timestamp }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    <p class="small">Logs all admin actions (premium grants, bans, events, etc.).</p>
                </div>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
"""

# Additional Admin Routes (Full Command Controls)
@app.route('/admin/remove-official', methods=['POST'])
@login_required
def admin_remove_official():
    try:
        guild_id = int(request.form['guild_id'])
        update_guild_data_sync(guild_id, is_official=False, spawn_multiplier=1.0)
        log_audit_sync('remove_official_server', OWNER_ID, None, guild_id)
        flash(f'Guild {guild_id} removed from official status.', 'info')
    except Exception as e:
        flash(f'Remove official error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/quest', methods=['POST'])
@login_required
def admin_quest():
    try:
        user_id = int(request.form['user_id'])
        reward = int(request.form.get('reward', 50))
        update_user_data_sync(user_id, credits=kwargs['credits'] + reward, streak=kwargs['streak'] + 1)
        flash(f'Quest reward granted to {user_id}: +{reward} credits, streak +1! 🏆', 'success')
    except Exception as e:
        flash(f'Quest error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/heist', methods=['POST'])
@login_required
def admin_heist():
    try:
        victim_id = int(request.form['victim_id'])
        thief_id = int(request.form['thief_id'])
        amount = int(request.form.get('amount', 100))
        # Simulate heist (transfer credits)
        victim_data = get_user_data_sync(victim_id)
        thief_data = get_user_data_sync(thief_id)
        if victim_data['credits'] >= amount:
            update_user_data_sync(victim_id, credits=victim_data['credits'] - amount)
            update_user_data_sync(thief_id, credits=thief_data['credits'] + amount)
            log_audit_sync('heist', OWNER_ID, thief_id, None, extra=f'from {victim_id} {amount}')
            flash(f'Heist success: {thief_id} stole {amount} from {victim_id}! 💰', 'success')
        else:
            flash('Not enough credits on victim!', 'warning')
    except Exception as e:
        flash(f'Heist error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/trade', methods=['POST'])
@login_required
def admin_trade():
    try:
        user1_id = int(request.form['user1_id'])
        user2_id = int(request.form['user2_id'])
        entity_id = int(request.form['entity_id'])  # Index in entities list
        # Transfer entity
        user1_data = get_user_data_sync(user1_id)
        user2_data = get_user_data_sync(user2_id)
        if 0 <= entity_id < len(user1_data['entities']):
            entity = user1_data['entities'].pop(entity_id)
            user2_data['entities'].append(entity)
            update_user_data_sync(user1_id, entities=user1_data['entities'])
            update_user_data_sync(user2_id, entities=user2_data['entities'])
            log_audit_sync('trade', OWNER_ID, user1_id, None, extra=f'to {user2_id} entity {entity_id}')
            flash(f'Trade complete: Entity from {user1_id} to {user2_id}! 🔄', 'success')
        else:
            flash('Invalid entity ID!', 'warning')
    except Exception as e:
        flash(f'Trade error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

# API Routes (Public/Owner)
@app.route('/api/users')
def api_users():
    try:
        total = get_total_users_sync()
        return jsonify({'total_users': total, 'status': 'active'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile/<int:user_id>')
@login_required
def api_profile(user_id):
    try:
        data = get_user_data_sync(user_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    try:
        return jsonify({
            'status': 'healthy',
            'total_users': get_total_users_sync(),
            'active_event': get_global_event_sync() or 'None'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/debug')
@login_required
def debug():
    try:
        owner_id = os.getenv('OWNER_ID', 'Not Set')
        db_exists = os.path.exists(DB_FILE)
        total_users = get_total_users_sync()
        return f'''
        <h1>Debug Info</h1>
        <p>OWNER_ID: {owner_id}</p>
        <p>DB Exists: {db_exists} (Size: {os.path.getsize(DB_FILE) if db_exists else 0} bytes)</p>
        <p>Total Users: {total_users}</p>
        <p>PORT: {os.getenv('PORT', 'Not Set')}</p>
        <p>Secret Key: {app.secret_key[:10]}...</p>
        <p>If issues: Run bot /start to init DB.</p>
        '''
    except Exception as e:
        return f"<h1>Debug Error: {e}</h1>", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print(f"🚀 Ultimate Dashboard starting on {host}:{port}")
    print(f"DB: {DB_FILE} | Owner ID: {OWNER_ID} | Secret: {app.secret_key[:10]}...")
    init_dashboard_db()  # Re-init for safety
    app.run(host=host, port=port, debug=False)  # Prod: No debug logs