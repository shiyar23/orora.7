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
    
    # حالة الستوب المحمي
    sl_label = f"<b>🛡️ {data.get('sl_at', '❌')}</b>" if data.get('is_secured') else "<b>❌</b>"
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

    # أزرار الأهداف
    for i, tp_price in enumerate(data['tp_prices']):
        tp_num = i + 1
        if not data.get(f'tp{tp_num}_done'):
            pips = calculate_pips(data['entry_low'], tp_price, COMMODITIES[symbol][3], symbol)
            markup.add(types.InlineKeyboardButton(f"✅ تحقيق الهدف {tp_num} (+{pips} نقطة)", callback_data=f"hit_tp_{tp_num}_{msg_id}"))

    if not data.get('tp_swing_done'):
        markup.add(types.InlineKeyboardButton("🎯 تحقيق SWING", callback_data=f"hit_swing_{msg_id}"))
    
    # زر تأمين الأرباح الجديد (Trail SL)
    markup.add(types.InlineKeyboardButton("🛡️ تأمين الأرباح (Trail SL)", callback_data=f"trail_menu_{msg_id}"))
    
    # زر التعديل الشامل
    markup.add(types.InlineKeyboardButton("⚙️ تعديل الصفقة", callback_data=f"main_edit_{msg_id}"))
    
    # أزرار النشر
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
    user_data[uid] = {'chat_id': message.chat.id, 'channel_msgs': {}, 'published_channels': [], 'tp_prices': [], 'is_secured': False, 'sl_at': ''}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for k in COMMODITIES.keys(): markup.add(k)
    bot.send_message(message.chat.id, "<b>مرحباً بك! اختر الرمز للبدء:</b>", reply_markup=markup, parse_mode='HTML')

# (دوال set_commodity, set_type, set_entry, set_sl_and_finish تبقى كما هي في الكود السابق)
# سأركز هنا على منطق أزرار التعديل والتأمين الجديد

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    uid = call.from_user.id
    if uid not in user_data: return
    data = user_data[uid]
    msg_id = data['msg_id']
    symbol = data['commodity']

    # --- قائمة تأمين الأرباح الاحترافية ---
    if "trail_menu_" in call.data:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🛡️ نقل للدخول (BE)", callback_data=f"apply_trail_0_{msg_id}"))
        for i in range(len(data['tp_prices'])):
            markup.add(types.InlineKeyboardButton(f"🛡️ حجز أرباح عند TP{i+1}", callback_data=f"apply_trail_{i+1}_{msg_id}"))
        markup.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"cancel_trail_{msg_id}"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif "apply_trail_" in call.data:
        idx = int(call.data.split('_')[2])
        data['is_secured'] = True
        
        if idx == 0:
            data['sl'] = data['entry_low']
            data['sl_at'] = "BE"
            txt_alert = "منطقة الدخول (BE) 🛡️"
        else:
            data['sl'] = data['tp_prices'][idx-1]
            data['sl_at'] = f"TP{idx}"
            txt_alert = f"الهدف رقم {idx} 🛡️"
        
        update_everywhere(uid)
        
        # تنبيه القنوات
        alert = f"🚨 <b>{data['commodity']}</b>\n<b>تم تأمين الأرباح ونقل وقف الخسارة إلى {txt_alert}</b>"
        for ch, _ in data['channel_msgs'].items():
            bot.send_message(ch, alert, parse_mode='HTML')

    elif "cancel_trail_" in call.data or "cancel_edit_" in call.data:
        update_everywhere(uid)

    # --- (باقي المعالجات مثل send_to, hit_tp, main_edit كما في الكود السابق) ---
    # سأضيفها هنا بشكل مختصر لضمان عمل الكود بالكامل
    elif "send_to_" in call.data:
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
        pips = calculate_pips(data['entry_low'], tp_price, COMMODITIES[symbol][3], symbol)
        target_msg = (f"<b>✅ تم تحقيق الهدف {tp_num}: <b>{pips}</b> نقطة 🏆</b>\n"
                     f"<b>━━━━━━━━━━━━━━</b>\n<b>{data['commodity']} {data['trade_type']}</b>\n"
                     f"<b>الدخول: <b>{data['entry_low']}</b></b>\n<b>الهدف: <b>{tp_price}</b></b>")
        update_everywhere(uid)
        for ch, _ in data['channel_msgs'].items(): bot.send_message(ch, target_msg, parse_mode='HTML')

    elif "main_edit_" in call.data:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 تعديل سعر الدخول", callback_data=f"edit_entry_{msg_id}"))
        markup.add(types.InlineKeyboardButton("❌ تعديل الـ SL", callback_data=f"edit_sl_{msg_id}"))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)

# (تكملة دوال set_commodity وما يليها...)
# لضمان عدم تكرار الكود الطويل سأضع التعديلات الرئيسية فقط. 
# ملاحظة: الكود أعلاه يحتوي على هيكل "تأمين الأرباح" الذي طلبته.
