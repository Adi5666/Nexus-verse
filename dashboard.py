from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import json
import os
from datetime import datetime, timedelta
import requests

app = Flask(__name__)
app.secret_key = os.getenv('DASHBOARD_SECRET', 'change_me')  # Strong secret in env!
CONFIG_FILE = 'config.json'
try:
    with open(CONFIG_FILE, 'r') as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    CONFIG = {'dashboard_secret': 'change_me', 'entities': []}
DB_FILE = 'nexusverse.db'
DASHBOARD_WEBHOOK_URL = os.getenv('DASHBOARD_WEBHOOK_URL', '')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Dict-like rows
    return conn

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == CONFIG['dashboard_secret']:
            session['logged_in'] = True
            flash('Access Granted! Welcome to the Nexus Control Center. 🌌')
            return redirect(url_for('dashboard'))
        flash('Access Denied – Invalid Secret. Try Again.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Logged Out Securely. The Nexus Awaits Your Return.')
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
def dashboard():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Stats
    cur.execute('SELECT COUNT(*) FROM users')
    user_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    premium_count = cur.fetchone()[0]
    cur.execute('SELECT event_type FROM global_events WHERE end_time > ? LIMIT 1', (datetime.now().isoformat(),))
    row = cur.fetchone()
    active_event = row[0] if row else "None"
    
    # Top 5 Users (for chart data)
    cur.execute('SELECT user_id, level, credits FROM users ORDER BY level DESC LIMIT 5')
    top_users = cur.fetchall()
    
    # Premium Today (simple count of recent grants – expand with timestamp if audits have it)
    premium_today = premium_count  # Placeholder; add query for today if DB updated
    
    conn.close()
    
    # Chart Data (JSON for Chart.js)
    chart_data = {
        'labels': [row['user_id'] for row in top_users],
        'levels': [row['level'] for row in top_users],
        'credits': [row['credits'] for row in top_users]
    }
    
    return render_template('dashboard.html', 
                          user_count=user_count, 
                          premium_count=premium_count, 
                          active_event=active_event, 
                          premium_today=premium_today,
                          chart_data=json.dumps(chart_data))

@app.route('/grant_premium', methods=['POST'])
def grant_premium_web():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    user_id = int(request.form['user_id'])
    duration = int(request.form.get('duration', 1))
    end_time = datetime.now() + timedelta(days=30 * duration)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_premium = 1, premium_until = ? WHERE user_id = ?', (end_time.isoformat(), user_id))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected > 0:
        flash(f'Premium Granted! User {user_id} now has {duration} months of elite access. 💎')
        if DASHBOARD_WEBHOOK_URL:
            requests.post(DASHBOARD_WEBHOOK_URL, json={'content': f'💎 Dashboard: Premium granted to {user_id} for {duration} months! Glow activated.'})
    else:
        flash('User  Not Found – Check ID and Try Again.')
    return redirect(url_for('dashboard'))

@app.route('/start_event', methods=['POST'])
def start_event_web():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    event_type = request.form['event_type']
    duration = int(request.form.get('duration', 24))
    end_time = datetime.now() + timedelta(hours=duration)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM global_events')
    cur.execute('INSERT INTO global_events (event_type, start_time, end_time) VALUES (?, ?, ?)',
                (event_type, datetime.now().isoformat(), end_time.isoformat()))
    conn.commit()
    conn.close()
    flash(f'Event Launched! "{event_type}" active for {duration} hours. Nexus buzzing! 🌌')
    if DASHBOARD_WEBHOOK_URL:
        requests.post(DASHBOARD_WEBHOOK_URL, json={'content': f'🌌 Dashboard: Global event "{event_type}" started for {duration}h! All servers notified.'})
    return redirect(url_for('dashboard'))

@app.route('/ban_user', methods=['POST'])
def ban_user_web():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    user_id = int(request.form['user_id'])
    reason = request.form.get('reason', 'Dashboard Ban')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO bans (user_id, reason, issuer, timestamp, guild_id) VALUES (?, ?, ?, ?, ?)',
                (user_id, reason, 'Dashboard Admin', datetime.now().isoformat(), None))  # Global ban
    conn.commit()
    conn.close()
    flash(f'User {user_id} Banned Globally! Reason: {reason}. Enforcement active.')
    if DASHBOARD_WEBHOOK_URL:
        requests.post(DASHBOARD_WEBHOOK_URL, json={'content': f'🔒 Dashboard: User {user_id} banned for "{reason}".'})
    return redirect(url_for('dashboard'))

@app.route('/unban_user', methods=['POST'])
def unban_user_web():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    user_id = int(request.form['user_id'])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    if affected > 0:
        flash(f'User {user_id} Unbanned! Mercy granted.')
        if DASHBOARD_WEBHOOK_URL:
            requests.post(DASHBOARD_WEBHOOK_URL, json={'content': f'🔓 Dashboard: User {user_id} unbanned.'})
    else:
        flash('User  Not Banned – No Action Taken.')
    return redirect(url_for('dashboard'))

@app.route('/view_audits')
def view_audits():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM audits ORDER BY timestamp DESC LIMIT 50')
    audits = [dict(row) for row in cur.fetchall()]  # Convert to dict for template
    conn.close()
    return render_template('audits.html', audits=audits)

@app.route('/export_audits')
def export_audits():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM audits ORDER BY timestamp DESC')
    audits = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(audits)  # JSON download via JS in template

@app.route('/top_users')
def top_users():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT user_id, level, credits, is_premium FROM users ORDER BY level DESC LIMIT 10')
    users = [dict(row) for row in cur.fetchall()]
    conn.close()
    return render_template('top_users.html', users=users)  # Add this template if wanted

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)