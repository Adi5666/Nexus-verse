from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import aiosqlite
import json
import os
from datetime import datetime, timedelta
import requests  # For webhook sends
import asyncio
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv('DASHBOARD_SECRET', 'change_me')  # Env var for security
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Load shared config/DB
CONFIG_FILE = 'config.json'
try:
    with open(CONFIG_FILE, 'r') as f:
        CONFIG = json.load(f)
except:
    CONFIG = {'dashboard_secret': 'change_me', 'entities': []}  # Fallback
DB_FILE = 'nexusverse.db'
DASHBOARD_WEBHOOK_URL = os.getenv('DASHBOARD_WEBHOOK_URL', '')

class AdminUser(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return AdminUser(user_id) if user_id == 'admin' else None

def require_secret(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == CONFIG['dashboard_secret']:  # Simple secret check
            session['logged_in'] = True
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
        flash('Invalid secret!')
    return render_template('login.html')  # Create templates/login.html below

@app.route('/logout')
@login_required
def logout():
    session.pop('logged_in', None)
    flash('Logged out!')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')  # Main UI

@app.route('/grant_premium', methods=['POST'])
@login_required
def grant_premium_web():
    user_id = int(request.form['user_id'])
    duration = int(request.form.get('duration', 1))
    end_time = datetime.now() + timedelta(days=30 * duration)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update_user_data_web(user_id, premium_until=end_time))  # Shared helper
    loop.close()
    # Send webhook notification
    if DASHBOARD_WEBHOOK_URL:
        requests.post(DASHBOARD_WEBHOOK_URL, json={'content': f'💎 Premium granted to user {user_id} for {duration} months via dashboard!'})
    flash(f'Premium granted to {user_id}!')
    return redirect(url_for('dashboard'))

@app.route('/start_event', methods=['POST'])
@login_required
def start_event_web():
    event_type = request.form['event_type']
    duration = int(request.form.get('duration', 24))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_global_event_web(event_type, duration))
    loop.close()
    if DASHBOARD_WEBHOOK_URL:
        requests.post(DASHBOARD_WEBHOOK_URL, json={'content': f'🌌 Global event "{event_type}" started for {duration}h via dashboard!'})
    flash(f'Event "{event_type}" started!')
    return redirect(url_for('dashboard'))

@app.route('/view_audits')
@login_required
def view_audits():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    audits = loop.run_until_complete(get_audits_web())
    loop.close()
    return render_template('audits.html', audits=audits)

# Shared DB Helpers (Non-Async for Flask; use sync sqlite3 if needed, but aiosqlite with loop)
async def update_user_data_web(user_id: int, **kwargs):
    # Reuse from bot (copy get_user_data logic, but sync for simplicity)
    import sqlite3
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # Similar to update_user_data, but sync
    set_parts = ', '.join([f"{k}=?" for k in kwargs])
    values = list(kwargs.values()) + [user_id]
    if 'premium_until' in kwargs:
        values[values.index(kwargs['premium_until'])] = kwargs['premium_until'].isoformat()
    cur.execute(f'UPDATE users SET {set_parts} WHERE user_id=?', values)
    conn.commit()
    conn.close()

async def start_global_event_web(event_type: str, duration_hours: int = 24):
    import sqlite3
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    end_time = datetime.now() + timedelta(hours=duration_hours)
    cur.execute('DELETE FROM global_events')
    cur.execute('INSERT INTO global_events (event_type, start_time, end_time) VALUES (?, ?, ?)',
                (event_type, datetime.now().isoformat(), end_time.isoformat()))
    conn.commit()
    conn.close()

async def get_audits_web():
    import sqlite3
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute('SELECT * FROM audits ORDER BY timestamp DESC LIMIT 50')
    rows = cur.fetchall()
    conn.close()
    return [{'id': r[0], 'action': r[1], 'issuer': r[2], 'target': r[3], 'guild': r[4], 'timestamp': r[5]} for r in rows]

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)