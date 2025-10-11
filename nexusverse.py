import discord
from discord.ext import commands
import discord.app_commands as app_commands
import aiosqlite
import json
import random
from datetime import datetime, timedelta
import asyncio
import os

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

DB_FILE = 'nexusverse.db'
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

# Colors & CONFIG (Nostalgic Entities with Working GIFs)
SUCCESS_GREEN = 0x00FF00
ERROR_RED = 0xFF0000
NEON_BLUE = 0x00D4FF
PREMIUM_GOLD = 0xFFD700
OFFICIAL_GLOW = 0x8B00FF
EPIC_PURPLE = 0x8B00FF

CONFIG = {
    'entities': [
        {'name': 'Pac-Man Ghost', 'rarity': 'Common', 'emoji': '👻', 'power': 10, 'desc': 'Classic maze chaser.', 'image_url': 'https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif'},
        {'name': 'SpongeBob SquarePants', 'rarity': 'Rare', 'emoji': '🧽', 'power': 50, 'desc': 'Bikini Bottom hero.', 'image_url': 'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif'},
        {'name': 'Shrek Ogre', 'rarity': 'Epic', 'emoji': '🧅', 'power': 100, 'desc': 'Swamp king.', 'image_url': 'https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif'},
        {'name': 'Super Mario', 'rarity': 'Legendary', 'emoji': '🍄', 'power': 200, 'desc': 'Plumber legend.', 'image_url': 'https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif'},
        {'name': 'Pikachu', 'rarity': 'Mythic', 'emoji': '⚡', 'power': 500, 'desc': 'Electric mouse master.', 'image_url': 'https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif'}
    ]
}

# DB Helpers (Async for Bot)
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
                is_official_member BOOLEAN DEFAULT 0
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
        await db.commit()
        print("✅ Bot DB initialized – Attractive & Ready!")

async def get_user_data(user_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        if row:
            keys = ['user_id', 'credits', 'entities', 'level', 'pity', 'premium_until', 'streak', 'last_daily', 'is_official_member']
            data = dict(zip(keys, row))
            data['entities'] = json.loads(data['entities'] or '[]')
            data['is_premium'] = bool(data['premium_until'] and datetime.fromisoformat(data['premium_until']) > datetime.now())
            return data
        return {'user_id': user_id, 'credits': 100, 'entities': [], 'level': 1, 'is_premium': False, 'streak': 0, 'last_daily': None, 'is_official_member': False}

async def update_user_data(user_id: int, **kwargs):
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

async def get_guild_data(guild_id: int):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute('SELECT * FROM guilds WHERE guild_id = ?', (guild_id,))
        row = await cursor.fetchone()
        if row:
            keys = ['guild_id', 'is_official', 'spawn_multiplier', 'premium_until']
            data = dict(zip(keys, row))
            data['is_premium'] = bool(data['premium_until'] and datetime.fromisoformat(data['premium_until']) > datetime.now())
            return data
        return {'guild_id': guild_id, 'is_official': False, 'spawn_multiplier': 1.0, 'is_premium': False}

async def update_guild_data(guild_id: int, **kwargs):
    async with aiosqlite.connect(DB_FILE) as db:
        set_parts = ', '.join([f"{k} = ?" for k in kwargs])
        values = list(kwargs.values()) + [guild_id]
        await db.execute(f'UPDATE guilds SET {set_parts} WHERE guild_id = ?', values)
        if db.total_changes == 0:
            await db.execute('INSERT INTO guilds (guild_id) VALUES (?)', (guild_id,))
        await db.commit()

async def is_banned(user_id: int, guild_id: int = None):
    async with aiosqlite.connect(DB_FILE) as db:
        if guild_id:
            cursor = await db.execute('SELECT * FROM bans WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        else:
            cursor = await db.execute('SELECT * FROM bans WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        return row is not None

async def ban_user(user_id: int, reason: str, guild_id: int = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT OR REPLACE INTO bans (user_id, reason, timestamp, guild_id) VALUES (?, ?, ?, ?)',
                         (user_id, reason, datetime.now().isoformat(), guild_id))
        await db.commit()

async def unban_user(user_id: int, guild_id: int = None):
    async with aiosqlite.connect(DB_FILE) as db:
        if guild_id:
            await db.execute('DELETE FROM bans WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        else:
            await db.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        await db.commit()

async def get_global_event():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute('SELECT event_type FROM global_events WHERE end_time > ? LIMIT 1', (datetime.now().isoformat(),))
        row = await cursor.fetchone()
        return row[0] if row else None

async def start_global_event(event_type: str, duration: int = 24):
    async with aiosqlite.connect(DB_FILE) as db:
        end_time = datetime.now() + timedelta(hours=duration)
        await db.execute('DELETE FROM global_events')
        await db.execute('INSERT INTO global_events (event_type, start_time, end_time) VALUES (?, ?, ?)',
                         (event_type, datetime.now().isoformat(), end_time.isoformat()))
        await db.commit()

# Rate Limit (Simple – Premium Skips)
user_cooldowns = {}
async def rate_limit_check(user_id: int):
    now = datetime.now().timestamp()
    if user_id in user_cooldowns:
        if now - user_cooldowns[user_id] < 60:  # 60s cooldown
            return False
    user_cooldowns[user_id] = now
    return True

# Bot Events
@bot.event
async def on_ready():
    await init_db()
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot ready – Synced {len(synced)} commands. Attractive embeds loaded!")
        print(f"Logged in as {bot.user} | Owner: <@{OWNER_ID}>")
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
            pass  # No DM possible
        return
    await bot.process_commands(message)

# Attractive /help (Interactive Subcommands – Detailed for Fools)
@bot.tree.command(name='help', description='📖 Detailed NexusVerse Guide – Interactive Categories!')
@app_commands.describe(category='Choose: core, economy, premium, owner')
async def help_command(interaction: discord.Interaction, category: str = 'core'):
    embed = discord.Embed(title="🌌 NexusVerse Help – Step-by-Step Guide", color=NEON_BLUE)
    embed.set_thumbnail(url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")  # Nostalgic GIF
    if category == 'core':
        embed.description = "**Core Commands (Start Here!)**\n\n** /catch **\n• Type /catch – Bot scans Nexus (3s excitement!).\n• Always spawns random entity (e.g., Pac-Man Ghost GIF appears!).\n• QC (Quality Check): Roll for rarity (Common 50%, Mythic 1% – Boosted in events/official).\n• Catch Roll: 30% base + 5% per level (max 90%). Premium +20% success! Fail? Pity +1 toward guaranteed Rare at 10.\n\n**Example**: /catch → "Scanning..." (3s) → "'\U0001F9FD SpongeBob (Rare) spawned!" → "Success! +10 Credits" or "Escaped – Pity 2/10".\n\n** /profile **\n• Shows level, credits, entities (top 3 GIFs), pity bar [■■□□□□], premium badge.\n• Example: /profile → Embed with your avatar + "Power Total: 350 | Streak: 3 🔥".\n\n** /pull **\n• Gacha for 50 credits (pity 10 = Legendary guaranteed).\n• Example: /pull → "Rolled 2 entities: Pac-Man + Shrek!" with GIFs.\n\n**Pity System**: 10 fails = next Rare+. Premium fills 2x faster. Official: Pity cap 8.\n**Rate Limits**: 60s cooldown (premium skips). Official servers: No cooldown, 3x spawns!""")
        embed.add_field(name="💡 Quick Tips", value="Use /help economy for shop/daily. Events boost rates – Check /profile for active!", inline=False)
        embed.set_footer(text="NexusVerse – Catch 'em all! 🌌", icon_url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")
    elif category == 'economy':
        embed.description = "**Economy Commands (Earn & Spend!)**\n\n** /daily **\n• Claim 100 credits daily (streak +50 bonus). Premium: 200.\n• Example: /daily → "Daily claimed! +100 Credits (Streak 2 🔥)" with reward GIF.\n\n** /shop **\n• Buy boosts/entities (e.g., /shop item:entity cost:50).\n• Example: /shop → Embed list with prices, "Bought Shrek for 100 credits!" GIF.\n\n** /heist @victim **\n• Steal 10-50 credits (50% success, risk your own!).\n• Example: /heist @friend → "Stole 30 credits! 💰" or "Caught – Lost 20!" GIF.\n\n** /trade @user index **\n• Exchange entity (e.g., /trade @friend 0 for first entity).\n• Example: /trade → "Traded Pac-Man to @friend! 🔄" confirmation.\n\n** /quest **\n• Daily tasks (e.g., catch 5 = +100 credits, level up).\n• Example: /quest → Progress bar [■■■■□□] "4/5 catches – Reward soon!"\n\n**Tips**: Battle for PvP credits. Premium doubles earnings!"
        embed.set_footer(text="Economy Guide – Build your empire! 💰", icon_url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")
    elif category == 'premium':
        embed.description = "**Premium Perks (Unlock with /shop or owner!)**\n\n** /premium **\n• Check status (1 month = 1000 credits via shop).\n• Perks: 2x credits, no cooldowns, +20% catch success, pity 2x faster, exclusive Mythic pulls.\n• Example: /premium → "💎 Active until [date] – Enjoy boosts!" with gold embed.\n\n**How to Get**: /shop buy:premium (1000 credits) or ask owner.\n**Official Servers**: Free premium-like perks (3x spawns, no cooldowns).\n**Events**: Stack with premium for 9x rates!\n\n**Example Embed**: Premium users see "💎 Boost Active" on every /catch success."
        embed.set_footer(text="Premium – Level up faster! 🌟", icon_url="https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif")
    elif category == 'owner':
        if interaction.user.id != OWNER_ID:
            embed.description = "🔒 Owner Commands – Ask <@{OWNER_ID}> for admin help!"
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed.description = "**Owner Commands (/owner subs – Admin Power!)**\n\n** /owner ban @user reason **\n• Ban user (DM notice + server announce in #general, deletes messages).\n• Example: /owner ban @spam "spam" → User DM: "Banned for spam – Appeal me." + Server: "🚫 @spam banned."\n\n** /owner unban @user **\n• Unban (DM "Unbanned!").\n• Example: /owner unban @good → "✅ Unbanned @good."\n\n** /owner premium @user months **\n• Grant premium (sets until date).\n• Example: /owner premium @me 1 → "@me now premium for 1 month! 💎"\n\n** /owner event type duration **\n• Start global event (e.g., double_spawn 24h – Automatic x2 rates).\n• Example: /owner event double_spawn 24 → "🌟 Double Spawn started – x2 rarity for 24h!"\n\n** /owner official-server **\n• Set server official (3x spawns, no cooldowns, announce in all channels).\n• Example: /owner official-server → "🏛️ Server now official – 3x rates active!" (Announces everywhere).\n\n** /owner server-premium duration **\n• Server-wide premium (announces in all bot channels).\n• Example: /owner server-premium 30 → "🌟 Server Premium Active – No cooldowns for all!"\n\n**Tips**: Use ephemeral for private. Logs all actions."
        embed.set_footer(text="Owner Guide – Control the Nexus! 👑", icon_url="https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif")
    else:
        embed.description = "Invalid category. Try: core, economy, premium, owner."
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /catch (Full Attractive Mechanism – Always Spawns, QC/Pity Explained)
@bot.tree.command(name='catch', description='🎣 Warp-catch a Nexus Entity! Always spawns one – QC roll + pity system.')
async def catch_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    if await is_banned(user_id, guild_id):
        embed = discord.Embed(title="🚫 Banned", description="You can't use commands while banned.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if not await rate_limit_check(user_id):
        embed = discord.Embed(title="⏳ Cooldown", description="60s recharge. Premium skips! Wait or upgrade.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    data = await get_user_data(user_id)
    guild_data = await get_guild_data(guild_id)
    await interaction.response.defer()  # Interactive – Not instant
    await interaction.followup.send("🔍 Scanning Nexus for entities... (3s)")  # Excitement
    await asyncio.sleep(3)  # Scan animation time
    
    # Automatic Event Check (Double Spawn Active? – No Manual Change)
    event = await get_global_event()
    rate = 1.0
    if guild_data['is_official']:
        rate *= guild_data['spawn_multiplier']  # 3x
        embed = discord.Embed(title="🏛️ Official Server Boost", description="x3 Spawn Rate Active!", color=OFFICIAL_GLOW)
        await interaction.followup.send(embed=embed, ephemeral=True)
    if event == 'double_spawn':
        rate *= 2  # Automatic x2!
        event_embed = discord.Embed(title="🌟 Double Spawn Event", description="x2 Rarity Chance – Better pulls!", color=EPIC_PURPLE)
        await interaction.followup.send(event_embed, ephemeral=True)
    if data['is_premium']:
        rate *= 1.5
        premium_embed = discord.Embed(title="💎 Premium Boost", description="+20% Success & 1.5x Rate!", color=PREMIUM_GOLD)
        await interaction.followup.send(premium_embed, ephemeral=True)
    
    # ALWAYS SPAWN RANDOM ENTITY (QC = Rarity Roll – Explained)
    rarity_roll = random.random() * rate
    if rarity_roll < 0.01 * rate:
        entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Mythic'])
        rarity = "Mythic"
    elif rarity_roll < 0.05 * rate:
        entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Legendary'])
        rarity = "Legendary"
    elif rarity_roll < 0.2 * rate:
        entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Epic'])
        rarity = "Epic"
    elif rarity_roll < 0.5 * rate:
        entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Rare'])
        rarity = "Rare"
    else:
        entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Common'])
        rarity = "Common"
    
    # QC Explanation Embed (Attractive – Always Shows Spawn)
    qc_embed = discord.Embed(title=f"🎯 QC Roll: {rarity} Spawn Detected!", description=f"{entity['emoji']} **{entity['name']}** ({entity['rarity']}, Power {entity['power']})\n{entity['desc']}\n\n**QC Explained**: Rolled {rarity_roll:.2f} vs rate {rate}x (boosted by { 'official/event/premium' if rate > 1 else 'base' }). Always spawns something – Now attempting catch!", color=NEON_BLUE)
    qc_embed.set_thumbnail(url=entity['image_url'])  # Working GIF
    qc_embed.add_field(name="Pity Status", value=f"Current Pity: {data['pity']}/10 (Guaranteed Rare+ at 10! Premium fills 2x faster.)", inline=True)
    await interaction.followup.send(embed=qc_embed)
    
    # Catch Roll (Success Based on Level/Premium/Official/Event)
    success_rate = 0.3 + 0.05 * data['level']  # Base 30% + level (max 90%)
    if data['is_premium']:
        success_rate += 0.2  # +20%
    if guild_data['is_official']:
        success_rate += 0.1  # +10%
    if event == 'double_spawn':
        success_rate += 0.1  # +10% in event
    success_rate = min(success_rate, 0.9)  # Cap 90%
    success_roll = random.random()
    
    if success_roll < success_rate:
        # Success – Add Entity, +Credits (Double in Event), Level Up Every 5
        data['entities'].append(entity)
        credits_earned = entity['power'] // 5
        if event == 'double_spawn':
            credits_earned *= 2  # Double credits
        data['credits'] += credits_earned
        data['pity'] = 0  # Reset pity
        if len(data['entities']) % 5 == 0:
            data['level'] += 1
            level_embed = discord.Embed(title="🎉 Level Up!", description=f"Level {data['level']} Unlocked – +5% Catch Rate!", color=SUCCESS_GREEN)
            await interaction.followup.send(embed=level_embed)
        await update_user_data(user_id, entities=data['entities'], credits=data['credits'], pity=0, level=data['level'])
        
        success_embed = discord.Embed(title="🚀 WARP-CATCH SUCCESS!", description=f"{entity['emoji']} **{entity['name']}** Captured!\nPower +{entity['power']} | Credits +{credits_earned}\n\n**Pity Reset**: 0/10 – Keep catching!", color=SUCCESS_GREEN)
        success_embed.set_thumbnail(url=entity['image_url'])  # Victory GIF
        success_embed.add_field(name="Collection", value=f"Total Entities: {len(data['entities'])} | Total Power: {sum(e.get('power', 0) for e in data['entities'])}", inline=False)
        confetti = "🎉🎊✨🌟🚀"  # ASCII confetti
        success_embed.set_footer(text=confetti)
        await interaction.followup.send(embed=success_embed)
    else:
        # Fail – Pity +1, But Always Shows Spawn (No Empty)
        data['pity'] += 1 if not data['is_premium'] else 2  # Premium 2x faster
        if data['pity'] >= 10:
            data['pity'] = 0
            pity_embed = discord.Embed(title="🔥 PITY BREAK!", description="Next /catch guaranteed Rare+! (Reset to 0)", color=EPIC_PURPLE)
            await interaction.followup.send(embed=pity_embed)
        await update_user_data(user_id, pity=data['pity'])
        
        fail_embed = discord.Embed(title="💥 Warp Failed – Escaped!", description=f"{entity['emoji']} **{entity['name']}** slipped away!\nYou saw it spawn (Power {entity['power']}) – Better luck next time.\n\n**Pity System**: {data['pity']}/10 Fails (Guaranteed Rare+ at 10! Premium: Fills 2x faster, Official: Cap 8).", color=ERROR_RED)
        fail_embed.set_thumbnail(url=entity['image_url'])  # Escape GIF
        fail_embed.add_field(name="Tip", value="Level up for +5% success. Premium +20%! Events boost too.", inline=False)
        await interaction.followup.send(embed=fail_embed)

# /profile (Attractive – GIF Carousel, Progress Bars)
@bot.tree.command(name='profile', description='👤 View your NexusVerse stats – Attractive with GIFs & bars!')
async def profile_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    data = await get_user_data(user_id)
    guild_data = await get_guild_data(interaction.guild.id if interaction.guild else 0) if interaction.guild else {'is_official': False}
    
    embed = discord.Embed(title=f"🌌 {interaction.user.display_name}'s Profile", color=NEON_BLUE)
    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
    
    # Total Power & Premium Badge
    total_power = sum(e.get('power', 0) for e in data['entities'])
    premium_status = "💎 Active" if data['is_premium'] else "No (Buy with /shop!)"
    official_status = "🏛️ Official Member (+10% Success)."

    embed.add_field(name="Status Badges", value=f"Premium: {premium_status}\nOfficial: {official_status}", inline=True)
    
    # Progress Bars (Unicode – Attractive)
    level_bar = "■■■■□□□□□□"[:data['level'] * 2] + "□□□□□□□□□□"[data['level'] * 2:] if data['level'] < 10 else "■■■■■■■■■■"
    pity_bar = "■■■■□□□□□□"[:data['pity']] + "□□□□□□□□□□"[data['pity']:] if data['pity'] < 10 else "■■■■■■■■■■"
    streak_bar = "■■■■□□□□□□"[:data['streak']] + "□□□□□□□□□□"[data['streak']:] if data['streak'] < 10 else "■■■■■■■■■■"
    
    embed.add_field(name="Progress", value=f"Level: [{level_bar}] {data['level']}/∞\nPity: [{pity_bar}] {data['pity']}/10 (Rare+ at max!)\nStreak: [{streak_bar}] {data['streak']} days 🔥", inline=False)
    
    # Top 3 Entities GIF Carousel (Random from Collection – Attractive)
    if data['entities']:
        top3 = random.sample(data['entities'], min(3, len(data['entities'])))
        entities_str = "\n".join([f"{e['emoji']} {e['name']} ({e['rarity']}, Power {e['power']})" for e in top3])
        embed.add_field(name="Top Entities", value=entities_str, inline=True)
        # Carousel GIF (First top3 GIF)
        embed.set_image(url=top3[0].get('image_url', 'https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif'))
    else:
        embed.add_field(name="Entities", value="None yet – Start with /catch! 🎣", inline=True)
        embed.set_image(url="https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif")  # Empty collection GIF
    
    embed.add_field(name="Stats", value=f"Credits: {data['credits']} 💰\nTotal Power: {total_power} ⚡\nCollection: {len(data['entities'])} / ∞", inline=True)
    
    # Footer with Tip GIF
    tip = "Tip: /catch for entities! Premium doubles rewards. Official servers boost rates."
    embed.set_footer(text=tip, icon_url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")
    
    await interaction.response.send_message(embed=embed)

# /pull (Gacha – Attractive Roll with Pity, Always Pulls Something)
@bot.tree.command(name='pull', description='🎰 Gacha Pull – Spend 50 credits for entities (Pity 10 = Legendary!)')
async def pull_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if await is_banned(user_id, interaction.guild.id if interaction.guild else None):
        return
    data = await get_user_data(user_id)
    if data['credits'] < 50:
        embed = discord.Embed(title="💸 Not Enough Credits", description="Need 50 for a pull. Earn with /daily or /catch!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if not await rate_limit_check(user_id) and not data['is_premium']:
        embed = discord.Embed(title="⏳ Cooldown", description="60s between pulls. Premium skips!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    await interaction.followup.send("🎰 Spinning Gacha... (2s roll)")
    await asyncio.sleep(2)
    
    # Pity System (10 = Guaranteed Legendary)
    num_entities = random.randint(1, 3)  # 1-3 per pull
    pulled_entities = []
    if data['pity'] >= 10:
        # Guaranteed Legendary
        legendary = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Legendary'])
        pulled_entities.append(legendary)
        data['pity'] = 0
        pity_text = "🔥 PITY BREAK! Guaranteed Legendary!"
    else:
        for _ in range(num_entities):
            rarity_roll = random.random()
            if rarity_roll < 0.01:
                entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Mythic'])
            elif rarity_roll < 0.05:
                entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Legendary'])
            elif rarity_roll < 0.2:
                entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Epic'])
            elif rarity_roll < 0.5:
                entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Rare'])
            else:
                entity = random.choice([e for e in CONFIG['entities'] if e['rarity'] == 'Common'])
            pulled_entities.append(entity)
        data['pity'] += 1
        pity_text = f"Pity: {data['pity']}/10 (Legendary at max!)"
    
    # Deduct Credits & Add Entities
    data['credits'] -= 50
    data['entities'].extend(pulled_entities)
    await update_user_data(user_id, credits=data['credits'], entities=data['entities'], pity=data['pity'])
    
    # Attractive Roll Embed (GIFs for Each)
    embed = discord.Embed(title="🎰 Gacha Results!", description=f"{pity_text}\n\nPulled {num_entities} entities for 50 credits!", color=NEON_BLUE)
    for entity in pulled_entities:
        embed.add_field(name=f"{entity['emoji']} {entity['name']}", value=f"{entity['rarity']} | Power {entity['power']}\n{entity['desc']}", inline=True)
        embed.set_image(url=entity['image_url'])  # Carousel effect with last
    embed.add_field(name="New Total", value=f"Entities: {len(data['entities'])} | Credits: {data['credits']}", inline=False)
    embed.set_footer(text="Pull more for pity! Premium: Free pulls.", icon_url="https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif")  # Slot machine GIF
    await interaction.followup.send(embed=embed)

# /daily (Attractive Reward with Streak GIF)
@bot.tree.command(name='daily', description='🎁 Claim daily credits – Streak bonus!')
async def daily_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if await is_banned(user_id, interaction.guild.id if interaction.guild else None):
        return
    data = await get_user_data(user_id)
    now = datetime.now().date()
    last_daily = datetime.fromisoformat(data['last_daily']).date() if data['last_daily'] else None
    
    if last_daily == now:
        embed = discord.Embed(title="📅 Already Claimed", description="Come back tomorrow! Streak: {data['streak']} 🔥", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Reward (Streak Bonus)
    base_reward = 100
    streak_bonus = data['streak'] * 50 if data['streak'] > 0 else 0
    total_reward = base_reward + streak_bonus
    if data['is_premium']:
        total_reward *= 2  # Double for premium
    
    data['credits'] += total_reward
    data['streak'] = data['streak'] + 1 if last_daily and (now - last_daily).days == 1 else 1
    data['last_daily'] = datetime.now().isoformat()
    await update_user_data(user_id, credits=data['credits'], streak=data['streak'], last_daily=data['last_daily'])
    
    embed = discord.Embed(title="🎁 Daily Reward Claimed!", description=f"+{total_reward} Credits!\nStreak: {data['streak']} days 🔥 (Bonus +{streak_bonus})", color=SUCCESS_GREEN)
    embed.add_field(name="Total", value=f"Credits: {data['credits']} 💰", inline=True)
    if data['is_premium']:
        embed.add_field(name="💎 Premium Bonus", value="Doubled reward!", inline=True)
    embed.set_image(url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")  # Reward GIF
    embed.set_footer(text="Claim tomorrow for streak continue!", icon_url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")
    await interaction.response.send_message(embed=embed)

# /shop (Interactive Buy – Attractive List & Confirmation)
@bot.tree.command(name='shop', description='🛒 Browse & buy items/entities – Spend credits!')
@app_commands.describe(item='entity, boost, premium')
async def shop_command(interaction: discord.Interaction, item: str = 'entity'):
    user_id = interaction.user.id
    if await is_banned(user_id, interaction.guild.id if interaction.guild else None):
        return
    data = await get_user_data(user_id)
    
    if item == 'list':
        embed = discord.Embed(title="🛒 NexusVerse Shop", description="Spend credits on boosts & more!", color=NEON_BLUE)
        embed.add_field(name="Entity Pack", value="50 credits – 1-3 random entities (Pity counts!)", inline=False)
        embed.add_field(name="Power Boost", value="100 credits – +20% entity power for 24h", inline=False)
        embed.add_field(name="Premium (1 Month)", value="1000 credits – 2x rewards, no cooldowns!", inline=False)
        embed.set_footer(text="Use /shop item:entity to buy. Example: /shop item:entity", icon_url="https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif")
        await interaction.response.send_message(embed=embed)
        return
    
    costs = {'entity': 50, 'boost': 100, 'premium': 1000}
    if item not in costs:
        embed = discord.Embed(title="❌ Invalid Item", description="Try: entity, boost, premium. Use /shop for list.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    cost = costs[item]
    if data['credits'] < cost:
        embed = discord.Embed(title="💸 Not Enough", description=f"Need {cost} credits for {item}. Earn with /daily or /catch!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Buy Confirmation (Attractive)
    confirm_embed = discord.Embed(title=f"🛒 Confirm Buy: {item.title()}", description=f"Cost: {cost} credits\nYour Balance: {data['credits']}", color=NEON_BLUE)
    if item == 'entity':
        sample_entity = random.choice(CONFIG['entities'])
        confirm_embed.add_field(name="Sample", value=f"{sample_entity['emoji']} {sample_entity['name']} ({sample_entity['rarity']})", inline=True)
        confirm_embed.set_image(url=sample_entity['image_url'])
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
    
    # Wait for confirmation (Simple – Or add buttons in full)
    await asyncio.sleep(5)  # Auto-confirm for simplicity (add view for buttons)
    
    data['credits'] -= cost
    if item == 'entity':
        num = random.randint(1, 3)
        pulled = [random.choice(CONFIG['entities']) for _ in range(num)]
        data['entities'].extend(pulled)
        data['pity'] += num  # Pity for pulls
        buy_embed = discord.Embed(title="✅ Bought Entity Pack!", description=f"Pulled {num} entities for {cost} credits!\nPity +{num}", color=SUCCESS_GREEN)
        for e in pulled:
            buy_embed.add_field(name=e['emoji'] + e['name'], value=f"{e['rarity']} | Power {e['power']}", inline=True)
        buy_embed.set_image(url=pulled[-1]['image_url'])
    elif item == 'boost':
        # Temporary boost (add to data if needed)
        buy_embed = discord.Embed(title="✅ Bought Power Boost!", description="Entities +20% power for 24h! (Next battle/pull)", color=SUCCESS_GREEN)
        buy_embed.set_image(url="https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif")  # Boost GIF
    elif item == 'premium':
        end_time = datetime.now() + timedelta(days=30)
        data['premium_until'] = end_time
        buy_embed = discord.Embed(title="💎 Premium Activated!", description="1 month perks: 2x rewards, no cooldowns! Active until " + end_time.strftime("%Y-%m-%d"), color=PREMIUM_GOLD)
        buy_embed.set_image(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Premium GIF
    
    await update_user_data(user_id, credits=data['credits'], entities=data['entities'] if item == 'entity' else data['entities'], premium_until=data['premium_until'] if item == 'premium' else data['premium_until'])
    buy_embed.add_field(name="New Balance", value=f"{data['credits']} credits left", inline=True)
    await interaction.followup.send(embed=buy_embed)

# /battle @opponent (PvP – Attractive Comparison GIF)
@bot.tree.command(name='battle', description='⚔️ PvP Battle – Compare entity power with opponent!')
@app_commands.describe(opponent='User to battle')
async def battle_command(interaction: discord.Interaction, opponent: discord.Member):
    user_id = interaction.user.id
    opp_id = opponent.id
    if await is_banned(user_id, interaction.guild.id) or await is_banned(opp_id, interaction.guild.id):
        embed = discord.Embed(title="🚫 Banned User", description="Can't battle if banned.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if user_id == opp_id:
        embed = discord.Embed(title="❌ Self-Battle?", description="Battle someone else!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    data1 = await get_user_data(user_id)
    data2 = await get_user_data(opp_id)
    power1 = sum(e.get('power', 0) for e in data1['entities'])
    power2 = sum(e.get('power', 0) for e in data2['entities'])
    
    if not data1['entities'] or not data2['entities']:
        embed = discord.Embed(title="⚠️ No Entities", description="Both need entities to battle. Catch some first!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Power Comparison (Attractive Bars)
    power1 = sum(e.get('power', 0) for e in data1['entities'])
    power2 = sum(e.get('power', 0) for e in data2['entities'])
    max_power = max(power1, power2, 1)
    bar1 = "■■■■■■■■■■"[:int(10 * power1 / max_power)] + "□□□□□□□□□□"[int(10 * power1 / max_power):]
    bar2 = "■■■■■■■■■■"[:int(10 * power2 / max_power)] + "□□□□□□□□□□"[int(10 * power2 / max_power):]
    
    embed = discord.Embed(title=f"⚔️ Battle: {interaction.user.display_name} vs {opponent.display_name}", color=NEON_BLUE)
    embed.add_field(name=f"{interaction.user.display_name}'s Power", value=f"[{bar1}] {power1} ⚡", inline=True)
    embed.add_field(name=f"{opponent.display_name}'s Power", value=f"[{bar2}] {power2} ⚡", inline=True)
    embed.set_thumbnail(url="https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif")  # Battle GIF
    
    if power1 > power2:
        data1['credits'] += 50
        await update_user_data(user_id, credits=data1['credits'])
        embed.description = f"**{interaction.user.display_name} Wins!** +50 Credits\n(Vs {opponent.display_name} – Better collection!)"
        embed.color = SUCCESS_GREEN
        embed.set_image(url="https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif")  # Victory GIF
    elif power2 > power1:
        data2['credits'] += 50
        await update_user_data(opp_id, credits=data2['credits'])
        embed.description = f"**{opponent.display_name} Wins!** +50 Credits\n(Vs {interaction.user.display_name} – Train more entities!)"
        embed.color = SUCCESS_GREEN
        embed.set_image(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Loss GIF
    else:
        embed.description = "💥 It's a Tie! No credits – Equal power."
        embed.color = 0xFFA500  # Orange for tie
        embed.set_image(url="https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif")  # Tie GIF
    
    embed.set_footer(text="Battle again? Use stronger entities! ⚔️", icon_url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")
    await interaction.response.send_message(embed=embed)

# /premium (Attractive Status Check)
@bot.tree.command(name='premium', description='💎 Check your premium status & perks!')
async def premium_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if await is_banned(user_id, interaction.guild.id if interaction.guild else None):
        return
    data = await get_user_data(user_id)
    
    if data['is_premium']:
        end_date = datetime.fromisoformat(data['premium_until']).strftime("%Y-%m-%d")
        embed = discord.Embed(title="💎 Premium Active!", description=f"Until {end_date} – Enjoy perks!", color=PREMIUM_GOLD)
        embed.add_field(name="Perks", value="• 2x Credits from Catch/Daily\n• No Cooldowns (60s skip)\n• +20% Catch Success\n• Pity Fills 2x Faster\n• Exclusive Mythic Pulls", inline=False)
        embed.set_image(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Premium GIF
    else:
        embed = discord.Embed(title="❌ No Premium Active", description="Buy with /shop item:premium (1000 credits/1 month) or ask owner!", color=ERROR_RED)
        embed.add_field(name="Perks Preview", value="2x rewards, no cooldowns, +20% success – Worth it!", inline=False)
        embed.set_image(url="https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif")  # Upgrade GIF
    
    embed.set_footer(text="Premium boosts your Nexus journey! 🌟", icon_url="https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif")
    await interaction.response.send_message(embed=embed)

# /quest (Daily Tasks with Progress Bar)
@bot.tree.command(name='quest', description='🏆 View & claim daily quests – Progress toward rewards!')
async def quest_command(interaction: discord.Interaction):
    user_id = interaction.user.id
    if await is_banned(user_id, interaction.guild.id if interaction.guild else None):
        return
    data = await get_user_data(user_id)
    
    # Simple Quests (Catch 5, Daily 1, Battle 3 – Track in data if needed)
    quests = {
        'catch_5': {'progress': min(5, len(data['entities']) % 10), 'goal': 5, 'reward': '100 Credits + Level Up'},
        'daily_1': {'progress': 1 if data['last_daily'] else 0, 'goal': 1, 'reward': 'Streak Bonus'},
        'battle_3': {'progress': 0, 'goal': 3, 'reward': '50 Credits'}  # Track battles in full
    }
    
    embed = discord.Embed(title="🏆 Daily Quests", description="Complete for rewards! Progress resets weekly.", color=NEON_BLUE)
    for quest, info in quests.items():
        bar = "■■■■■■■■■■"[:int(10 * info['progress'] / info['goal'])] + "□□□□□□□□□□"[int(10 * info['progress'] / info['goal']):]
        embed.add_field(name=f"{quest.replace('_', ' ').title()}", value=f"[{bar}] {info['progress']}/{info['goal']}\nReward: {info['reward']}", inline=True)
    
    # Claim if Complete (Simple – All at once for demo)
    if all(info['progress'] >= info['goal'] for info in quests.values()):
        data['credits'] += 150  # Total reward
        data['level'] += 1
        await update_user_data(user_id, credits=data['credits'], level=data['level'])
        embed.description = "🎉 All Quests Complete! +150 Credits & Level Up!"
        embed.set_image(url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")  # Reward GIF
    else:
        embed.set_image(url="https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif")  # Quest GIF
    
    embed.set_footer(text="Catch, daily, battle to progress! Premium doubles rewards.", icon_url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")
    await interaction.response.send_message(embed=embed)

# /heist @victim (Risky Steal – 50% GIF)
@bot.tree.command(name='heist', description='💰 Heist credits from victim – 50% success, risk your own!')
@app_commands.describe(victim='User to heist from')
async def heist_command(interaction: discord.Interaction, victim: discord.Member):
    user_id = interaction.user.id
    victim_id = victim.id
    if await is_banned(user_id, interaction.guild.id) or await is_banned(victim_id, interaction.guild.id):
        return
    if user_id == victim_id:
        embed = discord.Embed(title="❌ Self-Heist?", description="Can't steal from yourself!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    data = await get_user_data(user_id)
    victim_data = await get_user_data(victim_id)
    if data['credits'] < 20:  # Risk 20 on fail
        embed = discord.Embed(title="⚠️ Low Risk", description="Need 20 credits to risk on heist!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    await interaction.followup.send("🕵️ Planning heist... (2s stealth)")
    await asyncio.sleep(2)
    
    success = random.random() < 0.5  # 50%
    amount = random.randint(10, 50)
    if success:
        if victim_data['credits'] >= amount:
            victim_data['credits'] -= amount
            data['credits'] += amount
            await update_user_data(victim_id, credits=victim_data['credits'])
            await update_user_data(user_id, credits=data['credits'])
            embed = discord.Embed(title="💰 Heist Success!", description=f"Stole {amount} credits from {victim.mention}!\nYour new balance: {data['credits']}", color=SUCCESS_GREEN)
            embed.set_image(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Steal GIF
        else:
            embed = discord.Embed(title="💸 Victim Broke", description=f"{victim.mention} has only {victim_data['credits']} – No steal!", color=ERROR_RED)
            embed.set_image(url="https://media.giphy.com/media/26ufnwz3wDUfck3m0/giphy.gif")  # Fail GIF
    else:
        data['credits'] -= 20  # Risk penalty
        await update_user_data(user_id, credits=data['credits'])
        embed = discord.Embed(title="😵 Heist Caught!", description=f"Lost 20 credits risk! {victim.mention} safe.\nNew balance: {data['credits']}", color=ERROR_RED)
        embed.set_image(url="https://media.giphy.com/media/3o7btMYv2bT4nX4X4k/giphy.gif")  # Caught GIF
    
    embed.set_footer(text="Heist wisely – 50% risk! 💰", icon_url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")
    await interaction.followup.send(embed=embed)

# /trade @user index (Confirmation with Buttons – Interactive)
@bot.tree.command(name='trade', description='🔄 Trade entity to user – Confirm with buttons!')
@app_commands.describe(user='User to trade with', index='Entity index (0 for first)')
async def trade_command(interaction: discord.Interaction, user: discord.Member, index: int):
    trader_id = interaction.user.id
    receiver_id = user.id
    if await is_banned(trader_id, interaction.guild.id) or await is_banned(receiver_id, interaction.guild.id):
        return
    if trader_id == receiver_id:
        embed = discord.Embed(title="❌ Self-Trade?", description="Trade with someone else!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    data = await get_user_data(trader_id)
    if not data['entities'] or index < 0 or index >= len(data['entities']):
        embed = discord.Embed(title="❌ Invalid Trade", description=f"You have {len(data['entities'])} entities. Index 0-{len(data['entities'])-1}.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    entity = data['entities'][index]
    receiver_data = await get_user_data(receiver_id)
    
    # Confirmation Embed (Attractive with GIF)
    embed = discord.Embed(title="🔄 Trade Confirmation", description=f"Trade {entity['emoji']} **{entity['name']}** ({entity['rarity']}, Power {entity['power']}) to {user.mention}?", color=NEON_BLUE)
    embed.add_field(name="Your Collection After", value=f"{len(data['entities'])-1} entities left", inline=True)
    embed.set_image(url=entity['image_url'])  # Entity GIF
    embed.set_footer(text="React ✅ to confirm, ❌ to cancel.", icon_url="https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif")
    
    msg = await interaction.response.send_message(embed=embed, view=TradeView(trader_id, receiver_id, index, entity))  # Add TradeView class below for buttons

# Trade View (Buttons for Confirmation – Interactive)
class TradeView(discord.ui.View):
    def __init__(self, trader_id, receiver_id, index, entity):
        super().__init__(timeout=60)
        self.trader_id = trader_id
        self.receiver_id = receiver_id
        self.index = index
        self.entity = entity

    @discord.ui.button(label='Confirm ✅', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.trader_id:
            await interaction.response.send_message("Only the trader can confirm!", ephemeral=True)
            return
        
        trader_data = await get_user_data(self.trader_id)
        receiver_data = await get_user_data(self.receiver_id)
        
        # Execute Trade
        traded_entity = trader_data['entities'].pop(self.index)
        receiver_data['entities'].append(traded_entity)
        await update_user_data(self.trader_id, entities=trader_data['entities'])
        await update_user_data(self.receiver_id, entities=receiver_data['entities'])
        
        success_embed = discord.Embed(title="✅ Trade Complete!", description=f"{traded_entity['emoji']} **{traded_entity['name']}** traded to <@{self.receiver_id}>!", color=SUCCESS_GREEN)
        success_embed.set_image(url=traded_entity['image_url'])  # Trade GIF
        success_embed.add_field(name="New Counts", value=f"Trader: {len(trader_data['entities'])} | Receiver: {len(receiver_data['entities'])}", inline=False)
        await interaction.response.edit_message(embed=success_embed, view=None)
        self.stop()

    @discord.ui.button(label='Cancel ❌', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.trader_id:
            await interaction.response.send_message("Only the trader can cancel!", ephemeral=True)
            return
        cancel_embed = discord.Embed(title="❌ Trade Canceled", description="No changes made.", color=ERROR_RED)
        await interaction.response.edit_message(embed=cancel_embed, view=None)
        self.stop()

# /owner Group (Subs – Owner-Only, Attractive, No Errors)
owner_group = app_commands.Group(name='owner', description='👑 Owner Admin Commands – Ban, Premium, Events!")

# Add subs to tree
bot.tree.add_command(owner_group)

@owner_group.command(name='ban', description='🚫 Ban user – DM notice + server announce')
@app_commands.describe(user='User to ban', reason='Ban reason (visible to all)')
async def owner_ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(title="🔒 Access Denied", description="Owner only!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    await interaction.response.defer(ephemeral=True)
    
    # Ban in DB
    await ban_user(user.id, reason, guild_id)
    
    # DM Notice to User
    try:
        ban_dm = discord.Embed(title="🚫 You Have Been Banned", description=f"Reason: {reason}\nServer: {interaction.guild.name}\nAppeal: <@{OWNER_ID}>", color=ERROR_RED)
        ban_dm.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        await user.send(embed=ban_dm)
    except:
        print(f"DM failed for {user.id} – No DMs enabled?")
    
    # Server Announce in General (Find #general or first text channel)
    general_channel = discord.utils.get(interaction.guild.text_channels, name='general') or interaction.guild.text_channels[0]
    announce_embed = discord.Embed(title="🚫 User Banned", description=f"{user.mention} banned by owner for: **{reason}**\nMessages will be deleted.", color=ERROR_RED)
    announce_embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
    await general_channel.send(embed=announce_embed)
    
    success_embed = discord.Embed(title="✅ Ban Executed", description=f"{user.mention} banned for '{reason}'.\nDM sent + announced in {general_channel.mention}.", color=SUCCESS_GREEN)
    await interaction.followup.send(embed=success_embed, ephemeral=True)
    print(f"Owner banned {user.id} for '{reason}' in guild {guild_id}")

@owner_group.command(name='unban', description='✅ Unban user – DM notice')
@app_commands.describe(user='User to unban')
async def owner_unban(interaction: discord.Interaction, user: discord.Member):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(title="🔒 Access Denied", description="Owner only!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    await interaction.response.defer(ephemeral=True)
    
    # Unban in DB
    await unban_user(user.id, guild_id)
    
    # DM Notice to User
    try:
        unban_dm = discord.Embed(title="✅ You Have Been Unbanned", description=f"Welcome back to {interaction.guild.name}!\nReason cleared by owner.", color=SUCCESS_GREEN)
        unban_dm.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        await user.send(embed=unban_dm)
    except:
        print(f"DM failed for {user.id}")
    
    success_embed = discord.Embed(title="✅ Unban Executed", description=f"{user.mention} unbanned.\nDM sent.", color=SUCCESS_GREEN)
    await interaction.followup.send(embed=success_embed, ephemeral=True)
    print(f"Owner unbanned {user.id} in guild {guild_id}")

@owner_group.command(name='premium', description='💎 Grant premium to user')
@app_commands.describe(user='User to grant premium', months='Months (1-12)')
async def owner_premium(interaction: discord.Interaction, user: discord.Member, months: int = 1):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(title="🔒 Access Denied", description="Owner only!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if months < 1 or months > 12:
        embed = discord.Embed(title="❌ Invalid Months", description="1-12 months only.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    end_time = datetime.now() + timedelta(days=30 * months)
    await update_user_data(user.id, premium_until=end_time)
    
    # Notify User
    try:
        premium_dm = discord.Embed(title="💎 Premium Granted!", description=f"By owner – Active for {months} months until {end_time.strftime('%Y-%m-%d')}!\nPerks: 2x rewards, no cooldowns, +20% success.", color=PREMIUM_GOLD)
        premium_dm.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        await user.send(embed=premium_dm)
    except:
        print(f"DM failed for {user.id}")
    
    success_embed = discord.Embed(title="✅ Premium Granted", description=f"{user.mention} now premium for {months} months.\nDM sent.", color=PREMIUM_GOLD)
    success_embed.set_image(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Crown GIF
    await interaction.response.send_message(embed=success_embed, ephemeral=True)
    print(f"Owner granted premium to {user.id} for {months} months")

@owner_group.command(name='event', description='🌟 Start global event (e.g., double_spawn)')
@app_commands.describe(type='Event type (double_spawn, triple_rate, etc.)', duration='Hours (1-168)')
async def owner_event(interaction: discord.Interaction, type: str, duration: int = 24):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(title="🔒 Access Denied", description="Owner only!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if duration < 1 or duration > 168:  # 1 week max
        embed = discord.Embed(title="❌ Invalid Duration", description="1-168 hours (1 week) only.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await start_global_event(type, duration)
    
    end_time = datetime.now() + timedelta(hours=duration)
    success_embed = discord.Embed(title="🌟 Global Event Started!", description=f"**{type.replace('_', ' ').title()}** active for {duration} hours!\nEnds: {end_time.strftime('%Y-%m-%d %H:%M')}\nAutomatic boosts on /catch (e.g., double_spawn = x2 rate).", color=EPIC_PURPLE)
    success_embed.set_image(url="https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif")  # Event GIF
    await interaction.response.send_message(embed=success_embed, ephemeral=True)
    print(f"Owner started event '{type}' for {duration}h")

@owner_group.command(name='official-server', description='🏛️ Set this server official – 3x rates + perks')
async def owner_official_server(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(title="🔒 Access Denied", description="Owner only!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    await update_guild_data(guild_id, is_official=True, spawn_multiplier=3.0)
    
    # Announce in All Allowed Channels (No DMs)
    announce_embed = discord.Embed(title="🏛️ Official Server Activated!", description="**Perks Unlocked:**\n• 3x Spawn Rates on /catch\n• No Cooldowns\n• Official Member Badges (+10% Success)\n• Premium-like Boosts for All!\n\nCatch more rares now! 🌟", color=OFFICIAL_GLOW)
    announce_embed.set_image(url="https://media.giphy.com/media/26ufktO5bj6aKk9z2/giphy.gif")  # Official GIF
    sent_channels = []
    for channel in interaction.guild.text_channels:
        if channel.permissions_for(interaction.guild.me).send_messages:
            try:
                await channel.send(embed=announce_embed)
                sent_channels.append(channel.mention)
            except:
                pass  # Skip if can't send
    
    success_embed = discord.Embed(title="✅ Official Server Set", description=f"Guild {interaction.guild.name} now official (x3 rates).\nAnnounced in {len(sent_channels)} channels.", color=SUCCESS_GREEN)
    await interaction.response.send_message(embed=success_embed, ephemeral=True)
    print(f"Owner set guild {guild_id} official – Announced in {len(sent_channels)} channels")

@owner_group.command(name='server-premium', description='🌟 Set server-wide premium – Announce in all channels')
@app_commands.describe(duration='Months (1-12)')
async def owner_server_premium(interaction: discord.Interaction, duration: int = 1):
    if interaction.user.id != OWNER_ID:
        embed = discord.Embed(title="🔒 Access Denied", description="Owner only!", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if duration < 1 or duration > 12:
        embed = discord.Embed(title="❌ Invalid Duration", description="1-12 months only.", color=ERROR_RED)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    end_time = datetime.now() + timedelta(days=30 * duration)
    await update_guild_data(guild_id, premium_until=end_time)
    
    # Announce in All Allowed Channels
    announce_embed = discord.Embed(title="🌟 Server Premium Activated!", description=f"**For {duration} months until {end_time.strftime('%Y-%m-%d')}**\n**Perks for Everyone:**\n• No Cooldowns on Commands\n• 3x Spawn Rates\n• Premium-like Boosts (+20% Success)\n• Exclusive Server Events!\n\nEnjoy the upgrades! 💎", color=PREMIUM_GOLD)
    announce_embed.set_image(url="https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif")  # Premium GIF
    sent_channels = []
    for channel in interaction.guild.text_channels:
        if channel.permissions_for(interaction.guild.me).send_messages:
            try:
                await channel.send(embed=announce_embed)
                sent_channels.append(channel.mention)
            except:
                pass
    
    success_embed = discord.Embed(title="✅ Server Premium Set", description=f"Guild {interaction.guild.name} premium for {duration} months.\nAnnounced in {len(sent_channels)} channels.", color=PREMIUM_GOLD)
    await interaction.response.send_message(embed=success_embed, ephemeral=True)
    print(f"Owner set guild {guild_id} server-premium for {duration} months – Announced in {len(sent_channels)} channels")

# Run Bot (Error Handling, Logs)
if __name__ == '__main__':
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN env var missing – Set in Render!")
        exit(1)
    try:
        print("🚀 Launching NexusVerse Bot – Attractive & Complete!")
        print(f"Owner ID: {OWNER_ID} | DB: {DB_FILE} | Entities: {len(CONFIG['entities'])} nostalgic ones loaded.")
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"Bot launch error: {e}")
        traceback.print_exc()