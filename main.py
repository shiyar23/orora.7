import telebot
import time
import logging
import os
from telebot import types

# --- إعدادات البيئة ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNELS_RAW = os.getenv('CHANNELS', '@aicodtrading,-1003715686424')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing!")

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
    "BTCUSD": ("BITCOIN", "BTC", 2, 1.0, 100.0),
}

# --- الدوال المساعدة ---

def calculate_pips(entry, target, pip_size, symbol):
    try:
        diff = abs(float(target) - float(entry))
        if "XAU" in symbol: return int(round(diff * 10, 0))
        return int(round(diff / pip_size, 0))
    except: return 0

def generate_setup_text(data):
    symbol = data['commodity']
    name, _, decimals, _, _ = COMMODITIES[symbol]
    direction_emoji = '🟢' if 'BUY' in data['trade_type'] else '🔴'
    
    txt = f"<b>📊 SETUP: {name} {data['emoji']}</b>\n"
    txt += f"<b>━━━━━━━━━━━━━━</b>\n"
    txt += f"<b>Type: {data['trade_type']} {direction_emoji}</b>\n\n"
    txt += f"<b>Entry: <code><b>{data['entry_display']}</b></code></b>\n"
    
    sl_label = f"<b>🛡️ {data.get('sl_at', '')}</b>" if data.get('is_secured') else "<b>❌</b>"
    txt += f"<b>SL: <code><b>{data['sl']:.{decimals}f}</b></code> {sl_label}</b>\n\n"
    
    for i, tp in enumerate(data['tp_prices']):
        status = "<b>✅ Done</b>" if data.get(f'tp{i+1}_done') else "<b>☑️</b>"
        txt += f"{status} <b>TP{i+1}: <code><b>{tp:.{decimals}f}</b></code></b>\n"
        
    swing_status = "<b>✅ Done</b>" if data.get('tp_swing_done') else "<b>☑️</b>"
    txt += f"{swing_status} <b>TP SWING</b>\n"
    txt += f"<b>━━━━━━━━━━━━━━</b>\n"
    txt += "<b>⚠️ الالتزام الصارم بإدارة رأس المال 📊💰</b>"
    return txt

def create_inline_buttons(data):
    msg_id = data['msg_id']
    symbol = data['commodity']
    markup = types.InlineKeyboardMarkup(row_width=1)

    for i, tp_price in enumerate(data['tp_prices']):
        tp_num = i + 1
        if not data.get(f'tp{tp_num}_done'):
            pips = calculate_pips(data['entry_low'], tp_price, COMMODITIES[symbol][3], symbol)
            markup.add(types.InlineKeyboardButton(f"✅ تحقيق الهدف {tp_num} (+{pips} نقطة)", callback_data=f"hit_tp_{tp_num}"))

    if not data.get('tp_swing_done'):
        markup.add(types.InlineKeyboardButton("🎯 تحقيق SWING", callback_data=f"hit_swing"))
    
    markup.add(types.InlineKeyboardButton("🛡️ تأمين الأرباح (Trail SL)", callback_data=f"trail_menu"))
    markup.add(types.InlineKeyboardButton("⚙️ تعديل الصفقة", callback_data=f"main_edit"))
    
    for channel in CHANNELS_LIST:
        if str(channel) not in data.get('published_channels', []):
            label = "القناة الخاصة" if isinstance(channel, int) else channel
            markup.add(types.InlineKeyboardButton(f"📢 نشر في {label}", callback_data=f"send_to_{channel}"))
            
    return markup

def update_everywhere(user_id):
    data = user_data[user_id]
    text = generate_setup_text(data)
    markup = create_inline_buttons(data)
    try: bot.edit_message_text(text, data['chat_id'], data['msg_id'], reply_markup=markup, parse_mode='HTML')
    except: pass
    for channel, m_id in data.get('channel_msgs', {}).items():
        try: bot.edit_message_text(text, channel, m_id, parse_mode='HTML')
        except: pass

# --- المعالجات ---

@bot.message_handler(commands=['start', 'new'])
def cmd_start(message):
    uid = message.from_user.id
    user_data[uid] = {
        'chat_id': message.chat.id, 
        'channel_msgs': {}, 
        'published_channels': [], 
        'tp_prices': [], 
        'is_secured': False, 
        'sl_at': '',
        'tp_swing_done': False
    }
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for k in COMMODITIES.keys(): markup.add(k)
    bot.send_message(message.chat.id, "<b>مرحباً بك! اختر الرمز للبدء:</b>", reply_markup=markup, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text in COMMODITIES)
def set_commodity(message):
    uid = message.from_user.id
    user_data[uid]['commodity'] = message.text
    user_data[uid]['emoji'] = EMOJI_MAP.get(COMMODITIES[message.text][1], "📈")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("BUY", "SELL", "BUY LIMIT", "SELL LIMIT")
    bot.send_message(message.chat.id, "<b>اختر نوع الصفقة:</b>", reply_markup=markup, parse_mode='HTML')
    bot.register_next_step_handler(message, set_type)

def set_type(message):
    user_data[message.from_user.id]['trade_type'] = message.text
    bot.send_message(message.chat.id, "<b>أدخل سعر الدخول:</b>", reply_markup=types.ReplyKeyboardRemove(), parse_mode='HTML')
    bot.register_next_step_handler(message, set_entry)

def set_entry(message):
    uid = message.from_user.id
    try:
        user_data[uid]['entry_low'] = float(message.text)
        user_data[uid]['entry_display'] = message.text
        bot.send_message(message.chat.id, "<b>أدخل سعر وقف الخسارة (SL):</b>", parse_mode='HTML')
        bot.register_next_step_handler(message, set_sl_and_finish)
    except:
        bot.send_message(message.chat.id, "⚠️ رقم غير صحيح، حاول ثانية:")
        bot.register_next_step_handler(message, set_entry)

def set_sl_and_finish(message):
    uid = message.from_user.id
    try:
        user_data[uid]['sl'] = float(message.text)
        symbol = user_data[uid]['commodity']
        step = COMMODITIES[symbol][4]
        direction = 1 if "BUY" in user_data[uid]['trade_type'] else -1
        user_data[uid]['tp_prices'] = [round(user_data[uid]['entry_low'] + (i+1)*step*direction, COMMODITIES[symbol][2]) for i in range(3)]
        
        msg = bot.send_message(message.chat.id, generate_setup_text(user_data[uid]), parse_mode='HTML')
        user_data[uid]['msg_id'] = msg.message_id
        bot.edit_message_reply_markup(message.chat.id, msg.message_id, reply_markup=create_inline_buttons(user_data[uid]))
    except:
        bot.send_message(message.chat.id, "⚠️ رقم غير صحيح، حاول ثانية:")
        bot.register_next_step_handler(message, set_sl_and_finish)

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    uid = call.from_user.id
    if uid not in user_data: return
    data = user_data[uid]
    symbol = data['commodity']
    decimals = COMMODITIES[symbol][2]

    if call.data == "trail_menu":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🛡️ نقل للدخول (BE)", callback_data="apply_trail_0"))
        for i in range(len(data['tp_prices'])):
            markup.add(types.InlineKeyboardButton(f"🛡️ حجز أرباح عند TP{i+1}", callback_data=f"apply_trail_{i+1}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("apply_trail_"):
        idx = int(call.data.split('_')[2])
        data['is_secured'] = True
        if idx == 0:
            data['sl'], data['sl_at'] = data['entry_low'], "BE"
        else:
            data['sl'], data['sl_at'] = data['tp_prices'][idx-1], f"TP{idx}"
        update_everywhere(uid)
        alert = f"🚨 <b>{symbol}</b>\n<b>تم نقل وقف الخسارة إلى {data['sl_at']} 🛡️</b>"
        for ch in data['channel_msgs']: bot.send_message(ch, alert, parse_mode='HTML')

    elif call.data == "main_edit":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 تعديل سعر الدخول", callback_data="edit_entry"))
        markup.add(types.InlineKeyboardButton("❌ تعديل الـ SL", callback_data="edit_sl"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "edit_entry":
        bot.send_message(call.message.chat.id, "<b>أدخل سعر الدخول الجديد:</b>", parse_mode='HTML')
        bot.register_next_step_handler(call.message, process_manual_edit, 'entry_low')

    elif call.data == "edit_sl":
        bot.send_message(call.message.chat.id, "<b>أدخل سعر الـ SL الجديد:</b>", parse_mode='HTML')
        bot.register_next_step_handler(call.message, process_manual_edit, 'sl')

    elif call.data.startswith("hit_tp_"):
        tp_num = int(call.data.split('_')[2])
        data[f'tp{tp_num}_done'] = True
        tp_price = data['tp_prices'][tp_num-1]
        pips = calculate_pips(data['entry_low'], tp_price, COMMODITIES[symbol][3], symbol)
        update_everywhere(uid)
        target_msg = (f"<b>✅ تم تحقيق الهدف {tp_num}: <b>{pips}</b> نقطة 🏆</b>\n"
                     f"<b>━━━━━━━━━━━━━━</b>\n<b>{symbol} {data['trade_type']}</b>\n"
                     f"<b>الدخول: <b>{data['entry_low']:.{decimals}f}</b></b>\n<b>الهدف: <b>{tp_price:.{decimals}f}</b></b>")
        for ch in data['channel_msgs']: bot.send_message(ch, target_msg, parse_mode='HTML')

    elif call.data == "hit_swing":
        data['tp_swing_done'] = True
        update_everywhere(uid)

    elif call.data == "back_to_main":
        update_everywhere(uid)

    elif call.data.startswith("send_to_"):
        target = call.data.split('_')[2]
        if target.replace('-', '').isdigit(): target = int(target)
        sent = bot.send_message(target, generate_setup_text(data), parse_mode='HTML')
        data['channel_msgs'][target] = sent.message_id
        data['published_channels'].append(str(target))
        update_everywhere(uid)

def process_manual_edit(message, field):
    uid = message.from_user.id
    try:
        new_val = float(message.text)
        user_data[uid][field] = new_val
        if field == 'entry_low': user_data[uid]['entry_display'] = message.text
        update_everywhere(uid)
        bot.send_message(message.chat.id, "✅ تم التعديل!")
    except: bot.send_message(message.chat.id, "⚠️ خطأ في الرقم.")

if __name__ == "__main__":
    bot.infinity_polling()
