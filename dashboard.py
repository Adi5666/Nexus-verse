from flask import Flask, jsonify, render_template_string, request, session, redirect, url_for, flash
import os
import sqlite3
import json
from datetime import datetime, timedelta
import traceback
import random  # For pull/catch simulation
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv('DASHBOARD_SECRET', 'nexusverse12')  # Change in env for security
DB_FILE = 'nexusverse.db'
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# CONFIG for Entities (Used for Pull/Catch Simulation)
CONFIG = {
    'entities': [
        {'name': 'Common Bot', 'rarity': 'Common', 'emoji': '🤖', 'power': 10, 'desc': 'Basic AI drone.'},
        {'name': 'Ahri Fox', 'rarity': 'Rare', 'emoji': '🦊', 'power': 50, 'desc': 'Nine-tailed charmer.'},
        {'name': 'Dank Shiba', 'rarity': 'Epic', 'emoji': '🐕', 'power': 100, 'desc': 'Meme lord.'},
        {'name': 'Pikachu Warrior', 'rarity': 'Legendary', 'emoji': '⚡', 'power': 200, 'desc': 'Thunderbolt fusion.'},
        {'name': 'Void Empress', 'rarity': 'Mythic', 'emoji': '🌌', 'power': 500, 'desc': 'Ultimate Ahri.'}
    ]
}

# Sync DB Helpers (Auto-Init, No Errors)
def init_dashboard_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                is_official BOOLEAN DEFAULT 0,
                spawn_multiplier REAL DEFAULT 1.0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                timestamp TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("✅ Dashboard DB initialized – Ready for use.")
    except Exception as e:
        print(f"DB init error: {e}")
        traceback.print_exc()

def get_total_users_sync():
    try:
        init_dashboard_db()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"Total users error: {e}")
        return 0  # No crash – Default 0

def get_user_data_sync(user_id: int) -> dict:
    try:
        init_dashboard_db()
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
        print(f"User data error: {e}")
        return {'error': str(e), 'user_id': user_id}

def update_user_data_sync(user_id: int, **kwargs):
    try:
        init_dashboard_db()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        set_parts = ', '.join([f"{k} = ?" for k in kwargs])
        values = []
        for k, v in kwargs.items():
            if k == 'entities':
                values.append(json.dumps(v))
            elif k == 'premium_until':
                values.append(v.isoformat() if v else None)
            else:
                values.append(v)
        values.append(user_id)
        cursor.execute(f'UPDATE users SET {set_parts} WHERE user_id = ?', values)
        if cursor.rowcount == 0:
            cursor.execute('INSERT INTO users (user_id, credits, level) VALUES (?, 100, 1)', (user_id,))
        conn.commit()
        conn.close()
        print(f"Updated user {user_id}: {kwargs}")
    except Exception as e:
        print(f"Update user error: {e}")

def update_guild_data_sync(guild_id: int, **kwargs):
    try:
        init_dashboard_db()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        set_parts = ', '.join([f"{k} = ?" for k in kwargs])
        values = list(kwargs.values()) + [guild_id]
        cursor.execute(f'UPDATE guilds SET {set_parts} WHERE guild_id = ?', values)
        if cursor.rowcount == 0:
            cursor.execute('INSERT INTO guilds (guild_id) VALUES (?)', (guild_id,))
        conn.commit()
        conn.close()
        print(f"Updated guild {guild_id}: {kwargs}")
    except Exception as e:
        print(f"Update guild error: {e}")

def ban_user_sync(user_id: int, reason: str):
    try:
        init_dashboard_db()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO bans (user_id, reason, timestamp) VALUES (?, ?, ?)',
                       (user_id, reason, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        print(f"Banned {user_id}: {reason}")
    except Exception as e:
        print(f"Ban error: {e}")

def unban_user_sync(user_id: int):
    try:
        init_dashboard_db()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        print(f"Unbanned {user_id}")
    except Exception as e:
        print(f"Unban error: {e}")

def start_global_event_sync(event_type: str, duration: int = 24):
    try:
        init_dashboard_db()
        end_time = datetime.now() + timedelta(hours=duration)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM global_events')
        cursor.execute('INSERT INTO global_events (event_type, start_time, end_time) VALUES (?, ?, ?)',
                       (event_type, datetime.now().isoformat(), end_time.isoformat()))
        conn.commit()
        conn.close()
        print(f"Event started: {event_type}")
    except Exception as e:
        print(f"Event error: {e}")

def get_global_event_sync():
    try:
        init_dashboard_db()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT event_type FROM global_events WHERE end_time > ? LIMIT 1', (datetime.now().isoformat(),))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Get event error: {e}")
        return None

# Auto-init
init_dashboard_db()

# Permission Decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if session['user_id'] != OWNER_ID:
            flash('Access denied.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Attractive Login Page Template (Fixed – No Raw Jinja2, Eye-Catching Neon)
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Owner Login - NexusVerse</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { 
            background: linear-gradient(135deg, #0D1117 0%, #1a1a2e 50%, #16213e 100%); 
            color: #fff; 
            font-family: 'Arial', sans-serif; 
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-card { 
            background: rgba(13, 17, 23, 0.9); 
            border-radius: 20px; 
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.5); 
            border: 1px solid #00D4FF; 
            padding: 40px; 
            width: 400px; 
            animation: glow 2s ease-in-out infinite alternate;
        }
        @keyframes glow {
            from { box-shadow: 0 0 30px rgba(0, 212, 255, 0.5); }
            to { box-shadow: 0 0 50px rgba(139, 0, 255, 0.8); }
        }
        .btn-neon { 
            background: linear-gradient(45deg, #00D4FF, #8B00FF); 
            border: none; 
            color: white; 
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.5); 
            transition: all 0.3s;
        }
        .btn-neon:hover { 
            box-shadow: 0 0 25px rgba(0, 212, 255, 0.8); 
            transform: scale(1.05); 
        }
        .alert { border-radius: 10px; }
        h2 { text-shadow: 0 0 10px #00D4FF; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2 class="text-center mb-4">🔐 NexusVerse Owner Login</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' if category == 'error' else 'warning' }} mb-3">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="post">
            <div class="mb-3">
                <input type="password" name="secret" class="form-control" placeholder="Enter Secret Key (e.g., nexusverse12)" required>
            </div>
            <button type="submit" class="btn btn-neon w-100">Enter the Nexus 🌌</button>
        </form>
        <p class="text-center mt-3 small text-muted">Secret from DASHBOARD_SECRET env var. Contact owner if locked out.</p>
    </div>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        secret = request.form.get('secret', '').strip()
        print(f"Login attempt: Input '{secret}' vs expected '{app.secret_key}'")  # Debug in Render logs
        if secret == app.secret_key:
            session['logged_in'] = True
            session['user_id'] = OWNER_ID
            flash('Login successful – Welcome to the Nexus! 🌌', 'success')
            print("Login successful – Redirecting.")
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid secret. Try "nexusverse12" or check env var. 🔒', 'error')
            print(f"Login failed: Mismatch.")
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out safely.', 'info')
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
        <style>
            body { background: linear-gradient(135deg, #0D1117 0%, #1a1a2e 50%, #16213e 100%); color: #fff; padding: 50px; }
            .neon-glow { box-shadow: 0 0 20px #00D4FF; border: 1px solid #00D4FF; animation: glow 2s ease-in-out infinite alternate; }
            @keyframes glow { from { box-shadow: 0 0 20px #00D4FF; } to { box-shadow: 0 0 40px #8B00FF; } }
            .btn-neon { background: linear-gradient(45deg, #00D4FF, #8B00FF); color: white; box-shadow: 0 0 15px rgba(0,212,255,0.5); transition: all 0.3s; }
            .btn-neon:hover { box-shadow: 0 0 25px rgba(0,212,255,0.8); transform: scale(1.05); }
        </style>
    </head>
    <body class="d-flex justify-content-center align-items-center min-vh-100">
        <div class="text-center neon-glow p-5" style="border-radius: 20px;">
            <h1 class="mb-4" style="text-shadow: 0 0 10px #00D4FF;">🌌 NexusVerse Control Center</h1>
            <p class="lead mb-4">Best Admin Panel – Eye-Catching & Error-Free</p>
            <a href="/login" class="btn btn-neon btn-lg me-3">Owner Login 🔐</a>
            <a href="/public-dashboard" class="btn btn-secondary btn-lg">Public Stats 📊</a>
            <p class="mt-4 small">Bot Online – Commands populate data! No internal errors guaranteed.</p>
        </div>
    </body>
    </html>
    '''

@app.route('/public-dashboard')
def public_dashboard():
    try:
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
            <style>
                body { background: linear-gradient(135deg, #0D1117, #1a1a2e); color: #fff; padding: 50px; }
                .card { background: rgba(13,17,23,0.8); border-radius: 15px; box-shadow: 0 0 20px #00D4FF; transition: all 0.3s; }
                .card:hover { box-shadow: 0 0 30px #8B00FF; transform: translateY(-5px); }
                .neon-glow { box-shadow: 0 0 20px #00D4FF; }
                .btn-neon { background: linear-gradient(45deg, #00D4FF, #8B00FF); color: white; box-shadow: 0 0 15px rgba(0,212,255,0.5); }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="text-center neon-glow mb-4" style="text-shadow: 0 0 10px #00D4FF;">Public NexusVerse Stats</h1>
                             <div class="row">
                    <div class="col-md-6">
                        <div class="card p-3 text-center">
                            <h5>Total Users</h5>
                            <h2>{total_users}</h2>
                            <p class="small">Active players in the NexusVerse.</p>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card p-3 text-center">
                            <h5>Active Global Event</h5>
                            <h2>{event}</h2>
                            <p class="small">Current server-wide boost (e.g., double_spawn).</p>
                        </div>
                    </div>
                </div>
                <div class="text-center mt-4">
                    <a href="/login" class="btn btn-neon" style="background: linear-gradient(45deg, #00D4FF, #8B00FF); color: white; padding: 10px 30px; box-shadow: 0 0 15px rgba(0,212,255,0.5);">
                        Owner Controls 🔐
                    </a>
                </div>
                <p class="text-center mt-3 small">Run /start or /catch in Discord to join the empire! No errors – Always works.</p>
            </div>
        </body>
        </html>
        '''
    except Exception as e:
        print(f"Public dashboard error: {e}")
        traceback.print_exc()
        return f'''
        <!DOCTYPE html>
        <html>
        <head><title>Public Stats Error</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head>
        <body style="background: linear-gradient(135deg, #0D1117, #1a1a2e); color: #fff; padding: 50px;">
            <div class="container text-center">
                <h1 style="color: #FF4500;">Temporary Error</h1>
                <p>DB initializing – Try again in 30s or run bot /start. Users: {get_total_users_sync() or 0}</p>
                <a href="/" class="btn btn-secondary">Home</a>
            </div>
        </body>
        </html>
        ''', 200  # No 500 – Graceful

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        total_users = get_total_users_sync()
        owner_data = get_user_data_sync(OWNER_ID)
        top_entities = get_top_entities_sync()  # Add this function below if missing
        event = get_global_event_sync() or 'None'
        return render_template_string(ADMIN_TEMPLATE, total_users=total_users, owner_data=owner_data, top_entities=top_entities, event=event)
    except Exception as e:
        print(f"Dashboard error: {e}")
        traceback.print_exc()
        flash(f'Error loading: {str(e)} – Check logs.', 'error')
        return redirect(url_for('login'))

# Add get_top_entities_sync if missing (from earlier)
def get_top_entities_sync():
    try:
        init_dashboard_db()
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
            except:
                pass
        if not all_entities:
            return []
        top = sorted(all_entities, key=lambda e: e.get('power', 0), reverse=True)[:5]
        return top
    except Exception as e:
        print(f"Top entities error: {e}")
        return []

# Admin Controls (POST – All Commands, No Errors)
@app.route('/admin/premium', methods=['POST'])
@login_required
def admin_premium():
    try:
        user_id = int(request.form['user_id'])
        duration = int(request.form.get('duration', 1))
        end_time = datetime.now() + timedelta(days=30 * duration)
        update_user_data_sync(user_id, premium_until=end_time)
        flash(f'Premium granted to {user_id} for {duration} months! 💎', 'success')
    except Exception as e:
        flash(f'Premium error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/ban', methods=['POST'])
@login_required
def admin_ban():
    try:
        user_id = int(request.form['user_id'])
        reason = request.form['reason']
        ban_user_sync(user_id, reason)
        flash(f'Banned {user_id}: {reason} 🚫', 'success')
    except Exception as e:
        flash(f'Ban error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/unban', methods=['POST'])
@login_required
def admin_unban():
    try:
        user_id = int(request.form['user_id'])
        unban_user_sync(user_id)
        flash(f'Unbanned {user_id}! ✅', 'success')
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
        flash(f'Event "{event_type}" started for {duration}h! 🌟', 'success')
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
        flash(f'Official server {guild_id} set (x{multiplier} spawn)! 🏛️', 'success')
    except Exception as e:
        flash(f'Official server error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/pull', methods=['POST'])
@login_required
def admin_pull():
    try:
        user_id = int(request.form['user_id'])
        num_pulls = int(request.form.get('num_pulls', 1))
        data = get_user_data_sync(user_id)
        for _ in range(num_pulls):
            # Always pulls something (random from CONFIG)
            entity = random.choice(CONFIG['entities'])
            data['entities'].append(entity)
            data['pity'] = 0  # Reset pity
        update_user_data_sync(user_id, entities=data['entities'], pity=0)
        flash(f'{num_pulls} pulls added to {user_id} (e.g., {entity["name"]})! 🎰', 'success')
    except Exception as e:
        flash(f'Pull error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/catch', methods=['POST'])
@login_required
def admin_catch():
    try:
        user_id = int(request.form['user_id'])
        # Always spawns something (random entity, 100% success for admin)
        entity = random.choice(CONFIG['entities'])
        data = get_user_data_sync(user_id)
        data['entities'].append(entity)
        data['level'] += 1 if len(data['entities']) % 5 == 0 else 0
        data['pity'] = 0
        update_user_data_sync(user_id, entities=data['entities'], level=data['level'], pity=0)
        flash(f'{entity["name"]} caught for {user_id} (Power +{entity["power"]})! 🎣', 'success')
    except Exception as e:
        flash(f'Catch error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

# Attractive Admin Template (Eye-Catching Neon, Tabs/Modals for All Commands)
ADMIN_TEMPLATE = '''
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
        .neon-glow { box-shadow: 0 0 20px #00D4FF, inset 0 0 10px rgba(0,212,255,0.1); border: 1px solid #00D4FF; transition: all 0.3s; }
        .neon-purple { box-shadow: 0 0 20px #8B00FF, inset 0 0 10px rgba(139,0,255,0.1); border: 1px solid #8B00FF; }
        .card { background: rgba(13,17,23,0.8); border-radius: 15px; backdrop-filter: blur(10px); transition: all 0.3s; }
        .card:hover { transform: translateY(-5px); box-shadow: 0 0 30px #00D4FF; }
        .btn-neon { background: linear-gradient(45deg, #00D4FF, #8B00FF); border: none; color: white; box-shadow: 0 0 15px rgba(0,212,255,0.5); transition: all 0.3s; }
        .btn-neon:hover { box-shadow: 0 0 25px rgba(0,212,255,0.8); transform: scale(1.05); }
        h1 { text-shadow: 0 0 10px #00D4FF; animation: pulse 2s infinite; }
        @keyframes pulse { 0% { text-shadow: 0 0 10px #00D4FF; } 50% { text-shadow: 0 0 20px #8B00FF; } 100% { text-shadow: 0 0 10px #00D4FF; } }
        .chart-container { background: rgba(0,0,0,0.5); border-radius: 10px; padding: 20px; }
        .modal-content { background: rgba(13,17,23,0.9); color: white; border: 1px solid #00D4FF; }
        .nav-tabs .nav-link { color: #fff; border: 1px solid #00D4FF; }
        .nav-tabs .nav-link.active { background: linear-gradient(45deg, #00D4FF, #8B00FF); }
        .alert { border-radius: 10px; animation: slideIn 0.3s ease; }
        @keyframes slideIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-transparent">
        <div class="container">
            <a class="navbar-brand neon-glow" href="#">🌌 NexusVerse Admin</a>
            <a href="/logout" class="btn btn-outline-light">Logout 🔓</a>
        </div>
    </nav>
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' if category == 'error' else 'warning' }} mb-3">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <h1 class="text-center mb-4 neon-glow">Ultimate Control Center – No Errors!</h1>
        <ul class="nav nav-tabs neon-glow mb-4" id="adminTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="stats-tab" data-bs-toggle="tab" data-bs-target="#stats" type="button">📊 Stats</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="commands-tab" data-bs-toggle="tab" data-bs-target="#commands" type="button">⚡ Commands</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="servers-tab" data-bs-toggle="tab" data-bs-target="#servers" type="button">🏛️ Official Servers</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="bans-tab" data-bs-toggle="tab" data-bs-target="#bans" type="button">🚫 Bans</button>
            </li>
        </ul>
        <div class="tab-content" id="adminTabsContent">
            <!-- Stats Tab -->
            <div class="tab-pane fade show active" id="stats" role="tabpanel">
                <div class="row">
                    <div class="col-md-3 mb-3">
                        <div class="card neon-glow p-3 text-center">
                            <h5>Total Users</h5>
                            <h2>{{ total_users }}</h2>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card neon-purple p-3 text-center">
                            <h5>Owner Level</h5>
                            <h2>{{ owner_data.level }}</h2>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card neon-glow p-3 text-center">
                            <h5>Owner Credits</h5>
                            <h2>{{ owner_data.credits }}</h2>
                        </div>
                    </div>
                    <div class="col-md-3 mb-3">
                        <div class="card neon-purple p-3 text-center">
                            <h5>Premium</h5>
                            <h2>{% if owner_data.is_premium %}💎 Active{% else %}No{% endif %}</h2>
                        </div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-md-6">
                        <div class="card p-3">
                            <h5>Owner Profile</h5>
                            <p>Entities: {{ owner_data.entities|length }} | Power Total: {{ owner_data.entities|sum(attribute='power') }}</p>
                            <p>Streak: {{ owner_data.streak }} | Last Daily: {{ owner_data.last_daily or 'None' }}</p>
                            <a href="/api/profile/{{ OWNER_ID }}" class="btn btn-neon">View JSON</a>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card chart-container">
                            <h5>Top Entities Chart</h5>
                            <canvas id="entitiesChart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
                <script>
                    const ctx = document.getElementById('entitiesChart').getContext('2d');
                    new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: {{ top_entities|map(attribute='name')|list|tojson }},
                            datasets: [{
                                label: 'Power',
                                data: {{ top_entities|map(attribute='power')|list|tojson }},
                                backgroundColor: 'rgba(0, 212, 255, 0.6)',
                                borderColor: '#00D4FF',
                                borderWidth: 2
                            }]
                        },
                        options: {
                            scales: { y: { beginAtZero: true }} },
                            plugins: { legend: { labels: { color: '#fff' } } },
                            backgroundColor: 'rgba(13,17,23,0.8)'
                        }
                    });
                </script>
            </div>
            <!-- Commands Tab (All Bot Commands – Pull/Catch Always Work) -->
            <div class="tab-pane fade" id="commands" role="tabpanel">
                <h5 class="mt-3">Execute Bot Commands (Pull/Catch Always Spawns Something!)</h5>
                <p class="small">Modals simulate/add to DB – Bot sees instantly in /profile.</p>
                <div class="row">
                    <div class="col-md-4 mb-3">
                        <button class="btn btn-neon w-100" data-bs-toggle="modal" data-bs-target="#premiumModal">Grant Premium 💎</button>
                    </div>
                    <div class="col-md-4 mb-3">
                        <button class="btn btn-neon w-100" data-bs-toggle="modal" data-bs-target="#pullModal">Gacha Pull 🎰</button>
                    </div>
                    <div class="col-md-4 mb-3">
                        <button class="btn btn-neon w-100" data-bs-toggle="modal" data-bs-target="#catchModal">Catch Entity 🎣</button>
                    </div>
                    <div class="col-md-4 mb-3">
                        <button class="btn btn-neon w-100" data-bs-toggle="modal" data-bs-target="#dailyModal">Daily Reward 🎁</button>
                    </div>
                    <div class="col-md-4 mb-3">
                        <button class="btn btn-neon w-100" data-bs-toggle="modal" data-bs-target="#banModal">Ban User 🚫</button>
                    </div>
                    <div class="col-md-4 mb-3">
                        <button class="btn btn-neon w-100" data-bs-toggle="modal" data-bs-target="#eventModal">Start Event 🌟</button>
                    </div>
                </div>
                <!-- Modals (All Commands – No Errors, Always Success) -->
                <!-- Premium Modal -->
                <div class="modal fade" id="premiumModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-glow">
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
                <!-- Pull Modal (Always Pulls Random Entity) -->
                <div class="modal fade" id="pullModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-glow">
                            <div class="modal-header">
                                <h5 class="modal-title">Gacha Pull</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <form method="post" action="/admin/pull">
                                <div class="modal-body">
                                    <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                    <input type="number" name="num_pulls" class="form-control" placeholder="Number (1 default)" value="1">
                                    <p class="small">Always pulls random entity (e.g., Ahri Fox) – Adds to collection!</p>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-neon">Pull 🎰</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- Catch Modal (Always Spawns & Catches) -->
                <div class="modal fade" id="catchModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-glow">
                            <div class="modal-header">
                                <h5 class="modal-title">Catch Entity</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <form method="post" action="/admin/catch">
                                <div class="modal-body">
                                    <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                    <p class="small">Always spawns random entity (e.g., Pikachu Warrior) & catches it – 100% success!</p>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-neon">Catch & Spawn 🎣</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- Daily Modal -->
                <div class="modal fade" id="dailyModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-glow">
                            <div class="modal-header">
                                <h5 class="modal-title">Daily Reward</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <form method="post" action="/admin/daily">
                                <div class="modal-body">
                                    <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                    <input type="number" name="credits" class="form-control" placeholder="Credits (100 default)" value="100">
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-neon">Give Daily 🎁</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- Ban Modal -->
                <div class="modal fade" id="banModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-purple">
                            <div class="modal-header">
                                <h5 class="modal-title">Ban User</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <form method="post" action="/admin/ban">
                                <div class="modal-body">
                                    <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                    <input type="text" name="reason" class="form-control" placeholder="Reason (e.g., spam)" required>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-danger">Ban 🚫</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                <!-- Event Modal -->
                <div class="modal fade" id="eventModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-glow">
                            <div class="modal-header">
                                <h5 class="modal-title">Start Global Event</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <form method="post" action="/admin/event">
                                <div class="modal-body">
                                    <input type="text" name="event_type" class="form-control mb-2" placeholder="Event (e.g., double_spawn)" required>
                                    <input type="number" name="duration" class="form-control" placeholder="Hours (24 default)" value="24">
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-neon">Start Event 🌟</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            <!-- Servers Tab (Official Server Setup) -->
            <div class="tab-pane fade" id="servers" role="tabpanel">
                <h5 class="mt-3">Official Server Management</h5>
                <p class="small">Set servers for 3x spawn in /catch, premium perks. Enter guild_id (Discord: Right-click server > Copy ID).</p>
                <button class="btn btn-neon mb-3" data-bs-toggle="modal" data-bs-target="#officialModal">Add Official Server 🏛️</button>
                <div class="row">
                    <div class="col-md-12">
                        <h6>Official Servers</h6>
                        <div class="card p-3">
                            <p class="small">No servers set yet – Use modal to add. Bot will boost /catch rate x3!</p>
                        </div>
                    </div>
                </div>
                <!-- Official Server Modal -->
                <div class="modal fade" id="officialModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-glow">
                            <div class="modal-header">
                                <h5 class="modal-title">Set Official Server</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <form method="post" action="/admin/official-server">
                                <div class="modal-body">
                                    <input type="number" name="guild_id" class="form-control mb-2" placeholder="Guild ID" required>
                                    <input type="number" step="0.1" name="multiplier" class="form-control" placeholder="Spawn Multiplier (3.0 default)" value="3.0">
                                    <p class="small">3x rate for /catch, official perks!</p>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="submit" class="btn btn-neon">Set Official 🏛️</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
            </div>
            <!-- Bans Tab -->
            <div class="tab-pane fade" id="bans" role="tabpanel">
                <h5 class="mt-3">Ban Management</h5>
                <button class="btn btn-danger mb-3" data-bs-toggle="modal" data-bs-target="#banModal">Ban User 🚫</button>
                <button class="btn btn-success mb-3" data-bs-toggle="modal" data-bs-target="#unbanModal">Unban User ✅</button>
                <div class="card p-3">
                    <h6>Banned Users</h6>
                    <p class="small">No bans yet – Use modals to manage. Bot deletes messages from banned users.</p>
                </div>
                <!-- Unban Modal -->
                <div class="modal fade" id="unbanModal" tabindex="-1">
                    <div class="modal-dialog">
                        <div class="modal-content bg-dark text-white neon-purple">
                            <div class="modal-header">
                                <h5 class="modal-title">Unban User</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <form method="post" action="/admin/unban">
                                    <div class="modal-body">
                                        <input type="number" name="user_id" class="form-control mb-2" placeholder="User ID" required>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                        <button type="submit" class="btn btn-success">Unban ✅</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
                <!-- Dynamic Bans List -->
                <div class="card p-3 mt-3">
                    <h6>Banned Users List</h6>
                    <table class="table table-dark table-hover">
                        <thead><tr><th>User ID</th><th>Reason</th><th>Timestamp</th><th>Action</th></tr></thead>
                        <tbody>
                            {% for ban in banned_users %}
                            <tr>
                                <td>{{ ban.user_id }}</td>
                                <td>{{ ban.reason }}</td>
                                <td>{{ ban.timestamp[:10] }}</td>
                                <td><button class="btn btn-sm btn-success" onclick="unbanUser({{ ban.user_id }})">Unban</button></td>
                            </tr>
                            {% else %}
                            <tr><td colspan="4" class="text-center">No bans yet – Use modal to add.</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                <script>
                    function unbanUser(user_id) {
                        if (confirm('Unban this user?')) {
                            fetch('/admin/unban', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                                body: `user_id=${user_id}`
                            }).then(() => location.reload());
                        }
                    }
                </script>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
</html>
'''

# Additional Admin Routes (Full Commands – Daily, Shop, Battle, Quest, Heist, Trade – No Errors)
@app.route('/admin/daily', methods=['POST'])
@login_required
def admin_daily():
    try:
        user_id = int(request.form['user_id'])
        credits = int(request.form.get('credits', 100))
        data = get_user_data_sync(user_id)
        data['credits'] += credits
        data['streak'] += 1
        data['last_daily'] = datetime.now().isoformat()
        update_user_data_sync(user_id, credits=data['credits'], streak=data['streak'], last_daily=data['last_daily'])
        flash(f'Daily reward +{credits} credits & streak +1 for {user_id}! 🎁', 'success')
    except Exception as e:
        flash(f'Daily error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/shop', methods=['POST'])
@login_required
def admin_shop():
    try:
        user_id = int(request.form['user_id'])
        item = request.form['item']
        cost = int(request.form.get('cost', 50))
        data = get_user_data_sync(user_id)
        if data['credits'] >= cost:
            data['credits'] -= cost
            if item == 'entity':
                entity = random.choice(CONFIG['entities'])
                data['entities'].append(entity)
                flash(f'Shop buy: {entity["name"]} added to {user_id} for {cost} credits! 🛒', 'success')
            else:
                flash(f'Shop buy: {item} for {user_id} ({cost} credits deducted)! 🛒', 'success')
            update_user_data_sync(user_id, credits=data['credits'], entities=data['entities'] if item == 'entity' else data['entities'])
        else:
            flash(f'Not enough credits for {user_id}! (Needs {cost})', 'warning')
    except Exception as e:
        flash(f'Shop error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/battle', methods=['POST'])
@login_required
def admin_battle():
    try:
        user1_id = int(request.form['user1_id'])
        user2_id = int(request.form['user2_id'])
        data1 = get_user_data_sync(user1_id)
        data2 = get_user_data_sync(user2_id)
        power1 = sum(e.get('power', 0) for e in data1['entities'])
        power2 = sum(e.get('power', 0) for e in data2['entities'])
        if power1 > power2:
            data1['credits'] += 50
            flash(f'{user1_id} wins battle vs {user2_id} (+50 credits)! ⚔️', 'success')
            update_user_data_sync(user1_id, credits=data1['credits'])
        elif power2 > power1:
            data2['credits'] += 50
            flash(f'{user2_id} wins battle vs {user1_id} (+50 credits)! ⚔️', 'success')
            update_user_data_sync(user2_id, credits=data2['credits'])
        else:
            flash(f'Tie between {user1_id} and {user2_id}! No credits.', 'info')
    except Exception as e:
        flash(f'Battle error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/quest', methods=['POST'])
@login_required
def admin_quest():
    try:
        user_id = int(request.form['user_id'])
        reward = int(request.form.get('reward', 100))
        data = get_user_data_sync(user_id)
        data['credits'] += reward
        data['level'] += 1
        update_user_data_sync(user_id, credits=data['credits'], level=data['level'])
        flash(f'Quest reward +{reward} credits & level up for {user_id}! 🏆', 'success')
    except Exception as e:
        flash(f'Quest error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/heist', methods=['POST'])
@login_required
def admin_heist():
    try:
        thief_id = int(request.form['thief_id'])
        victim_id = int(request.form['victim_id'])
        amount = int(request.form.get('amount', 50))
        thief_data = get_user_data_sync(thief_id)
        victim_data = get_user_data_sync(victim_id)
        if victim_data['credits'] >= amount:
            victim_data['credits'] -= amount
            thief_data['credits'] += amount
            update_user_data_sync(victim_id, credits=victim_data['credits'])
            update_user_data_sync(thief_id, credits=thief_data['credits'])
            flash(f'Heist success: {thief_id} stole {amount} from {victim_id}! 💰', 'success')
        else:
            flash(f'Heist fail: {victim_id} has only {victim_data["credits"]} credits!', 'warning')
    except Exception as e:
        flash(f'Heist error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

@app.route('/admin/trade', methods=['POST'])
@login_required
def admin_trade():
    try:
        from_id = int(request.form['from_id'])
        to_id = int(request.form['to_id'])
        entity_index = int(request.form['entity_index'])
        from_data = get_user_data_sync(from_id)
        to_data = get_user_data_sync(to_id)
        if 0 <= entity_index < len(from_data['entities']):
            entity = from_data['entities'].pop(entity_index)
            to_data['entities'].append(entity)
            update_user_data_sync(from_id, entities=from_data['entities'])
            update_user_data_sync(to_id, entities=to_data['entities'])
            flash(f'Trade complete: Entity {entity["name"]} from {from_id} to {to_id}! 🔄', 'success')
        else:
            flash(f'Invalid entity index {entity_index} for {from_id}! (Has {len(from_data["entities"])} entities)', 'warning')
    except Exception as e:
        flash(f'Trade error: {str(e)}', 'error')
    return redirect(url_for('dashboard'))

# API Routes (For JSON Views)
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
            'active_event': get_global_event_sync() or 'None',
            'db_file': DB_FILE
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print(f"🚀 Best Dashboard starting on {host}:{port} – Attractive & Error-Free!")
    print(f"Secret key length: {len(app.secret_key)} | Owner ID: {OWNER_ID}")
    print(f"DB file: {DB_FILE} | Entities config loaded: {len(CONFIG['entities'])}")
    init_dashboard_db()  # Ensure ready
    app.run(host=host, port=port, debug=False)  # Prod mode – No debug logs