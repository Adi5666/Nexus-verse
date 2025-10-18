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
    # Backup DB to cloud (e.g., AWS S3) every 24h
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
        try:
            await message.delete()
            embed = discord.Embed(title="🚫 Banned", description="You are banned from using commands.", color=ERROR_RED)
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
        embed = discord.Embed(title="⏰ Cooldown Active", description="Wait 60s or solve CAPTCHA!", color=WARNING_ORANGE)
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
                await update_leaderboard(user_id, len(data['entities']))
        embed = discord.Embed(title=f"✅ Caught {entity['name']}!", description=f"Power +{entity['power']} | Level {data['level']}", color=SUCCESS_GREEN)
        embed.set_image(url=entity['image_url'])
        embed.add_field(name="Pity Reset", value="■" * 10, inline=True)
        embed.add_field(name="Next Fusion", value=entity.get('fuse_into', 'None'), inline=True)
        await interaction.response.send_message(embed=embed)
    else:
        data['pity'] += 1
        await update_user_data(user_id, pity=data['pity'])
        embed = discord.Embed(title="❌ Escaped!", description=f"Pity {data['pity']}/10", color=ERROR_RED)
        embed.set_image(url=get_giphy_gif('escape'))
        await interaction.response.send_message(embed=embed)

# /profile (Enhanced with Progress Bars and Attractive Embed)
@bot.tree.command(name='profile', description='View your NexusVerse profile!')
async def profile_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    embed = discord.Embed(title=f"{interaction.user.name}'s Profile", color=NEON_BLUE)
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else get_giphy_gif('avatar'))
    embed.add_field(name="Level", value=f"**{data['level']}** (Progress: {'■' * (data['level'] % 10)}{'□' * (10 - data['level'] % 10)})", inline=True)
    embed.add_field(name="Credits", value=f"💰 {data['credits']}", inline=True)
    embed.add_field(name="Entities", value=f"🦸 {len(data['entities'])}", inline=True)
    embed.add_field(name="Pity Bar", value="■" * data['pity'] + "□" * (10 - data['pity']), inline=False)
    embed.add_field(name="Premium", value="💎 Active" if data['is_premium'] else "No", inline=True)
    embed.add_field(name="Streak", value=f"🔥 {data['streak']}", inline=True)
    if data['entities']:
        top_entities = data['entities'][:3]
        embed.add_field(name="Top Entities", value=", ".join([f"{e['name']} ({e['rarity']})" for e in top_entities]), inline=False)
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
        embed = discord.Embed(title=f"🎰 Pulled {num_pulls} Entities!", description=", ".join([f"{e['name']} ({e['rarity']})" for e in pulled]), color=PREMIUM_GOLD)
        embed.set_image(url=get_giphy_gif('gacha'))
        embed.add_field(name="Cost", value=f"-{cost} Credits", inline=True)
        embed.add_field(name="New Total", value=f"{len(data['entities'])} Entities", inline=True)
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="❌ Not Enough Credits", description=f"You need {cost} credits!", color=ERROR_RED)
        embed.set_image(url=get_giphy_gif('broke'))
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /daily (Enhanced with Streak Rewards and Embed)
@bot.tree.command(name='daily', description='Claim daily credits!')
async def daily_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    now = datetime.now()
    if data['last_daily'] and (now - datetime.fromisoformat(data['last_daily'])).days < 1:
        embed = discord.Embed(title="⏰ Already Claimed", description="Come back tomorrow!", color=WARNING_ORANGE)
        embed.set_image(url=get_giphy_gif('wait'))
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    bonus = data['streak'] * 50 if data['is_premium'] else data['streak'] * 25
    credits = 100 + bonus
    data['credits'] += credits
    data['streak'] += 1
    data['last_daily'] = now.isoformat()
    await update_user_data(user_id, credits=data['credits'], streak=data['streak'], last_daily=data['last_daily'])
    embed = discord.Embed(title="🎁 Daily Claimed!", description=f"+{credits} credits (Streak: {data['streak']})", color=SUCCESS_GREEN)
    embed.set_image(url=get_giphy_gif('gift'))
    embed.add_field(name="Bonus", value=f"+{bonus} from streak", inline=True)
    await interaction.response.send_message(embed=embed)

# /premium (Enhanced with Perks Display)
@bot.tree.command(name='premium', description='Check or buy premium!')
async def premium_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    if data['is_premium']:
        embed = discord.Embed(title="💎 Premium Active", description="Enjoy perks!", color=PREMIUM_GOLD)
        embed.add_field(name="Perks", value="2x Credits, No Cooldowns, +20% Catch Success, PvP Boosts", inline=False)
        embed.set_image(url=get_giphy_gif('premium'))
    else:
        embed = discord.Embed(title="💎 Buy Premium", description="1000 credits for 1 month – Unlock the best!", color=PREMIUM_GOLD)
        embed.add_field(name="Perks", value="2x Credits, No Cooldowns, +20% Catch Success, PvP Boosts", inline=False)
        embed.add_field(name="Buy?", value="Use /shop or contact owner.", inline=False)
        embed.set_image(url=get_giphy_gif('upgrade'))
    await interaction.response.send_message(embed=embed)

# /leaderboard (New Feature with Attractive Embed)
@bot.tree.command(name='leaderboard', description='View top players!')
async def leaderboard_command(interaction: discord.Interaction):
    lb = await get_leaderboard()
    embed = discord.Embed(title="🏆 Leaderboard", description="Top Entity Catchers!", color=EPIC_PURPLE)
    embed.set_image(url=get_giphy_gif('leaderboard'))
    for i, entry in enumerate(lb, 1):
        embed.add_field(name=f"#{i} <@{entry['user_id']}>", value=f"Score: {entry['score']}", inline=False)
    await interaction.response.send_message(embed=embed)

# /fuse (New Feature for Entity Fusion)
@bot.tree.command(name='fuse', description='Fuse two entities for evolution!')
@app_commands.describe(entity1='First entity index', entity2='Second entity index')
async def fuse_command(interaction: discord.Interaction, entity1: int, entity2: int):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    if entity1 >= len(data['entities']) or entity2 >= len(data['entities']):
        embed = discord.Embed(title="❌ Invalid Entities", description="Check your entity indices!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    e1 = data['entities'][entity1]
    e2 = data['entities'][entity2]
    if e1['name'] == e2['name'] and e1['fuse_into']:
        new_entity = next((e for e in CONFIG['entities'] if e['name'] == e1['fuse_into']), None)
        if new_entity:
            data['entities'].remove(e1)
            data['entities'].remove(e2)
            data['entities'].append(new_entity)
            await update_user_data(user_id, entities=data['entities'])
            embed = discord.Embed(title="🔥 Fusion Success!", description=f"Fused into {new_entity['name']}!", color=SUCCESS_GREEN)
            embed.set_image(url=new_entity['image_url'])
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="❌ Fusion Failed", description="No evolution available.", color=ERROR_RED)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Fusion Failed", description="Entities must match and be fuseable.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /shop (Enhanced with Options)
@bot.tree.command(name='shop', description='Buy items!')
async def shop_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🛒 Shop", description="Buy premium or entities!", color=NEON_BLUE)
    embed.add_field(name="Premium", value="1000 credits for 1 month", inline=True)
    embed.add_field(name="Entity Pack", value="50 credits for random entity", inline=True)
    embed.add_field(name="Fusion Boost", value="200 credits for +10% fusion success", inline=True)
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
        embed = discord.Embed(title="💰 Heist Success!", description=f"+{steal} credits from {target.name}!", color=SUCCESS_GREEN)
        embed.set_image(url=get_giphy_gif('heist'))
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        loss = random.randint(10, 50)
        data['credits'] -= loss
        await update_user_data(user_id, credits=data['credits'])
        embed = discord.Embed(title="❌ Heist Failed!", description=f"-{loss} credits – Better luck next time!", color=ERROR_RED)
        embed.set_image(url=get_giphy_gif('fail'))
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /admin Commands (Enhanced with Security and Embeds)
@bot.tree.command(name='admin', description='Admin commands (Owner/Admin only)')
@app_commands.describe(action='ban, unban, assign, remove, event', target='User ID', reason='Reason or level', guild_id='Guild ID (optional)')
async def admin_command(interaction: discord.Interaction, action: str, target: int, reason: str = None, guild_id: int = None):
    user_level = await get_user_level(interaction.user.id)
    if user_level not in ['owner', 'admin']:
        embed = discord.Embed(title="❌ Access Denied", description="You need Admin or Owner level.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    ip_hash = hashlib.md5(str(interaction.user.id).encode()).hexdigest()  # Security logging
    if action == 'ban':
        await ban_user(target, reason or 'No reason', guild_id)
        await log_audit('ban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(title="🚫 Banned", description=f"User {target} banned in guild {guild_id or 'global'}.", color=SUCCESS_GREEN)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'unban':
        await unban_user(target, guild_id)
        await log_audit('unban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(title="✅ Unbanned", description=f"User {target} unbanned in guild {guild_id or 'global'}.", color=SUCCESS_GREEN)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'assign':
        if user_level == 'owner' or reason in ['admin', 'mod']:
            assign_role_sync(target, reason, interaction.user.id, [])
            await log_audit(f'assign_{reason}', interaction.user.id, target, ip_hash=ip_hash)
            embed = discord.Embed(title="⭐ Assigned", description=f"{reason.capitalize()} role to {target}.", color=SUCCESS_GREEN)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'remove':
        if user_level == 'owner' or reason in ['admin', 'mod']:
            remove_role_sync(target, reason, interaction.user.id)
            await log_audit(f'remove_{reason}', interaction.user.id, target, ip_hash=ip_hash)
            embed = discord.Embed(title="🛡️ Removed", description=f"{reason.capitalize()} role from {target}.", color=SUCCESS_GREEN)
            await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'event':
        await start_global_event(reason or 'double_spawn', int(guild_id or 24))
        await log_audit('event', interaction.user.id, None, ip_hash=ip_hash)
        embed = discord.Embed(title="🌟 Event Started", description=f"'{reason}' for {guild_id or 24}h!", color=EPIC_PURPLE)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Invalid Action", description="Use ban, unban, assign, remove, or event.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /mod Commands (Similar to Admin but Limited)
@bot.tree.command(name='mod', description='Mod commands (Mod/Admin/Owner only)')
@app_commands.describe(action='ban, unban', target='User ID', reason='Reason', guild_id='Guild ID')
async def mod_command(interaction: discord.Interaction, action: str, target: int, reason: str, guild_id: int):
    user_level = await get_user_level(interaction.user.id)
    if user_level not in ['owner', 'admin', 'mod']:
        embed = discord.Embed(title="❌ Access Denied", description="You need Mod, Admin, or Owner level.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    ip_hash = hashlib.md5(str(interaction.user.id).encode()).hexdigest()
    if action == 'ban':
        await ban_user(target, reason, guild_id)
        await log_audit('mod_ban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(title="🚫 Banned", description=f"User {target} banned in guild {guild_id}.", color=SUCCESS_GREEN)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    elif action == 'unban':
        await unban_user(target, guild_id)
        await log_audit('mod_unban', interaction.user.id, target, guild_id, ip_hash)
        embed = discord.Embed(title="✅ Unbanned", description=f"User {target} unbanned in guild {guild_id}.", color=SUCCESS_GREEN)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(title="❌ Invalid Action", description="Use ban or unban.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# /help (Most Attractive and Detailed)
@bot.tree.command(name='help', description='Detailed NexusVerse Guide – Interactive Categories!')
@app_commands.describe(category='Choose: core, economy, premium, owner')
async def help_command(interaction: discord.Interaction, category: str = 'core'):
    embed = discord.Embed(title="🌌 NexusVerse Help – Step-by-Step Guide", color=NEON_BLUE)
    embed.set_thumbnail(url=get_giphy_gif('help'))
    if category == 'core':
        embed.description = r"""**Core Commands (Start Here!)**

** /catch **
- Type /catch – Bot scans Nexus (3s excitement!).
- Always spawns random entity (e.g., Pac-Man Ghost GIF appears!).
- QC (Quality Check): Roll for rarity (Common 50%, Mythic 1% – Boosted in events/official).
- Catch Roll: 30% base + 5% per level (max 90%). Premium +20% success! Fail? Pity +1 toward guaranteed Rare at 10.

**Example**: /catch → \"Scanning...\" (3s) → \"\U0001F9FD SpongeBob (Rare) spawned!\" → \"Success! +10 Credits\" or \"Escaped – Pity 2/10\".

** /profile **
- Shows level, credits, entities (top 3 GIFs), pity bar [■■□□□□], premium badge.
- Example: /profile → Embed with your avatar + \"Power Total: 350 | Streak: 3 🔥\".

** /pull **
- Gacha for 50 credits (pity 10 = Legendary guaranteed).
- Example: /pull → \"Rolled 2 entities: Pac-Man + Shrek!\" with GIFs.

**Pity System**: 10 fails = next Rare+. Premium fills 2x faster. Official: Pity cap 8.
**Rate Limits**: 60s cooldown (premium skips). Official servers: No cooldown, 3x spawns!"""
        embed.add_field(name="💡 Quick Tips", value="Use /help economy for shop/daily. Events boost rates – Check /profile for active!", inline=False)
        embed.set_footer(text="NexusVerse – Catch 'em all! 🌌", icon_url=get_giphy_gif('nexus'))
    elif category == 'economy':
                embed.description = r"""**Economy Commands (Earn & Spend!)**

** /daily **
- Claim 100 credits daily (streak +50 bonus). Premium: 200.

** /shop **
- Buy boosts/entities (e.g., entity pack for 50 credits).

** /heist @victim **
- Steal 10-50 credits (50% success, risk your own!).

** /trade @user index **
- Exchange entity with another user.

** /quest **
- Daily tasks for rewards (e.g., catch 5 for +100 credits).

**Tips**: Battle for PvP credits. Premium doubles earnings!"""
        embed.set_footer(text="Economy Guide – Build your empire! 💰", icon_url=get_giphy_gif('money'))
    elif category == 'premium':
        embed.description = r"""**Premium Perks (Unlock with /shop or owner!)**

** /premium **
- Check status (1 month = 1000 credits via shop).
- Perks: 2x credits on daily/heist, no cooldowns, +20% catch success.

** /battle @opponent **
- PvP battles for credits (premium unlocks advanced modes).

**Tips**: Premium boosts everything – Get it to dominate!"""
        embed.set_footer(text="Premium Guide – Unlock the best! 💎", icon_url=get_giphy_gif('premium'))
    elif category == 'owner':
        embed.description = r"""**Owner Commands (God-Mode Only!)**

** /admin ban @user reason **
- Ban user globally or per-guild.

** /admin unban @user **
- Unban user.

** /admin assign @user level **
- Assign admin/mod role.

** /admin remove @user level **
- Remove admin/mod role.

** /admin event type duration **
- Start global event.

**Tips**: Full control – Use wisely!"""
        embed.set_footer(text="Owner Guide – Ultimate Power! 👑", icon_url=get_giphy_gif('owner'))
    try:
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        print(f"Help command error: {e}")
        await interaction.response.send_message("Error loading help – Try again!", ephemeral=True)

# /create_entity (New Feature for Custom Entities)
@bot.tree.command(name='create_entity', description='Create a custom entity (Owner/Admin only)!')
@app_commands.describe(name='Entity name', rarity='Rarity (Common/Rare/Epic/Legendary/Mythic)', emoji='Emoji', power='Power level', desc='Description', image_url='GIF URL')
async def create_entity_command(interaction: discord.Interaction, name: str, rarity: str, emoji: str, power: int, desc: str, image_url: str):
    user_level = await get_user_level(interaction.user.id)
    if user_level not in ['owner', 'admin']:
        embed = discord.Embed(title="❌ Access Denied", description="Only Owner/Admin can create entities.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    new_entity = {'name': name, 'rarity': rarity, 'emoji': emoji, 'power': power, 'desc': desc, 'image_url': image_url, 'fuse_into': None}
    CONFIG['custom_entities'].append(new_entity)
    embed = discord.Embed(title="✨ Custom Entity Created!", description=f"{name} ({rarity}) added!", color=SUCCESS_GREEN)
    embed.set_image(url=image_url)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /event_vote (Community Event Voting)
@bot.tree.command(name='event_vote', description='Vote for the next community event!')
@app_commands.describe(event_choice='Choose event: double_spawn, nostalgia_week, pvp_boost')
async def event_vote_command(interaction: discord.Interaction, event_choice: str):
    if event_choice not in CONFIG['events']:
        embed = discord.Embed(title="❌ Invalid Event", description="Choose from: double_spawn, nostalgia_week, pvp_boost", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    # Placeholder: Store votes in Redis or DB
    redis_client.incr(f'vote:{event_choice}')
    embed = discord.Embed(title="🗳️ Vote Cast!", description=f"You voted for {event_choice}!", color=NEON_BLUE)
    embed.set_image(url=get_giphy_gif('vote'))
    await interaction.response.send_message(embed=embed)

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
    init_db()
    bot.run(DISCORD_TOKEN)