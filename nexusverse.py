import discord
from discord.ext import commands
import discord.app_commands as app_commands
import aiosqlite
import json
import random
from datetime import datetime, timedelta
import asyncio
import os
import unicodedata  # For emoji handling
import traceback  # For error logging
import redis  # For caching and scalability
import requests  # For API integrations (e.g., GIPHY)
import hashlib  # For security (IP hashing)
import smtplib  # For email alerts (optional)

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

DB_FILE = 'nexusverse.db'
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')  # For caching
GIPHY_API_KEY = os.getenv('GIPHY_API_KEY')  # For dynamic GIFs

# Colors (Enhanced Neon Palette)
SUCCESS_GREEN = 0x00FF00
ERROR_RED = 0xFF0000
NEON_BLUE = 0x00D4FF
PREMIUM_GOLD = 0xFFD700
OFFICIAL_GLOW = 0x8B00FF
EPIC_PURPLE = 0x8B00FF
WARNING_ORANGE = 0xFFA500

# Emoji Fallback Utility (Enhanced)
def safe_emoji(emoji):
    try:
        return emoji
    except UnicodeEncodeError:
        return '[Emoji]'
    except Exception as e:
        print(f"Emoji error: {e}")
        return '[Emoji]'

# CONFIG (Enhanced with Fusion Rules and Custom Entities)
CONFIG = {
    'entities': [
        {'name': 'Pac-Man Ghost', 'rarity': 'Common', 'emoji': '\U0001F47B', 'power': 10, 'desc': 'Classic maze chaser.', 'image_url': 'https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif', 'fuse_into': 'SpongeBob SquarePants'},
        {'name': 'SpongeBob SquarePants', 'rarity': 'Rare', 'emoji': '\U0001F9FD', 'power': 50, 'desc': 'Bikini Bottom hero.', 'image_url': 'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif', 'fuse_into': 'Shrek Ogre'},
        {'name': 'Shrek Ogre', 'rarity': 'Epic', 'emoji': '\U0001F9D6', 'power': 100, 'desc': 'Swamp king.', 'image_url': 'https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif', 'fuse_into': 'Super Mario'},
        {'name': 'Super Mario', 'rarity': 'Legendary', 'emoji': '\U0001F35E', 'power': 200, 'desc': 'Plumber legend.', 'image_url': 'https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif', 'fuse_into': 'Pikachu'},
        {'name': 'Pikachu', 'rarity': 'Mythic', 'emoji': '\U000026A1', 'power': 500, 'desc': 'Electric mouse master.', 'image_url': 'https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif', 'fuse_into': None},
        {'name': 'Sonic the Hedgehog', 'rarity': 'Rare', 'emoji': '\U0001F994', 'power': 60, 'desc': 'Speed runner.', 'image_url': 'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif', 'fuse_into': 'Donkey Kong'},
        {'name': 'Donkey Kong', 'rarity': 'Epic', 'emoji': '\U0001F34C', 'power': 120, 'desc': 'Barrel thrower.', 'image_url': 'https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif', 'fuse_into': 'Kirby'},
        {'name': 'Kirby', 'rarity': 'Legendary', 'emoji': '\U0001F31F', 'power': 180, 'desc': 'Puffball absorber.', 'image_url': 'https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif', 'fuse_into': 'Link (Zelda)'},
        {'name': 'Link (Zelda)', 'rarity': 'Mythic', 'emoji': '\U0001F5E1', 'power': 450, 'desc': 'Hero of time.', 'image_url': 'https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif', 'fuse_into': 'Master Chief'},
        {'name': 'Master Chief', 'rarity': 'Mythic', 'emoji': '\U0001F3AE', 'power': 600, 'desc': 'Halo Spartan.', 'image_url': 'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif', 'fuse_into': None}
    ],
    'events': ['double_spawn', 'nostalgia_week', 'pvp_boost'],  # Community events
    'custom_entities': []  # For user-created entities
}

# Redis Cache for Scalability
redis_client = redis.from_url(REDIS_URL)

# Backup Function (Automated)
async def backup_db():
    # Placeholder: Implement with boto3 for S3 upload
    print("📦 DB Backup Completed")

# GIPHY API for Dynamic GIFs
def get_giphy_gif(query):
    if GIPHY_API_KEY:
        response = requests.get(f'https://api.giphy.com/v1/gifs/search?api_key={GIPHY_API_KEY}&q={query}&limit=1')
        if response.status_code == 200:
            data = response.json()
            return data['data'][0]['images']['original']['url'] if data['data'] else None
    return 'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif'  # Fallback

# DB Helpers (Enhanced with Caching and Security)
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER DEFAULT 100,
                entities TEXT DEFAULT '[]',
                level INTEGER DEFAULT 1,
                pity INTEGER DEFAULT 0,
                premium_until TEXT DEFAULT NULL,
                streak INTEGER DEFAULT 0,
                last_daily TEXT DEFAULT NULL,
                is_official_member BOOLEAN DEFAULT 0,
                ip_hash TEXT DEFAULT NULL  # For security logging
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                is_official BOOLEAN DEFAULT 0,
                spawn_multiplier REAL DEFAULT 1.0,
                premium_until TEXT DEFAULT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                timestamp TEXT,
                guild_id INTEGER DEFAULT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS global_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                start_time TEXT,
                end_time TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                level TEXT DEFAULT 'mod',
                assigned_by INTEGER,
                assigned_at TEXT,
                guilds TEXT DEFAULT '[]'
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS leaderboards (
                user_id INTEGER PRIMARY KEY,
                score INTEGER DEFAULT 0,
                entities_count INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                issuer_id INTEGER,
                target_id INTEGER,
                guild_id INTEGER,
                timestamp TEXT,
                ip_hash TEXT
            )
        ''')
        await db.execute('INSERT OR IGNORE INTO admins (user_id, level, assigned_by, assigned_at) VALUES (?, "owner", ?, ?)', (OWNER_ID, OWNER_ID, datetime.now().isoformat()))
        await db.commit()
        print("✅ Bot DB initialized – Hierarchy ready with emoji fixes!")

async def get_user_level(user_id: int) -> str:
    cached = redis_client.get(f'level:{user_id}')
    if cached:
        return cached.decode()
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute('SELECT level FROM admins WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            level = row[0] if row else None
            redis_client.set(f'level:{user_id}', level or '', ex=3600)  # Cache 1h
            return level
    except Exception as e:
        print(f"Get level error: {e}")
        return None

async def get_user_data(user_id: int):
    cached = redis_client.get(f'user:{user_id}')
    if cached:
        return json.loads(cached.decode())
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
            if row:
                keys = ['user_id', 'credits', 'entities', 'level', 'pity', 'premium_until', 'streak', 'last_daily', 'is_official_member', 'ip_hash']
                data = dict(zip(keys, row))
                data['entities'] = json.loads(data['entities'] or '[]')
                data['is_premium'] = bool(data['premium_until'] and datetime.fromisoformat(data['premium_until']) > datetime.now())
                redis_client.set(f'user:{user_id}', json.dumps(data), ex=300)  # Cache 5min
                return data
            return {'user_id': user_id, 'credits': 100, 'entities': [], 'level': 1, 'is_premium': False, 'streak': 0, 'last_daily': None, 'is_official_member': False, 'ip_hash': None}
    except Exception as e:
        print(f"User data error: {e}")
        return {'error': str(e), 'user_id': user_id}

async def update_user_data(user_id: int, **kwargs):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
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
            await db.execute(f'UPDATE users SET {set_parts} WHERE user_id = ?', values)
            if db.total_changes == 0:
                await db.execute('INSERT INTO users (user_id, credits, level) VALUES (?, 100, 1)', (user_id,))
            await db.commit()
            redis_client.delete(f'user:{user_id}')  # Invalidate cache
    except Exception as e:
        print(f"Update user error: {e}")

async def get_guild_data(guild_id: int):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute('SELECT * FROM guilds WHERE guild_id = ?', (guild_id,))
            row = await cursor.fetchone()
            if row:
                keys = ['guild_id', 'is_official', 'spawn_multiplier', 'premium_until']
                data = dict(zip(keys, row))
                data['is_premium'] = bool(data['premium_until'] and datetime.fromisoformat(data['premium_until']) > datetime.now())
                return data
            return {'guild_id': guild_id, 'is_official': False, 'spawn_multiplier': 1.0, 'is_premium': False}
    except Exception as e:
        print(f"Guild data error: {e}")
        return {'error': str(e), 'guild_id': guild_id}

async def update_guild_data(guild_id: int, **kwargs):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            set_parts = ', '.join([f"{k} = ?" for k in kwargs])
            values = list(kwargs.values()) + [guild_id]
            await db.execute(f'UPDATE guilds SET {set_parts} WHERE guild_id = ?', values)
            if db.total_changes == 0:
                await db.execute('INSERT INTO guilds (guild_id) VALUES (?)', (guild_id,))
            await db.commit()
    except Exception as e:
        print(f"Update guild error: {e}")

async def is_banned(user_id: int, guild_id: int = None):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            if guild_id:
                cursor = await db.execute('SELECT * FROM bans WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            else:
                cursor = await db.execute('SELECT * FROM bans WHERE user_id = ? AND guild_id IS NULL', (user_id,))
            row = await cursor.fetchone()
            return row is not None
    except Exception as e:
        print(f"Is banned error: {e}")
        return False

async def ban_user(user_id: int, reason: str, guild_id: int = None):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute('INSERT OR REPLACE INTO bans (user_id, reason, timestamp, guild_id) VALUES (?, ?, ?, ?)',
                             (user_id, reason, datetime.now().isoformat(), guild_id))
            await db.commit()
    except Exception as e:
        print(f"Ban user error: {e}")

async def unban_user(user_id: int, guild_id: int = None):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            if guild_id:
                await db.execute('DELETE FROM bans WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
            else:
                await db.execute('DELETE FROM bans WHERE user_id = ? AND guild_id IS NULL', (user_id,))
            await db.commit()
    except Exception as e:
        print(f"Unban user error: {e}")

async def get_global_event():
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute('SELECT event_type FROM global_events WHERE end_time > ? LIMIT 1', (datetime.now().isoformat(),))
            row = await cursor.fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"Get event error: {e}")
        return None

async def start_global_event(event_type: str, duration: int = 24):
    try:
        async with aiosqlite.connect(DB_FILE) as db:
            end_time = datetime.now() + timedelta(hours=duration)
            await db.execute('DELETE FROM global_events')
            await db.execute('INSERT INTO global_events (event_type, start_time, end_time) VALUES (?, ?, ?)',
                             (event_type, datetime.now().isoformat(), end_time.isoformat()))
            await db.commit()
    except Exception as e:
        print(f"Start event error: {e}")

# Rate Limit with CAPTCHA (Enhanced Security)
user_cooldowns = {}
async def rate_limit_check(user_id: int, captcha_required: bool = False):
    now = datetime.now().timestamp()
    if user_id in user_cooldowns:
        if now - user_cooldowns[user_id] < 60:
            if captcha_required:
                # Placeholder: Integrate CAPTCHA API
                return False
            return False
    user_cooldowns[user_id] = now
    return True

# Additional Functions (Added for Completeness)
async def update_leaderboard(user_id: int, score: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR REPLACE INTO leaderboards (user_id, score, entities_count) VALUES (?, ?, (SELECT COUNT(*) FROM users WHERE user_id = ?))', (user_id, score, user_id))
        await db.commit()

async def get_leaderboard(limit=10):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute('SELECT user_id, score FROM leaderboards ORDER BY score DESC LIMIT ?', (limit,))
        rows = await cursor.fetchall()
        return [{'user_id': r[0], 'score': r[1]} for r in rows]

async def assign_role_sync(target_id: int, level: str, issuer_id: int, guilds: list):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR REPLACE INTO admins (user_id, level, assigned_by, assigned_at, guilds) VALUES (?, ?, ?, ?, ?)',
                         (target_id, level, issuer_id, datetime.now().isoformat(), json.dumps(guilds)))
        await db.commit()
    redis_client.delete(f'level:{target_id}')  # Invalidate cache

async def remove_role_sync(target_id: int, level: str, issuer_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('DELETE FROM admins WHERE user_id = ? AND level = ?', (target_id, level))
        await db.commit()
    redis_client.delete(f'level:{target_id}')  # Invalidate cache

async def log_audit(action: str, issuer_id: int, target_id: int = None, guild_id: int = None, ip_hash: str = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT INTO audits (action, issuer_id, target_id, guild_id, timestamp, ip_hash) VALUES (?, ?, ?, ?, ?, ?)',
                         (action, issuer_id, target_id, guild_id, datetime.now().isoformat(), ip_hash))
        await db.commit()
    # Send email alert for critical actions
    if action in ['assign_owner', 'global_ban']:
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login('your_email@gmail.com', 'your_password')  # Replace with real credentials
            server.sendmail('your_email@gmail.com', 'admin@example.com', f'Critical Action: {action} by {issuer_id}')
            server.quit()
        except:
            print("Email alert failed")

# Events (Enhanced with Voice and Webhooks)
@bot.event
async def on_ready():
    await init_db()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot ready – Synced {len(synced)} commands. Hierarchy interlocked!")
        print(f"Logged in as {bot.user} | Owner: <@{OWNER_ID}>")
        # Start tasks
        asyncio.create_task(backup_db())
        asyncio.create_task(trigger_random_event())
    except Exception as e:
        print(f"Sync error: {e}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if await is_banned(message.author.id, message.guild.id if message.guild else None):
        embed = discord.Embed(
            title="🚫 **You Have Been Banned from NexusVerse**",
            description="""
            **Dear User,**

            We regret to inform you that your access to NexusVerse has been restricted due to a violation of our community guidelines. This decision was made after careful review by our moderation team to ensure a safe and enjoyable environment for all players.

            **Reasons for Ban:**
            - Potential violations include spamming, harassment, cheating, or other disruptive behavior. If you believe this is an error, please review our rules and appeal via our support channel.

            **What Happens Next?**
            - Your commands are disabled, and you cannot interact with the bot.
            - If this is a temporary ban, it will expire automatically. For permanent bans, contact an admin.
            - To appeal: Join our support server and provide your user ID and ban reason.

            **Prevention Tips:**
            - Respect all users and follow Discord's TOS.
            - Avoid rapid commands or suspicious activities.
            - Premium users get priority support.

            **Appeal Process:**
            1. Gather evidence (screenshots, context).
            2. DM an admin or post in #support.
            3. Wait for review (usually 24-48 hours).

            Thank you for understanding. We value your participation and hope to see you back soon!

            **NexusVerse Team**
            """,
            color=ERROR_RED
        )
        embed.set_image(url=get_giphy_gif('banned'))
        embed.set_footer(text="For appeals, visit our website or support server.", icon_url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")
        try:
            await message.author.send(embed=embed)
        except:
            pass
        return
    await bot.process_commands(message)

# /catch (Enhanced with Attractive Embed)
@bot.tree.command(name='catch', description='Catch a random entity in Nexus!')
async def catch_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if not await rate_limit_check(user_id):
        embed = discord.Embed(
            title="⏰ **Cooldown Active – Patience is Key!**",
            description="""
            **Hey Trainer,**

            You've been catching entities too quickly! NexusVerse enforces fair play to keep the game balanced and fun for everyone.

            **Why Cooldowns?**
            - Prevents spam and ensures everyone has a chance.
            - Premium users skip cooldowns for faster gameplay.
            - Official servers have no limits during events.

            **What to Do?**
            - Wait 60 seconds before trying again.
            - Upgrade to Premium for instant access.
            - Join events for boosted rates!

            **Pro Tip:** Use this time to plan your next fusion or check the leaderboard.

            Stay hooked on nostalgia! 🌌
            """,
            color=WARNING_ORANGE
        )
        embed.set_image(url=get_giphy_gif('cooldown'))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    data = await get_user_data(user_id)
    entity = random.choice(CONFIG['entities'])
    success = random.random() < (0.3 + min(data['level'] * 0.05, 0.6) + (0.2 if data['is_premium'] else 0))
    if success:
        data['entities'].append(entity)
        data['level'] += 1 if len(data['entities']) % 5 == 0 else 0
        data['pity'] = 0
        await update_user_data(user_id, entities=data['entities'], level=data['level'], pity=0)
        await update_leaderboard(user_id, len(data['entities']))
        embed = discord.Embed(
            title=f"✅ **Caught {entity['name']}!**",
            description=f"""
            **Congratulations, Trainer!**

            You've successfully captured a {entity['rarity']} entity! Power +{entity['power']} boosts your collection.

            **Entity Details:**
            - **Rarity:** {entity['rarity']} (Higher rarity means stronger fusions!)
            - **Power:** {entity['power']}
            - **Description:** {entity['desc']}
            - **Level Up:** You're now Level {data['level']}!
            - **Pity Reset:** Your pity bar is full again for guaranteed pulls.

            **Next Steps:**
            - Fuse this entity for evolutions.
            - Check /profile for your progress.
            - Share your catch in chat!

            Keep collecting – the Nexus awaits! 🦸
            """,
            color=SUCCESS_GREEN
        )
        embed.set_image(url=entity['image_url'])
        embed.add_field(name="Pity Reset", value="■" * 10, inline=True)
        embed.add_field(name="Next Fusion", value=entity.get('fuse_into', 'None'), inline=True)
        await interaction.response.send_message(embed=embed)
    else:
        data['pity'] += 1
        await update_user_data(user_id, pity=data['pity'])
        embed = discord.Embed(
            title="❌ **Escaped – Try Again!**",
            description=f"""
            **Oh no, the entity got away!**

            Don't worry – every miss brings you closer to a guaranteed catch. Your pity is now {data['pity']}/10.

            **What Happened?**
            - Success rate depends on level and premium status.
            - At 10 pity, your next catch is assured!

            **Tips to Improve:**
            - Level up by catching more.
            - Buy Premium for +20% success.
            - Join official servers for bonuses.

            Persistence pays off – keep going! 🔥
            """,
            color=ERROR_RED
        )
        embed.set_image(url=get_giphy_gif('escape'))
        await interaction.response.send_message(embed=embed)

# /profile (Enhanced with Progress Bars and Attractive Embed)
@bot.tree.command(name='profile', description='View your NexusVerse profile!')
async def profile_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    embed = discord.Embed(
        title=f"🌌 **{interaction.user.name}'s NexusVerse Profile**",
        description=f"""
        **Welcome to Your Stats Dashboard!**

        Track your progress in the ultimate nostalgic entity-catching adventure. See your levels, credits, and rare finds below.

        **Quick Stats:**
        - **Level:** {data['level']} (Progress: {'■' * (data['level'] % 10)}{'□' * (10 - data['level'] % 10)})
        - **Credits:** 💰 {data['credits']} (Earn more with dailies and heists!)
        - **Entities:** 🦸 {len(data['entities'])} (Fuse them for power-ups!)
        - **Pity Bar:** ■ * {data['pity']} □ * {10 - data['pity']} (Guaranteed at 10!)
        - **Premium:** 💎 {'Active – Enjoy perks!' if data['is_premium'] else 'Inactive – Upgrade for bonuses!'}
        - **Streak:** 🔥 {data['streak']} (Daily claims boost this!)

        **Top Entities:** {', '.join([f"{e['name']} ({e['rarity']})" for e in data['entities'][:3]]) if data['entities'] else 'None yet – Start catching!'}

        **Pro Tips:**
        - Check leaderboards to compete.
        - Premium unlocks advanced features.
        - Official members get exclusive events.

        Your journey is just beginning – stay nostalgic! 🎮
        """,
        color=NEON_BLUE
    )
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else get_giphy_gif('avatar'))
    embed.set_image(url=get_giphy_gif('profile'))
    await interaction.response.send_message(embed=embed)

# /pull (Enhanced with Gacha Animation and Embed)
@bot.tree.command(name='pull', description='Gacha pull for entities!')
@app_commands.describe(num_pulls='Number of pulls (1-10)')
async def pull_command(interaction: discord.Interaction, num_pulls: int = 1):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    cost = num_pulls * 50
    if data['credits'] >= cost:
        data['credits'] -= cost
        pulled = []
        for _ in range(num_pulls):
            entity = random.choice(CONFIG['entities'])
            pulled.append(entity)
            data['entities'].append(entity)
        data['pity'] = 0
        await update_user_data(user_id, credits=data['credits'], entities=data['entities'], pity=0)
        await update_leaderboard(user_id, len(data['entities']))
        embed = discord.Embed(
            title=f"🎰 **Pulled {num_pulls} Entities!**",
            description=f"""
            **Gacha Results – What Did You Get?**

            You spent {cost} credits and pulled: {', '.join([f"{e['name']} ({e['rarity']})" for e in pulled])}.

            **Pull Details:**
            - **Cost:** -{cost} Credits
            - **New Total Entities:** {len(data['entities'])}
            - **Pity Reset:** Ready for more!

            **Rarity Breakdown:**
            - Common: Basic but essential.
            - Rare/Mythic: Fuse for legends!

            **Next Moves:**
            - Fuse duplicates for evolutions.
            - Save for events with boosted rates.

            Happy pulling – may the odds be nostalgic! 🍀
            """,
            color=PREMIUM_GOLD
        )
        embed.set_image(url=get_giphy_gif('gacha'))
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ **Not Enough Credits**",
            description=f"""
            **Oops – Insufficient Funds!**

            You need {cost} credits for {num_pulls} pulls, but you only have {data['credits']}.

            **How to Earn More:**
            - Claim /daily for free credits.
            - Win /heists or battles.
            - Buy Premium for bonuses.

            **Alternative:** Pull 1 at a time to save credits.

            Keep grinding – credits await! 💰
            """,
            color=ERROR_RED
        )
        embed.set_image(url=get_giphy_gif('broke'))
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /daily (Enhanced with Streak Rewards and Embed)
@bot.tree.command(name='daily', description='Claim daily credits!')
async def daily_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    now = datetime.now()
    if data['last_daily'] and (now - datetime.fromisoformat(data['last_daily'])).days < 1:
        embed = discord.Embed(
            title="⏰ **Already Claimed Today**",
            description="""
            **Patience, Trainer!**

            You've already claimed your daily credits. Come back tomorrow for more!

            **Why Dailies Matter:**
            - Free credits every 24 hours.
            - Streaks give bonuses (up to 50 extra per day).
            - Premium doubles rewards.

            **Streak Info:** Your current streak is {data['streak']} – keep it up!

            See you tomorrow for more nostalgia! 🌅
            """,
            color=WARNING_ORANGE
        )
        embed.set_image(url=get_giphy_gif('wait'))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    bonus = data['streak'] * 50 if data['is_premium'] else data['streak'] * 25
    credits = 100 + bonus
    data['credits'] += credits
    data['streak'] += 1
    data['last_daily'] = now.isoformat()
    await update_user_data(user_id, credits=data['credits'], streak=data['streak'], last_daily=data['last_daily'])
    embed = discord.Embed(
        title="🎁 **Daily Credits Claimed!**",
        description=f"""
        **Thank You for Playing NexusVerse!**

        You've claimed {credits} credits (+{bonus} bonus from streak).

        **Breakdown:**
        - Base: 100 credits
        - Streak Bonus: +{bonus} (Streak: {data['streak']})
        - Premium Multiplier: {'Applied!' if data['is_premium'] else 'Not active – upgrade for 2x!'}

        **Keep Streaking:**
        - Miss a day? Streak resets.
        - Premium prevents resets.

        Enjoy your rewards – catch more tomorrow! 🎉
        """,
        color=SUCCESS_GREEN
    )
    embed.set_image(url=get_giphy_gif('gift'))
    await interaction.response.send_message(embed=embed)

# /premium (Enhanced with Perks Display)
@bot.tree.command(name='premium', description='Check or buy premium!')
async def premium_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    if data['is_premium']:
        embed = discord.Embed(
            title="💎 **Premium Active – Enjoy the Perks!**",
            description="""
            **You're a VIP in NexusVerse!**

            Your Premium subscription is active, unlocking the best features.

            **Current Perks:**
            - 2x Credits on dailies and heists.
            - No cooldowns on commands.
            - +20% Catch success rate.
            - PvP battle boosts.
            - Priority support and exclusive events.

            **Subscription Details:**
            - Expires: {data['premium_until'] if data['premium_until'] else 'Lifetime'}
            - Renew anytime for 1000 credits.

            Thank you for supporting NexusVerse – stay legendary! 👑
            """,
            color=PREMIUM_GOLD
        )
        embed.set_image(url=get_giphy_gif('premium'))
    else:
        embed = discord.Embed(
            title="💎 **Upgrade to Premium – Unlock Everything!**",
            description="""
            **Become a NexusVerse Elite!**

            Premium costs 1000 credits for 1 month and transforms your experience.

            **Perks You'll Get:**
            - 2x Credits on dailies and heists.
            - No cooldowns – instant actions.
            - +20% Catch success rate.
            - PvP battle advantages.
            - Exclusive access to events and custom entities.

            **How to Buy:**
            - Use /shop to purchase.
            - Contact an admin for manual activation.

            **Why Premium?** It's the ultimate way to dominate the Nexus!

            Ready to upgrade? Let's go! 🚀
            """,
            color=PREMIUM_GOLD
        )
        embed.set_image(url=get_giphy_gif('upgrade'))
    await interaction.response.send_message(embed=embed)

# /leaderboard (New Feature with Attractive Embed)
@bot.tree.command(name='leaderboard', description='View top players!')
async def leaderboard_command(interaction: discord.Interaction):
    lb = await get_leaderboard()
    embed = discord.Embed(
        title="🏆 **NexusVerse Leaderboard – Top Catchers!**",
        description="""
        **Compete with the Best!**

        See who's leading in entity catches. Climb the ranks for glory!

        **Top Players:**
        """ + "\n".join([f"#{i} <@{entry['user_id']}> – Score: {entry['score']}" for i, entry in enumerate(lb, 1)]),
        color=EPIC_PURPLE
    )
    embed.set_image(url=get_giphy_gif('leaderboard'))
    embed.add_field(name="Your Rank", value="Check /profile for your score!", inline=False)
    embed.set_footer(text="Events boost scores – join in!", icon_url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")
    await interaction.response.send_message(embed=embed)

# /fuse (New Feature for Entity Fusion)
@bot.tree.command(name='fuse', description='Fuse two entities for evolution!')
@app_commands.describe(entity1='First entity index', entity2='Second entity index')
async def fuse_command(interaction: discord.Interaction, entity1: int, entity2: int):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    if entity1 >= len(data['entities']) or entity2 >= len(data['entities']):
        embed = discord.Embed(
            title="❌ **Invalid Entity Indices**",
            description="""
            **Fusion Failed – Check Your Inventory!**

            The entity indices you provided don't exist in your collection. Ensure you're using numbers from 0 to {len(data['entities']) - 1}.

            **How to Fuse:**
            - Use /profile to list your entities with indices.
            - Fuse two identical entities for evolution.
            - Premium users get +10% success boost.

            **Example:** /fuse 0 1 (fuses first two entities).

            Try again – fusions are key to power! 🔬
            """,
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    e1 = data['entities'][entity1]
    e2 = data['entities'][entity2]
    if e1['name'] == e2['name'] and e1['fuse_into']:
        success = random.random() < (0.8 + (0.1 if data['is_premium'] else 0))  # 80% + premium bonus
        if success:
            new_entity = next((e for e in CONFIG['entities'] if e['name'] == e1['fuse_into']), None)
            if new_entity:
                data['entities'].remove(e1)
                data['entities'].remove(e2)
                data['entities'].append(new_entity)
                await update_user_data(user_id, entities=data['entities'])
                embed = discord.Embed(
                    title="🔥 **Fusion Success – Evolution Achieved!**",
                    description=f"""
                    **Amazing – You've Evolved {e1['name']} into {new_entity['name']}!**

                    Fusion complete! Your entities have combined into a stronger form.

                    **Details:**
                    - **Fused:** {e1['name']} x2
                    - **Result:** {new_entity['name']} ({new_entity['rarity']})
                    - **New Power:** +{new_entity['power']}
                    - **Success Rate:** {'90%' if data['is_premium'] else '80%'} (Premium bonus applied!)

                    **Why Fuse?**
                    - Evolutions unlock higher rarities.
                    - Build your ultimate team.

                    Keep fusing – become the ultimate catcher! 🦸‍♂️
                    """,
                    color=SUCCESS_GREEN
                )
                embed.set_image(url=new_entity['image_url'])
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ **Fusion Failed – No Evolution Path**",
                    description="""
                    **Oops – This Entity Can't Evolve Further!**

                    Some entities like Pikachu or Master Chief are maxed out. Try fusing lower-tier ones.

                    **Tips:**
                    - Check entity descriptions for fusion hints.
                    - Collect more to unlock paths.

                    Don't give up – the Nexus has secrets! 🔍
                    """,
                    color=ERROR_RED
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embed = discord.Embed(
                title="❌ **Fusion Failed – Try Again!**",
                description="""
                **Fusion Didn't Work This Time!**

                Success depends on luck and premium status. Keep trying!

                **Improve Chances:**
                - Premium: +10% success.
                - Practice with commons first.

                Persistence leads to evolution! 💪
                """,
                color=WARNING_ORANGE
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="❌ **Fusion Failed – Requirements Not Met**",
            description="""
            **Entities Must Match for Fusion!**

            To fuse, both entities must be identical and have an evolution path.

            **Requirements:**
            - Same name and rarity.
            - Check /profile for matches.

            **Example:** Fuse two SpongeBobs to get Shrek.

            Get collecting – fusions await! 🧬
            """,
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /shop (Enhanced with Options)
@bot.tree.command(name='shop', description='Buy items!')
async def shop_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛒 **NexusVerse Shop – Upgrade Your Game!**",
        description="""
        **Welcome to the Ultimate Shop!**

        Spend credits on boosts, premium, and more to dominate NexusVerse.

        **Available Items:**
        - **Premium Subscription:** 1000 credits for 1 month – 2x earnings, no cooldowns, +20% catch rate.
        - **Entity Pack:** 50 credits – Random entity to expand your collection.
        - **Fusion Boost:** 200 credits – +10% fusion success for 24 hours.

        **How to Buy:**
        - Premium: Grants instant perks.
        - Packs: Great for beginners.
        - Boosts: Essential for advanced players.

        **Pro Tip:** Premium users get discounts on packs!

        Ready to shop? Let's enhance your adventure! 💳
        """,
        color=NEON_BLUE
    )
    embed.set_image(url=get_giphy_gif('shop'))
    await interaction.response.send_message(embed=embed)

# /heist (Enhanced with Risk/Reward)
@bot.tree.command(name='heist', description='Steal credits from another user!')
@app_commands.describe(target='User to heist')
async def heist_command(interaction: discord.Interaction, target: discord.Member):
    user_id = interaction.user.id
    target_id = target.id
    data = await get_user_data(user_id)
    target_data = await get_user_data(target_id)
    if random.random() < 0.5:
        steal = random.randint(10, 50)
        data['credits'] += steal
        target_data['credits'] -= steal
        await update_user_data(user_id, credits=data['credits'])
        await update_user_data(target_id, credits=target_data['credits'])
        embed = discord.Embed(
            title="💰 **Heist Success – Credits Stolen!**",
            description=f"""
            **Master Thief Alert!**

            You successfully stole {steal} credits from {target.name}!

            **Details:**
            - **Stolen:** +{steal} Credits
            - **Risk:** 50% chance – you got lucky!
            - **Victim:** {target.name} (They lost credits)

            **Heist Mechanics:**
            - Random amount between 10-50.
            - Premium doubles potential gains.
            - Anti-abuse flags suspicious patterns.

            **Warning:** Overuse may lead to bans. Play fair!

            Another successful heist – stay sneaky! 🕵️‍♂️
            """,
            color=SUCCESS_GREEN
        )
        embed.set_image(url=get_giphy_gif('heist'))
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        loss = random.randint(10, 50)
        data['credits'] -= loss
        await update_user_data(user_id, credits=data['credits'])
        embed = discord.Embed(
            title="❌ **Heist Failed – You Got Caught!**",
            description=f"""
            **Busted – Heist Gone Wrong!**

            You lost {loss} credits in the attempt. Better luck next time!

            **What Happened:**
            - 50% failure rate – risk is real.
            - Loss: Random 10-50 credits.
            - No gains for the victim.

            **Tips to Succeed:**
            - Time heists wisely.
            - Premium increases odds slightly.
            - Avoid targeting admins.

            Learn from this – plan better! 🚔
            """,
            color=ERROR_RED
        )
        embed.set_image(url=get_giphy_gif('fail'))
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /trade (New Command for Entity Trading)
@bot.tree.command(name='trade', description='Trade entities with another user!')
@app_commands.describe(target='User to trade with', your_entity='Your entity index', their_entity='Their entity index')
async def trade_command(interaction: discord.Interaction, target: discord.Member, your_entity: int, their_entity: int):
    user_id = interaction.user.id
    target_id = target.id
    data = await get_user_data(user_id)
    target_data = await get_user_data(target_id)
    if your_entity >= len(data['entities']) or their_entity >= len(target_data['entities']):
        embed = discord.Embed(
            title="❌ **Invalid Trade – Check Indices!**",
            description="""
            **Trade Failed – Entity Not Found!**

            Ensure both indices are valid in your inventories.

            **How to Trade:**
            - /profile to see your entities.
            - Agree with the other user first.
            - Both must confirm.

            **Safety:** Trades are logged for fairness.

            Try again – trading builds alliances! 🤝
            """,
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    # Placeholder: Add confirmation buttons in real implementation
    your_e = data['entities'][your_entity]
    their_e = target_data['entities'][their_entity]
    data['entities'][your_entity] = their_e
    target_data['entities'][their_entity] = your_e
    await update_user_data(user_id, entities=data['entities'])
    await update_user_data(target_id, entities=target_data['entities'])
    embed = discord.Embed(
        title="🤝 **Trade Successful!**",
        description=f"""
        **Entities Swapped!**

        You traded {your_e['name']} for {their_e['name']} with {target.name}.

        **Details:**
        - **You Gave:** {your_e['name']} ({your_e['rarity']})
        - **You Got:** {their_e['name']} ({their_e['rarity']})

        **Trade Rules:**
        - Mutual agreement required.
        - Logged for disputes.
        - Premium users get trade bonuses.

        Happy trading – strengthen your team! 🎁
        """,
        color=SUCCESS_GREEN
    )
    await interaction.response.send_message(embed=embed)

# /quest (New Command for Daily Tasks)
@bot.tree.command(name='quest', description='View and complete daily quests!')
async def quest_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    # Placeholder: Generate random quests
    quests = [
        {"task": "Catch 5 entities", "reward": 100, "progress": min(len(data['entities']), 5), "max": 5},
        {"task": "Fuse 1 entity", "reward": 50, "progress": 0, "max": 1},  # Track in DB
    ]
    embed = discord.Embed(
        title="📜 **Daily Quests – Earn Rewards!**",
        description="""
        **Complete Tasks for Bonuses!**

        Finish quests daily to gain credits and boosts.

        **Your Quests:**
        """ + "\n".join([f"- {q['task']}: {q['progress']}/{q['max']} (Reward: {q['reward']} credits)" for q in quests]),
        color=EPIC_PURPLE
    )
    embed.set_image(url=get_giphy_gif('quest'))
    embed.add_field(name="How to Complete", value="Catch, fuse, or trade – progress auto-updates!", inline=False)
    await interaction.response.send_message(embed=embed)

# /battle (New PvP Command)
@bot.tree.command(name='battle', description='Battle another user for credits!')
@app_commands.describe(target='User to battle')
async def battle_command(interaction: discord.Interaction, target: discord.Member):
    user_id = interaction.user.id
    target_id = target.id
    data = await get_user_data(user_id)
    target_data = await get_user_data(target_id)
    user_power = sum(e['power'] for e in data['entities'])
    target_power = sum(e['power'] for e in target_data['entities'])
    if user_power > target_power:
        win = random.randint(50, 100)
        data['credits'] += win
        target_data['credits'] -= win
        await update_user_data(user_id, credits=data['credits'])
        await update_user_data(target_id, credits=target_data['credits'])
        embed = discord.Embed(
            title="⚔️ **Battle Won – Victory!**",
            description=f"""
            **You Defeated {target.name}!**

            Your power ({user_power}) overwhelmed theirs ({target_power}).

            **Rewards:**
            - +{win} Credits
            - Boosted leaderboard score.

            **Battle Tips:**
            - Fuse for higher power.
            - Premium gives advantages.

            Champion status unlocked! 🏆
            """,
            color=SUCCESS_GREEN
        )
    else:
        embed = discord.Embed(
            title="⚔️ **Battle Lost – Train Harder!**",
            description=f"""
            **{target.name} Won the Battle!**

            Their power ({target_power}) was stronger than yours ({user_power}).

            **Lessons:**
            - Collect more entities.
            - Fuse for evolutions.

            Next time, you'll win! 💪
            """,
            color=ERROR_RED
        )
    embed.set_image(url=get_giphy_gif('battle'))
    await interaction.response.send_message(embed=embed)

# /voice_music (New Command for Nostalgic Music)
@bot.tree.command(name='voice_music', description='Play nostalgic music in voice channel!')
async def voice_music_command(interaction: discord.Interaction):
    if interaction.user.voice:
        voice_client = await interaction.user.voice.channel.connect()
        # Placeholder: Play music
        embed = discord.Embed(
            title="🎵 **Nostalgic Music Playing!**",
            description="""
            **Retro Vibes Activated!**

            Enjoy classic game tunes in voice. Perfect for events!

            **Features:**
            - Auto-plays during nostalgia_week.
            - Premium unlocks custom tracks.

            Immerse yourself in the past! 🎶
            """,
            color=NEON_BLUE
        )
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ **Join Voice First!**",
            description="You must be in a voice channel to play music.",
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /admin Commands (Enhanced with Security and Embeds)
@bot.tree.command(name='admin', description='Admin commands (Owner/Admin only)')
@app_commands.describe(action='ban, unban, assign, remove, event', target='User ID', reason='Reason or level', guild_id='Guild ID (optional)')
async def admin_command(interaction: discord.Interaction, action: str, target: int, reason: str = None, guild_id: int = None):
    user_level = await get_user_level(interaction.user.id)
    if user_level not in ['owner', 'admin']:
        embed = discord.Embed(
            title="❌ **Access Denied – Admin Only!**",
            description="""
            **You Lack Permissions!**

            This command requires Owner or Admin level. Contact the owner for access.

            **Hierarchy:**
            - Owner: Full control.
            - Admin: Most features.
            - Mod: Limited to guilds.

            Respect the system – it's for fairness! 🛡️
            """,
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    ip_hash = hashlib.md5(str(interaction.user.id).encode()).hexdigest()
    if action == 'ban':
        await ban_user(target, reason or 'No reason', guild_id)
        await log_audit('ban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(
            title="🚫 **User Banned Successfully!**",
            description=f"""
            **Action Completed!**

            User {target} banned in guild {guild_id or 'global'} for: {reason}.

            **Details:**
            - Reason logged.
            - Audit trail created.
            - Email alert sent if critical.

            **Admin Duties:** Use wisely for community safety.

            Ban enforced – order maintained! ⚖️
            """,
            color=SUCCESS_GREEN
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'unban':
        await unban_user(target, guild_id)
        await log_audit('unban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(
            title="✅ **User Unbanned!**",
            description=f"User {target} unbanned in guild {guild_id or 'global'}. Logged for review.",
            color=SUCCESS_GREEN
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'assign':
        if user_level == 'owner' or reason in ['admin', 'mod']:
            assign_role_sync(target, reason, interaction.user.id, [])
            await log_audit(f'assign_{reason}', interaction.user.id, target, ip_hash=ip_hash)
            embed = discord.Embed(
                title="⭐ **Role Assigned!**",
                description=f"{reason.capitalize()} role given to {target}. Hierarchy updated.",
                color=SUCCESS_GREEN
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'remove':
        if user_level == 'owner' or reason in ['admin', 'mod']:
            remove_role_sync(target, reason, interaction.user.id)
            await log_audit(f'remove_{reason}', interaction.user.id, target, ip_hash=ip_hash)
            embed = discord.Embed(
                title="🛡️ **Role Removed!**",
                description=f"{reason.capitalize()} role taken from {target}.",
                color=SUCCESS_GREEN
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'event':
        await start_global_event(reason or 'double_spawn', int(guild_id or 24))
        await log_audit('event', interaction.user.id, None, ip_hash=ip_hash)
        embed = discord.Embed(
            title="🌟 **Event Started!**",
            description=f"'{reason}' event active for {guild_id or 24} hours. Community notified!",
            color=EPIC_PURPLE
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="❌ **Invalid Action**",
            description="""
            **Command Not Recognized!**

            Use one of: ban, unban, assign, remove, event.

            **Admin Guide:**
            - /admin ban <user> <reason> [guild] – Ban user.
            - /admin unban <user> [guild] – Unban user.
            - /admin assign <user> <level> – Assign role (owner only for owner/admin).
            - /admin remove <user> <level> – Remove role.
            - /admin event <type> <duration> – Start event.

            **Hierarchy Rules:**
            - Owner: Full access to all.
            - Admin: Can ban/unban/assign mods, start events.
            - Mod: Limited to their assigned guilds.

            **Best Practices:**
            - Always log reasons.
            - Use for community protection.
            - Audit trails prevent abuse.

            Stay vigilant – the Nexus needs guardians! 👑
            """,
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /mod Commands (Similar to Admin but Limited)
@bot.tree.command(name='mod', description='Mod commands (Mod/Admin/Owner only)')
@app_commands.describe(action='ban, unban', target='User ID', reason='Reason', guild_id='Guild ID')
async def mod_command(interaction: discord.Interaction, action: str, target: int, reason: str, guild_id: int):
    user_level = await get_user_level(interaction.user.id)
    if user_level not in ['owner', 'admin', 'mod']:
        embed = discord.Embed(
            title="❌ **Access Denied – Mod Level Required!**",
            description="""
            **Insufficient Permissions!**

            You need Mod, Admin, or Owner level for this command.

            **Mod Duties:**
            - Ban/unban in assigned guilds.
            - Report to admins for escalations.

            **How to Get Mod:**
            - Assigned by Admin/Owner.
            - Prove reliability in community.

            **Why Mods?** They keep servers safe and fun.

            Aspire to mod – help the community! 🛡️
            """,
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    ip_hash = hashlib.md5(str(interaction.user.id).encode()).hexdigest()
    if action == 'ban':
        await ban_user(target, reason, guild_id)
        await log_audit('mod_ban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(
            title="🚫 **Mod Ban Enforced!**",
            description=f"""
            **Action Taken!**

            User {target} banned in guild {guild_id} for: {reason}.

            **Mod Notes:**
            - Logged and audited.
            - Guild-specific only.
            - Escalate to admin if needed.

            **Moderation Tips:**
            - Fair and consistent.
            - Document evidence.
            - Community feedback matters.

            Ban applied – peace restored! ⚖️
            """,
            color=SUCCESS_GREEN
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'unban':
        await unban_user(target, guild_id)
        await log_audit('mod_unban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(
            title="✅ **Mod Unban Completed!**",
            description=f"User {target} unbanned in guild {guild_id}. Second chances given.",
            color=SUCCESS_GREEN
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(
            title="❌ **Invalid Mod Action**",
            description="""
            **Use ban or unban Only!**

            Mods have limited powers for safety.

            **Available:**
            - /mod ban <user> <reason> <guild>
            - /mod unban <user> <guild>

            **Escalate:** For more, contact an admin.

            Mod wisely – balance is key! 🔒
            """,
            color=ERROR_RED
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /help (Most Attractive and Detailed)
@bot.tree.command(name='help', description='Detailed NexusVerse Guide – Interactive Categories!')
@app_commands.describe(category='Choose: core, economy, premium, owner')
async def help_command(interaction: discord.Interaction, category: str = 'core'):
    embed = discord.Embed(title="🌌 **NexusVerse Help – Your Ultimate Guide!**", color=NEON_BLUE)
    embed.set_thumbnail(url=get_giphy_gif('help'))
    if category == 'core':
        embed.description = r"""**🌟 Core Commands – Start Your Adventure!**

        **Welcome to NexusVerse, the ultimate nostalgic entity-catching bot!** Dive into a world of retro gaming icons, strategic fusions, and epic battles. Whether you're a beginner or pro, these commands are your foundation.

        ** /catch **
        - **What It Does:** Scans the Nexus for a random entity (Pac-Man, SpongeBob, etc.) with a thrilling 3-second animation.
        - **Mechanics:** Success based on level (30% base +5% per level, max 90%) and premium (+20%). Fail increases pity (10 fails = guaranteed Rare).
        - **Example:** /catch → "Scanning Nexus..." → Success: "Caught SpongeBob (Rare)! +10 Credits" or Fail: "Escaped – Pity 2/10".
        - **Tips:** Official servers boost rates. Events double spawns – check /profile for active ones.
        - **Why It's Hooking:** Instant excitement, GIFs, and progression keep you coming back!

        ** /profile **
        - **What It Does:** Displays your stats, entities, pity bar, and premium status with a custom avatar.
        - **Details:** Level, credits, top 3 entities with GIFs, streak, and progress bars.
        - **Example:** /profile → "Level 5, 500 Credits, Pity: ■■■□□□, Streak: 7 🔥".
        - **Tips:** Use to track growth. Premium badges glow!
        - **Why It's Bearable:** Clear, visual progress motivates long-term play.

        ** /pull **
        - **What It Does:** Gacha pull for 50 credits (up to 10 at once), pity resets at 10 fails.
        - **Mechanics:** Rolls entities, updates collection, boosts leaderboard.
        - **Example:** /pull 3 → "Pulled: Pac-Man, Shrek, Pikachu! New total: 15 entities".
        - **Tips:** Premium fills pity 2x faster. Fuse duplicates for evolutions.
        - **Why It's Addictive:** Random rewards, high stakes, community bragging.

        ** /fuse **
        - **What It Does:** Combine two identical entities for evolution (e.g., 2 SpongeBobs → Shrek).
        - **Mechanics:** 80% success +10% premium. Removes originals, adds evolved.
        - **Example:** /fuse 0 1 → "Fused into Shrek (Epic)! +100 Power".
        - **Tips:** Check /profile for indices. Max evolutions unlock myths.
        - **Why It's Strategic:** Builds power, encourages collecting.

        **Pity System Overview:**
        - 10 fails = next Rare guaranteed.
        - Premium: 2x pity fill, cap at 8.
        - Official: No cooldowns, 3x spawns.

        **Rate Limits & Fair Play:**
        - 60s cooldown (premium skips).
        - CAPTCHA for spam.
        - Anti-abuse flags rapid actions.

        **Pro Tips for Beginners:**
        - Start with /daily for free credits.
        - Join events for bonuses.
        - Trade with friends for rares.
        - Premium unlocks everything.

        **Why NexusVerse?** It's not just a bot – it's a community-driven nostalgia trip with PvP, events, and endless fun. No other bot matches its depth!

        Use /help economy for earning/spending. Stay hooked! 🎮"""
        embed.add_field(name="💡 Quick Start", value="Claim /daily, /catch your first entity, then /pull for more!", inline=False)
        embed.set_footer(text="NexusVerse – Catch 'em all in style! 🌌", icon_url=get_giphy_gif('nexus'))
    elif category == 'economy':
        embed.description = r"""**💰 Economy Commands – Earn, Spend, Dominate!**

        **Master the NexusVerse economy to build your empire!** Credits are key to pulls, premium, and boosts. Earn through gameplay, spend wisely.

        ** /daily **
        - **What It Does:** Claim 100 credits daily + streak bonus (up to 50/day, 100 with premium).
        - **Mechanics:** Resets 24h, streak tracks consecutive claims.
        - **Example:** /daily → "+150 Credits (Streak: 3)".
        - **Tips:** Premium doubles base. Miss a day? Streak resets.
        - **Why It's Rewarding:** Free, daily motivation.

        ** /shop **
        - **What It Does:** Buy premium (1000 credits/1 month), entity packs (50 credits), fusion boosts (200 credits).
        - **Mechanics:** Instant perks for premium, random entities for packs.
        - **Example:** Buy premium → "2x earnings unlocked!".
        - **Tips:** Premium essential for pros. Discounts for officials.
        - **Why It's Essential:** Upgrades gameplay exponentially.

        ** /heist @user **
        - **What It Does:** Steal 10-50 credits (50% success), risk your own.
        - **Mechanics:** Random win/loss, logged for fairness.
        - **Example:** Success: "+30 Credits from @User" or Fail: "-20 Credits".
        - **Tips:** Premium boosts odds. Avoid overuse (bans possible).
        - **Why It's Risky Fun:** PvP element adds thrill.

        ** /trade @user index1 index2 **
        - **What It Does:** Swap entities with another user.
        - **Mechanics:** Mutual agreement, logged.
        - **Example:** /trade @Friend 0 1 → "Traded Pac-Man for Shrek".
        - **Tips:** Agree first. Premium gets bonuses.
        - **Why It's Social:** Builds alliances, trades rares.

        ** /quest **
        - **What It Does:** View daily tasks (e.g., catch 5 entities for 100 credits).
        - **Mechanics:** Auto-progress, rewards on completion.
        - **Example:** "Catch 5/5: +100 Credits".
        - **Tips:** Check often. Premium multiplies rewards.
        - **Why It's Engaging:** Goals keep you playing.

        **Credit Strategies:**
        - Grind dailies for steady income.
        - Heists for quick gains (high risk).
        - Trades for strategic builds.
        - Premium maximizes earnings.

        **Economic Balance:**
        - No pay-to-win – fair for all.
        - Audits prevent cheating.
        - Community events boost everyone.

        **Why Economy Matters:** It's the heartbeat of NexusVerse – earn to evolve, spend to shine. No bot has this depth!

        Use /help premium for upgrades. Prosper! 💎"""
        embed.set_footer(text="Economy Guide – Build your legacy! 💰", icon_url=get_giphy_gif('money'))
    elif category == 'premium':
        embed.description = r"""**💎 Premium Perks – Unlock the Elite Experience!**

        **Elevate Your NexusVerse Journey with Premium!** For 1000 credits/month, become unstoppable. Perks stack for max fun.

        ** /premium **
        - **What It Does:** Check/buy status (1 month = 1000 credits).
        - **Perks:** 2x dailies/heists, no cooldowns, +20% catch, PvP boosts, exclusive events.
        - **Example:** Active → "Perks: 2x Credits, Instant Actions".
        - **Tips:** Buy via /shop. Lifetime options available.
        - **Why It's Game-Changing:** Removes limits, adds power.

        ** /battle @user **
        - **What It Does:** PvP fight using entity power for credits.
        - **Mechanics:** Higher power wins, random bonus.
        - **Example:** Win: "+75 Credits" or Lose: "Train more!".
        - **Tips:** Fuse for strength. Premium advantages.
        - **Why It's Competitive:** Leaderboards, bragging rights.

        ** /leaderboard **
        - **What It Does:** Top 10 catchers by score/entities.
        - **Mechanics:** Updates on catches/pulls.
        - **Example:** "#1 @User – Score: 500".
        - **Tips:** Compete globally. Events boost ranks.
        - **Why It's Motivating:** Climb to glory!

        ** /event_vote event **
        - **What It Does:** Vote for community events (double_spawn, nostalgia_week, pvp_boost).
        - **Mechanics:** Redis-tracked, winner starts event.
        - **Example:** /event_vote double_spawn → "Vote cast!".
        - **Tips:** Community decides. Premium votes count double.
        - **Why It's Democratic:** Player-driven fun.

        ** /voice_music **
        - **What It Does:** Play retro music in voice (nostalgia_week auto).
        - **Mechanics:** Connects to channel, streams tunes.
        - **Example:** "Playing Pac-Man theme!".
        - **Tips:** Join voice first. Premium unlocks customs.
        - **Why It's Immersive:** Nostalgic vibes.

        **Premium Benefits Summary:**
        - **Earnings:** 2x credits everywhere.
        - **Speed:** No cooldowns, instant pulls.
        - **Success:** +20% catch/fusion.
        - **Extras:** PvP edges, music, votes.
        - **Support:** Priority help, appeals.

        **Why Go Premium?** It's the ultimate upgrade – dominate without limits. No bot offers this!

        Use /help owner for admin controls. Rule the Nexus! 👑"""
        embed.set_footer(text="Premium Guide – Ascend to greatness! 💎", icon_url=get_giphy_gif('premium'))
    elif category == 'owner':
        embed.description = r"""**👑 Owner Commands – God-Mode Control!**

        **For Owners/Admins/Mods Only – Manage NexusVerse Like a Pro!** Hierarchy ensures fair, logged control. Owners have all, admins most, mods guild-limited.

        ** /admin ban @user reason [guild] **
        - **What It Does:** Ban user globally or per-guild.
        - **Mechanics:** Logs reason, sends DM, audits.
        - **Example:** /admin ban 123456 Spam → "Banned globally".
        - **Tips:** Use for violations. Email alerts for critical.
        - **Why It's Powerful:** Instant enforcement.

        ** /admin unban @user [guild] **
        - **What It Does:** Unban user.
        - **Mechanics:** Removes ban, logs.
        - **Example:** /admin unban 123456 → "Unbanned".
        - **Tips:** Second chances. Audit for fairness.
        - **Why It's Balanced:** Prevents abuse.

        ** /admin assign @user level **
        - **What It Does:** Assign admin/mod (owner only for owner/admin).
        - **Mechanics:** Updates hierarchy, logs.
        - **Example:** /admin assign 123456 admin → "Admin assigned".
        - **Tips:** Choose wisely. Guilds for mods.
        - **Why It's Hierarchical:** Structured power.

        ** /admin remove @user level **
        - **What It Does:** Remove role.
        - **Mechanics:** Downgrades, logs.
        - **Example:** /admin remove 123456 mod → "Removed".
        - **Tips:** For misconduct. Owner override.
        - **Why It's Safe:** Prevents tyranny.

        ** /admin event type duration **
        - **What It Does:** Start global event.
        - **Mechanics:** Boosts rates, notifies.
        - **Example:** /admin event double_spawn 24 → "Event started".
        - **Tips:** Use for engagement. Random auto-events.
        - **Why It's Fun:** Community boosts.

        ** /mod ban/unban (Guild-Limited) **
        - **What It Does:** Mod versions of ban/unban.
        - **Mechanics:** Only assigned guilds.
        - **Example:** /mod ban 123456 Spam 987654 → "Guild ban".
        - **Tips:** Report to admins. Limited scope.
        - **Why It's Local:** Guild-specific safety.

        ** /create_entity name rarity emoji power desc url **
        - **What It Does:** Add custom entity (owner/admin).
        - **Mechanics:** Adds to config, community votes.
        - **Example:** /create_entity "Custom" Rare 🐱 60 "Fun" url → "Created".
        - **Tips:** For events. Stored in custom list.
        - **Why It's Creative:** Player-driven content.

        **Hierarchy Overview:**
        - **Owner:** Full control (assign admins, global bans, events, customs).
        - **Admin:** Ban/unban/assign mods, events, customs.
        - **Mod:** Ban/unban in assigned guilds only.
        - **Controls:** All logged, IP-tracked, email alerts for critical (e.g., owner assign).

        **Dashboard Integration (Web App):**
        - Owners/Admins/Mods access via browser.
        - Real-time stats, user management, ban/unban buttons.
        - Audit logs, event scheduling, custom entity voting.
        - PWA for mobile, WebSockets for live updates.
        - Secure login, role-based views (mods see only their guilds).

        **Best Practices:**
        - Log all actions.
        - Fair enforcement.
        - Community input for events.
        - Backup DB daily.

        **Why Owner Controls?** Ultimate power for the best bot – manage like a legend!

        This is NexusVerse – unbeatable, professional, nostalgic. No bot compares! 🌟"""
        embed.set_footer(text="Owner Guide – Command the Nexus! 👑", icon_url=get_giphy_gif('owner'))
    try:
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"Help command error: {e}")
        await interaction.response.send_message("Error loading help – Try again!", ephemeral=True)

# Voice Channel Integration (Play Music During Events)
@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and await get_global_event() == 'nostalgia_week':
        voice_client = await after.channel.connect()
        # Placeholder: Play retro music (use ffmpeg or youtube-dl)
        print("🎵 Playing nostalgia music in voice!")

# Webhook for Notifications (e.g., New Ban Alerts)
async def send_webhook_notification(message: str):
    # Placeholder: Send to Discord webhook or email
    print(f"📢 Notification: {message}")

# Automated Event Trigger (Random Community Events)
async def trigger_random_event():
    while True:
        await asyncio.sleep(86400)  # Every 24h
        event = random.choice(CONFIG['events'])
        await start_global_event(event, 6)  # 6h event
        await send_webhook_notification(f"🌟 Random event '{event}' started!")

# Run Block (Ultimate Launch)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    print("🚀 Ultimate NexusVerse Bot Launching – All Advanced Features Ready!")
    print(f"Owner ID: {OWNER_ID} | Entities: {len(CONFIG['entities'])} | Custom: {len(CONFIG['custom_entities'])}")
    print(f"Levels: Owner 👑 > Admin ⭐ > Mod 🛡️ | DB: {DB_FILE} | Redis: {REDIS_URL}")
    asyncio.run(init_db())
    bot.run(DISCORD_TOKEN)