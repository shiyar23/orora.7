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
logger = logging.getLogger(__name__)

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
    diff = abs(target - entry)
    if "XAU" in symbol: return int(round(diff * 10, 0))
    return int(round(diff / pip_size, 0))

def generate_setup_text(data):
    symbol = data['commodity']
    name, _, decimals, _, _ = COMMODITIES[symbol]
    
    txt = f"<b>📊 SETUP: {name} {data['emoji']}</b>\n"
    txt += f"<b>Type:</b> {data['trade_type']} {'🟢' if 'BUY' in data['trade_type'] else '🔴'}\n\n"
    txt += f"<b>Entry:</b> <code>{data['entry_display']}</code>\n"
    txt += f"<b>SL:</b> <code>{data['sl']:.{decimals}f}</code> {'🛡️ BE' if data.get('is_be') else '❌'}\n\n"
    
    for i, tp in enumerate(data['tp_prices']):
        status = "✅ <b>Done</b>" if data.get(f'tp{i+1}_done') else "☑️"
        txt += f"{status} <b>TP{i+1}:</b> <code>{tp:.{decimals}f}</code>\n"
        
    txt += f"{'✅ <b>Done</b>' if data.get('tp_swing_done') else '☑️'} <b>TP SWING</b>\n\n"
    txt += "<i>⚠️ الالتزام الصارم بإدارة رأس المال 📊💰</i>"
    return txt

def create_inline_buttons(data):
    msg_id = data['msg_id']
    symbol = data['commodity']
    markup = types.InlineKeyboardMarkup(row_width=1)

    for i, tp_price in enumerate(data['tp_prices']):
        tp_num = i + 1
        if not data.get(f'tp{tp_num}_done'):
            pips = calculate_pips(data['entry_low'], tp_price, COMMODITIES[symbol][3], symbol)
            markup.add(types.InlineKeyboardButton(f"✅ Hit TP{tp_num} (+{pips} Pips)", callback_data=f"hit_tp_{tp_num}_{msg_id}"))

    if not data.get('tp_swing_done'):
        markup.add(types.InlineKeyboardButton("🎯 Hit SWING", callback_data=f"hit_swing_{msg_id}"))
    
    # زر تعديل الستوب إلى الدخول
    if not data.get('is_be'):
        markup.add(types.InlineKeyboardButton("🛡️ Move SL to Entry (BE)", callback_data=f"move_be_{msg_id}"))
    
    markup.add(types.InlineKeyboardButton("➕ إضافة هدف جديد (TP)", callback_data=f"add_manual_tp_{msg_id}"))
    
    for channel in CHANNELS_LIST:
        if str(channel) not in data.get('published_channels', []):
            label = "القناة الخاصة" if isinstance(channel, int) else channel
            markup.add(types.InlineKeyboardButton(f"📢 نشر في {label}", callback_data=f"send_to_{channel}_{msg_id}"))
            
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
    user_data[uid] = {'chat_id': message.chat.id, 'channel_msgs': {}, 'published_channels': [], 'tp_prices': [], 'is_be': False}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for k in COMMODITIES.keys(): markup.add(k)
    bot.send_message(message.chat.id, "مرحباً! اختر الرمز:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in COMMODITIES)
def set_commodity(message):
    uid = message.from_user.id
    user_data[uid]['commodity'] = message.text
    user_data[uid]['emoji'] = EMOJI_MAP.get(COMMODITIES[message.text][1], "📈")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("BUY", "SELL", "BUY LIMIT", "SELL LIMIT")
    bot.send_message(message.chat.id, "نوع الصفقة:", reply_markup=markup)
    bot.register_next_step_handler(message, set_type)

def set_type(message):
    user_data[message.from_user.id]['trade_type'] = message.text
    bot.send_message(message.chat.id, "سعر الدخول:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, set_entry)

def set_entry(message):
    uid = message.from_user.id
    try:
        user_data[uid]['entry_low'] = float(message.text)
        user_data[uid]['entry_display'] = message.text
        bot.send_message(message.chat.id, "سعر الـ SL:")
        bot.register_next_step_handler(message, set_sl_and_finish)
    except:
        bot.send_message(message.chat.id, "أدخل رقم صحيح.")

def set_sl_and_finish(message):
    uid = message.from_user.id
    data = user_data[uid]
    try:
        data['sl'] = float(message.text)
        symbol = data['commodity']
        step = COMMODITIES[symbol][4]
        direction = 1 if "BUY" in data['trade_type'] else -1
        data['tp_prices'] = [round(data['entry_low'] + (i+1)*step*direction, COMMODITIES[symbol][2]) for i in range(3)]
        msg = bot.send_message(message.chat.id, generate_setup_text(data), parse_mode='HTML')
        data['msg_id'] = msg.message_id
        bot.edit_message_reply_markup(message.chat.id, msg.message_id, reply_markup=create_inline_buttons(data))
    except:
        bot.send_message(message.chat.id, "أدخل رقم صحيح.")

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    uid = call.from_user.id
    if uid not in user_data: return
    data = user_data[uid]
    symbol = data['commodity']
    name, _, decimals, pip_size, _ = COMMODITIES[symbol]
    
    if "send_to_" in call.data:
        channel_val = call.data.split('_')[2]
        target = int(channel_val) if channel_val.replace('-', '').isdigit() else channel_val
        sent = bot.send_message(target, generate_setup_text(data), parse_mode='HTML')
        data['channel_msgs'][target] = sent.message_id
        data['published_channels'].append(str(target))
        update_everywhere(uid)
        
    elif "hit_tp_" in call.data:
        tp_num = int(call.data.split('_')[2])
        data[f'tp{tp_num}_done'] = True
        tp_price = data['tp_prices'][tp_num-1]
        pips = calculate_pips(data['entry_low'], tp_price, pip_size, symbol)
        
        # تنسيق رسالة الهدف كما طلبت
        target_msg = (
            f"✅Done TP{tp_num}: {pips} PIPS 🏆\n"
            f"<b>{name} {data['trade_type']}</b>\n"
            f"Entry: {data['entry_low']:.{decimals}f}\n"
            f"TP{tp_num}: {tp_price:.{decimals}f}"
        )
        
        update_everywhere(uid)
        for ch, _ in data['channel_msgs'].items():
            bot.send_message(ch, target_msg, parse_mode='HTML')

    elif "move_be_" in call.data:
        data['is_be'] = True
        data['sl'] = data['entry_low'] # تعديل SL لمنطقة الدخول
        update_everywhere(uid)
        
        # تنبيه القنوات بنقل الستوب باللغة العربية
        be_msg = f"🚨 <b>{name}</b>\n<b>تم نقل وقف الخسارة إلى منطقة الدخول (Break Even) 🛡️</b>"
        for ch, _ in data['channel_msgs'].items():
            bot.send_message(ch, be_msg, parse_mode='HTML')

    elif "add_manual_tp_" in call.data:
        msg = bot.send_message(call.message.chat.id, "أدخل سعر الهدف الجديد:")
        bot.register_next_step_handler(msg, add_tp_logic)

def add_tp_logic(message):
    uid = message.from_user.id
    try:
        new_val = float(message.text)
        user_data[uid]['tp_prices'].append(new_val)
        update_everywhere(uid)
        bot.send_message(message.chat.id, "✅ تم إضافة الهدف وتحديث الرسائل!")
    except:
        bot.send_message(message.chat.id, "رقم غير صحيح.")

if __name__ == "__main__":
    bot.infinity_polling()
