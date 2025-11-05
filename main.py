import telebot
import time
import logging
import types
import os

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN غير موجود! أضفه في Railway.")

bot = telebot.TeleBot(BOT_TOKEN)
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@the_hunter_of_forex')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}

# إيموجيات آمنة ومدعومة عالميًا
EMOJI_MAP = {
    "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "AUD": "🇦🇺",
    "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "GOLD": "🥇", "SILVER": "🥈", "BTC": "₿", "ETH": "💎"
}

COMMODITIES = {
    "EURUSD": ("EUR/USD", "EUR", 5, 0.0001, 50),
    "GBPUSD": ("GBP/USD", "GBP", 5, 0.0001, 50),
    "USDJPY": ("USD/JPY", "JPY", 3, 0.01, 5.0),
    "AUDUSD": ("AUD/USD", "AUD", 5, 0.0001, 50),
    "USDCAD": ("USD/CAD", "CAD", 5, 0.0001, 50),
    "NZDUSD": ("NZD/USD", "NZD", 5, 0.0001, 50),
    "USDCHF": ("USD/CHF", "CHF", 5, 0.0001, 50),
    "XAUUSD": ("GOLD", "GOLD", 2, 0.1, 5.0),      # 1 pip = 0.1 → 1$ = 10 pips
    "XAGUSD": ("SILVER", "SILVER", 3, 0.001, 0.5), # 1 pip = 0.001 → 1$ = 1000 pips
    "BTCUSD": ("BITCOIN", "BTC", 2, 1.0, 100.0),
    "ETHUSD": ("ETHEREUM", "ETH", 2, 1.0, 50.0),
}

def commodity_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    for key, (name, code, _, _, _) in COMMODITIES.items():
        emoji = EMOJI_MAP.get(code, "Chart")
        markup.add(types.KeyboardButton(f"{name} {emoji}"))
    markup.add("تنظيف الدردشة", "حذف", "بدء جديد")
    return markup

def buy_sell_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("BUY", "SELL")
    return markup

def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("بدء جديد", "حذف")
    markup.add("تنظيف الدردشة")
    return markup

def send_and_save_message(chat_id, text, reply_markup=None, user_id=None, parse_mode='HTML'):
    try:
        msg = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        if user_id and user_id in user_data:
            user_data[user_id]['bot_messages'].append(msg.message_id)
            user_data[user_id]['last_setup_msg_id'] = msg.message_id
        return msg
    except Exception as e:
        logger.error(f"فشل الإرسال: {e}")
        return None

def calculate_pips(entry, target, pip_size):
    diff = abs(target - entry)
    pips = round(diff / pip_size, 1)  # دقة عشرية واحدة للنقاط
    return pips

def create_inline_buttons(data):
    symbol = data['commodity']
    entry_low = data['entry_low']
    tp_prices = data['tp_prices']
    sl = data['sl']
    pip_size = COMMODITIES[symbol][3]

    markup = types.InlineKeyboardMarkup(row_width=1)
    pips_tp1 = calculate_pips(entry_low, tp_prices[0], pip_size)
    pips_tp2 = calculate_pips(entry_low, tp_prices[1], pip_size)
    pips_tp3 = calculate_pips(entry_low, tp_prices[2], pip_size)
    pips_sl = calculate_pips(entry_low, sl, pip_size)

    btn_tp1 = types.InlineKeyboardButton(f"TP1: {pips_tp1} pips", callback_data=f"tp1_{data['msg_id']}")
    btn_tp2 = types.InlineKeyboardButton(f"TP2: {pips_tp2} pips", callback_data=f"tp2_{data['msg_id']}")
    btn_tp3 = types.InlineKeyboardButton(f"TP3: {pips_tp3} pips", callback_data=f"tp3_{data['msg_id']}")
    btn_tp4 = types.InlineKeyboardButton("TP4: SWING", callback_data=f"tp4_{data['msg_id']}")
    btn_sl = types.InlineKeyboardButton(f"SL: {pips_sl} pips", callback_data=f"sl_{data['msg_id']}")

    markup.add(btn_tp1, btn_tp2, btn_tp3, btn_tp4, btn_sl)
    return markup

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    if user_id not in user_data: 
        return
    data = user_data[user_id]
    msg_id = data.get('last_setup_msg_id')
    if not msg_id or call.message.message_id != msg_id: 
        return

    action, callback_msg_id = call.data.split('_', 1)
    if callback_msg_id != str(msg_id): 
        return

    lines = call.message.text.split('\n')
    updated = False
    for i, line in enumerate(lines):
        if action == 'tp1' and "TP1" in line and "Checkmark" not in line:
            lines[i] = line.replace("CHECK <b>TP1", "Checkmark <b>TP1").replace("TP1", "TP1 Done")
            updated = True
        elif action == 'tp2' and "TP2" in line and "Checkmark" not in line:
            lines[i] = line.replace("CHECK <b>TP2", "Checkmark <b>TP2").replace("TP2", "TP2 Done")
            updated = True
        elif action == 'tp3' and "TP3" in line and "Checkmark" not in line:
            lines[i] = line.replace("CHECK <b>TP3", "Checkmark <b>TP3").replace("TP3", "TP3 Done")
            updated = True
        elif action == 'tp4' and "TP4" in line and "Checkmark" not in line:
            lines[i] = line.replace("CHECK <b>TP4", "Checkmark <b>TP4").replace("TP4", "TP4 Done")
            updated = True
        elif action == 'sl' and "SL" in line and "Cross" not in line:
            lines[i] = line.replace("SL", "Cross SL Hit")
            updated = True

    if updated:
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text='\n'.join(lines),
                parse_mode='HTML'
            )
            bot.answer_callback_query(call.id, "تم التحديث! Checkmark")
        except Exception as e:
            logger.error(f"فشل التحديث: {e}")
    else:
        bot.answer_callback_query(call.id, "تم بالفعل!")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data[user_id] = {'bot_messages': []}
    send_and_save_message(chat_id, "<b>مرحبًا! إعداد صفقات احترافي</b>\nاختر السلعة:", commodity_keyboard(), user_id)

@bot.message_handler(func=lambda m: any(f"{v[0]} {EMOJI_MAP.get(v[1], '')}" in m.text for v in COMMODITIES.values()))
def process_commodity(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    selected = None
    for key, (name, code, _, _, _) in COMMODITIES.items():
        emoji = EMOJI_MAP.get(code, "")
        if f"{name} {emoji}" in message.text:
            selected = key
            break
    if not selected:
        send_and_save_message(chat_id, "*اختر من القائمة.*", commodity_keyboard(), user_id)
        return
    user_data.setdefault(user_id, {'bot_messages': []})
    emoji = EMOJI_MAP.get(COMMODITIES[selected][1], "Chart")
    user_data[user_id].update({
        'commodity': selected,
        'display_name': COMMODITIES[selected][0],
        'emoji': emoji
    })
    send_and_save_message(chat_id, f"<b>تم اختيار {COMMODITIES[selected][0]} {emoji}</b>\n\nاختر نوع الصفقة:", buy_sell_keyboard(), user_id)
    bot.register_next_step_handler(message, process_trade_type)

def process_trade_type(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    trade_type = message.text.upper()
    if trade_type not in ['BUY', 'SELL']:
        send_and_save_message(chat_id, "*اختر BUY أو SELL فقط.*", buy_sell_keyboard(), user_id)
        bot.register_next_step_handler(message, process_trade_type)
        return
    user_data[user_id]['trade_type'] = trade_type
    send_and_save_message(chat_id, f"<b>تم اختيار {trade_type}</b>\n\nأدخل سعر الدخول:", types.ReplyKeyboardRemove(), user_id)
    bot.register_next_step_handler(message, process_entry_price)

def process_entry_price(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        entry = float(message.text.replace(',', '.'))
        user_data[user_id]['entry_price'] = entry
        send_and_save_message(chat_id, "أدخل سعر وقف الخسارة (SL):", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_stop_loss)
    except ValueError:
        send_and_save_message(chat_id, "*سعر غير صحيح. استخدم أرقام فقط.*", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_entry_price)

def process_stop_loss(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        sl = float(message.text.replace(',', '.'))
        user_data[user_id]['stop_loss'] = sl
        generate_and_send_setup(user_id, chat_id)
    except ValueError:
        send_and_save_message(chat_id, "*سعر SL غير صحيح.*", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_stop_loss)

def generate_and_send_setup(user_id, chat_id):
    data = user_data[user_id]
    symbol = data['commodity']
    name, code, decimals, pip_size, tp_step = COMMODITIES[symbol]
    entry_price = data['entry_price']
    stop_loss = data['stop_loss']
    trade_type = data.get('trade_type', 'BUY')
    direction = 1 if trade_type == 'BUY' else -1
    emoji = data['emoji']

    # تحديد نطاق الدخول
    if symbol in ["XAUUSD"]:
        entry_low = round(entry_price - 1.5 if trade_type == 'BUY' else entry_price, 2)
        entry_high = round(entry_price + 1.5 if trade_type == 'BUY' else entry_price + 3, 2)
    elif symbol in ["BTCUSD", "ETHUSD"]:
        entry_low = round(entry_price - 10 if trade_type == 'BUY' else entry_price, 2)
        entry_high = round(entry_price + 10 if trade_type == 'BUY' else entry_price + 20, 2)
    else:
        entry_low = round(entry_price - 0.00015, decimals)
        entry_high = round(entry_price + 0.00015, decimals)

    # ضبط SL
    sl = round(max(entry_high + pip_size, stop_loss) if trade_type == 'SELL' else min(entry_low - pip_size, stop_loss), decimals)

    # حساب TPs
    tp1 = round(entry_low + (tp_step * direction), decimals)  # لأن اتجاه BUY يزيد، SELL ينقص
    tp2 = round(tp1 + (tp_step * direction), decimals)
    tp3 = round(tp2 + (tp_step * direction), decimals)

    output = f"<b>SETUP: {name} {emoji} › {trade_type}</b>\n\n"
    output += f"<b>Entry:</b> {entry_low:.{decimals}f} - {entry_high:.{decimals}f}\n"
    output += f"<b>SL:</b> {sl:.{decimals}f} PROHIBITED\n\n"
    output += f"CHECK <b>TP1:</b> {tp1:.{decimals}f}\n"
    output += f"CHECK <b>TP2:</b> {tp2:.{decimals}f}\n"
    output += f"CHECK <b>TP3:</b> {tp3:.{decimals}f}\n"
    output += f"CHECK <b>TP4: SWING</b>\n\n"
    output += f"WARNING <i>ليس نصيحة مالية. التداول محفوف بالمخاطر.</i>"

    msg = send_and_save_message(chat_id, output, user_id=user_id)
    if msg:
        data.update({
            'msg_id': msg.message_id,
            'entry_low': entry_low,
            'tp_prices': [tp1, tp2, tp3],
            'sl': sl,
            'direction': direction
        })
        bot.edit_message_reply_markup(chat_id, msg.message_id, reply_markup=create_inline_buttons(data))

    # إرسال إلى القناة
    if CHANNEL_USERNAME:
        try:
            bot.send_message(
                CHANNEL_USERNAME,
                f"<b>صفقة جديدة - {name} {emoji} {trade_type}</b>\n\n" + output,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"فشل النشر في القناة: {e}")

@bot.message_handler(func=lambda m: m.text == 'بدء جديد')
def new_setup(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data[user_id] = {'bot_messages': []}
    send_and_save_message(chat_id, "<b>إعداد جديد!</b>\nاختر السلعة:", commodity_keyboard(), user_id)

@bot.message_handler(func=lambda m: m.text == 'حذف')
def delete_setup(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data.pop(user_id, None)
    send_and_save_message(chat_id, "<b>تم الحذف!</b>", main_menu_keyboard(), user_id)

@bot.message_handler(func=lambda m: m.text == 'تنظيف الدردشة')
def clean_chat(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if user_id in user_data and 'bot_messages' in user_data[user_id]:
        for msg_id in user_data[user_id]['bot_messages']:
            try: 
                bot.delete_message(chat_id, msg_id)
            except: 
                pass
        user_data[user_id]['bot_messages'] = []
    try: 
        bot.delete_message(chat_id, message.message_id)
    except: 
        pass
    send_and_save_message(chat_id, "<b>تم التنظيف!</b>", main_menu_keyboard(), user_id)

if __name__ == "__main__":
    logger.info("البوت يعمل الآن على Railway!")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"خطأ في الاتصال: {e}")
            time.sleep(5)
