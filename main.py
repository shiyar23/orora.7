import telebot
import time
import logging
import os
from telebot import types

BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN غير موجود! أضفه في Railway.")

bot = telebot.TeleBot(BOT_TOKEN)
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', '@aicodtrading')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_data = {}

# إيموجيات
EMOJI_MAP = {
    "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵", "AUD": "🇦🇺",
    "CAD": "🇨🇦", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "GOLD": "🏆", "SILVER": "🪙", "BTC": "₿", "ETH": "💎"
}

COMMODITIES = {
    "EURUSD": ("EUR/USD", "EUR", 5, 0.0001, 50),
    "GBPUSD": ("GBP/USD", "GBP", 5, 0.0001, 50),
    "USDJPY": ("USD/JPY", "JPY", 3, 0.01, 5.0),
    "AUDUSD": ("AUD/USD", "AUD", 5, 0.0001, 50),
    "USDCAD": ("USD/CAD", "CAD", 5, 0.0001, 50),
    "NZDUSD": ("NZD/USD", "NZD", 5, 0.0001, 50),
    "USDCHF": ("USD/CHF", "CHF", 5, 0.0001, 50),
    "XAUUSD": ("GOLD", "GOLD", 2, 1.0, 5.0),
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
            user_data[user_id]['last_setup_msg_id'] = msg.message_id  # تحديث دائمًا
        return msg
    except Exception as e:
        logger.error(f"فشل الإرسال: {e}")
        return None

def calculate_pips(entry, target, pip_size, symbol):
    diff = abs(target - entry)
    if symbol == "XAUUSD":
        return int(round(diff * 10, 0))
    else:
        return int(round(diff / pip_size, 0))

def create_inline_buttons(data):
    symbol = data['commodity']
    entry_low = data['entry_low']
    tp_prices = data['tp_prices']
    sl = data['sl']
    pip_size = COMMODITIES[symbol][3]
    msg_id = data['last_setup_msg_id']
    code = COMMODITIES[symbol][1]
    emoji = EMOJI_MAP.get(code, "Chart")

    markup = types.InlineKeyboardMarkup(row_width=1)

    # TP1 - TP3
    for i, tp in enumerate(tp_prices, 1):
        pips = calculate_pips(entry_low, tp, pip_size, symbol)
        done_key = f'tp{i}_done'
        btn = types.InlineKeyboardButton(
            f"{'Done TP' + str(i) if data.get(done_key) else 'TP' + str(i)}: {pips} PIPS {emoji}",
            callback_data=f"tp{i}_{msg_id}"
        )
        markup.add(btn)

    # TP إضافية
    extra_tps = data.get('extra_tps', [])
    for i, tp in enumerate(extra_tps, start=4):
        pips = calculate_pips(entry_low, tp, pip_size, symbol)
        done_key = f'tp{i}_done'
        btn = types.InlineKeyboardButton(
            f"{'Done TP' + str(i) if data.get(done_key) else 'TP' + str(i)}: {pips} PIPS {emoji}",
            callback_data=f"tp{i}_{msg_id}"
        )
        markup.add(btn)

    # إضافة TP
    btn_add_tp = types.InlineKeyboardButton("إضافة TP", callback_data=f"add_tp_{msg_id}")
    markup.add(btn_add_tp)

    # SWING
    btn_swing = types.InlineKeyboardButton(
        f"{'Done SWING' if data.get('swing_done') else 'SWING'} {emoji}",
        callback_data=f"swing_{msg_id}"
    )
    markup.add(btn_swing)

    # SL
    pips_sl = calculate_pips(entry_low, sl, pip_size, symbol)
    btn_sl = types.InlineKeyboardButton(
        f"{'Hit SL' if data.get('sl_hit') else 'SL'}: {pips_sl} PIPS",
        callback_data=f"sl_{msg_id}"
    )
    markup.add(btn_sl)

    # تعديل SL
    btn_edit_sl = types.InlineKeyboardButton("تعديل SL", callback_data=f"edit_sl_{msg_id}")
    markup.add(btn_edit_sl)

    return markup

def create_updated_setup_text(data):
    symbol = data['commodity']
    name, code, decimals, _, _ = COMMODITIES[symbol]
    emoji = data['emoji']
    entry_low = data['entry_low']
    sl = data['sl']
    tp_prices = data['tp_prices']
    trade_type = data['trade_type']
    is_buy = data['is_buy']
    direction_emoji = "Green Circle" if is_buy else "Red Circle"

    entry_display = f"<b>Entry (Limit):</b> {data['entry_price']:.{decimals}f}" if data.get('is_limit') else f"<b>Entry:</b> {entry_low:.{decimals}f} - {data.get('entry_high', entry_low):.{decimals}f}"

    output = f"SETUP: {name} {emoji} › {trade_type} {direction_emoji}\n\n"
    output += f"{entry_display}\n"
    output += f"<b>SL:</b> {sl:.{decimals}f}Cross\n\n"
    for i, tp in enumerate(tp_prices, 1):
        status = "✅Done" if data.get(f'tp{i}_done') else "Check"
        output += f"{status} <b>Check TP{i}:</b> {tp:.{decimals}f}\n"
    for i, tp in enumerate(data.get('extra_tps', []), start=4):
        status = "✅Done" if data.get(f'tp{i}_done') else "Check"
        output += f"{status} <b>Check TP{i}:</b> {tp:.{decimals}f}\n"
    output += f"{'✅Done' if data.get('swing_done') else 'Check'} <b>Check SWING</b>\n\n"
    output += "Warning <i>Warning تنويه هام: يجب الالتزام الصارم بإجراءات وضوابط إدارة رأس المال المقررة. Chart Money</i>"
    return output

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

    was_done = False

    # TP1-TP3
    if action.startswith('tp') and action[2:].isdigit():
        tp_num = int(action[2:])
        done_key = f'tp{tp_num}_done'
        if tp_num <= 3:
            if not data.get(done_key):
                data[done_key] = True
                was_done = True
        elif tp_num >= 4 and tp_num - 3 <= len(data.get('extra_tps', [])):
            if not data.get(done_key):
                data[done_key] = True
                was_done = True

    # SL
    elif action == 'sl' and not data.get('sl_hit'):
        data['sl_hit'] = True
        was_done = True

    # SWING
    elif action == 'swing' and not data.get('swing_done'):
        data['swing_done'] = True
        was_done = True

    # إضافة TP
    elif action == 'add_tp':
        user_data[user_id]['waiting_for'] = {'type': 'tp', 'msg_id': msg_id}
        bot.answer_callback_query(call.id, "أدخل سعر الهدف الجديد (TP):")
        return

    # تعديل SL
    elif action == 'edit_sl':
        user_data[user_id]['waiting_for'] = {'type': 'sl', 'msg_id': msg_id}
        bot.answer_callback_query(call.id, "أدخل سعر SL الجديد:")
        return

    if not was_done:
        bot.answer_callback_query(call.id, "تم بالفعل!")
        return

    # تحديث الرسالة في الدردشة الخاصة
    update_setup_message(user_id, call.message.chat.id)

    # تحديث القناة
    if 'channel_msg_id' in data:
        try:
            updated_text = create_updated_setup_text(data)
            bot.edit_message_text(
                chat_id=CHANNEL_USERNAME,
                message_id=data['channel_msg_id'],
                text=updated_text,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"فشل تحديث القناة: {e}")

    # إرسال تحديث منفصل
    symbol = data['commodity']
    name, code, _, _, _ = COMMODITIES[symbol]
    emoji = EMOJI_MAP.get(code, "Chart")
    trade_type = data['trade_type']

    if action.startswith('tp'):
        tp_num = int(action[2:])
        tp_price = data['tp_prices'][tp_num-1] if tp_num <= 3 else data['extra_tps'][tp_num-4]
        pips = calculate_pips(data['entry_low'], tp_price, COMMODITIES[symbol][3], symbol)
        update_text = f"<b>✅Done TP{tp_num}: {pips} PIPS {emoji}</b>\n" \
                      f"<b>{name} {trade_type}</b>\n" \
                      f"Entry: {data['entry_low']:.{COMMODITIES[symbol][2]}f}\n" \
                      f"TP{tp_num}: {tp_price:.{COMMODITIES[symbol][2]}f}"
    elif action == 'swing':
        update_text = f"<b>✅Done SWING {emoji}</b>\n<b>{name} {trade_type}</b>"
    elif action == 'sl':
        pips = calculate_pips(data['entry_low'], data['sl'], COMMODITIES[symbol][3], symbol)
        update_text = f"<b>❌Hit SL: {pips} PIPS</b>\n" \
                      f"<b>{name} {trade_type}</b>\n" \
                      f"Entry: {data['entry_low']:.{COMMODITIES[symbol][2]}f}\n" \
                      f"SL: {data['sl']:.{COMMODITIES[symbol][2]}f}"
    else:
        update_text = None

    if update_text:
        try:
            bot.send_message(CHANNEL_USERNAME, update_text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"فشل إرسال التحديث: {e}")

    bot.answer_callback_query(call.id, "تم!")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data[user_id] = {'bot_messages': [], 'waiting_for': None}
    send_and_save_message(chat_id, "<b>أهلاً بك في بوت التداول الذكي لترتيب الصفقات ORORA.UN</b>\nاختر السلعة:", commodity_keyboard(), user_id)

@bot.message_handler(func=lambda m: any(f"{v[0]} {EMOJI_MAP.get(v[1], 'Chart')}" in m.text for v in COMMODITIES.values()))
def process_commodity(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    selected = next((k for k, v in COMMODITIES.items() if f"{v[0]} {EMOJI_MAP.get(v[1], 'Chart')}" in message.text), None)
    if not selected:
        send_and_save_message(chat_id, "*اختر من القائمة.*", commodity_keyboard(), user_id)
        return
    user_data[user_id].update({
        'commodity': selected,
        'display_name': COMMODITIES[selected][0],
        'emoji': EMOJI_MAP.get(COMMODITIES[selected][1], "Chart"),
        'waiting_for': None
    })
    send_and_save_message(chat_id, f"<b>تم اختيار {COMMODITIES[selected][0]} {user_data[user_id]['emoji']}</b>\n\nاختر نوع الصفقة:", buy_sell_keyboard(), user_id)
    bot.register_next_step_handler(message, process_trade_type)

def process_trade_type(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    trade_type = message.text.upper()
    if trade_type not in ['BUY', 'SELL', 'BUY LIMIT', 'SELL LIMIT']:
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
    direction_emoji = "🟢" if is_buy else "🔴"

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

    if is_buy:
        tp1 = round(entry_low + tp_step, decimals)
        tp2 = round(tp1 + tp_step, decimals)
        tp3 = round(tp2 + tp_step, decimals)
    else:
        tp1 = round(entry_low - tp_step, decimals)
        tp2 = round(tp1 - tp_step, decimals)
        tp3 = round(tp2 - tp_step, decimals)

    display_type = f"{trade_type} {direction_emoji}"

    output = f"SETUP: {name} {emoji} › {display_type}\n\n"
    output += f"{entry_display}\n"
    output += f"<b>SL:</b> {sl:.{decimals}f}❌\n\n"
    output += f"Check <b>✅TP1:</b> {tp1:.{decimals}f}\n"
    output += f"Check <b>✅TP2:</b> {tp2:.{decimals}f}\n"
    output += f"Check <b>✅TP3:</b> {tp3:.{decimals}f}\n"
    output += f"Check <b>✅SWING</b>\n\n"
    output += "Warning <i>Warning تنويه هام: يجب الالتزام الصارم بإجراءات وضوابط إدارة رأس المال المقررة. Chart Money</i>"

    msg = send_and_save_message(chat_id, output, user_id=user_id)
    if msg:
        data.update({
            'msg_id': msg.message_id,
            'last_setup_msg_id': msg.message_id,  # مهم
            'entry_low': entry_low,
            'entry_high': entry_high,
            'tp_prices': [tp1, tp2, tp3],
            'sl': sl,
            'direction': direction,
            'is_buy': is_buy,
            'is_limit': is_limit,
            'tp1_done': False, 'tp2_done': False, 'tp3_done': False,
            'swing_done': False, 'sl_hit': False,
            'extra_tps': [],
            'waiting_for': None
        })
        bot.edit_message_reply_markup(chat_id, msg.message_id, reply_markup=create_inline_buttons(data))

    if CHANNEL_USERNAME:
        try:
            channel_msg = bot.send_message(CHANNEL_USERNAME, output, parse_mode='HTML', disable_web_page_preview=True)
            data['channel_msg_id'] = channel_msg.message_id
        except Exception as e:
            logger.error(f"فشل النشر: {e}")

def update_setup_message(user_id, chat_id):
    data = user_data[user_id]
    updated_text = create_updated_setup_text(data)
    try:
        bot.edit_message_text(chat_id=chat_id, message_id=data['last_setup_msg_id'], text=updated_text, parse_mode='HTML')
        bot.edit_message_reply_markup(chat_id=chat_id, message_id=data['last_setup_msg_id'], reply_markup=create_inline_buttons(data))
        if 'channel_msg_id' in data:
            bot.edit_message_text(chat_id=CHANNEL_USERNAME, message_id=data['channel_msg_id'], text=updated_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"فشل تحديث الرسالة: {e}")

@bot.message_handler(func=lambda m: True)
def handle_user_input(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id not in user_data or 'waiting_for' not in user_data[user_id]:
        return

    waiting = user_data[user_id]['waiting_for']
    if not waiting:
        return

    msg_id = waiting['msg_id']
    current_msg_id = user_data[user_id].get('last_setup_msg_id')
    if not current_msg_id or current_msg_id != msg_id:
        bot.send_message(chat_id, "الإعداد انتهى. ابدأ من جديد.")
        user_data[user_id]['waiting_for'] = None
        return

    try:
        value = float(message.text)
    except ValueError:
        bot.send_message(chat_id, "الرجاء إدخال رقم صحيح.")
        return

    symbol = user_data[user_id]['commodity']
    decimals = COMMODITIES[symbol][2]
    name = COMMODITIES[symbol][0]
    emoji = user_data[user_id]['emoji']
    trade_type = user_data[user_id]['trade_type']

    if waiting['type'] == 'sl':
        old_sl = user_data[user_id]['sl']
        user_data[user_id]['sl'] = round(value, decimals)
        pips = calculate_pips(user_data[user_id]['entry_low'], value, COMMODITIES[symbol][3], symbol)
        update_text = f"<b>تم تعديل SL: {pips} PIPS</b>\n" \
                      f"<b>{name} {trade_type}</b>\n" \
                      f"Entry: {user_data[user_id]['entry_low']:.{decimals}f}\n" \
                      f"SL الجديد: {value:.{decimals}f}"
        bot.send_message(chat_id, f"تم تعديل SL إلى: {value:.{decimals}f}")

    elif waiting['type'] == 'tp':
        new_tp = round(value, decimals)
        user_data[user_id].setdefault('extra_tps', []).append(new_tp)
        tp_index = len(user_data[user_id]['extra_tps']) + 3
        pips = calculate_pips(user_data[user_id]['entry_low'], new_tp, COMMODITIES[symbol][3], symbol)
        update_text = f"<b>تم إضافة TP{tp_index}: {pips} PIPS {emoji}</b>\n" \
                      f"<b>{name} {trade_type}</b>\n" \
                      f"Entry: {user_data[user_id]['entry_low']:.{decimals}f}\n" \
                      f"TP{tp_index}: {new_tp:.{decimals}f}"
        bot.send_message(chat_id, f"تم إضافة TP{tp_index}: {new_tp:.{decimals}f}")

    # إرسال إلى القناة
    try:
        bot.send_message(CHANNEL_USERNAME, update_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"فشل إرسال التحديث: {e}")

    # تحديث الرسالة الأصلية
    update_setup_message(user_id, chat_id)
    user_data[user_id]['waiting_for'] = None

@bot.message_handler(func=lambda m: m.text == 'بدء جديد')
def new_setup(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_data[user_id] = {'bot_messages': [], 'waiting_for': None}
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
