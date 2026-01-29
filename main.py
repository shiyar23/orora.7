import telebot
import logging
import os
from telebot import types

# --- إعدادات البيئة ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNELS_RAW = os.getenv('CHANNELS', '@aicodtrading,-1003715686424')

bot = telebot.TeleBot(BOT_TOKEN)

CHANNELS_LIST = []
for c in CHANNELS_RAW.split(','):
    c = c.strip()
    if c.replace('-', '').isdigit():
        CHANNELS_LIST.append(int(c))
    else:
        CHANNELS_LIST.append(c)

logging.basicConfig(level=logging.INFO)
user_data = {}

EMOJI_MAP = {
    "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "AUD": "🇦🇺",
    "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "GOLD": "🏆", "SILVER": "🪙", "BTC": "₿", "ETH": "💎"
}

COMMODITIES = {
    "EURUSD": ("EUR/USD", "EUR", 5, 0.0001, 50),
    "GBPUSD": ("GBP/USD", "GBP", 5, 0.0001, 50),
    "USDJPY": ("USD/JPY", "JPY", 3, 0.01, 5.0),
    "XAUUSD": ("GOLD", "GOLD", 2, 1.0, 5.0),
    "BTCUSD": ("BTC/USD", "BTC", 2, 1.0, 100.0),
}

# --- الدوال المساعدة ---

def calculate_pips(entry, target, pip_size, symbol):
    try:
        diff = abs(float(target) - float(entry))
        if "XAU" in symbol or "GOLD" in symbol: return int(round(diff * 10, 0))
        return int(round(diff / pip_size, 0))
    except: return 0

def generate_setup_text(data):
    symbol = data['commodity']
    name, _, decimals, _, _ = COMMODITIES[symbol]
    direction_emoji = '🟢' if 'BUY' in data['trade_type'] else '🔴'
    
    if data.get('is_closed'):
        status_label = "🛑 انتهت صلاحية الصفقة (CLOSED)"
    elif "LIMIT" in data['trade_type'] and not data.get('is_active'):
        status_label = "⏳ معلقة (LIMIT)"
    else:
        status_label = "⚡ مفعلة (ACTIVE)"
    
    txt = f"<b>📊 SETUP: {name} {data['emoji']}</b>\n"
    txt += f"<b>━━━━━━━━━━━━━━</b>\n"
    txt += f"<b>Status: {status_label}</b>\n"
    txt += f"<b>Type: {data['trade_type']} {direction_emoji}</b>\n\n"
    txt += f"<b>Entry: <code>{data['entry_display']}</code></b>\n"
    
    sl_label = f"<b>🛡️ {data.get('sl_at', '')}</b>" if data.get('is_secured') else "<b>❌</b>"
    txt += f"<b>SL: <code>{data['sl']:.{decimals}f}</code> {sl_label}</b>\n\n"
    
    for i, tp in enumerate(data['tp_prices']):
        status = "<b>✅ Done</b>" if data.get(f'tp{i+1}_done') else "<b>☑️</b>"
        txt += f"{status} <b>TP{i+1}: <code>{tp:.{decimals}f}</code></b>\n"
        
    if data.get('swing_price'):
        swing_status = "<b>✅ Done</b>" if data.get('tp_swing_done') else "<b>☑️</b>"
        txt += f"{swing_status} <b>TP SWING <code>{data['swing_price']}</code></b>\n"
    
    txt += f"<b>━━━━━━━━━━━━━━</b>\n"
    txt += "<b>⚠️ الالتزام الصارم بإدارة رأس المال 📊💰</b>"
    return txt

def create_inline_buttons(data, is_for_admin=True):
    if not is_for_admin or data.get('is_closed'): return None
    markup = types.InlineKeyboardMarkup(row_width=1)
    symbol = data['commodity']

    if "LIMIT" in data['trade_type'] and not data.get('is_active'):
        markup.add(types.InlineKeyboardButton("🚀 تفعيل الصفقة الآن", callback_data="activate_trade"))

    for i, tp_price in enumerate(data['tp_prices']):
        tp_num = i + 1
        if not data.get(f'tp{tp_num}_done'):
            pips = calculate_pips(data['entry_low'], tp_price, COMMODITIES[symbol][3], symbol)
            markup.add(types.InlineKeyboardButton(f"✅ تحقيق الهدف {tp_num} (+{pips})", callback_data=f"hit_tp_{tp_num}"))

    if not data.get('tp_swing_done'):
        markup.add(types.InlineKeyboardButton("🎯 تحقيق SWING", callback_data="hit_swing"))
    
    markup.add(types.InlineKeyboardButton("➕ إضافة هدف (TP+)", callback_data="add_new_tp"))
    markup.add(types.InlineKeyboardButton("🛡️ تأمين (Trail SL)", callback_data="trail_menu"))
    markup.add(types.InlineKeyboardButton("⚙️ تعديل الصفقة", callback_data="main_edit"))
    markup.add(types.InlineKeyboardButton("✖️ إغلاق الصفقة نهائياً", callback_data="close_trade"))
    
    for channel in CHANNELS_LIST:
        if str(channel) not in data.get('published_channels', []):
            label = f"📢 نشر في {channel}"
            markup.add(types.InlineKeyboardButton(label, callback_data=f"send_to_{channel}"))
            
    return markup

def send_update_to_channels(data, text):
    for channel_id, msg_id in data.get('channel_msgs', {}).items():
        try: bot.send_message(channel_id, text, reply_to_message_id=msg_id, parse_mode='HTML')
        except: pass

def update_everywhere(user_id):
    if user_id not in user_data: return
    data = user_data[user_id]
    text = generate_setup_text(data)
    
    admin_markup = create_inline_buttons(data, is_for_admin=True)
    try: bot.edit_message_text(text, data['chat_id'], data['msg_id'], reply_markup=admin_markup, parse_mode='HTML')
    except: pass
    
    for channel, m_id in data.get('channel_msgs', {}).items():
        try: bot.edit_message_text(text, channel, m_id, reply_markup=None, parse_mode='HTML')
        except: pass

# --- المعالجات (Handlers) ---

@bot.message_handler(commands=['start', 'new'])
def cmd_start(message):
    uid = message.from_user.id
    user_data[uid] = {
        'chat_id': message.chat.id, 'channel_msgs': {}, 'published_channels': [], 
        'tp_prices': [], 'is_secured': False, 'sl_at': '',
        'tp_swing_done': False, 'swing_price': '', 'is_active': False, 'is_closed': False
    }
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for k in COMMODITIES.keys(): markup.add(k)
    bot.send_message(message.chat.id, "<b>مرحباً! اختر الرمز للبدء:</b>", reply_markup=markup, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text in COMMODITIES)
def set_commodity(message):
    uid = message.from_user.id
    if uid not in user_data: cmd_start(message); return
    user_data[uid]['commodity'] = message.text
    user_data[uid]['emoji'] = EMOJI_MAP.get(COMMODITIES[message.text][1], "📈")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("BUY", "SELL", "BUY LIMIT", "SELL LIMIT")
    bot.send_message(message.chat.id, f"تم اختيار {message.text}. الآن اختر نوع الصفقة:", reply_markup=markup)
    bot.register_next_step_handler(message, set_type)

def set_type(message):
    uid = message.from_user.id
    if message.text not in ["BUY", "SELL", "BUY LIMIT", "SELL LIMIT"]:
        bot.send_message(message.chat.id, "عذراً، اختر النوع من الأزرار فقط.")
        return
    user_data[uid]['trade_type'] = message.text
    bot.send_message(message.chat.id, "أدخل سعر الدخول:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, set_entry)

def set_entry(message):
    uid = message.from_user.id
    try:
        user_data[uid]['entry_low'] = float(message.text)
        user_data[uid]['entry_display'] = message.text
        bot.send_message(message.chat.id, "أدخل سعر الـ SL (وقف الخسارة):")
        bot.register_next_step_handler(message, set_sl_and_finish)
    except:
        bot.send_message(message.chat.id, "الرجاء إدخال رقم صحيح لسعر الدخول:")
        bot.register_next_step_handler(message, set_entry)

def set_sl_and_finish(message):
    uid = message.from_user.id
    try:
        data = user_data[uid]
        data['sl'] = float(message.text)
        symbol = data['commodity']
        step = COMMODITIES[symbol][4]
        direction = 1 if "BUY" in data['trade_type'] else -1
        # توليد الأهداف التلقائية
        data['tp_prices'] = [round(data['entry_low'] + (i+1)*step*direction, COMMODITIES[symbol][2]) for i in range(3)]
        
        msg = bot.send_message(message.chat.id, generate_setup_text(data), parse_mode='HTML')
        data['msg_id'] = msg.message_id
        bot.edit_message_reply_markup(message.chat.id, msg.message_id, reply_markup=create_inline_buttons(data))
    except:
        bot.send_message(message.chat.id, "الرجاء إدخال رقم صحيح لـ SL:")
        bot.register_next_step_handler(message, set_sl_and_finish)

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    uid = call.from_user.id
    if uid not in user_data: return
    data = user_data[uid]
    symbol = data['commodity']

    if call.data == "activate_trade":
        data['is_active'] = True
        update_everywhere(uid)
        send_update_to_channels(data, f"🚀 <b>{symbol}</b>\n<b>تم تفعيل الصفقة الآن بنجاح! ✅</b>")

    elif call.data == "close_trade":
        data['is_closed'] = True
        update_everywhere(uid)
        send_update_to_channels(data, f"✖️ <b>{symbol}</b>\n<b>تم إغلاق الصفقة وإيقاف المتابعة. 🛑</b>")

    elif call.data.startswith("hit_tp_"):
        tp_num = int(call.data.split('_')[2])
        data[f'tp{tp_num}_done'] = True
        pips = calculate_pips(data['entry_low'], data['tp_prices'][tp_num-1], COMMODITIES[symbol][3], symbol)
        update_everywhere(uid)
        send_update_to_channels(data, f"<b>✅ تم تحقيق الهدف {tp_num}: <b>{pips}</b> نقطة 🏆</b>")

    elif call.data == "hit_swing":
        data['tp_swing_done'] = True
        update_everywhere(uid)
        send_update_to_channels(data, f"<b>🎯 تم تحقيق هدف SWING لـ {symbol} 🏆</b>")

    elif call.data == "add_new_tp":
        bot.send_message(call.message.chat.id, "أدخل سعر الهدف الجديد (TP+):")
        bot.register_next_step_handler(call.message, process_add_tp)

    elif call.data == "trail_menu":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🛡️ BE", callback_data="apply_trail_0"))
        for i in range(len(data['tp_prices'])):
            markup.add(types.InlineKeyboardButton(f"🛡️ TP{i+1}", callback_data=f"apply_trail_{i+1}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("apply_trail_"):
        idx = int(call.data.split('_')[2])
        data['is_secured'] = True
        data['sl'] = data['entry_low'] if idx == 0 else data['tp_prices'][idx-1]
        data['sl_at'] = "BE" if idx == 0 else f"TP{idx}"
        update_everywhere(uid)
        send_update_to_channels(data, f"🚨 <b>{symbol}</b>\n<b>تم تأمين الصفقة عند {data['sl_at']} 🛡️</b>")

    elif call.data == "main_edit":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 تعديل الدخول", callback_data="manual_edit_entry"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "manual_edit_entry":
        bot.send_message(call.message.chat.id, "أدخل سعر الدخول الجديد:")
        bot.register_next_step_handler(call.message, process_entry_edit)

    elif call.data == "back_to_main":
        update_everywhere(uid)

    elif call.data.startswith("send_to_"):
        target = call.data.split('_')[2]
        if target.replace('-', '').isdigit(): target = int(target)
        sent = bot.send_message(target, generate_setup_text(data), parse_mode='HTML')
        data['channel_msgs'][target] = sent.message_id
        update_everywhere(uid)

def process_add_tp(message):
    uid = message.from_user.id
    try:
        user_data[uid]['tp_prices'].append(float(message.text))
        update_everywhere(uid)
        bot.send_message(message.chat.id, "✅ تم إضافة الهدف الجديد.")
    except: bot.send_message(message.chat.id, "❌ خطأ في القيمة.")

def process_entry_edit(message):
    uid = message.from_user.id
    try:
        user_data[uid]['entry_low'] = float(message.text)
        user_data[uid]['entry_display'] = message.text
        update_everywhere(uid)
        bot.send_message(message.chat.id, "✅ تم تعديل سعر الدخول.")
    except: bot.send_message(message.chat.id, "❌ خطأ في القيمة.")

if __name__ == "__main__":
    bot.infinity_polling()
