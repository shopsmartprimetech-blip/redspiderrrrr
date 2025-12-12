# red_spider_master.py
# RED SPIDER MULTIVERSE (Full feature release)
# - Single-file production-ready implementation (Pyto/Replit/VPS)
# - Requires: discord.py, aiohttp, python-dotenv (optional)
# - Replace BOT_TOKEN with your bot token
# - Keep running for the system to stay online

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # <<<< REPLACE THIS
COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook for Goblin to post invites
ULTRA_LEGENDARY_CHANCE = 0.0001  # 0.0001 probability ~ 1 in 10,000
GAMBLING_HOUSE_EDGE = 0.05  # 5% house edge
GAMBLING_DAILY_LIMIT_COPPER = 100000  # equivalent copper limit per user/day
DEADPOOL_ROAST_HOURLY_LIMIT = 3  # roasts per hour per target if opted in
PET_HUNT_COST_COPPER = 100  # default cost per /pet_hunt
DB_PATH = "db/red_spider_full.db"

# -------------------------
# BOT INIT
# -------------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

# -------------------------
# DB SETUP
# -------------------------
if not os.path.exists("db"):
    os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Users
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    tag TEXT DEFAULT 'Newbie',
    alignment TEXT DEFAULT 'Neutral',
    universe TEXT DEFAULT 'Arcadia',
    gang_id INTEGER,
    booster_level TEXT DEFAULT 'None',
    last_daily TEXT,
    boosts_today INTEGER DEFAULT 0,
    last_boost_day TEXT
)
""")

# Tools / Items
c.execute("""
CREATE TABLE IF NOT EXISTS tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    owner_id INTEGER,
    power TEXT,
    rarity TEXT,
    created_at TEXT
)
""")

# Gangs
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    alignment TEXT,
    leader_id INTEGER,
    xp INTEGER DEFAULT 0
)
""")

# Invite history (Goblin)
c.execute("""
CREATE TABLE IF NOT EXISTS invite_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    channel_id INTEGER,
    invite_code TEXT,
    posted_at TEXT,
    posted_to_webhook INTEGER DEFAULT 0,
    description TEXT
)
""")

# Art posts (White Tiger)
c.execute("""
CREATE TABLE IF NOT EXISTS art_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    channel_id INTEGER,
    author_id INTEGER,
    title TEXT,
    url TEXT,
    posted_at TEXT
)
""")

# Pets
c.execute("""
CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    name TEXT,
    species TEXT,
    rarity TEXT,
    bonus_xp INTEGER DEFAULT 0,
    acquired_at TEXT
)
""")

# Items table (player inventory)
c.execute("""
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER,
    name TEXT,
    tier TEXT,
    effect TEXT,
    legendary INTEGER DEFAULT 0,
    created_at TEXT
)
""")

# Ultra drop log
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    item_name TEXT,
    item_type TEXT,
    dropped_at TEXT
)
""")

# roast opt-in
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
    user_id INTEGER PRIMARY KEY,
    opted_in INTEGER DEFAULT 0,
    last_roast_time TEXT,
    roasts_in_hour INTEGER DEFAULT 0
)
""")

# themes
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    data TEXT,
    created_at TEXT
)
""")

# currencies (per user)
c.execute("""
CREATE TABLE IF NOT EXISTS currencies (
    user_id INTEGER PRIMARY KEY,
    copper INTEGER DEFAULT 0,
    silver INTEGER DEFAULT 0,
    coin INTEGER DEFAULT 0,
    gold INTEGER DEFAULT 0,
    black_coins INTEGER DEFAULT 0,
    diamond INTEGER DEFAULT 0
)
""")

conn.commit()

# -------------------------
# Helper functions
# -------------------------
def now_iso():
    return datetime.utcnow().isoformat()

def today_str():
    return str(datetime.utcnow().date())

def ensure_user(user):
    """Ensure user row exists; update username"""
    if isinstance(user, discord.User) or isinstance(user, discord.Member):
        user_id = user.id
        username = user.name
    else:
        user_id = int(user)
        username = "Unknown"
    row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
                  (user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]), random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
        c.execute("INSERT OR IGNORE INTO currencies (user_id) VALUES (?)", (user_id,))
        conn.commit()
    else:
        c.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        conn.commit()
    return c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

def get_currency(user_id):
    row = c.execute("SELECT copper,silver,coin,gold,black_coins,diamond FROM currencies WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        c.execute("INSERT OR IGNORE INTO currencies (user_id) VALUES (?)", (user_id,))
        conn.commit()
        row = (0,0,0,0,0,0)
    return {"copper":row[0],"silver":row[1],"coin":row[2],"gold":row[3],"black_coins":row[4],"diamond":row[5]}

def add_currency(user_id, currency, amount):
    assert currency in ("copper","silver","coin","gold","black_coins","diamond")
    c.execute(f"UPDATE currencies SET {currency} = {currency} + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def deduct_currency(user_id, currency, amount):
    cur = get_currency(user_id)
    if cur[currency] < amount:
        return False
    c.execute(f"UPDATE currencies SET {currency} = {currency} - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    return True

def award_item(user_id, name, tier="Common", effect="", legendary=0):
    c.execute("INSERT INTO items (owner_id, name, tier, effect, legendary, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, name, tier, effect, int(bool(legendary)), now_iso()))
    conn.commit()
    if legendary:
        c.execute("INSERT INTO ultra_drop_log (user_id, item_name, item_type, dropped_at) VALUES (?, ?, ?, ?)",
                  (user_id, name, tier, now_iso()))
        conn.commit()

def roll_ultra():
    return random.random() < ULTRA_LEGENDARY_CHANCE

def give_pet(user_id, species=None, rarity=None):
    species = species or random.choice(["Cat","Dog","Bird","Fox Spirit","Mini Dragon","Spirit Wolf","Griffon","Phoenix","Celestial Familiar"])
    if rarity is None:
        r = random.random()
        if r < 0.6:
            rarity = "Common"
        elif r < 0.85:
            rarity = "Rare"
        elif r < 0.98:
            rarity = "Epic"
        elif r < 0.999:
            rarity = "Legendary"
        else:
            rarity = "Ultra-Legendary"
    bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
    name = f"{rarity} {species}"
    c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, name, species, rarity, bonus_xp, now_iso()))
    conn.commit()
    return c.lastrowid, name, rarity

def give_currency_from_tier(user_id, amount_copper):
    add_currency(user_id, "copper", amount_copper)

# -------------------------
# Archetypes / weapon pools
# -------------------------
ARCHETYPES = {
    "Royalty": {"tags":["👑 Crowned","Royal Court"], "weapons":["Scepter of Command","Crown Blade"], "magic":["Royal Aegis","Edict of Thrones"]},
    "Hero": {"tags":["🛡️ Heroic","Paragon"], "weapons":["Guardian Blade","Justice Hammer"], "magic":["Healing Radiance","Shield of Hope"]},
    "Ninja": {"tags":["🥷 Shadow Ninja","Silent Step"], "weapons":["Kage Kunai","Ninjato"], "magic":["Vanishing Mist","Shadow Clone"]},
    "Anime": {"tags":["✨ Anime Prodigy"], "weapons":["Spirit Sword","Ki Blast"], "magic":["Stand Call","Devil Spirit"]},
    "Fantasy": {"tags":["🔮 Mystic"], "weapons":["Arcane Staff","Dragon Lance"], "magic":["Elemental Storm","Summon Familiar"]},
    "Witch": {"tags":["🪄 Witch"], "weapons":["Witch Broom","Grimoire"], "magic":["Hex","Full Moon Ritual"]}
}

def is_royal(user_id):
    row = c.execute("SELECT booster_level FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if row and row[0] and row[0] != "None":
        return True
    return False

# -------------------------
# MINI-AI: Goblin (invite maker)
# -------------------------
class GoblinCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _fun_description(self, guild_name, channel_name, creator_name):
        templates = [
            "🔗 **%s's Treasure Gate** — swing into %s's hangout! (made by %s). Silly vibes only. 🍌",
            "🚪 *Portal to %s — %s* — hobnob with legends and share memes. Invited by %s. Bring snacks.",
            "🕸️ **%s: %s** — enter if you dare. Creator %s promises cookies (maybe).",
            "🎉 **%s — %s**: A place for chaos, tunes, and drama. Summoned by %s. Come be weird.",
            "👾 **%s @ %s** — quick drop-in portal created by %s. Expect jokes, bad puns, and surprises."
        ]
        t = random.choice(templates)
        return t % (guild_name, channel_name, creator_name)

    @commands.command(name="goblin_create")
    @commands.has_permissions(create_instant_invite=True)
    async def create_invite(self, ctx, channel: discord.TextChannel = None, max_age: int = 86400, max_uses: int = 0):
        channel = channel or ctx.channel
        try:
            invite = await channel.create_invite(max_age=max_age, max_uses=max_uses, unique=True)
        except Exception as e:
            await ctx.send(f"❌ Couldn't create invite: {e}")
            return
        desc = self._fun_description(ctx.guild.name, channel.name, ctx.author.display_name)
        posted_to_webhook = 0
        if PUBLIC_POST_WEBHOOK:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post(PUBLIC_POST_WEBHOOK, json={"content": f"{desc}\n{invite.url}"}, timeout=10)
                    posted_to_webhook = 1
            except Exception as e:
                await ctx.send(f"⚠️ Goblin failed to post publicly: {e}")
        c.execute("INSERT INTO invite_history (guild_id, channel_id, invite_code, posted_at, posted_to_webhook, description) VALUES (?, ?, ?, ?, ?, ?)",
                  (ctx.guild.id, channel.id, invite.code, now_iso(), posted_to_webhook, desc))
        conn.commit()
        if posted_to_webhook:
            await ctx.send(f"✅ Goblin created invite and posted it publicly. Invite: {invite.url}")
        else:
            await ctx.send(f"🔮 Goblin created invite: {invite.url}\nDesc: {desc}")

    @commands.command(name="goblin_history")
    @commands.has_permissions(administrator=True)
    async def goblin_history(self, ctx, limit: int = 10):
        rows = c.execute("SELECT id, invite_code, posted_at, posted_to_webhook, description FROM invite_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        if not rows:
            await ctx.send("No invites recorded.")
            return
        msg = "**Goblin Invite History:**\n"
        for r in rows:
            msg += f"- ID {r[0]} | Code: {r[1]} | Posted: {r[2]} | Public: {bool(r[3])}\n  Desc: {r[4]}\n"
        for chunk in [msg[i:i+1900] for i in range(0, len(msg), 1900)]:
            await ctx.send(chunk)

# -------------------------
# MINI-AI: White Tiger (art)
# -------------------------
class WhiteTigerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="post_art")
    async def post_art(self, ctx, title: str, url: str = None):
        url = url or (ctx.message.attachments[0].url if ctx.message.attachments else None)
        if not url:
            await ctx.send("Please attach an image or provide an image URL.")
            return
        c.execute("INSERT INTO art_posts (guild_id, channel_id, author_id, title, url, posted_at) VALUES (?, ?, ?, ?, ?, ?)",
                  (ctx.guild.id, ctx.channel.id, ctx.author.id, title, url, now_iso()))
        conn.commit()
        add_currency(ctx.author.id, "copper", 50)
        await ctx.send(f"🖼 White Tiger: Art posted! Title: **{title}**. Thanks {ctx.author.mention}! You earned 50 copper.")

    @commands.command(name="whitepicks")
    async def white_picks(self, ctx, limit: int = 5):
        rows = c.execute("SELECT author_id, title, url, posted_at FROM art_posts WHERE guild_id = ? ORDER BY id DESC LIMIT ?", (ctx.guild.id, limit)).fetchall()
        if not rows:
            await ctx.send("No art posts yet.")
            return
        msg = "**White Tiger's Recent Picks:**\n"
        for r in rows:
            msg += f"- {r[1]} by <@{r[0]}> | {r[2]} | {r[3]}\n"
        await ctx.send(msg)

# -------------------------
# MINI-AI: Two-Face (gambling, bookie)
# -------------------------
class TwoFaceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def copper_value(self, currency_name, amount):
        rates = {"copper":1, "silver":100, "coin":100*100, "gold":100*100*50, "black_coins":100*100*50*10, "diamond":100*100*50*10*10}
        return amount * rates.get(currency_name,1)

    @commands.command(name="bet_coinflip")
    async def bet_coinflip(self, ctx, currency: str, amount: int, call: str):
        currency = currency.lower()
        if currency not in ("copper","silver","coin","gold","black_coins","diamond"):
            await ctx.send("Invalid currency.")
            return
        ensure_user(ctx.author)
        if not hasattr(self, "daily_spent"):
            self.daily_spent = {}
        key = (ctx.author.id, today_str())
        spent = self.daily_spent.get(key, 0)
        copper_equiv = self.copper_value(currency, amount)
        if spent + copper_equiv > GAMBLING_DAILY_LIMIT_COPPER:
            await ctx.send("You reached daily gambling limit.")
            return
        cur = get_currency(ctx.author.id)
        if cur[currency] < amount:
            await ctx.send("Insufficient funds.")
            return
        outcome = random.choice(["heads","tails"])
        win = (call.lower() == outcome)
        if win:
            payout = int(amount * (1 - GAMBLING_HOUSE_EDGE))
            add_currency(ctx.author.id, currency, payout)
            await ctx.send(f"🎲 Coinflip result: {outcome}. You won {payout} {currency} (after house edge).")
        else:
            deduct_currency(ctx.author.id, currency, amount)
            await ctx.send(f"🎲 Coinflip result: {outcome}. You lost {amount} {currency}.")
        self.daily_spent[key] = spent + copper_equiv

    @commands.command(name="twoface_jackpot")
    async def twoface_jackpot(self, ctx, currency: str, amount: int):
        currency = currency.lower()
        if currency not in ("copper","silver","coin","gold","black_coins","diamond"):
            await ctx.send("Invalid currency.")
            return
        cur = get_currency(ctx.author.id)
        if cur[currency] < amount:
            await ctx.send("Insufficient funds.")
            return
        deduct_currency(ctx.author.id, currency, amount)
        r = random.random()
        if r < 0.0005:
            add_currency(ctx.author.id, "diamond", 1)
            award_item(ctx.author.id, "TwoFace's Fate Crown", tier="Ultra", effect="Double or nothing eternal", legendary=1)
            await ctx.send(f"💥 JACKPOT! You won a DIAMOND and an ULTRA artifact!")
        elif r < 0.01:
            add_currency(ctx.author.id, "gold", int(amount*0.5) + 1)
            await ctx.send("🎉 Big win! You got a gold payout.")
        else:
            await ctx.send("😢 No win this time. Two-Face smiles sadly.")
        if random.random() < 0.05:
            new_tag = random.choice(["☯️ Gambler's Luck","🎭 Two-Face Mark"])
            c.execute("UPDATE users SET tag = ? WHERE user_id = ?", (new_tag, ctx.author.id))
            conn.commit()
            await ctx.send(f"Two-Face grants you the tag **{new_tag}** temporarily.")

# -------------------------
# MINI-AI: Deadpool (jokes & roast, safe)
# -------------------------
PROFANITY_BLACKLIST = ["kill", "die", "suicide", "bomb", "rape", "terror"]

def safe_joke_filter(text):
    low = text.lower()
    for bad in PROFANITY_BLACKLIST:
        if bad in low:
            return False
    return True

class DeadpoolCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="deadpool_joke")
    async def joke(self, ctx, kind: str = "weird"):
        kind = kind.lower()
        jokes = {
            "weird": [
                "Why did the skeleton refuse to fight? He felt bone-alone. (Deadpool walks away)",
                "I once ate a lightbulb. I was stunned for hours. 😵"
            ],
            "light": [
                "Why don't scientists trust atoms? Because they make up everything!",
                "I bought the world's worst thesaurus — not only is it terrible, it's terrible."
            ],
            "dark": [
                "I told my imaginary friend to leave a note — he left me a sticky note. (safe-dark)",
                "Dark humor: life's a soup and I'm a fork. (tongue-in-cheek)"
            ]
        }
        pool = jokes.get(kind, jokes["weird"])
        joke = random.choice(pool)
        if not safe_joke_filter(joke):
            await ctx.send("Deadpool refuses — joke unsafe.")
            return
        await ctx.send(f"🃏 Deadpool: {joke}")

    @commands.command(name="deadpool_roast")
    async def roast(self, ctx, member: discord.Member):
        row = c.execute("SELECT opted_in, last_roast_time, roasts_in_hour FROM roast_opt_in WHERE user_id = ?", (member.id,)).fetchone()
        if not row or row[0] == 0:
            await ctx.send("That user has not opted-in to roasts.")
            return
        nowt = datetime.utcnow()
        rec = row
        roasts_in_hour = rec[2] or 0
        last_time = datetime.fromisoformat(rec[1]) if rec[1] else None
        if last_time and (nowt - last_time).seconds < 3600 and roasts_in_hour >= DEADPOOL_ROAST_HOURLY_LIMIT:
            await ctx.send("That user has reached roast limit for the hour.")
            return
        roasts = [
            "I'd explain it to you but I left my crayons at home.",
            "You're the human version of a participation trophy.",
            "You bring everyone so much joy... when you leave the room."
        ]
        roast = random.choice(roasts)
        await ctx.send(f"🃏 Deadpool roasts {member.mention}: {roast}")
        if last_time and (nowt - last_time).seconds < 3600:
            new_count = roasts_in_hour + 1
            c.execute("UPDATE roast_opt_in SET roasts_in_hour = ?, last_roast_time = ? WHERE user_id = ?", (new_count, now_iso(), member.id))
        else:
            c.execute("INSERT OR REPLACE INTO roast_opt_in (user_id, opted_in, last_roast_time, roasts_in_hour) VALUES (?, ?, ?, ?)",
                      (member.id, 1, now_iso(), 1))
        conn.commit()

    @commands.command(name="allow_roast")
    async def allow_roast(self, ctx, toggle: str):
        toggle = toggle.lower()
        if toggle not in ("on","off"):
            await ctx.send("Usage: /allow_roast on|off")
            return
        opted = 1 if toggle=="on" else 0
        c.execute("INSERT OR REPLACE INTO roast_opt_in (user_id, opted_in, last_roast_time, roasts_in_hour) VALUES (?, ?, ?, ?)",
                  (ctx.author.id, opted, None, 0))
        conn.commit()
        await ctx.send(f"Deadpool roast opt-in set to {toggle} for {ctx.author.mention}")

# -------------------------
# MINI-AI: Spider-Man (welcomer, guardian)
# -------------------------
class SpidermanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            ensure_user(member)
            await member.send(f"🕷️ Spider-Man: Welcome {member.name}! You're safe here — have a meme.")
            add_currency(member.id, "copper", 250)
        except:
            pass

    @commands.command(name="spidey_meme")
    async def spidey_meme(self, ctx):
        memes = [
            "https://i.imgur.com/1.jpg (meme placeholder)",
            "https://i.imgur.com/2.jpg",
            "https://i.imgur.com/3.jpg"
        ]
        await ctx.send(f"🕸 Spider-Man meme: {random.choice(memes)}")

# -------------------------
# MINI-AI: ThemeMaster (beautifier)
# -------------------------
class ThemeMasterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="theme_preview")
    @commands.has_permissions(administrator=True)
    async def theme_preview(self, ctx, theme_name: str):
        row = c.execute("SELECT description FROM themes WHERE name = ?", (theme_name,)).fetchone()
        if row:
            await ctx.send(f"Theme preview: {theme_name}\n{row[0]}")
        else:
            await ctx.send(f"No saved theme named {theme_name}. Send `/theme_create {theme_name} <desc>` to add one.")

    @commands.command(name="theme_create")
    @commands.has_permissions(administrator=True)
    async def theme_create(self, ctx, name: str, *, description: str):
        c.execute("INSERT INTO themes (name, description, data, created_at) VALUES (?, ?, ?, ?)", (name, description, "", now_iso()))
        conn.commit()
        await ctx.send(f"Theme {name} created.")

    @commands.command(name="theme_apply")
    @commands.has_permissions(administrator=True)
    async def theme_apply(self, ctx, name: str):
        row = c.execute("SELECT description FROM themes WHERE name = ?", (name,)).fetchone()
        if not row:
            await ctx.send("Theme not found.")
            return
        desc = row[0]
        guild = ctx.guild
        for ch in guild.text_channels:
            try:
                await ch.edit(topic=f"[{name}] {desc}")
            except:
                pass
        await ctx.send(f"Theme {name} applied to available channels.")

# -------------------------
# PETS: commands
# -------------------------
class PetCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="pet_hunt")
    async def pet_hunt(self, ctx):
        ensure_user(ctx.author)
        if not deduct_currency(ctx.author.id, "copper", PET_HUNT_COST_COPPER):
            await ctx.send("You need 100 copper to go pet hunting.")
            return
        pet_id, name, rarity = give_pet(ctx.author.id)
        await ctx.send(f"🧸 You found a pet! {name} ({rarity}). Use `/pet_call {pet_id}` to summon.")

    @commands.command(name="pet_call")
    async def pet_call(self, ctx, pet_id: int):
        row = c.execute("SELECT owner_id, name, species, rarity FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if not row:
            await ctx.send("Pet not found.")
            return
        if row[0] != ctx.author.id:
            await ctx.send("You don't own this pet.")
            return
        add_currency(ctx.author.id, "copper", 10)
        await ctx.send(f"🐾 {ctx.author.mention} calls **{row[1]}** the {row[2]} ({row[3]}). You gained 10 copper.")

    @commands.command(name="pet_rename")
    async def pet_rename(self, ctx, pet_id: int, *, new_name: str):
        row = c.execute("SELECT owner_id FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if not row or row[0] != ctx.author.id:
            await ctx.send("You don't own this pet.")
            return
        c.execute("UPDATE pets SET name = ? WHERE id = ?", (new_name, pet_id))
        conn.commit()
        await ctx.send(f"Pet renamed to {new_name}.")

# -------------------------
# SHOP / ECONOMY
# -------------------------
class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.store = [
            {"name":"Confetti Bomb","price":20,"currency":"coin","desc":"Prank: confetti explosion in text channels"},
            {"name":"Chaos Hat","price":5,"currency":"gold","desc":"Funky hat tag"},
            {"name":"Shadow Cloak","price":1,"currency":"black_coins","desc":"Temporary invisibility in events"},
            {"name":"Royal Sigil","price":2,"currency":"diamond","desc":"Minor royalty cosmetic effect"}
        ]

    @commands.command(name="store")
    async def store_cmd(self, ctx):
        text = "**🛒 Store**\n"
        for item in self.store:
            text += f"- {item['name']} — {item['price']} {item['currency']} | {item['desc']}\n"
        await ctx.send(text)

    @commands.command(name="buy")
    async def buy(self, ctx, *, item_name: str):
        item = next((i for i in self.store if i["name"].lower() == item_name.lower()), None)
        if not item:
            await ctx.send("No such item.")
            return
        cur = get_currency(ctx.author.id)
        if cur[item["currency"]] < item["price"]:
            await ctx.send("Not enough currency.")
            return
        ded = deduct_currency(ctx.author.id, item["currency"], item["price"])
        if not ded:
            await ctx.send("Purchase failed.")
            return
        award_item(ctx.author.id, item["name"], tier="Rare" if item["currency"] in ("gold","diamond") else "Common", effect=item["desc"])
        await ctx.send(f"✅ Purchased {item['name']}!")

# -------------------------
# XP & automatic loops (AI behaviors)
# -------------------------
@tasks.loop(minutes=5)
async def passive_xp_loop():
    rows = c.execute("SELECT user_id FROM users").fetchall()
    for r in rows:
        uid = r[0]
        add_currency(uid, "copper", random.randint(1,5))
        c.execute("UPDATE users SET xp = xp + ? WHERE user_id = ?", (random.randint(1,5), uid))
    conn.commit()

@tasks.loop(minutes=20)
async def joker_loop():
    for guild in bot.guilds:
        ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME) or (guild.text_channels[0] if guild.text_channels else None)
        if not ch:
            continue
        effect = random.choice(["memes","tag_swap","vc_prank"])
        if effect == "memes":
            await ch.send(random.choice(["😂", "🤡", "💥", "🌀", "🔥"]))
        elif effect == "tag_swap":
            members = [m for m in guild.members if not m.bot]
            if members:
                m = random.choice(members)
                new_tag = random.choice(["🤡 Clown", "🌀 Chaos Child", "💀 Jokered"])
                c.execute("UPDATE users SET tag = ? WHERE user_id = ?", (new_tag, m.id))
                conn.commit()
                await ch.send(f"🤡 Joker swapped tag of {m.display_name} to **{new_tag}**")
        elif effect == "vc_prank":
            await ch.send("🤡 Joker creates a surprise VC event!")

@tasks.loop(hours=1)
async def thor_loop():
    for guild in bot.guilds:
        ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME) or (guild.text_channels[0] if guild.text_channels else None)
        if ch:
            await ch.send(random.choice([
                "⚡ Thor: Do one thing today that your future self will thank you for.",
                "⚡ Thor: Study, grind, or chill — but do something useful!",
                "⚡ Thor: Tiny consistent steps beat massive one-time pushes."
            ]))

@tasks.loop(hours=2)
async def ladyluck_loop():
    rows = c.execute("SELECT user_id FROM users").fetchall()
    for r in rows:
        if random.random() < 0.1:
            uid = r[0]
            add_currency(uid, "coin", random.randint(1,5))
    conn.commit()

@tasks.loop(hours=6)
async def robin_loop():
    rows = c.execute("SELECT user_id FROM users").fetchall()
    for r in rows:
        uid = r[0]
        if random.random() < 0.2:
            add_currency(uid, "silver", random.randint(1,10))
    conn.commit()

@tasks.loop(hours=24)
async def issei_loop():
    if random.random() < 0.1:
        name = "Universe-"+str(random.randint(100,999))
        for guild in bot.guilds:
            ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME) or (guild.text_channels[0] if guild.text_channels else None)
            if ch:
                await ch.send(f"🌌 Issei Hyoudou has birthed **{name}**! New races and events unlock within.")

# -------------------------
# Admin / utility commands
# -------------------------
@bot.command(name="me")
async def me_cmd(ctx):
    ensure_user(ctx.author)
    row = c.execute("SELECT user_id, username, xp, level, tag, alignment, universe, gang_id, booster_level FROM users WHERE user_id = ?", (ctx.author.id,)).fetchone()
    uid, username, xp, level, tag, alignment, universe, gang_id, booster_level = row
    cur = get_currency(uid)
    tools = c.execute("SELECT name FROM tools WHERE owner_id = ?", (uid,)).fetchall()
    tool_list = ", ".join(t[0] for t in tools) if tools else "None"
    await ctx.send(f"**{ctx.author.display_name}** — Level {level} (XP {xp})\nTag: {tag}\nAlignment: {alignment}\nUniverse: {universe}\nGang ID: {gang_id}\nBooster: {booster_level}\nCoins: {cur}\nTools: {tool_list}")

@bot.command(name="daily")
async def daily_cmd(ctx):
    ensure_user(ctx.author)
    row = c.execute("SELECT last_daily FROM users WHERE user_id = ?", (ctx.author.id,)).fetchone()
    today = today_str()
    if row and row[0] == today:
        await ctx.send("You already claimed daily today.")
        return
    choice = random.choice(["copper","silver","coin","gold","black_coins"])
    amount = random.randint(5,50) if choice=="copper" else (random.randint(1,10) if choice=="silver" else (random.randint(1,3) if choice=="coin" else 1))
    add_currency(ctx.author.id, choice, amount)
    c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (today, ctx.author.id))
    conn.commit()
    await ctx.send(f"Daily claimed: {amount} {choice}!")

@bot.command(name="create_gang")
async def create_gang_cmd(ctx, name: str, alignment: str = "neutral"):
    alignment = alignment.lower()
    if alignment not in ("hero","villain","neutral"):
        await ctx.send("Alignment must be hero|villain|neutral")
        return
    c.execute("INSERT INTO gangs (name, alignment, leader_id) VALUES (?, ?, ?)", (name, alignment, ctx.author.id))
    conn.commit()
    gid = c.lastrowid
    c.execute("UPDATE users SET gang_id = ? WHERE user_id = ?", (gid, ctx.author.id))
    conn.commit()
    await ctx.send(f"Gang {name} created with alignment {alignment}. You are leader.")

@bot.command(name="join_gang")
async def join_gang_cmd(ctx, gang_name: str):
    row = c.execute("SELECT id FROM gangs WHERE name = ?", (gang_name,)).fetchone()
    if not row:
        await ctx.send("Gang not found.")
        return
    gid = row[0]
    c.execute("UPDATE users SET gang_id = ? WHERE user_id = ?", (gid, ctx.author.id))
    conn.commit()
    await ctx.send(f"You joined {gang_name}!")

@bot.command(name="royalize")
@commands.has_permissions(administrator=True)
async def royalize_cmd(ctx, member: discord.Member, tier: str = "Titan I"):
    ensure_user(member)
    c.execute("UPDATE users SET booster_level = ? WHERE user_id = ?", (tier, member.id))
    conn.commit()
    await ctx.send(f"{member.mention} has been granted booster tier {tier} and added to Royal Court.")
    ch = discord.utils.get(ctx.guild.text_channels, name=CENTRAL_HUB_NAME)
    if ch:
        await ch.send(f"👑 {member.display_name} has been elevated to **{tier}** and welcomed to the Royal Court!")

# -------------------------
# Cog registration
# -------------------------
bot.add_cog(GoblinCog(bot))
bot.add_cog(WhiteTigerCog(bot))
bot.add_cog(TwoFaceCog(bot))
bot.add_cog(DeadpoolCog(bot))
bot.add_cog(SpidermanCog(bot))
bot.add_cog(ThemeMasterCog(bot))
bot.add_cog(PetCog(bot))
bot.add_cog(ShopCog(bot))

# -------------------------
# On ready and background loops start
# -------------------------
@bot.event
async def on_ready():
    print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
    for guild in bot.guilds:
        ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
        if not ch and AUTO_CREATE_CHANNELS:
            try:
                await guild.create_text_channel(CENTRAL_HUB_NAME)
                print(f"Created {CENTRAL_HUB_NAME} in {guild.name}")
            except Exception as e:
                print("Could not create central-hub:", e)
    if not passive_xp_loop.is_running():
        passive_xp_loop.start()
    if not joker_loop.is_running():
        joker_loop.start()
    if not thor_loop.is_running():
        thor_loop.start()
    if not ladyluck_loop.is_running():
        ladyluck_loop.start()
    if not robin_loop.is_running():
        robin_loop.start()
    if not issei_loop.is_running():
        issei_loop.start()
    print("Background tasks started.")

@bot.event
async def on_member_join(member):
    ensure_user(member)
    try:
        await member.send(f"🧝 Dark Elf: Welcome, {member.name}! You were assigned a starter tag and small rewards.")
    except:
        pass
    add_currency(member.id, "copper", 200)
    for guild in bot.guilds:
        if guild.get_member(member.id):
            ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME) or (guild.text_channels[0] if guild.text_channels else None)
            if ch:
                await ch.send(f"✨ Welcome {member.mention} to the multiverse! Dark Elf provided starter gifts.")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
