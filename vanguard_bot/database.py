import aiosqlite
from config import DB_PATH, COMMISSION

class Database:
    async def init(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    balance REAL DEFAULT 0,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS deals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_number TEXT UNIQUE,
                    seller_id INTEGER,
                    buyer_id INTEGER,
                    amount REAL,
                    commission REAL,
                    seller_gets REAL,
                    description TEXT,
                    status TEXT DEFAULT 'pending_payment',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    total_volume REAL DEFAULT 624042.5,
                    total_deals INTEGER DEFAULT 1247,
                    total_commission REAL DEFAULT 9360.64
                )
            ''')
            await db.commit()

    async def add_user(self, user_id, username, full_name):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute('INSERT OR IGNORE INTO users (id, username, full_name) VALUES (?, ?, ?)',
                           (user_id, username, full_name))
            await db.commit()

    async def create_deal(self, seller_id, buyer_id, amount, description):
        import random
        deal_number = f"VG{random.randint(10000, 99999)}"
        commission = amount * COMMISSION
        seller_gets = amount - commission
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute('''
                INSERT INTO deals (deal_number, seller_id, buyer_id, amount, commission, seller_gets, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (deal_number, seller_id, buyer_id, amount, commission, seller_gets, description))
            await db.commit()
            return cursor.lastrowid, deal_number

    async def get_stats(self):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute('SELECT total_volume, total_deals, total_commission FROM stats WHERE id = 1')
            return await cursor.fetchone()

db = Database()