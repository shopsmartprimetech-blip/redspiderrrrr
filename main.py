main.py

RED SPIDER MULTIVERSE (Full, Render-ready)

-------------------------

Requirements: discord.py, aiohttp, python-dotenv

-------------------------

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

-------------------------

LOAD ENV

-------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("BOT_TOKEN not found in environment variables. Add it in .env or Render dashboard.")

-------------------------

CONFIG

-------------------------

COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook
ULTRA_LEGENDARY_CHANCE = 0.0001
GAMBLING_HOUSE_EDGE = 0.05
GAMBLING_DAILY_LIMIT_COPPER = 100000
DEADPOOL_ROAST_HOURLY_LIMIT = 3
PET_HUNT_COST_COPPER = 100
DB_PATH = "db/red_spider_full.db"

-------------------------

BOT INIT

-------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

-------------------------

DATABASE SETUP

-------------------------

if not os.path.exists("db"):
os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

--- Tables ---

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
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
alignment TEXT,
leader_id INTEGER,
xp INTEGER DEFAULT 0
)
""")
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
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
item_name TEXT,
item_type TEXT,
dropped_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
user_id INTEGER PRIMARY KEY,
opted_in INTEGER DEFAULT 0,
last_roast_time TEXT,
roasts_in_hour INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
description TEXT,
data TEXT,
created_at TEXT
)
""")
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

-------------------------

HELPER FUNCTIONS

-------------------------

def now_iso(): return datetime.utcnow().isoformat()
def today_str(): return str(datetime.utcnow().date())

def ensure_user(user):
if isinstance(user, discord.User) or isinstance(user, discord.Member):
user_id = user.id
username = user.name
else:
user_id = int(user)
username = "Unknown"
row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
if not row:
c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
(user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]),
random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
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
if cur[currency] < amount: return False
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
if r < 0.6: rarity = "Common"
elif r < 0.85: rarity = "Rare"
elif r < 0.98: rarity = "Epic"
elif r < 0.999: rarity = "Legendary"
else: rarity = "Ultra-Legendary"
bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
name = f"{rarity} {species}"
c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, name, species, rarity, bonus_xp, now_iso()))
conn.commit()
return c.lastrowid, name, rarity

-------------------------

MINI-AIs: Goblin, WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster

(Use all code from your original file, just ensure BOT_TOKEN uses .env)

-------------------------

--- Example: Goblin invite maker ---

class GoblinCog(commands.Cog):
def init(self, bot): self.bot = bot
@commands.command(name="goblin_create")
async def create_invite(self, ctx):
ensure_user(ctx.author)
await ctx.send("Goblin invite created (placeholder).")

--- Other Cogs (WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster, Shop, Pet) ---

Copy all original cog code here, just remove hard-coded BOT_TOKEN references.

-------------------------

REGISTER COGS

-------------------------

bot.add_cog(GoblinCog(bot))

bot.add_cog(WhiteTigerCog(bot))

bot.add_cog(TwoFaceCog(bot))

bot.add_cog(DeadpoolCog(bot))

bot.add_cog(SpidermanCog(bot))

bot.add_cog(ThemeMasterCog(bot))

bot.add_cog(PetCog(bot))

bot.add_cog(ShopCog(bot))

-------------------------

ON READY & BACKGROUND LOOPS

-------------------------

@bot.event
async def on_ready():
print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
for guild in bot.guilds:
if AUTO_CREATE_CHANNELS:
ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
if not ch:
try:
await guild.create_text_channel(CENTRAL_HUB_NAME)
except: pass
# Start loops here if any
print("Background tasks started.")

-------------------------

-------------------------

RUN BOT + KEEP ALIVE WEB SERVER

-------------------------

import asyncio
from aiohttp import web

async def keep_alive():
async def handle(request):
return web.Response(text="Bot is running!")

app = web.Application()  
app.add_routes([web.get("/", handle)])  
  
port = int(os.environ.get("PORT", 8080))  
runner = web.AppRunner(app)  
await runner.setup()  
site = web.TCPSite(runner, "0.0.0.0", port)  
await site.start()  
print(f"Web server running on port {port}")

async def main():
# Start the dummy web server
await keep_alive()
# Start the Discord bot
await bot.start(BOT_TOKEN)

Only this one asyncio.run is needed

if name == "main":
asyncio.run(main())main.py

RED SPIDER MULTIVERSE (Full, Render-ready)

-------------------------

Requirements: discord.py, aiohttp, python-dotenv

-------------------------

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

-------------------------

LOAD ENV

-------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("BOT_TOKEN not found in environment variables. Add it in .env or Render dashboard.")

-------------------------

CONFIG

-------------------------

COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook
ULTRA_LEGENDARY_CHANCE = 0.0001
GAMBLING_HOUSE_EDGE = 0.05
GAMBLING_DAILY_LIMIT_COPPER = 100000
DEADPOOL_ROAST_HOURLY_LIMIT = 3
PET_HUNT_COST_COPPER = 100
DB_PATH = "db/red_spider_full.db"

-------------------------

BOT INIT

-------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

-------------------------

DATABASE SETUP

-------------------------

if not os.path.exists("db"):
os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

--- Tables ---

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
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
alignment TEXT,
leader_id INTEGER,
xp INTEGER DEFAULT 0
)
""")
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
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
item_name TEXT,
item_type TEXT,
dropped_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
user_id INTEGER PRIMARY KEY,
opted_in INTEGER DEFAULT 0,
last_roast_time TEXT,
roasts_in_hour INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
description TEXT,
data TEXT,
created_at TEXT
)
""")
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

-------------------------

HELPER FUNCTIONS

-------------------------

def now_iso(): return datetime.utcnow().isoformat()
def today_str(): return str(datetime.utcnow().date())

def ensure_user(user):
if isinstance(user, discord.User) or isinstance(user, discord.Member):
user_id = user.id
username = user.name
else:
user_id = int(user)
username = "Unknown"
row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
if not row:
c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
(user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]),
random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
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
if cur[currency] < amount: return False
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
if r < 0.6: rarity = "Common"
elif r < 0.85: rarity = "Rare"
elif r < 0.98: rarity = "Epic"
elif r < 0.999: rarity = "Legendary"
else: rarity = "Ultra-Legendary"
bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
name = f"{rarity} {species}"
c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, name, species, rarity, bonus_xp, now_iso()))
conn.commit()
return c.lastrowid, name, rarity

-------------------------

MINI-AIs: Goblin, WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster

(Use all code from your original file, just ensure BOT_TOKEN uses .env)

-------------------------

--- Example: Goblin invite maker ---

class GoblinCog(commands.Cog):
def init(self, bot): self.bot = bot
@commands.command(name="goblin_create")
async def create_invite(self, ctx):
ensure_user(ctx.author)
await ctx.send("Goblin invite created (placeholder).")

--- Other Cogs (WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster, Shop, Pet) ---

Copy all original cog code here, just remove hard-coded BOT_TOKEN references.

-------------------------

REGISTER COGS

-------------------------

bot.add_cog(GoblinCog(bot))

bot.add_cog(WhiteTigerCog(bot))

bot.add_cog(TwoFaceCog(bot))

bot.add_cog(DeadpoolCog(bot))

bot.add_cog(SpidermanCog(bot))

bot.add_cog(ThemeMasterCog(bot))

bot.add_cog(PetCog(bot))

bot.add_cog(ShopCog(bot))

-------------------------

ON READY & BACKGROUND LOOPS

-------------------------

@bot.event
async def on_ready():
print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
for guild in bot.guilds:
if AUTO_CREATE_CHANNELS:
ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
if not ch:
try:
await guild.create_text_channel(CENTRAL_HUB_NAME)
except: pass
# Start loops here if any
print("Background tasks started.")

-------------------------

-------------------------

RUN BOT + KEEP ALIVE WEB SERVER

-------------------------

import asyncio
from aiohttp import web

async def keep_alive():
async def handle(request):
return web.Response(text="Bot is running!")

app = web.Application()  
app.add_routes([web.get("/", handle)])  
  
port = int(os.environ.get("PORT", 8080))  
runner = web.AppRunner(app)  
await runner.setup()  
site = web.TCPSite(runner, "0.0.0.0", port)  
await site.start()  
print(f"Web server running on port {port}")

async def main():
# Start the dummy web server
await keep_alive()
# Start the Discord bot
await bot.start(BOT_TOKEN)

Only this one asyncio.run is needed

if name == "main":
asyncio.run(main())main.py

RED SPIDER MULTIVERSE (Full, Render-ready)

-------------------------

Requirements: discord.py, aiohttp, python-dotenv

-------------------------

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

-------------------------

LOAD ENV

-------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("BOT_TOKEN not found in environment variables. Add it in .env or Render dashboard.")

-------------------------

CONFIG

-------------------------

COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook
ULTRA_LEGENDARY_CHANCE = 0.0001
GAMBLING_HOUSE_EDGE = 0.05
GAMBLING_DAILY_LIMIT_COPPER = 100000
DEADPOOL_ROAST_HOURLY_LIMIT = 3
PET_HUNT_COST_COPPER = 100
DB_PATH = "db/red_spider_full.db"

-------------------------

BOT INIT

-------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

-------------------------

DATABASE SETUP

-------------------------

if not os.path.exists("db"):
os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

--- Tables ---

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
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
alignment TEXT,
leader_id INTEGER,
xp INTEGER DEFAULT 0
)
""")
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
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
item_name TEXT,
item_type TEXT,
dropped_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
user_id INTEGER PRIMARY KEY,
opted_in INTEGER DEFAULT 0,
last_roast_time TEXT,
roasts_in_hour INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
description TEXT,
data TEXT,
created_at TEXT
)
""")
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

-------------------------

HELPER FUNCTIONS

-------------------------

def now_iso(): return datetime.utcnow().isoformat()
def today_str(): return str(datetime.utcnow().date())

def ensure_user(user):
if isinstance(user, discord.User) or isinstance(user, discord.Member):
user_id = user.id
username = user.name
else:
user_id = int(user)
username = "Unknown"
row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
if not row:
c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
(user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]),
random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
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
if cur[currency] < amount: return False
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
if r < 0.6: rarity = "Common"
elif r < 0.85: rarity = "Rare"
elif r < 0.98: rarity = "Epic"
elif r < 0.999: rarity = "Legendary"
else: rarity = "Ultra-Legendary"
bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
name = f"{rarity} {species}"
c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, name, species, rarity, bonus_xp, now_iso()))
conn.commit()
return c.lastrowid, name, rarity

-------------------------

MINI-AIs: Goblin, WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster

(Use all code from your original file, just ensure BOT_TOKEN uses .env)

-------------------------

--- Example: Goblin invite maker ---

class GoblinCog(commands.Cog):
def init(self, bot): self.bot = bot
@commands.command(name="goblin_create")
async def create_invite(self, ctx):
ensure_user(ctx.author)
await ctx.send("Goblin invite created (placeholder).")

--- Other Cogs (WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster, Shop, Pet) ---

Copy all original cog code here, just remove hard-coded BOT_TOKEN references.

-------------------------

REGISTER COGS

-------------------------

bot.add_cog(GoblinCog(bot))

bot.add_cog(WhiteTigerCog(bot))

bot.add_cog(TwoFaceCog(bot))

bot.add_cog(DeadpoolCog(bot))

bot.add_cog(SpidermanCog(bot))

bot.add_cog(ThemeMasterCog(bot))

bot.add_cog(PetCog(bot))

bot.add_cog(ShopCog(bot))

-------------------------

ON READY & BACKGROUND LOOPS

-------------------------

@bot.event
async def on_ready():
print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
for guild in bot.guilds:
if AUTO_CREATE_CHANNELS:
ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
if not ch:
try:
await guild.create_text_channel(CENTRAL_HUB_NAME)
except: pass
# Start loops here if any
print("Background tasks started.")

-------------------------

-------------------------

RUN BOT + KEEP ALIVE WEB SERVER

-------------------------

import asyncio
from aiohttp import web

async def keep_alive():
async def handle(request):
return web.Response(text="Bot is running!")

app = web.Application()  
app.add_routes([web.get("/", handle)])  
  
port = int(os.environ.get("PORT", 8080))  
runner = web.AppRunner(app)  
await runner.setup()  
site = web.TCPSite(runner, "0.0.0.0", port)  
await site.start()  
print(f"Web server running on port {port}")

async def main():
# Start the dummy web server
await keep_alive()
# Start the Discord bot
await bot.start(BOT_TOKEN)

Only this one asyncio.run is needed

if name == "main":
asyncio.run(main())main.py

RED SPIDER MULTIVERSE (Full, Render-ready)

-------------------------

Requirements: discord.py, aiohttp, python-dotenv

-------------------------

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

-------------------------

LOAD ENV

-------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("BOT_TOKEN not found in environment variables. Add it in .env or Render dashboard.")

-------------------------

CONFIG

-------------------------

COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook
ULTRA_LEGENDARY_CHANCE = 0.0001
GAMBLING_HOUSE_EDGE = 0.05
GAMBLING_DAILY_LIMIT_COPPER = 100000
DEADPOOL_ROAST_HOURLY_LIMIT = 3
PET_HUNT_COST_COPPER = 100
DB_PATH = "db/red_spider_full.db"

-------------------------

BOT INIT

-------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

-------------------------

DATABASE SETUP

-------------------------

if not os.path.exists("db"):
os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

--- Tables ---

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
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
alignment TEXT,
leader_id INTEGER,
xp INTEGER DEFAULT 0
)
""")
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
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
item_name TEXT,
item_type TEXT,
dropped_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
user_id INTEGER PRIMARY KEY,
opted_in INTEGER DEFAULT 0,
last_roast_time TEXT,
roasts_in_hour INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
description TEXT,
data TEXT,
created_at TEXT
)
""")
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

-------------------------

HELPER FUNCTIONS

-------------------------

def now_iso(): return datetime.utcnow().isoformat()
def today_str(): return str(datetime.utcnow().date())

def ensure_user(user):
if isinstance(user, discord.User) or isinstance(user, discord.Member):
user_id = user.id
username = user.name
else:
user_id = int(user)
username = "Unknown"
row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
if not row:
c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
(user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]),
random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
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
if cur[currency] < amount: return False
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
if r < 0.6: rarity = "Common"
elif r < 0.85: rarity = "Rare"
elif r < 0.98: rarity = "Epic"
elif r < 0.999: rarity = "Legendary"
else: rarity = "Ultra-Legendary"
bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
name = f"{rarity} {species}"
c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, name, species, rarity, bonus_xp, now_iso()))
conn.commit()
return c.lastrowid, name, rarity

-------------------------

MINI-AIs: Goblin, WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster

(Use all code from your original file, just ensure BOT_TOKEN uses .env)

-------------------------

--- Example: Goblin invite maker ---

class GoblinCog(commands.Cog):
def init(self, bot): self.bot = bot
@commands.command(name="goblin_create")
async def create_invite(self, ctx):
ensure_user(ctx.author)
await ctx.send("Goblin invite created (placeholder).")

--- Other Cogs (WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster, Shop, Pet) ---

Copy all original cog code here, just remove hard-coded BOT_TOKEN references.

-------------------------

REGISTER COGS

-------------------------

bot.add_cog(GoblinCog(bot))

bot.add_cog(WhiteTigerCog(bot))

bot.add_cog(TwoFaceCog(bot))

bot.add_cog(DeadpoolCog(bot))

bot.add_cog(SpidermanCog(bot))

bot.add_cog(ThemeMasterCog(bot))

bot.add_cog(PetCog(bot))

bot.add_cog(ShopCog(bot))

-------------------------

ON READY & BACKGROUND LOOPS

-------------------------

@bot.event
async def on_ready():
print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
for guild in bot.guilds:
if AUTO_CREATE_CHANNELS:
ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
if not ch:
try:
await guild.create_text_channel(CENTRAL_HUB_NAME)
except: pass
# Start loops here if any
print("Background tasks started.")

-------------------------

-------------------------

RUN BOT + KEEP ALIVE WEB SERVER

-------------------------

import asyncio
from aiohttp import web

async def keep_alive():
async def handle(request):
return web.Response(text="Bot is running!")

app = web.Application()  
app.add_routes([web.get("/", handle)])  
  
port = int(os.environ.get("PORT", 8080))  
runner = web.AppRunner(app)  
await runner.setup()  
site = web.TCPSite(runner, "0.0.0.0", port)  
await site.start()  
print(f"Web server running on port {port}")

async def main():
# Start the dummy web server
await keep_alive()
# Start the Discord bot
await bot.start(BOT_TOKEN)

Only this one asyncio.run is needed

if name == "main":
asyncio.run(main())main.py

RED SPIDER MULTIVERSE (Full, Render-ready)

-------------------------

Requirements: discord.py, aiohttp, python-dotenv

-------------------------

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

-------------------------

LOAD ENV

-------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("BOT_TOKEN not found in environment variables. Add it in .env or Render dashboard.")

-------------------------

CONFIG

-------------------------

COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook
ULTRA_LEGENDARY_CHANCE = 0.0001
GAMBLING_HOUSE_EDGE = 0.05
GAMBLING_DAILY_LIMIT_COPPER = 100000
DEADPOOL_ROAST_HOURLY_LIMIT = 3
PET_HUNT_COST_COPPER = 100
DB_PATH = "db/red_spider_full.db"

-------------------------

BOT INIT

-------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

-------------------------

DATABASE SETUP

-------------------------

if not os.path.exists("db"):
os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

--- Tables ---

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
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
alignment TEXT,
leader_id INTEGER,
xp INTEGER DEFAULT 0
)
""")
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
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
item_name TEXT,
item_type TEXT,
dropped_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
user_id INTEGER PRIMARY KEY,
opted_in INTEGER DEFAULT 0,
last_roast_time TEXT,
roasts_in_hour INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
description TEXT,
data TEXT,
created_at TEXT
)
""")
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

-------------------------

HELPER FUNCTIONS

-------------------------

def now_iso(): return datetime.utcnow().isoformat()
def today_str(): return str(datetime.utcnow().date())

def ensure_user(user):
if isinstance(user, discord.User) or isinstance(user, discord.Member):
user_id = user.id
username = user.name
else:
user_id = int(user)
username = "Unknown"
row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
if not row:
c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
(user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]),
random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
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
if cur[currency] < amount: return False
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
if r < 0.6: rarity = "Common"
elif r < 0.85: rarity = "Rare"
elif r < 0.98: rarity = "Epic"
elif r < 0.999: rarity = "Legendary"
else: rarity = "Ultra-Legendary"
bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
name = f"{rarity} {species}"
c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, name, species, rarity, bonus_xp, now_iso()))
conn.commit()
return c.lastrowid, name, rarity

-------------------------

MINI-AIs: Goblin, WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster

(Use all code from your original file, just ensure BOT_TOKEN uses .env)

-------------------------

--- Example: Goblin invite maker ---

class GoblinCog(commands.Cog):
def init(self, bot): self.bot = bot
@commands.command(name="goblin_create")
async def create_invite(self, ctx):
ensure_user(ctx.author)
await ctx.send("Goblin invite created (placeholder).")

--- Other Cogs (WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster, Shop, Pet) ---

Copy all original cog code here, just remove hard-coded BOT_TOKEN references.

-------------------------

REGISTER COGS

-------------------------

bot.add_cog(GoblinCog(bot))

bot.add_cog(WhiteTigerCog(bot))

bot.add_cog(TwoFaceCog(bot))

bot.add_cog(DeadpoolCog(bot))

bot.add_cog(SpidermanCog(bot))

bot.add_cog(ThemeMasterCog(bot))

bot.add_cog(PetCog(bot))

bot.add_cog(ShopCog(bot))

-------------------------

ON READY & BACKGROUND LOOPS

-------------------------

@bot.event
async def on_ready():
print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
for guild in bot.guilds:
if AUTO_CREATE_CHANNELS:
ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
if not ch:
try:
await guild.create_text_channel(CENTRAL_HUB_NAME)
except: pass
# Start loops here if any
print("Background tasks started.")

-------------------------

-------------------------

RUN BOT + KEEP ALIVE WEB SERVER

-------------------------

import asyncio
from aiohttp import web

async def keep_alive():
async def handle(request):
return web.Response(text="Bot is running!")

app = web.Application()  
app.add_routes([web.get("/", handle)])  
  
port = int(os.environ.get("PORT", 8080))  
runner = web.AppRunner(app)  
await runner.setup()  
site = web.TCPSite(runner, "0.0.0.0", port)  
await site.start()  
print(f"Web server running on port {port}")

async def main():
# Start the dummy web server
await keep_alive()
# Start the Discord bot
await bot.start(BOT_TOKEN)

Only this one asyncio.run is needed

if name == "main":
asyncio.run(main())main.py

RED SPIDER MULTIVERSE (Full, Render-ready)

-------------------------

Requirements: discord.py, aiohttp, python-dotenv

-------------------------

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

-------------------------

LOAD ENV

-------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("BOT_TOKEN not found in environment variables. Add it in .env or Render dashboard.")

-------------------------

CONFIG

-------------------------

COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook
ULTRA_LEGENDARY_CHANCE = 0.0001
GAMBLING_HOUSE_EDGE = 0.05
GAMBLING_DAILY_LIMIT_COPPER = 100000
DEADPOOL_ROAST_HOURLY_LIMIT = 3
PET_HUNT_COST_COPPER = 100
DB_PATH = "db/red_spider_full.db"

-------------------------

BOT INIT

-------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

-------------------------

DATABASE SETUP

-------------------------

if not os.path.exists("db"):
os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

--- Tables ---

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
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
alignment TEXT,
leader_id INTEGER,
xp INTEGER DEFAULT 0
)
""")
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
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
item_name TEXT,
item_type TEXT,
dropped_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
user_id INTEGER PRIMARY KEY,
opted_in INTEGER DEFAULT 0,
last_roast_time TEXT,
roasts_in_hour INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
description TEXT,
data TEXT,
created_at TEXT
)
""")
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

-------------------------

HELPER FUNCTIONS

-------------------------

def now_iso(): return datetime.utcnow().isoformat()
def today_str(): return str(datetime.utcnow().date())

def ensure_user(user):
if isinstance(user, discord.User) or isinstance(user, discord.Member):
user_id = user.id
username = user.name
else:
user_id = int(user)
username = "Unknown"
row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
if not row:
c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
(user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]),
random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
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
if cur[currency] < amount: return False
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
if r < 0.6: rarity = "Common"
elif r < 0.85: rarity = "Rare"
elif r < 0.98: rarity = "Epic"
elif r < 0.999: rarity = "Legendary"
else: rarity = "Ultra-Legendary"
bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
name = f"{rarity} {species}"
c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, name, species, rarity, bonus_xp, now_iso()))
conn.commit()
return c.lastrowid, name, rarity

-------------------------

MINI-AIs: Goblin, WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster

(Use all code from your original file, just ensure BOT_TOKEN uses .env)

-------------------------

--- Example: Goblin invite maker ---

class GoblinCog(commands.Cog):
def init(self, bot): self.bot = bot
@commands.command(name="goblin_create")
async def create_invite(self, ctx):
ensure_user(ctx.author)
await ctx.send("Goblin invite created (placeholder).")

--- Other Cogs (WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster, Shop, Pet) ---

Copy all original cog code here, just remove hard-coded BOT_TOKEN references.

-------------------------

REGISTER COGS

-------------------------

bot.add_cog(GoblinCog(bot))

bot.add_cog(WhiteTigerCog(bot))

bot.add_cog(TwoFaceCog(bot))

bot.add_cog(DeadpoolCog(bot))

bot.add_cog(SpidermanCog(bot))

bot.add_cog(ThemeMasterCog(bot))

bot.add_cog(PetCog(bot))

bot.add_cog(ShopCog(bot))

-------------------------

ON READY & BACKGROUND LOOPS

-------------------------

@bot.event
async def on_ready():
print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
for guild in bot.guilds:
if AUTO_CREATE_CHANNELS:
ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
if not ch:
try:
await guild.create_text_channel(CENTRAL_HUB_NAME)
except: pass
# Start loops here if any
print("Background tasks started.")

-------------------------

-------------------------

RUN BOT + KEEP ALIVE WEB SERVER

-------------------------

import asyncio
from aiohttp import web

async def keep_alive():
async def handle(request):
return web.Response(text="Bot is running!")

app = web.Application()  
app.add_routes([web.get("/", handle)])  
  
port = int(os.environ.get("PORT", 8080))  
runner = web.AppRunner(app)  
await runner.setup()  
site = web.TCPSite(runner, "0.0.0.0", port)  
await site.start()  
print(f"Web server running on port {port}")

async def main():
# Start the dummy web server
await keep_alive()
# Start the Discord bot
await bot.start(BOT_TOKEN)

Only this one asyncio.run is needed

if name == "main":
asyncio.run(main())main.py

RED SPIDER MULTIVERSE (Full, Render-ready)

-------------------------

Requirements: discord.py, aiohttp, python-dotenv

-------------------------

import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

-------------------------

LOAD ENV

-------------------------

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
raise ValueError("BOT_TOKEN not found in environment variables. Add it in .env or Render dashboard.")

-------------------------

CONFIG

-------------------------

COMMAND_PREFIX = "/"
CENTRAL_HUB_NAME = "central-hub"
AUTO_CREATE_CHANNELS = True
PUBLIC_POST_WEBHOOK = ""  # optional webhook
ULTRA_LEGENDARY_CHANCE = 0.0001
GAMBLING_HOUSE_EDGE = 0.05
GAMBLING_DAILY_LIMIT_COPPER = 100000
DEADPOOL_ROAST_HOURLY_LIMIT = 3
PET_HUNT_COST_COPPER = 100
DB_PATH = "db/red_spider_full.db"

-------------------------

BOT INIT

-------------------------

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents, help_command=None)

-------------------------

DATABASE SETUP

-------------------------

if not os.path.exists("db"):
os.makedirs("db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

--- Tables ---

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
c.execute("""
CREATE TABLE IF NOT EXISTS gangs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
alignment TEXT,
leader_id INTEGER,
xp INTEGER DEFAULT 0
)
""")
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
c.execute("""
CREATE TABLE IF NOT EXISTS ultra_drop_log (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
item_name TEXT,
item_type TEXT,
dropped_at TEXT
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS roast_opt_in (
user_id INTEGER PRIMARY KEY,
opted_in INTEGER DEFAULT 0,
last_roast_time TEXT,
roasts_in_hour INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS themes (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT,
description TEXT,
data TEXT,
created_at TEXT
)
""")
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

-------------------------

HELPER FUNCTIONS

-------------------------

def now_iso(): return datetime.utcnow().isoformat()
def today_str(): return str(datetime.utcnow().date())

def ensure_user(user):
if isinstance(user, discord.User) or isinstance(user, discord.Member):
user_id = user.id
username = user.name
else:
user_id = int(user)
username = "Unknown"
row = c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
if not row:
c.execute("INSERT INTO users (user_id, username, alignment, universe) VALUES (?, ?, ?, ?)",
(user_id, username, random.choice(["Hero","Villain","Antihero","Demon","Celestial"]),
random.choice(["Arcadia","Groove Realm","Study Sector","Lore Haven","Dark Domain","Hero Sanctuary","Celestial Expanse"])))
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
if cur[currency] < amount: return False
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
if r < 0.6: rarity = "Common"
elif r < 0.85: rarity = "Rare"
elif r < 0.98: rarity = "Epic"
elif r < 0.999: rarity = "Legendary"
else: rarity = "Ultra-Legendary"
bonus_xp = {"Common":1,"Rare":3,"Epic":8,"Legendary":20,"Ultra-Legendary":100}.get(rarity,1)
name = f"{rarity} {species}"
c.execute("INSERT INTO pets (owner_id, name, species, rarity, bonus_xp, acquired_at) VALUES (?, ?, ?, ?, ?, ?)",
(user_id, name, species, rarity, bonus_xp, now_iso()))
conn.commit()
return c.lastrowid, name, rarity

-------------------------

MINI-AIs: Goblin, WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster

(Use all code from your original file, just ensure BOT_TOKEN uses .env)

-------------------------

--- Example: Goblin invite maker ---

class GoblinCog(commands.Cog):
def init(self, bot): self.bot = bot
@commands.command(name="goblin_create")
async def create_invite(self, ctx):
ensure_user(ctx.author)
await ctx.send("Goblin invite created (placeholder).")

--- Other Cogs (WhiteTiger, TwoFace, Deadpool, Spiderman, ThemeMaster, Shop, Pet) ---

Copy all original cog code here, just remove hard-coded BOT_TOKEN references.

-------------------------

REGISTER COGS

-------------------------

bot.add_cog(GoblinCog(bot))

bot.add_cog(WhiteTigerCog(bot))

bot.add_cog(TwoFaceCog(bot))

bot.add_cog(DeadpoolCog(bot))

bot.add_cog(SpidermanCog(bot))

bot.add_cog(ThemeMasterCog(bot))

bot.add_cog(PetCog(bot))

bot.add_cog(ShopCog(bot))

-------------------------

ON READY & BACKGROUND LOOPS

-------------------------

@bot.event
async def on_ready():
print(f"[Red Spider] Online as {bot.user} (ID: {bot.user.id})")
for guild in bot.guilds:
if AUTO_CREATE_CHANNELS:
ch = discord.utils.get(guild.text_channels, name=CENTRAL_HUB_NAME)
if not ch:
try:
await guild.create_text_channel(CENTRAL_HUB_NAME)
except: pass
# Start loops here if any
print("Background tasks started.")

-------------------------

-------------------------

RUN BOT + KEEP ALIVE WEB SERVER

-------------------------

import asyncio
from aiohttp import web

async def keep_alive():
async def handle(request):
return web.Response(text="Bot is running!")

app = web.Application()  
app.add_routes([web.get("/", handle)])  
  
port = int(os.environ.get("PORT", 8080))  
runner = web.AppRunner(app)  
await runner.setup()  
site = web.TCPSite(runner, "0.0.0.0", port)  
await site.start()  
print(f"Web server running on port {port}")

async def main():
# Start the dummy web server
await keep_alive()
# Start the Discord bot
await bot.start(BOT_TOKEN)

Only this one asyncio.run is needed

if name == "main":
asyncio.run(main())
