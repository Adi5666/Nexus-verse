import discord
from discord.ext import commands, tasks
import aiosqlite
import json
import random
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import aiohttp
from collections import defaultdict
import requests  # For dashboard webhooks
import os  # For env vars

# === COLORS FOR EYE-CATCHING EMBEDS ===
NEON_BLUE = 0x00D4FF
NEON_PURPLE = 0x8B00FF
SUCCESS_GREEN = 0x00FF7F
ERROR_RED = 0xFF4500
PREMIUM_GOLD = 0xFFD700
ADMIN_SILVER = 0xC0C0C0
OFFICIAL_GLOW = 0xFF1493
DARK_BG = 0x0D1117

# === BOT SETUP ===
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Env Vars for Secrets (Safe for GitHub – No Hard-Codes)
OWNER_ID = int(os.getenv('OWNER_ID', '0'))  # Must set in deploy; 0 = invalid
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', None)
DASHBOARD_WEBHOOK_URL = os.getenv('DASHBOARD_WEBHOOK_URL', '')

# Config (Load or default – auto-creates if missing)
CONFIG_FILE = 'config.json'
try:
    with open(CONFIG_FILE, 'r') as f:
        CONFIG = json.load(f)
    print(f"✅ Loaded config from {CONFIG_FILE}")
except (FileNotFoundError, json.JSONDecodeError):
    CONFIG = {
        'entities': [
            {'name': 'Common Bot', 'rarity': 'Common', 'emoji': '🤖', 'power': 10, 'desc': 'Basic AI drone.', 'image_url': 'https://via.placeholder.com/128?text=Bot'},
            {'name': 'Ahri Fox', 'rarity': 'Rare', 'emoji': '🦊', 'power': 50, 'desc': 'Nine-tailed charmer.', 'image_url': 'https://ddragon.leagueoflegends.com/cdn/img/champion/loading/Ahri_0.jpg'},
            {'name': 'Dank Shiba', 'rarity': 'Epic', 'emoji': '🐕', 'power': 100, 'desc': 'Meme lord.', 'image_url': 'https://via.placeholder.com/128?text=Shiba'},
            {'name': 'Pikachu Warrior', 'rarity': 'Legendary', 'emoji': '⚡', 'power': 200, 'desc': 'Thunderbolt fusion.', 'image_url': 'https://via.placeholder.com/128?text=Pikachu'},
            {'name': 'Void Empress', 'rarity': 'Mythic', 'emoji': '🌌', 'power': 500, 'desc': 'Ultimate Ahri.', 'image_url': 'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif'}
        ],
        'events': ['double_spawn', 'meme_fest', 'pvp_tournament'],
        'default_spawn_rate': 1.0,
        'official_perks': {'spawn_multiplier': 3.0},
        'premium_cost': 1000,
        'catch_cooldown': 30,
        'pull_cost': 50,
        'dashboard_secret': 'change_me'  # Change in deploy env if using dashboard
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(CONFIG, f, indent=4)
    print(f"📝 Created default {CONFIG_FILE}")

ENTITIES = CONFIG['entities']
EVENTS = CONFIG['events']

DB_FILE = 'nexusverse.db'
rate_limits = defaultdict(list)
guild_limits = defaultdict(list)

# Startup Token Check (Prevents Run Without Token)
if DISCORD_TOKEN is None or DISCORD_TOKEN == '':
    raise ValueError("❌ DISCORD_TOKEN env var required! Set in Railway/Render.")
if OWNER_ID == 0:
    print("⚠️ OWNER_ID env var recommended for owner commands.")
# === DB INIT ===
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER DEFAULT 100,
                entities TEXT DEFAULT '[]',
                level INTEGER DEFAULT 1,
                pity_count INTEGER DEFAULT 0,
                premium_until TEXT DEFAULT NULL,
                daily_streak INTEGER DEFAULT 0,
                last_daily TEXT DEFAULT NULL,
                is_official_member BOOLEAN DEFAULT FALSE
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id INTEGER PRIMARY KEY,
                boosted BOOLEAN DEFAULT FALSE,
                admins TEXT DEFAULT '[]',
                mods TEXT DEFAULT '[]',
                prefix TEXT DEFAULT '!',
                is_official BOOLEAN DEFAULT FALSE,
                spawn_multiplier REAL DEFAULT 1.0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS bans (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                issuer_id INTEGER,
                timestamp TEXT,
                guild_id INTEGER DEFAULT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                issuer_id INTEGER,
                target_id INTEGER,
                guild_id INTEGER,
                timestamp TEXT
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
        await db.commit()

# === DB HELPERS ===
async def get_user_data(user_id: int) -> dict:
    async with aiosqlite.connect(DB_FILE) -> dict:
        cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        if row:
            data = dict(zip(['user_id', 'credits', 'entities', 'level', 'pity', 'premium_until', 'streak', 'last_daily', 'is_official_member'], row))
            data['entities'] = json.loads(data['entities'] or '[]')
            data['is_premium'] = data['premium_until'] and datetime.fromisoformat(data['premium_until']) > datetime.now()
            return data
        await db.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        await db.commit()
        return {'user_id': user_id, 'credits': 100, 'entities': [], 'level': 1, 'pity': 0, 'premium_until': None, 'is_premium': False, 'streak': 0, 'last_daily': None, 'is_official_member': False}

async def update_user_data(user_id: int, **kwargs):
    async with aiosqlite.connect(DB_FILE) as db:
        set_parts = []
        values = []
        for k, v in kwargs.items():
            set_parts.append(f"{k} = ?")
            if k == 'entities':
                values.append(json.dumps(v))
            elif k == 'premium_until':
                values.append(v.isoformat() if v else None)
            else:
                values.append(v)
        values.append(user_id)
        if set_parts:
            await db.execute(f'UPDATE users SET {", ".join(set_parts)} WHERE user_id = ?', values)
            await db.commit()

async def get_guild_data(guild_id: int) -> dict:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute('SELECT * FROM guilds WHERE guild_id = ?', (guild_id,))
        row = await cursor.fetchone()
        if row:
            data = dict(zip(['guild_id', 'boosted', 'admins', 'mods', 'prefix', 'is_official', 'spawn_multiplier'], row))
            data['admins'] = json.loads(data['admins'] or '[]')
            data['mods'] = json.loads(data['mods'] or '[]')
            return data
        await db.execute('INSERT INTO guilds (guild_id) VALUES (?)', (guild_id,))
        await db.commit()
        return {'guild_id': guild_id, 'boosted': False, 'admins': [], 'mods': [], 'prefix': '!', 'is_official': False, 'spawn_multiplier': 1.0}

async def update_guild_data(guild_id: int, **kwargs):
    async with aiosqlite.connect(DB_FILE) as db:
        set_parts = []
        values = []
        for k, v in kwargs.items():
            set_parts.append(f"{k} = ?")
            if k in ['admins', 'mods']:
                values.append(json.dumps(v))
            else:
                values.append(v)
        values.append(guild_id)
        if set_parts:
            await db.execute(f'UPDATE guilds SET {", ".join(set_parts)} WHERE guild_id = ?', values)
            await db.commit()

async def is_banned(user_id: int, guild_id: Optional[int] = None) -> Optional[dict]:
    async with aiosqlite.connect(DB_FILE) as db:
        params = [user_id]
        where = 'guild_id = ?' if guild_id else 'guild_id IS NULL'
        if guild_id:
            params.append(guild_id)
        cursor = await db.execute(f'SELECT reason, issuer_id, timestamp, guild_id FROM bans WHERE user_id = ? AND {where}', params)
        row = await cursor.fetchone()
        if row:
            return {'reason': row[0], 'issuer': row[1], 'timestamp': row[2], 'guild_id': row[3]}
    return None

async def ban_user(user_id: int, reason: str, issuer_id: int, guild_id: Optional[int] = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR REPLACE INTO bans (user_id, reason, issuer_id, timestamp, guild_id) VALUES (?, ?, ?, ?, ?)',
                         (user_id, reason, issuer_id, datetime.now().isoformat(), guild_id))
        await db.commit()

async def unban_user(user_id: int, guild_id: Optional[int] = None):
    async with aiosqlite.connect(DB_FILE) as db:
        params = [user_id]
        where = 'guild_id = ?' if guild_id else 'guild_id IS NULL'
        if guild_id:
            params.append(guild_id)
        await db.execute(f'DELETE FROM bans WHERE user_id = ? AND {where}', params)
        await db.commit()

async def log_audit(action: str, issuer_id: int, target_id: Optional[int] = None, guild_id: int = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT INTO audits (action, issuer_id, target_id, guild_id, timestamp) VALUES (?, ?, ?, ?, ?)',
                         (action, issuer_id, target_id, guild_id, datetime.now().isoformat()))
        await db.commit()

async def grant_premium(user_id: int, duration_months: int = 1):
    end_time = datetime.now() + timedelta(days=30 * duration_months)
    await update_user_data(user_id, premium_until=end_time)

async def get_global_event() -> Optional[str]:
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute('SELECT event_type FROM global_events WHERE end_time > ? LIMIT 1', (datetime.now().isoformat(),))
        row = await cursor.fetchone()
        return row[0] if row else None

async def start_global_event(event_type: str, duration_hours: int = 24):
    end_time = datetime.now() + timedelta(hours=duration_hours)
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('DELETE FROM global_events')
        await db.execute('INSERT INTO global_events (event_type, start_time, end_time) VALUES (?, ?, ?)',
                         (event_type, datetime.now().isoformat(), end_time.isoformat()))
        await db.commit()
    # Broadcast to all guilds
    for guild in bot.guilds:
        channel = guild.system_channel
        if channel:
            embed = discord.Embed(title=f"🌌 GLOBAL EVENT: {event_type.upper()}!", description=f"Affects all servers! Duration: {duration_hours}h", color=NEON_PURPLE)
            await channel.send(embed=embed)

async def get_current_spawn_rate(guild_id: int, user_id: int) -> float:
# === BOT EVENTS ===
@bot.event
async def on_ready():
    await init_db()
    print(f'🌌 NexusVerse Online! Owner: <@{OWNER_ID}> | Guilds: {len(bot.guilds)}')
    try:
        synced = await bot.tree.sync()
        print(f'🔮 Synced {len(synced)} commands.')
    except Exception as e:
        print(f'⚠️ Sync Error: {e}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    ban_info = await is_banned(message.author.id, message.guild.id if message.guild else None) or await is_banned(message.author.id)
    if ban_info:
        try:
            await message.delete()
        except:
            pass
        embed = discord.Embed(
            title="🚫 NEXUS BAN ENFORCED: ACCESS DENIED ⚠️",
            description=f"**User :** {message.author.mention} ({message.author.name})\n**Status:** Banned.\n\n**Reason:** {ban_info['reason']}\n**Issued By:** <@{ban_info['issuer']}>\n**Timestamp:** {ban_info['timestamp']}\n\n*Exiled from the Nexus for code violations. This ban is {'server-specific' if ban_info['guild_id'] else 'global'}*\n\n**Impacts:** Commands disabled, messages deleted, economy frozen.\n\n**Appeal:**\n1. Reflect.\n2. DM issuer or owner.\n3. Show change.\n4. Wait 24h-7d.\n\n**Rules:** No spam/harass/exploits. Play fair!\n\n[🔒 Locked | Appeal wisely...]",
            color=ERROR_RED
        )
        embed.set_thumbnail(url="https://media.giphy.com/media/26ufnwz3wDUli7GU0/giphy.gif")
        embed.set_footer(text="NexusVerse v1.0 | Security Protocol")
        await message.channel.send(embed=embed, delete_after=60)
        return
    await bot.process_commands(message)

@bot.event
async def on_guild_join(guild):
    await update_guild_data(guild.id, admins=[guild.owner_id])

# === HELP UI WITH SELECT MENU ===
class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.select(placeholder="Select Category...", options=[
        discord.SelectOption(label="Core", value="core", description="Catch, Pull, Profile"),
        discord.SelectOption(label="Economy", value="economy", description="Quest, Shop, Heist"),
        discord.SelectOption(label="Social", value="social", description="Battle, Guild, Leaderboard"),
        discord.SelectOption(label="Premium", value="premium", description="Unlock power!"),
        discord.SelectOption(label="Mod/Admin", value="modadmin", description="Control tools")
    ])
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        categories = {
            "core": "• /catch - Warp-catch entities! (Cooldown: 30s, premium bypass)\n• /pull - Gacha packs (50 credits, pity system)\n• /profile - View your empire stats and collection.",
            "economy": "• /quest - Daily tasks for credits and streaks.\n• /shop - Buy upgrades/evolutions with credits.\n• /heist @user - Steal credits (risk of failure).\n• /trade @user entity_id - Exchange entities.",
            "social": "• /battle @user - PvP with your strongest entity.\n• /guild create/join - Form alliances for shared boosts.\n• /leaderboard - Global top 10 by level/power.",
            "premium": "💎 Perks: 2x credits/rates, no cooldowns, exclusive evos/skins, PvP priority. Buy with 1000 credits or admin grant! (Desirable for fast progression).",
            "modadmin": "Mods: /mod warn/mute/logs (local control).\nAdmins: /admin event (global!)/premium grant/config tweak (feels like Overseer power).\nOwner: /owner ban/stats/shutdown (god-mode)."
        }
        embed = discord.Embed(title=f"🔮 {select.values[0].upper()} COMMANDS", description=categories[select.values[0]], color=NEON_BLUE)
        embed.set_footer(text="Use /help for more | Premium users get priority support!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='help', description='🔮 Interactive NexusVerse Guide')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌌 Welcome to NexusVerse!",
        description="The ultimate cyberpunk collector empire. Select a category below for commands. Premium users: Enjoy unlimited access! 💎",
        color=NEON_PURPLE
    )
    embed.set_thumbnail(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Cyberpunk GIF
    embed.add_field(name="Quick Start", value="• /catch to begin collecting\n• /profile to check progress\n• /quest for daily rewards", inline=False)
    embed.set_footer(text="Official servers: 3x rates! | v1.0")
    await interaction.response.send_message(embed=embed, view=HelpView(), ephemeral=False)

# === CORE COMMANDS ===
@bot.tree.command(name='catch', description='🌌 Warp-catch a Nexus Entity! (Boosted in official/events/premium)')
async def catch_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    if not rate_limit_check(user_id):
        embed = discord.Embed(title="⏳ NEXUS RECHARGE ACTIVE", description="Rate limit (5/min) to prevent spam for fair play. Premium skips this! 💎 Wait 60s or quest for boosts.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    data = await get_user_data(user_id)
    guild_data = await get_guild_data(guild_id)
    rate = await get_current_spawn_rate(guild_id, user_id)
    await interaction.response.defer()
    
    # Random entity with rarity (boosted by rate)
    rarity_roll = random.random() * rate
    if rarity_roll < 0.01:  # Mythic 1%
        entity = random.choice([e for e in ENTITIES if e['rarity'] == 'Mythic'])
    elif rarity_roll < 0.05:  # Legendary 4%
        entity = random.choice([e for e in ENTITIES if e['rarity'] == 'Legendary'])
    elif rarity_roll < 0.2:  # Epic 15%
        entity = random.choice([e for e in ENTITIES if e['rarity'] == 'Epic'])
    elif rarity_roll < 0.5:  # Rare 30%
        entity = random.choice([e for e in ENTITIES if e['rarity'] == 'Rare'])
    else:
        entity = random.choice([e for e in ENTITIES if e['rarity'] == 'Common'])
    
    # Success rate boosted by level + rate
    success_rate = min(0.3 + (data['level'] * 0.05) * rate, 0.9)
    if random.random() < success_rate:
        data['entities'].append(entity)
        bonus_credits = entity['power'] // 5 * (2 if data['is_premium'] else 1)
        data['credits'] += bonus_credits
        if len(data['entities']) % 5 == 0:
            data['level'] += 1
        data['pity'] = 0
        await update_user_data(user_id, entities=data['entities'], credits=data['credits'], level=data['level'], pity=data['pity'])
        
        # Eye-Catching Success Embed
        color = PREMIUM_GOLD if data['is_premium'] else SUCCESS_GREEN
        if guild_data['is_official']:
            color = OFFICIAL_GLOW
            desc = f"🏛️ **OFFICIAL SERVER BOOST!** {entity['desc']}\n\nPower: +{entity['power']} | Bonus Credits: +{bonus_credits}\nCollection: {len(data['entities'])} | Level: {data['level']} ↑"
        else:
            desc = f"*{entity['desc']}*\n\nPower: +{entity['power']} | Bonus Credits: +{bonus_credits}\nCollection: {len(data['entities'])} | Level: {data['level']} ↑"
        embed = discord.Embed(
            title=f"🚀 WARP SUCCESS: {entity['name'].upper()} CAPTURED! 🌟 {entity['emoji']}",
            description=desc,
            color=color
        )
        embed.set_thumbnail(url=entity['image_url'])
        # ASCII Confetti
        confetti = "🎉 *Neural Surge!* 🎉\n \\o/ Victory! \\o/\n🎉 Level Up Hype! 🎉"
        embed.add_field(name="Warp Echo", value=confetti, inline=False)
        embed.set_footer(text="Share your triumph! | Streak Active" if data['streak'] > 0 else "Daily Quest for more!")
        
        view = discord.ui.View(timeout=300)
        view.add_item(discord.ui.Button(label="View Profile", style=discord.ButtonStyle.primary, custom_id="profile_button"))  # Handles in on_interaction if needed
        await interaction.followup.send(embed=embed, content=f"{interaction.user.mention} – The Nexus bows! {entity['emoji']}", view=view)
    else:
        data['pity'] += 1
        await update_user_data(user_id, pity=data['pity'])
        # Motivational Failure Embed
        color = ERROR_RED
        if guild_data['is_official']:
            color = OFFICIAL_GLOW
            desc = f"💥 **Official Glitch – But Pity Builds!** {entity['desc']}\n\nPity: {data['pity']}/10 (Rare soon!)"
        else:
            desc = f"💥 *Dimensional Slip!* {entity['desc']}\n\nPity: {data['pity']}/10 (Rare incoming!)"
        embed = discord.Embed(
            title=f"⚡ RIFT GLITCH: {entity['name']} ESCAPED! 😤 {entity['emoji']}",
            description=desc,
            color=color
        )
                embed.set_image(url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")  # Glitch GIF
        pity_bar = "🟢" * data['pity'] + "🔴" * (10 - data['pity'])
        embed.add_field(name="Pity Progress", value=pity_bar, inline=False)
        embed.add_field(name="Tip", value="Premium: +20% success & instant retry! 💎 Or upgrade in /shop.", inline=False)
        embed.set_footer(text="Persistence forges legends... Next warp soon!")
        view = discord.ui.View(timeout=300)
        view.add_item(discord.ui.Button(label="Daily Quest", style=discord.ButtonStyle.success, custom_id="quest_button"))
        await interaction.followup.send(embed=embed, content=f"{interaction.user.mention} – Close call! Keep warping...")

@bot.tree.command(name='pull', description='🔮 Gacha pull for Mystery Pack! (50 credits, pity guaranteed rare)')
async def pull_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if not rate_limit_check(user_id):
        embed = discord.Embed(title="⏳ RECHARGE", description="Rate limit hit. Premium: Unlimited pulls! 💎", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    data = await get_user_data(user_id)
    if data['credits'] < CONFIG['pull_cost']:
        embed = discord.Embed(title="⚠️ Low Quantum Credits", description=f"Need {CONFIG['pull_cost']} QC. /quest to farm!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    await interaction.response.defer()
    data['credits'] -= CONFIG['pull_cost']
    data['pity'] += 1
    
    # Pity & Rarity Logic
    if data['pity'] >= 10:
        entity = random.choice([e for e in ENTITIES if e['rarity'] in ['Legendary', 'Mythic']])
        data['pity'] = 0
        bonus = random.randint(100, 500)
    else:
        rarities = ['Common', 'Rare', 'Epic']
        entity = random.choice([e for e in ENTITIES if e['rarity'] in rarities])
        bonus = random.randint(20, 100) if entity['rarity'] in ['Epic'] else 0
    
    data['entities'].append(entity)
    data['credits'] += bonus * (2 if data['is_premium'] else 1)
    await update_user_data(user_id, credits=data['credits'], entities=data['entities'], pity=data['pity'])
    
    # Eye-Catching Pull Embed
    color = NEON_PURPLE if entity['rarity'] == 'Mythic' else SUCCESS_GREEN
    desc = f"**{entity['name']}** breaches the void! *{entity['desc']}*\nRarity: {entity['rarity']} | Power: {entity['power']}\nBonus: +{bonus} QC (x2 premium!)"
    embed = discord.Embed(title=f"🌌 PULL EXECUTED: {entity['rarity']} HIT! {entity['emoji']}", description=desc, color=color)
    embed.set_thumbnail(url=entity['image_url'])
    if data['is_premium']:
        embed.add_field(name="Premium Glow", value="Your entity shines gold – exclusive evolution unlocked! ✨", inline=True)
    embed.add_field(name="Gacha Log", value=f"Cost: -{CONFIG['pull_cost']} | Total QC: {data['credits']}\nPity Reset: {'Yes!' if data['pity'] == 0 else f'{data['pity']}/10'}", inline=False)
    embed.set_footer(text="Warp your empire! Daily limit: 10 | Share for luck boost")
    await interaction.followup.send(embed=embed, content=f"{interaction.user.mention} – Epic pull! {entity['emoji']}")

# === ECONOMY COMMANDS ===
@bot.tree.command(name='profile', description='📊 Holographic Nexus Profile – View Stats & Collection')
async def profile_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    guild_data = await get_guild_data(interaction.guild.id if interaction.guild else 0)
    
    # Holographic Embed
    color = PREMIUM_GOLD if data['is_premium'] else NEON_BLUE
    if guild_data['is_official']:
        color = OFFICIAL_GLOW
        desc = f"🏛️ **OFFICIAL MEMBER STATUS**"
    else:
        desc = f"**Nexus Avatar:** {interaction.user.name}"
    desc += f"\n**Level:** {data['level']} | **QC:** {data['credits']} 💎\n**Entities:** {len(data['entities'])} / ∞\n**Streak:** {data['streak']} days | Premium: {'Active! 💎' if data['is_premium'] else 'Grind for it!'}\n**Rarest:** {max((e['rarity'] for e in data['entities']), default='None', key=lambda r: ['Common', 'Rare', 'Epic', 'Legendary', 'Mythic'].index(r))}"
    
    embed = discord.Embed(title=f"🔮 {interaction.user.name}'s NEXUS EMPIRE", description=desc, color=color)
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
    # Progress Bar for Level
    level_bar = "🟢" * min(data['level'], 20) + "🔵" * max(0, 20 - data['level'])
    embed.add_field(name="Power Level", value=level_bar, inline=False)
    if data['is_premium']:
        embed.add_field(name="Premium Perks", value="2x Rewards | No Limits | Golden Skins", inline=True)
    if data['entities']:
        top_entity = max(data['entities'], key=lambda e: e['power'])
        embed.add_field(name="Strongest Entity", value=f"{top_entity['name']} {top_entity['emoji']} (Power: {top_entity['power']})", inline=True)
    embed.set_footer(text="Evolve your collection! /pull for more | Official servers get boosts")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='quest', description='📜 Daily Quest – Farm Credits & Streaks!')
async def quest_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    now = datetime.now().date().isoformat()
    if data['last_daily'] == now:
        embed = discord.Embed(title="📜 Quest Complete Today!", description=f"Streak: {data['streak']} days. Tomorrow for more! (Premium: Double rewards)", color=SUCCESS_GREEN)
        embed.add_field(name="Streak Perk", value="7+ days: Free pull tomorrow! 🔥", inline=False)
        await interaction.response.send_message(embed=embed)
        return
    # Random Quest Reward (expand with tasks like "Catch 3 entities")
    reward = random.randint(50, 200) * (2 if data['is_premium'] else 1)
    data['credits'] += reward
    data['streak'] = data['streak'] + 1 if data['last_daily'] else 1
    data['last_daily'] = now
    if data['streak'] >= 7:
        data['credits'] += 100  # Bonus
        bonus_msg = "\n**7-DAY STREAK BONUS: +100 QC!** 🎉"
    else:
        bonus_msg = ""
    await update_user_data(user_id, credits=data['credits'], streak=data['streak'], last_daily=now)
    
    embed = discord.Embed(title="📜 QUEST COMPLETE: Dimensional Patrol!", description=f"Reward: +{reward} QC!{bonus_msg}\nStreak: {data['streak']} days\n*Task: Scanned rifts for anomalies.*", color=SUCCESS_GREEN)
    embed.add_field(name="Streak Bonus", value=f"{'Double rewards tomorrow!' if data['streak'] >= 3 else 'Keep going!'}", inline=True)
    if data['is_premium']:
        embed.add_field(name="Premium Boost", value="x2 Rewards Active! 💎", inline=True)
    embed.set_thumbnail(url="https://media.giphy.com/media/26ufnwz3wDUli7GU0/giphy.gif")  # Quest GIF
    embed.set_footer(text="Daily reset at midnight. /heist for risky extras!")
    await interaction.response.send_message(embed=embed, content=f"{interaction.user.mention} – Quest logged! +{reward} QC")

@bot.tree.command(name='shop', description='🛒 Nexus Shop – Buy Upgrades & Evolutions')
async def shop_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    embed = discord.Embed(title="🛒 NEXUS MARKETPLACE", description="Spend QC on power-ups! Premium users: 20% off.", color=NEON_PURPLE)
    items = [
        {"name": "Entity Evolution (+50 Power)", "cost": 200, "desc": "Upgrade a common to rare."},
        {"name": "Credit Booster (x1.5 Next Quest)", "cost": 100, "desc": "Temporary buff."},
        {"name": "Pity Reset", "cost": 50, "desc": "Clear pity for fresh pulls."},
        {"name": "Premium (1 Month)", "cost": CONFIG['premium_cost'], "desc": "Unlock 2x boosts & exclusives! 💎"}
    ]
    for item in items:
        discount = int(item['cost'] * 0.8) if data['is_premium'] else item['cost']
        embed.add_field(name=item['name'], value=f"{item['desc']} | Cost: {discount} QC", inline=False)
    embed.set_footer(text="Use /buy <item_name> to purchase. Grind /quest for QC!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='buy', description='💰 Purchase from Shop (e.g., /buy Premium)')
async def buy_command(interaction: discord.Interaction, item: str):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    items = {
        "entity evolution": {"cost": 200, "effect": lambda: print("Evolve entity!") },  # Placeholder; expand
        "credit booster": {"cost": 100, "effect": lambda: None},
        "pity reset": {"cost": 50, "effect": lambda: update_user_data(user_id, pity=0)},
        "premium": {"cost": CONFIG['premium_cost'], "effect": lambda: grant_premium(user_id, 1)}
    }
    item_lower = item.lower()
    if item_lower not in items:
        embed = discord.Embed(title="❌ Invalid Item", description="Check /shop for options.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    item_info = items[item_lower]
    cost = int(item_info['cost'] * 0.8) if data['is_premium'] else item_info['cost']
    if data['credits'] < cost:
        embed = discord.Embed(title="⚠️ Insufficient QC", description=f"Need {cost} QC. /quest to earn!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    data['credits'] -= cost
    item_info['effect']()  # Apply effect
    await update_user_data(user_id, credits=data['credits'])
    if item_lower == "premium":
        embed = discord.Embed(title="💎 PREMIUM UNLOCKED!", description="1 month of glory: 2x rates, no limits, exclusives! ✨", color=PREMIUM_GOLD)
    else:
        embed = discord.Embed(title="✅ Purchase Successful!", description=f"{item.title()} acquired for {cost} QC!", color=SUCCESS_GREEN)
    embed.add_field(name="Balance", value=f"QC: {data['credits']}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='heist', description='💰 Risky Heist – Steal from Another User! (50% fail chance)')
async def heist_command(interaction: discord.Interaction, target: discord.Member):
    user_id = interaction.user.id
    target_id = target.id
    if target_id == user_id:
        embed = discord.Embed(title="🚫 Self-Heist Invalid", description="Can't rob yourself! Try a rival.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    if not rate_limit_check(user_id, limit=3, window=300):  # 3/5min for risky action
        embed = discord.Embed(title="⏳ Heist Cooldown", description="High-risk ops limited. Premium: Unlimited!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    data = await get_user_data(user_id)
    target_data = await get_user_data(target_id)
    if target_data['credits'] < 10:
        embed = discord.Embed(title="💸 Empty Vault", description=f"{target.mention} has no QC to steal! Target richer foes.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    
    await interaction.response.defer()
    success_chance = 0.5 * (1.5 if data['is_premium'] else 1)  # Premium 75% edge
    amount = random.randint(10, min(100, target_data['credits'] // 2))
    if random.random() < success_chance:
        target_data['credits'] -= amount
        data['credits'] += amount * (2 if data['is_premium'] else 1)
        await update_user_data(user_id, credits=data['credits'])
        await update_user_data(target_id, credits=target_data['credits'])
        await log_audit("heist_success", user_id, target_id, interaction.guild.id if interaction.guild else None)
        embed = discord.Embed(title="💰 HEIST SUCCESS! 🤑", description=f"Stole {amount} QC from {target.mention}!\nYour Vault: +{amount} (x2 premium!)", color=SUCCESS_GREEN)
        embed.set_image(url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")  # Heist GIF
    else:
        penalty = amount // 2
        data['credits'] = max(0, data['credits'] - penalty)
        await update_user_data(user_id, credits=data['credits'])
        await log_audit("heist_fail", user_id, target_id, interaction.guild.id if interaction.guild else None)
        embed = discord.Embed(title="💥 HEIST BUSTED! 😵", description=f"Caught by {target.mention}'s security! Penalty: -{penalty} QC\nTip: Premium boosts success to 75%!", color=ERROR_RED)
        embed.add_field(name="Risk Reminder", value="Heists: 50% win, but high reward. Play smart!", inline=False)
    embed.set_footer(text="Audit logged. Fair play in the Nexus!")
    await interaction.followup.send(embed=embed, content=f"{interaction.user.mention} vs {target.mention} – Heist outcome!")

@bot.tree.command(name='trade', description='🔄 Trade Entity with User (e.g., /trade @user Ahri Fox)')
async def trade_command(interaction: discord.Interaction, target: discord.Member, entity_name: str):
    user_id = interaction.user.id
    target_id = target.id
    data = await get_user_data(user_id)
    target_data = await get_user_data(target_id)
    entity = next((e for e in data['entities'] if e['name'].lower() == entity_name.lower()), None)
    if not entity:
        embed = discord.Embed(title="❌ Entity Not Found", description=f"You don't own '{entity_name}'. Check /profile.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    # Simple trade (in prod, add DM confirmation buttons for both)
    if len(target_data['entities']) >= 50:  # Collection limit example
        embed = discord.Embed(title="⚠️ Trade Denied", description=f"{target.mention} has full collection (50 max).", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    data['entities'].remove(entity)
    target_data['entities'].append(entity)
    await update_user_data(user_id, entities=data['entities'])
    await update_user_data(target_id, entities=target_data['entities'])
    await log_audit("trade", user_id, target_id, interaction.guild.id if interaction.guild else None)
    embed = discord.Embed(title="🔄 TRADE COMPLETE!", description=f"{entity['name']} {entity['emoji']} traded to {target.mention}!\nPower Transfer: {entity['power']}", color=NEON_BLUE)
    embed.set_thumbnail(url=entity['image_url'])
    embed.add_field(name="Trade Tip", value="Premium: No fees + bonus value in future trades!", inline=True)
    embed.set_footer(text="Build alliances! /guild for shared boosts.")
    await interaction.response.send_message(embed=embed, content=f"{interaction.user.mention} ↔ {target.mention}")
# === SOCIAL COMMANDS ===
@bot.tree.command(name='battle', description='⚔️ PvP Battle – Pit Your Strongest Entity vs User!')
async def battle_command(interaction: discord.Interaction, opponent: discord.Member):
    user_id = interaction.user.id
    opp_id = opponent.id
    if user_id == opp_id:
        embed = discord.Embed(title="🚫 Solo Battle Invalid", description="Find a worthy rival!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    data = await get_user_data(user_id)
    opp_data = await get_user_data(opp_id)
    if not data['entities'] or not opp_data['entities']:
        embed = discord.Embed(title="⚔️ No Entities", description="Both need collections to battle! /catch first.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    if not rate_limit_check(user_id, limit=2, window=180):  # 2/3min for PvP
        embed = discord.Embed(title="⏳ Arena Cooldown", description="Battles limited for balance. Premium: Unlimited duels!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    
    await interaction.response.defer()
    # PvP Logic: Strongest entity (premium +20% power edge)
    my_power = max(e['power'] for e in data['entities']) * (1.2 if data['is_premium'] else 1)
    opp_power = max(e['power'] for e in opp_data['entities']) * (1.2 if opp_data['is_premium'] else 1)
    reward = random.randint(50, 150)
    if my_power > opp_power:
        data['credits'] += reward
        await update_user_data(user_id, credits=data['credits'])
        result = f"VICTORY! {interaction.user.mention} dominates with {int(my_power)} power vs {int(opp_power)}!\nReward: +{reward} QC"
        color = SUCCESS_GREEN
        await log_audit("battle_win", user_id, opp_id, interaction.guild.id if interaction.guild else None)
    else:
        opp_data['credits'] += reward
        await update_user_data(opp_id, credits=opp_data['credits'])
        result = f"DEFEAT! {opponent.mention} triumphs with {int(opp_power)} power vs {int(my_power)}.\nBetter luck next rift!"
        color = ERROR_RED
        await log_audit("battle_loss", user_id, opp_id, interaction.guild.id if interaction.guild else None)
    
    embed = discord.Embed(title="⚔️ NEXUS ARENA BATTLE", description=result, color=color)
    embed.add_field(name="Your Top Power", value=f"{int(my_power)}", inline=True)
    embed.add_field(name="Opponent's Power", value=f"{int(opp_power)}", inline=True)
    if data['is_premium']:
        embed.add_field(name="Premium Edge", value="+20% Power Boost! 💎", inline=True)
    embed.set_thumbnail(url="https://media.giphy.com/media/26ufnwz3wDUli7GU0/giphy.gif")  # Battle GIF
    embed.set_footer(text="Guild members get team buffs. /guild join!")
    await interaction.followup.send(embed=embed, content=f"{interaction.user.mention} vs {opponent.mention} – Arena clash!")

# === SOCIAL COMMANDS ===
@bot.tree.command(name='battle', description='⚔️ PvP Battle – Pit Your Strongest Entity vs User!')
async def battle_command(interaction: discord.Interaction, opponent: discord.Member):
    user_id = interaction.user.id
    opp_id = opponent.id
    if user_id == opp_id:
        embed = discord.Embed(title="🚫 Solo Battle Invalid", description="Find a worthy rival!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    data = await get_user_data(user_id)
    opp_data = await get_user_data(opp_id)
    if not data['entities'] or not opp_data['entities']:
        embed = discord.Embed(title="⚔️ No Entities", description="Both need collections to battle! /catch first.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    if not rate_limit_check(user_id, limit=2, window=180):  # 2/3min for PvP
        embed = discord.Embed(title="⏳ Arena Cooldown", description="Battles limited for balance. Premium: Unlimited duels!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)
        return
    
    await interaction.response.defer()
    # PvP Logic: Strongest entity (premium +20% power edge)
    my_power = max(e['power'] for e in data['entities']) * (1.2 if data['is_premium'] else 1)
    opp_power = max(e['power'] for e in opp_data['entities']) * (1.2 if opp_data['is_premium'] else 1)
    reward = random.randint(50, 150)
    if my_power > opp_power:
        data['credits'] += reward
        await update_user_data(user_id, credits=data['credits'])
        result = f"VICTORY! {interaction.user.mention} dominates with {int(my_power)} power vs {int(opp_power)}!\nReward: +{reward} QC"
        color = SUCCESS_GREEN
        await log_audit("battle_win", user_id, opp_id, interaction.guild.id if interaction.guild else None)
    else:
        opp_data['credits'] += reward
        await update_user_data(opp_id, credits=opp_data['credits'])
        result = f"DEFEAT! {opponent.mention} triumphs with {int(opp_power)} power vs {int(my_power)}.\nBetter luck next rift!"
        color = ERROR_RED
        await log_audit("battle_loss", user_id, opp_id, interaction.guild.id if interaction.guild else None)
    
    embed = discord.Embed(title="⚔️ NEXUS ARENA BATTLE", description=result, color=color)
    embed.add_field(name="Your Top Power", value=f"{int(my_power)}", inline=True)
    embed.add_field(name="Opponent's Power", value=f"{int(opp_power)}", inline=True)
    if data['is_premium']:
        embed.add_field(name="Premium Edge", value="+20% Power Boost! 💎", inline=True)
    embed.set_thumbnail(url="https://media.giphy.com/media/26ufnwz3wDUli7GU0/giphy.gif")  # Battle GIF
    embed.set_footer(text="Guild members get team buffs. /guild join!")
    await interaction.followup.send(embed=embed, content=f"{interaction.user.mention} vs {opponent.mention} – Arena clash!")

@bot.tree.command(name='guild', description='🏛️ Create or Join Nexus Guild – Shared Boosts! (e.g., /guild create MyEmpire)')
async def guild_command(interaction: discord.Interaction, action: str = "create", name: Optional[str] = None):
    guild_id = interaction.guild.id if interaction.guild else 0
    user_id = interaction.user.id
    guild_data = await get_guild_data(guild_id)
    if action == "create":
        if not name:
            embed = discord.Embed(title="❌ Missing Name", description="Use /guild create <name> to form alliance.", color=ERROR_RED)
            await interaction.response.send_message(embed=embed)
            return
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="🚫 Admin Required", description="Only server admins can create guilds!", color=ERROR_RED)
            await interaction.response.send_message(embed=embed)
            return
        # Set guild as boosted ( +10% rates, shared quests)
        guild_data['boosted'] = True
        guild_data['admins'].append(user_id)  # Creator as admin
        await update_guild_data(guild_id, boosted=True, admins=guild_data['admins'])
        embed = discord.Embed(title="🏛️ GUILD FORMED!", description=f"{name} rises in the Nexus! Server-wide: +10% spawn rates & team events.\nInvite members with /guild join <name>.", color=ADMIN_SILVER)
        embed.add_field(name="Guild Perks", value="Shared quests, battle alliances, official boosts if flagged via dashboard.", inline=False)
        embed.set_thumbnail(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Alliance GIF
    elif action == "join":
        if guild_data['boosted']:
            # Add to members (simplified; expand with members list)
            embed = discord.Embed(title="🏛️ Joined Guild!", description=f"Welcome to {name or 'the alliance'}! Enjoy +10% rates & team events.\n*Your contributions boost the empire.*", color=SUCCESS_GREEN)
            embed.add_field(name="Next", value="Use /battle with allies for combo bonuses!", inline=False)
        else:
            embed = discord.Embed(title="❌ No Guild Yet", description="Create one first with /guild create <name>.", color=ERROR_RED)
    else:
        embed = discord.Embed(title="❌ Invalid Action", description="Use 'create <name>' or 'join <name>'.", color=ERROR_RED)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='leaderboard', description='🏆 Global Leaderboard – Top Empires! (level or power)')
async def leaderboard_command(interaction: discord.Interaction, type: str = "level"):
    await interaction.response.defer()
    async with aiosqlite.connect(DB_FILE) as db:
        if type == "level":
            cursor = await db.execute('SELECT user_id, level FROM users ORDER BY level DESC LIMIT 10')
        elif type == "power":
            # Sum entity powers (JSON query)
            cursor = await db.execute('''
                SELECT u.user_id, COALESCE(SUM(json_extract(e.value, '$.power')), 0) as total_power 
                FROM users u 
                LEFT JOIN json_each(u.entities) e ON 1=1 
                GROUP BY u.user_id 
                ORDER BY total_power DESC LIMIT 10
            ''')
        else:
            embed = discord.Embed(title="❌ Invalid Type", description="Use 'level' or 'power'.", color=ERROR_RED)
            await interaction.followup.send(embed=embed)
            return
        rows = await cursor.fetchall()
    
    embed = discord.Embed(title=f"🏆 NEXUS {type.upper()} LEADERBOARD", description="Top 10 Dominators!", color=NEON_PURPLE)
    if not rows:
        embed.description = "No data yet – Start collecting to climb!"
    rank = 1
    for row in rows:
        user_id, score = row
        try:
            user = await bot.fetch_user(user_id)
            medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"#{rank}"
            embed.add_field(name=f"{medal} {user.name}", value=f"Score: {score}", inline=False)
        except discord.NotFound:
            pass  # Skip invalid users
        rank += 1
    embed.set_footer(text="Premium users climb faster! /profile to check your rank. | Official servers boost scores.")
    await interaction.followup.send(embed=embed)
# === PREMIUM COMMANDS (Desirable: 2x Boosts, Exclusives, No Limits – Grind/Buy for Glory!) ===
@bot.tree.command(name='premium', description='💎 Manage Premium – Unlock Empire Perks! (Status/Buy/Grant)')
async def premium_command(interaction: discord.Interaction, sub: str = "status"):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    if sub == "status":
        if data['is_premium']:
            end = datetime.fromisoformat(data['premium_until'])
            days_left = max(0, (end - datetime.now()).days)
            desc = f"**Active Until:** {days_left} days left.\n**Perks:** 2x Credits/Rates | No Cooldowns | Exclusive Evolutions (Golden Skins) | PvP +20% Edge | Custom Embeds\n*Your empire glows – rivals envy the power!*"
            color = PREMIUM_GOLD
        else:
            desc = f"**Not Active.** Grind 1000 QC to buy or ask admin!\n**Why Premium?** Accelerate to mythics, skip grinds, dominate leaderboards. Resell access in trades for profit!"
            color = NEON_BLUE
        embed = discord.Embed(title="💎 PREMIUM STATUS", description=desc, color=color)
        embed.add_field(name="Buy Now", value=f"Cost: {CONFIG['premium_cost']} QC (/buy Premium) | Or /premium grant (admin)", inline=False)
        embed.set_thumbnail(url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")  # Glow GIF
        embed.set_footer(text="Premium: The path to Nexus legend. 💎")
        await interaction.response.send_message(embed=embed)
       elif sub == "buy":
        if data['is_premium']:
            embed = discord.Embed(title="💎 Already Premium!", description="Your glow is active. Extend later?", color=PREMIUM_GOLD)
            await interaction.response.send_message(embed=embed)
            return
        if data['credits'] < CONFIG['premium_cost']:
            embed = discord.Embed(title="⚠️ Insufficient QC", description=f"Need {CONFIG['premium_cost']} QC for 1 month. /quest to grind!", color=ERROR_RED)
            embed.add_field(name="Why Buy?", value="2x rates, no cooldowns, golden entities – dominate without sweat! 💎", inline=False)
            await interaction.response.send_message(embed=embed)
            return
        data['credits'] -= CONFIG['premium_cost']
        await grant_premium(user_id, 1)  # 1 month
        await update_user_data(user_id, credits=data['credits'])
        await log_audit("premium_buy", user_id, guild_id=interaction.guild.id if interaction.guild else None)
        embed = discord.Embed(title="💎 PREMIUM UNLOCKED – EMPIRE ASCENDS!", description="1 month activated! Perks: 2x Credits/Rates | Unlimited Actions | Exclusive Mythic Evolutions | PvP Priority\n*Your name now glows in embeds – others will notice.*", color=PREMIUM_GOLD)
        embed.add_field(name="Balance Update", value=f"QC Remaining: {data['credits']}", inline=True)
        embed.set_image(url="https://media.giphy.com/media/26ufnwz3wDUli7GU0/giphy.gif")  # Glow/upgrade GIF
        embed.set_footer(text="Resell premium access in trades for profit! | Grind smarter, not harder.")
        await interaction.response.send_message(embed=embed, content=f"{interaction.user.mention} – Welcome to the elite! ✨")
    elif sub == "grant":
        if not (interaction.user.id == OWNER_ID or interaction.user.guild_permissions.administrator):
            embed = discord.Embed(title="🚫 Access Denied", description="Only owners/admins can grant premium!", color=ERROR_RED)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        # Expect target as option; for simplicity, use message content or add param (expand later)
        # Placeholder: Grant to self or prompt; in full, /premium grant @user [months:1]
        target_id = user_id  # Default to self; adjust for param
        duration = 1  # Default 1 month
        await grant_premium(target_id, duration)
        await log_audit("premium_grant", user_id, target_id, interaction.guild.id if interaction.guild else None)
        try:
            target_user = await bot.fetch_user(target_id)
            embed = discord.Embed(title="🔑 PREMIUM GRANTED (Admin Power)", description=f"{target_user.mention} receives {duration} month(s) of premium!\n*Official perk: Boost your community.*", color=ADMIN_SILVER)
            embed.add_field(name="Perks Activated", value="2x Boosts | Exclusives | No Limits – For loyal members!", inline=False)
        except:
            embed = discord.Embed(title="🔑 PREMIUM GRANTED", description=f"User  ID {target_id} upgraded for {duration} month(s).", color=ADMIN_SILVER)
        embed.set_footer(text="Use wisely – Builds empire loyalty!")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="❌ Invalid Sub", description="Use 'status', 'buy', or 'grant' (admin).", color=ERROR_RED)
        await interaction.response.send_message(embed=embed)

# === FINAL BOT RUN (Add This at the Very End of the File) ===
@bot.event
async def on_ready():
    await init_db()  # Ensure DB ready
    print(f'🌌 NexusVerse Online! Owner: <@{OWNER_ID}> | Guilds: {len(bot.guilds)} | Entities: {len(ENTITIES)}')
    try:
        synced = await bot.tree.sync()
        print(f'🔮 Synced {len(synced)} slash commands globally.')
    except Exception as e:
        print(f'⚠️ Command Sync Error: {e}')

if __name__ == '__main__':
    if DISCORD_TOKEN is None:
        print("❌ DISCORD_TOKEN not set! Add to env vars in Railway/Render.")
        exit(1)
    asyncio.run(bot.start(DISCORD_TOKEN))  # Use asyncio.run for modern discord.py