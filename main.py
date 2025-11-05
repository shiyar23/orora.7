import telebot
import time
import logging
import os
from telebot import types  # ← هذا السطر الجديد

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN غير موجود! أضفه في Railway.")

bot = telebot.TeleBot(BOT_TOKEN)
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@the_hunter_of_forex')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}

EMOJI_MAP = {
    "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "AUD": "🇦🇺",
    "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "GOLD": "🏆", "SILVER": "🪙", "BTC": "₿", "ETH": "Ξ"
}
TROPHY = "Trophy"

COMMODITIES = {
    "EURUSD": ("EUR/USD", "EUR", 5, 0.0001, 50),
    "GBPUSD": ("GBP/USD", "GBP", 5, 0.0001, 50),
    "USDJPY": ("USD/JPY", "JPY", 3, 0.01, 5.0),
    "AUDUSD": ("AUD/USD", "AUD", 5, 0.0001, 50),
    "USDCAD": ("USD/CAD", "CAD", 5, 0.0001, 50),
    "NZDUSD": ("NZD/USD", "NZD", 5, 0.0001, 50),
    "USDCHF": ("USD/CHF", "CHF", 5, 0.0001, 50),
    "XAUUSD": ("GOLD", "GOLD", 2, 1.0, 5.0),     # 1$ = 10 نقاط
    "XAGUSD": ("SILVER", "SILVER", 3, 0.01, 0.5),
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
    markup.add("BUY LIMIT", "SELL LIMIT")
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

def calculate_pips(entry, target, pip_size, symbol):
    diff = abs(target - entry)
    if symbol == "XAUUSD":
        return int(round(diff * 10, 0))  # 1$ = 10 نقاط
    else:
        return int(round(diff / pip_size, 0))

def create_inline_buttons(data):
    symbol = data['commodity']
    entry_low = data['entry_low']
    tp_prices = data['tp_prices']
    sl = data['sl']
    pip_size = COMMODITIES[symbol][3]
    msg_id = data['msg_id']
    code = COMMODITIES[symbol][1]
    emoji = EMOJI_MAP.get(code, "Chart")

    markup = types.InlineKeyboardMarkup(row_width=1)

    pips_tp1 = calculate_pips(entry_low, tp_prices[0], pip_size, symbol)
    pips_tp2 = calculate_pips(entry_low, tp_prices[1], pip_size, symbol)
    pips_tp3 = calculate_pips(entry_low, tp_prices[2], pip_size, symbol)
    pips_sl = calculate_pips(entry_low, sl, pip_size, symbol)

    btn_tp1 = types.InlineKeyboardButton(
        f"{'Done TP1' if data.get('tp1_done') else 'TP1'}: {pips_tp1} PIPS {TROPHY if data.get('tp1_done') else ''} {emoji}",
        callback_data=f"tp1_{msg_id}"
    )
    btn_tp2 = types.InlineKeyboardButton(
        f"{'Done TP2' if data.get('tp2_done') else 'TP2'}: {pips_tp2} PIPS {TROPHY if data.get('tp2_done') else ''} {emoji}",
        callback_data=f"tp2_{msg_id}"
    )
    btn_tp3 = types.InlineKeyboardButton(
        f"{'Done TP3' if data.get('tp3_done') else 'TP3'}: {pips_tp3} PIPS {TROPHY if data.get('tp3_done') else ''} {emoji}",
        callback_data=f"tp3_{msg_id}"
    )
    btn_tp4 = types.InlineKeyboardButton(
        f"{'Done TP4: SWING' if data.get('tp4_done') else 'TP4: SWING'} {TROPHY if data.get('tp4_done') else ''} {emoji}",
        callback_data=f"tp4_{msg_id}"
    )
    btn_sl = types.InlineKeyboardButton(
        f"{'Hit SL' if data.get('sl_hit') else 'SL'}: {pips_sl} PIPS {'Warning' if data.get('sl_hit') else ''}",
        callback_data=f"sl_{msg_id}"
    )

    markup.add(btn_tp1, btn_tp2, btn_tp3, btn_tp4, btn_sl)
    return markup

# حفظ معرف الرسالة في القناة
channel_message_ids = {}

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

    # تحديث الحالة
    was_done = False
    if action == 'tp1' and not data.get('tp1_done'): data['tp1_done'] = True; was_done = True
    elif action == 'tp2' and not data.get('tp2_done'): data['tp2_done'] = True; was_done = True
    elif action == 'tp3' and not data.get('tp3_done'): data['tp3_done'] = True; was_done = True
    elif action == 'tp4' and not data.get('tp4_done'): data['tp4_done'] = True; was_done = True
    elif action == 'sl' and not data.get('sl_hit'): data['sl_hit'] = True; was_done = True

    if not was_done:
        bot.answer_callback_query(call.id, "تم بالفعل!")
        return

    # تحديث النص في المحادثة
    lines = call.message.text.split('\n')
    new_lines = []
    for line in lines:
        if 'TP1:' in line and action == 'tp1':
            line = line.replace("CHECK", "Done").replace("TP1:", "✅Done TP1:")
        elif 'TP2:' in line and action == 'tp2':
            line = line.replace("CHECK", "Done").replace("TP2:", "✅Done TP2:")
        elif 'TP3:' in line and action == 'tp3':
            line = line.replace("CHECK", "Done").replace("TP3:", "✅Done TP3:")
        elif 'TP4:' in line and action == 'tp4':
            line = line.replace("CHECK", "Done").replace("TP4:", "✅Done TP4:")
        elif 'SL:' in line and action == 'sl':
            line = line.replace("PROHIBITED", "HIT")
        new_lines.append(line)

    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text='\n'.join(new_lines),
            parse_mode='HTML'
        )
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=create_inline_buttons(data)
        )
    except Exception as e:
        logger.error(f"فشل تحديث المحادثة: {e}")

    # --- إرسال تحديث إلى القناة ---
    symbol = data['commodity']
    name, code, _, _, _ = COMMODITIES[symbol]
    emoji = EMOJI_MAP.get(code, "Chart")
    trade_type = data['trade_type']

    # نص التحديث
    pips = 0
    tp_price = 0
    if action.startswith('tp'):
        idx = int(action[2]) - 1 if action != 'tp4' else 3
        if idx < 3:
            pips = calculate_pips(data['entry_low'], data['tp_prices'][idx], COMMODITIES[symbol][3], symbol)
            tp_price = data['tp_prices'][idx]
        update_text = f"<b>Done TP{action[2]}: {pips} PIPS {TROPHY} {emoji}</b>\n" \
                      f"<b>{name} {trade_type}</b>\n" \
                      f"Entry: {data['entry_low']:.{COMMODITIES[symbol][2]}f}\n" \
                      f"TP{action[2]}: {tp_price:.{COMMODITIES[symbol][2]}f}"
    elif action == 'tp4':
        update_text = f"<b>Done TP4: SWING {TROPHY} {emoji}</b>\n" \
                      f"<b>{name} {trade_type}</b>\n" \
                      f"Entry: {data['entry_low']:.{COMMODITIES[symbol][2]}f}\n" \
                      f"TP4: SWING"
    elif action == 'sl':
        pips = calculate_pips(data['entry_low'], data['sl'], COMMODITIES[symbol][3], symbol)
        update_text = f"<b>Hit SL: {pips} PIPS {'Warning'}</b>\n" \
                      f"<b>{name} {trade_type}</b>\n" \
                      f"Entry: {data['entry_low']:.{COMMODITIES[symbol][2]}f}\n" \
                      f"SL: {data['sl']:.{COMMODITIES[symbol][2]}f}"

    # إرسال رسالة منفصلة إلى القناة
    try:
        sent = bot.send_message(CHANNEL_USERNAME, update_text, parse_mode='HTML', disable_web_page_preview=True)
        channel_message_ids[f"{user_id}_{action}"] = sent.message_id
    except Exception as e:
        logger.error(f"فشل إرسال إلى القناة: {e}")

    # تحديث الرسالة الأصلية في القناة إن وُجدت
    if 'channel_msg_id' in data:
        try:
            original_text = call.message.text
            for line in new_lines:
                if 'Done' in line or 'HIT' in line:
                    original_text = original_text.replace(
                        line.split("Done")[-1] if "Done" in line else line.split("HIT")[-1],
                        line
                    )
            bot.edit_message_text(
                chat_id=CHANNEL_USERNAME,
                message_id=data['channel_msg_id'],
                text=original_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"فشل تحديث الرسالة في القناة: {e}")

    bot.answer_callback_query(call.id, "تم الإرسال إلى القناة!")

# باقي الدوال بدون تغيير (مختصرة هنا)
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data[user_id] = {'bot_messages': []}
    send_and_save_message(chat_id, "<b>مرحبًا! إعداد صفقات احترافي</b>\nاختر السلعة:", commodity_keyboard(), user_id)

@bot.message_handler(func=lambda m: any(f"{v[0]} {EMOJI_MAP.get(v[1], 'Chart')}" in m.text for v in COMMODITIES.values()))
def process_commodity(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    selected = next((k for k, v in COMMODITIES.items() if f"{v[0]} {EMOJI_MAP.get(v[1], 'Chart')}" in message.text), None)
    if not selected:
        send_and_save_message(chat_id, "*اختر من القائمة.*", commodity_keyboard(), user_id)
        return
    user_data.setdefault(user_id, {'bot_messages': []})
    code = COMMODITIES[selected][1]
    user_data[user_id].update({
        'commodity': selected,
        'display_name': COMMODITIES[selected][0],
        'emoji': EMOJI_MAP.get(code, "Chart")
    })
    send_and_save_message(chat_id, f"<b>تم اختيار {COMMODITIES[selected][0]} {EMOJI_MAP.get(code, 'Chart')}</b>\n\nاختر نوع الصفقة:", buy_sell_keyboard(), user_id)
    bot.register_next_step_handler(message, process_trade_type)

def process_trade_type(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    trade_type = message.text.upper()
    if trade_type not in ['🟢BUY', '🔴SELL', '🟢BUY LIMIT', '🔴SELL LIMIT']:
        send_and_save_message(chat_id, "*اختر BUY, SELL, BUY LIMIT أو SELL LIMIT فقط.*", buy_sell_keyboard(), user_id)
        bot.register_next_step_handler(message, process_trade_type)
        return
    user_data[user_id]['trade_type'] = trade_type
    if 'LIMIT' in trade_type:
        send_and_save_message(chat_id, f"<b>تم اختيار {trade_type}</b>\n\nأدخل <b>سعر الدخول (المحدد)</b>:", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_limit_entry_price)
    else:
        send_and_save_message(chat_id, f"<b>تم اختيار {trade_type}</b>\n\nأدخل سعر الدخول:", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_entry_price)

def process_limit_entry_price(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        user_data[user_id]['entry_price'] = float(message.text)
        send_and_save_message(chat_id, "أدخل سعر وقف الخسارة (SL):", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_stop_loss)
    except ValueError:
        send_and_save_message(chat_id, "*سعر غير صحيح.*", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_limit_entry_price)

def process_entry_price(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        user_data[user_id]['entry_price'] = float(message.text)
        send_and_save_message(chat_id, "أدخل سعر وقف الخسارة (SL):", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_stop_loss)
    except ValueError:
        send_and_save_message(chat_id, "*سعر غير صحيح.*", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_entry_price)

def process_stop_loss(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        user_data[user_id]['stop_loss'] = float(message.text)
        generate_and_send_setup(user_id, chat_id)
    except ValueError:
        send_and_save_message(chat_id, "*سعر SL غير صحيح.*", types.ReplyKeyboardRemove(), user_id)
        bot.register_next_step_handler(message, process_stop_loss)

def generate_and_send_setup(user_id, chat_id):
    data = user_data[user_id]
    symbol = data['commodity']
    name, code, decimals, pip_size, tp_step = COMMODITIES[symbol]
    emoji = data['emoji']
    entry_price = data['entry_price']
    stop_loss = data['stop_loss']
    trade_type = data.get('trade_type', 'BUY')

    is_limit = 'LIMIT' in trade_type
    is_buy = 'BUY' in trade_type
    direction = 1 if is_buy else -1

    if symbol in ["XAUUSD", "BTCUSD", "ETHUSD"]:
        entry_low = round(entry_price - 1.5 if is_buy else entry_price, 2)
        entry_high = round(entry_price + 1.5 if is_buy else entry_price + 3, 2)
    else:
        entry_low = round(entry_price - 0.00015, decimals)
        entry_high = round(entry_price + 0.00015, decimals)

    if is_limit:
        entry_display = f"<b>Entry (Limit):</b> {entry_price:.{decimals}f}"
        entry_low = entry_price
    else:
        entry_display = f"<b>Entry:</b> {entry_low:.{decimals}f} - {entry_high:.{decimals}f}"

    sl = round(max(entry_high + pip_size, stop_loss) if not is_buy else min(entry_low - pip_size, stop_loss), decimals)

    tp1 = round(entry_low - (tp_step * direction), decimals)
    tp2 = round(tp1 - (tp_step * direction), decimals)
    tp3 = round(tp2 - (tp_step * direction), decimals)

    display_type = trade_type.replace(" ", "\n") if "LIMIT" in trade_type else trade_type

    output = f"<b>SETUP: {name} {emoji} › {display_type}</b>\n\n"
    output += f"{entry_display}\n"
    output += f"<b>SL:</b> {sl:.{decimals}f} PROHIBITED\n\n"
    output += f"CHECK <b>☑️TP1:</b> {tp1:.{decimals}f}\n"
    output += f"CHECK <b>☑️TP2:</b> {tp2:.{decimals}f}\n"
    output += f"CHECK <b>☑️TP3:</b> {tp3:.{decimals}f}\n"
    output += f"CHECK <b>☑️TP4: SWING</b>\n\n"
    output += f"WARNING <i>⚠️تنويه هام:يجب الالتزام الصارم بإجراءات وضوابط إدارة رأس المال المقررة. 📊💰</i>"

    msg = send_and_save_message(chat_id, output, user_id=user_id)
    if msg:
        data.update({
            'msg_id': msg.message_id,
            'entry_low': entry_low,
            'tp_prices': [tp1, tp2, tp3],
            'sl': sl,
            'direction': direction,
            'is_buy': is_buy,
            'is_limit': is_limit,
            'tp1_done': False, 'tp2_done': False, 'tp3_done': False,
            'tp4_done': False, 'sl_hit': False
        })
        bot.edit_message_reply_markup(chat_id, msg.message_id, reply_markup=create_inline_buttons(data))

    # إرسال إلى القناة + حفظ المعرف
    if CHANNEL_USERNAME:
        try:
            channel_msg = bot.send_message(CHANNEL_USERNAME, f"<b>صفقة جديدة - {name} {emoji} {trade_type}</b>\n\n" + output, parse_mode='HTML', disable_web_page_preview=True)
            data['channel_msg_id'] = channel_msg.message_id
        except Exception as e:
            logger.error(f"فشل النشر: {e}")

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
            try: bot.delete_message(chat_id, msg_id)
            except: pass
        user_data[user_id]['bot_messages'] = []
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    send_and_save_message(chat_id, "<b>تم التنظيف!</b>", main_menu_keyboard(), user_id)

if __name__ == "__main__":
    logger.info("البوت يعمل الآن على Railway!")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            logger.error(f"خطأ: {e}")
            time.sleep(5)
