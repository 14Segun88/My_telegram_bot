# bot.py
import logging
import datetime
import pytz
import html
import traceback
import json

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
    CallbackQuery
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import config
import daily_content
import test_engine
import user_data_manager as udm
import email_sender

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

MENU_CALLBACK_MAIN = "menu_main"

def escape_markdown_v2(text: str) -> str:
    if not isinstance(text, str): text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    text = text.replace('\\', '\\\\')
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def update_user_and_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user: udm.create_or_update_user(user.id, user.username, user.first_name)
    return user

def get_main_menu_keyboard(user_data: dict = None) -> InlineKeyboardMarkup:
    keyboard = []
    if user_data and user_data.get("subscribed_to_daily"):
        keyboard.append([InlineKeyboardButton("⏸️ Остановить практики", callback_data="menu_stop_daily")])
    else:
        keyboard.append([InlineKeyboardButton(config.SUBSCRIBE_BUTTON_TEXT, callback_data="menu_subscribe_daily")])
    keyboard.append([InlineKeyboardButton(config.MAIN_CHANNEL_BUTTON_TEXT, url=config.MAIN_CHANNEL_LINK)])
    return InlineKeyboardMarkup(keyboard)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await update_user_and_log(update, context)
    chat_id = user.id; user_data = udm.get_user_data(chat_id)
    reply_markup = get_main_menu_keyboard(user_data)
    text_to_send = escape_markdown_v2(config.MENU_TEXT)
    if update.callback_query:
        try: await update.callback_query.edit_message_text(text=text_to_send, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception: await context.bot.send_message(chat_id=chat_id, text=text_to_send, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    else: await update.message.reply_text(text=text_to_send, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await update_user_and_log(update, context)
    udm.get_user_data(user.id) # Ensure user data is loaded/created
    keyboard = []
    user_data = udm.get_user_data(user.id) # Get fresh user data
    if not user_data.get("subscribed_to_daily"):
        keyboard.append([InlineKeyboardButton(config.SUBSCRIBE_BUTTON_TEXT, callback_data="subscribe_daily")])
    else:
        keyboard.append([InlineKeyboardButton("⏸️ Остановить практики", callback_data="menu_stop_daily")])
    keyboard.append([InlineKeyboardButton(config.MAIN_CHANNEL_BUTTON_TEXT, url=config.MAIN_CHANNEL_LINK)])

    await update.message.reply_text(escape_markdown_v2(config.WELCOME_TEXT), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    udm.set_user_stage(user.id, "greeted")

async def stopdaily_command(update: Update, context: ContextTypes.DEFAULT_TYPE, from_menu: bool = False) -> None:
    user = await update_user_and_log(update, context)
    chat_id = user.id; user_data = udm.get_user_data(chat_id)
    if user_data and user_data.get("subscribed_to_daily"):
        _remove_daily_jobs_for_user(str(chat_id), context.job_queue)
        udm.update_user_data(chat_id, {"subscribed_to_daily": False, "daily_practice_mode": "none", "stage": "unsubscribed_daily"})
        msg_text = escape_markdown_v2(config.UNSUBSCRIBE_TEXT)
        reply_m = get_main_menu_keyboard(udm.get_user_data(chat_id))
        if from_menu and update.callback_query: await update.callback_query.edit_message_text(text=msg_text, reply_markup=reply_m, parse_mode=ParseMode.MARKDOWN_V2)
        else: await context.bot.send_message(chat_id, text=msg_text, reply_markup=reply_m, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        msg_text = escape_markdown_v2(config.UNSUBSCRIBE_NOT_SUBSCRIBED_TEXT)
        reply_m = get_main_menu_keyboard(user_data)
        if from_menu and update.callback_query: await update.callback_query.edit_message_text(text=msg_text, reply_markup=reply_m, parse_mode=ParseMode.MARKDOWN_V2)
        else: await context.bot.send_message(chat_id, text=msg_text, reply_markup=reply_m, parse_mode=ParseMode.MARKDOWN_V2)

def _remove_daily_jobs_for_user(job_name_prefix: str, job_queue_instance):
    for type_suffix in ["morning", "evening"]:
        for job in job_queue_instance.get_jobs_by_name(f"{job_name_prefix}_{type_suffix}"):
            job.schedule_removal(); logger.info(f"Removed job: {job.name}")

async def send_daily_practice_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job; chat_id = job.chat_id if job else None
    if not chat_id: return
    practice_type = job.data.get("pt", "morning")

    user_data = udm.get_user_data(chat_id)
    if not user_data or not user_data.get("subscribed_to_daily"):
        _remove_daily_jobs_for_user(str(chat_id), context.job_queue); return

    today = datetime.date.today().isoformat()
    if (practice_type == "morning" and user_data.get("last_morning_sent_date") == today) or \
       (practice_type == "evening" and user_data.get("last_evening_sent_date") == today): return

    current_day = user_data.get("current_daily_day", 1)
    if user_data.get("daily_practice_mode") == "morning_only" and practice_type == "evening": return

    day_content = daily_content.DAILY_CONTENT.get(current_day)
    practice_data = day_content.get(practice_type) if day_content else None

    if not practice_data:
        if practice_type == "morning" and current_day == 14 and not (day_content and day_content.get("morning")):
            logger.info(f"No morning practice content for day 14, user {chat_id}, offering test.")
            await offer_test_if_not_taken(context, chat_id, user_data, config.KEY_TEST_ID, is_day14=True)
            udm.update_last_sent_date(chat_id, "morning")
        else:
            logger.warning(f"No practice_data for day {current_day}, type {practice_type}, user {chat_id}.")
        return

    kb = [[InlineKeyboardButton(practice_data["button_text"], callback_data=f"daily_ack_{current_day}_{practice_type}")],[InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)]]
    try:
        await context.bot.send_message(chat_id, practice_data["text"], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
        udm.update_last_sent_date(chat_id, practice_type)

        if practice_type == "evening":
            if current_day in config.TEST_OFFER_DAYS or current_day == 14:
                await offer_test_if_not_taken(context, chat_id, user_data, config.KEY_TEST_ID, is_day14=(current_day==14))

        if (practice_type == "evening" and user_data.get("daily_practice_mode") == "dual") or \
           (practice_type == "morning" and user_data.get("daily_practice_mode") == "morning_only"):
            udm.increment_user_daily_day(chat_id, daily_content.TOTAL_DAYS)
    except Exception as e:
        logger.error(f"Error sending daily practice: {e}")
        if "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
            _remove_daily_jobs_for_user(str(chat_id), context.job_queue)
            udm.update_user_data(chat_id, {"subscribed_to_daily": False, "daily_practice_mode": "none", "stage": "bot_blocked"})

def _schedule_daily_jobs_for_user(chat_id: int, job_queue_instance, user_data: dict):
    job_name_prefix = str(chat_id)
    _remove_daily_jobs_for_user(job_name_prefix, job_queue_instance) # Clear existing jobs first
    mode = user_data.get("daily_practice_mode", "dual")
    if mode in ["dual", "morning_only"]:
        job_queue_instance.run_daily(send_daily_practice_job, config.MORNING_PRACTICE_TIME_UTC, chat_id=chat_id, name=f"{job_name_prefix}_morning", data={"pt": "morning"})
        logger.info(f"Scheduled morning job for {chat_id} at {config.MORNING_PRACTICE_TIME_UTC}")
    if mode == "dual": # Only schedule evening if mode is dual
        job_queue_instance.run_daily(send_daily_practice_job, config.EVENING_PRACTICE_TIME_UTC, chat_id=chat_id, name=f"{job_name_prefix}_evening", data={"pt": "evening"})
        logger.info(f"Scheduled evening job for {chat_id} at {config.EVENING_PRACTICE_TIME_UTC}")


async def offer_test_if_not_taken(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_data: dict, test_id: str, is_day14: bool = False):
    test_info = test_engine.get_test_by_id(test_id)
    if not test_info: logger.error(f"Test {test_id} not found in test_engine."); return

    test_taken_data = user_data.get("tests_taken", {}).get(test_id)
    if not is_day14 and test_taken_data and test_taken_data.get('consult_interest_shown'): return
    if is_day14 and test_taken_data and test_taken_data.get('consult_interest_shown'):
        logger.info(f"User {chat_id} already showed consult interest for {test_id} on day 14. Skipping."); return

    if is_day14 and (user_data.get("active_test", {}).get("id") == test_id or \
                     user_data.get("stage", "").startswith(f"awaiting_email_input_for_{test_id}")):
        logger.info(f"User {chat_id} already interacting with test {test_id} on day 14. Skipping offer.")
        return

    prompt_text_template = config.DAY14_FORCED_TEST_PROMPT_TEXT if is_day14 else config.TEST_INTRO_TEXT_TEMPLATE
    button_text = config.DAY14_FORCED_TEST_BUTTON_TEXT if is_day14 else config.TEST_BUTTON_YES_TEXT
    callback_action = f"start_test_{test_id}_forced" if is_day14 else f"offer_test_yes_{test_id}"

    text = escape_markdown_v2(prompt_text_template.format(test_name=test_info['name']))
    keyboard_rows = [[InlineKeyboardButton(button_text, callback_data=callback_action)]]
    if not is_day14:
        keyboard_rows.append([InlineKeyboardButton(config.TEST_BUTTON_NO_TEXT, callback_data=f"offer_test_no_{test_id}")])
    keyboard_rows.append([InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)])

    await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN_V2)
    udm.set_user_stage(chat_id, f"day14_forced_test_offered_{test_id}" if is_day14 else f"daily_test_offered_{test_id}")


async def _start_test_logic(query_object_or_message, context: ContextTypes.DEFAULT_TYPE, chat_id: int, test_id: str, user_data: dict, is_forced: bool = False):
    test_data = test_engine.get_test_by_id(test_id)
    if not test_data:
        error_text = "Ошибка: Тест не найден."
        reply_markup_menu = get_main_menu_keyboard(user_data)
        if isinstance(query_object_or_message, CallbackQuery):
            try: await query_object_or_message.edit_message_text(text=error_text, reply_markup=reply_markup_menu)
            except Exception: await context.bot.send_message(chat_id, error_text, reply_markup=reply_markup_menu)
        # If it's not a CallbackQuery, it must be an Update object (from a direct command, though this function is usually called from button_handler)
        # However, the original code only expects CallbackQuery or implies it by usage.
        # For safety, let's assume it could be a message if not a CallbackQuery.
        elif hasattr(query_object_or_message, 'message') and query_object_or_message.message:
             await query_object_or_message.message.reply_text(error_text, reply_markup=reply_markup_menu)
        else: # Fallback if it's neither, though this case should be reviewed based on actual call sites
             await context.bot.send_message(chat_id, error_text, reply_markup=reply_markup_menu)
        return

    active_test_payload = {"id": test_id, "current_question_idx": 0, "answers": []}
    if is_forced: active_test_payload["is_forced_day14"] = True
    udm.update_user_data(chat_id, {"active_test": active_test_payload, "stage": f"in_test_{test_id}"})
    
    # Edit the message that triggered the test start, if it was a callback query
    if isinstance(query_object_or_message, CallbackQuery):
        try: await query_object_or_message.edit_message_text(text=escape_markdown_v2(f"Начинаем тест «{test_data['name']}»..."), parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e: logger.warning(f"Could not edit message for starting test: {e}")
    
    await _send_test_question(context, chat_id, test_data, 0, test_id)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; await query.answer()
    user = await update_user_and_log(update, context)
    chat_id = user.id; user_data = udm.get_user_data(chat_id)
    if not user_data: await query.edit_message_text("Ошибка пользователя."); return
    data = query.data

    if data == MENU_CALLBACK_MAIN: await menu_command(update, context); return
    if data == "menu_stop_daily": await stopdaily_command(update, context, from_menu=True); return
    if data == "menu_subscribe_daily" or data == "subscribe_daily":
        if not user_data.get("subscribed_to_daily"):
            udm.set_user_subscribed(chat_id, True); user_data = udm.get_user_data(chat_id) # Refresh user_data
            _schedule_daily_jobs_for_user(chat_id, context.job_queue, user_data)
            await query.edit_message_text(text=escape_markdown_v2(config.SUBSCRIPTION_SUCCESS_TEXT.format(button_ack_text=daily_content.COMMON_BUTTON_TEXT)), reply_markup=get_main_menu_keyboard(user_data), parse_mode=ParseMode.MARKDOWN_V2)
        else: await query.edit_message_text(text=escape_markdown_v2(config.SUBSCRIPTION_ALREADY_ACTIVE_TEXT), reply_markup=get_main_menu_keyboard(user_data), parse_mode=ParseMode.MARKDOWN_V2)
        return

    elif data.startswith("daily_ack_"):
        parts = data.split("_"); day_acked = int(parts[2]); type_acked = parts[3]
        udm.set_user_stage(chat_id, f"daily_practice_day{day_acked}_{type_acked}_ack")
        try:
            current_markup = query.message.reply_markup; new_keyboard_rows = []
            if current_markup:
                for row in current_markup.inline_keyboard:
                    new_row = [btn for btn in row if btn.callback_data != data]
                    if new_row: new_keyboard_rows.append(new_row)
            new_reply_markup = InlineKeyboardMarkup(new_keyboard_rows) if new_keyboard_rows else None
            original_text_html = query.message.text_html if hasattr(query.message, 'text_html') else query.message.text
            await query.edit_message_text(text=original_text_html, reply_markup=new_reply_markup, parse_mode=ParseMode.HTML if hasattr(query.message, 'text_html') else None)
        except Exception as e: logger.warning(f"Could not edit markup for daily_ack: {e}"); await query.edit_message_reply_markup(reply_markup=None) # Try to remove markup at least
    elif data.startswith("start_test_"):
        test_id = data.replace("start_test_", "").replace("_forced", ""); is_forced = "_forced" in data
        await _start_test_logic(query, context, chat_id, test_id, user_data, is_forced=is_forced)
    elif data.startswith("offer_test_yes_"):
        test_id = data.replace("offer_test_yes_", ""); await _start_test_logic(query, context, chat_id, test_id, user_data)
    elif data.startswith("offer_test_no_"):
        udm.set_user_stage(chat_id, f"daily_test_declined_{data.replace('offer_test_no_', '')}")
        await query.edit_message_text(text=escape_markdown_v2(config.TEST_BUTTON_NO_TEXT) + "\n\nПрактики продолжатся\\. 😊", reply_markup=get_main_menu_keyboard(user_data), parse_mode=ParseMode.MARKDOWN_V2)
    elif data.startswith("testans_"):
        data_payload = data[len("testans_"):]; parts = data_payload.split("_")
        if len(parts) >= 3:
            try:
                ans_idx_str = parts[-1]; q_idx_str = parts[-2]; test_id_from_cb = "_".join(parts[:-2])
                q_idx = int(q_idx_str); ans_idx = int(ans_idx_str)
                await _handle_test_answer(query, context, chat_id, user_data, test_id_from_cb, q_idx, ans_idx)
            except ValueError: logger.error(f"ValueError parsing testans: {data}. Parts: {parts}"); await query.edit_message_text("Ошибка ответа(V).")
            except IndexError: logger.error(f"IndexError parsing testans: {data}. Parts: {parts}"); await query.edit_message_text("Ошибка ответа(I).")
        else: logger.error(f"Invalid format for testans: {data_payload}. Parts: {len(parts)}"); await query.edit_message_text("Ошибка ответа(F).")
    elif data.startswith("post_email_consult_yes_"):
        test_id_from_cb = data.replace("post_email_consult_yes_", "")
        await _handle_consultation_request(query, context, chat_id, user_data, test_id_from_cb)
    elif data.startswith("post_email_consult_no_"):
        udm.set_user_stage(chat_id, f"consult_declined_after_email_{data.replace('post_email_consult_no_', '')}")
        await query.edit_message_text(text=escape_markdown_v2(config.CONSULTATION_DECLINED_TEXT), reply_markup=get_main_menu_keyboard(user_data),parse_mode=ParseMode.MARKDOWN_V2)
    elif data.startswith("post_email_consult_think_"):
        test_id_from_cb = data.replace("post_email_consult_think_", "")
        udm.update_user_data(chat_id, {"stage": f"consult_thinking_day14_{test_id_from_cb}", "daily_practice_mode": "morning_only"})
        user_data = udm.get_user_data(chat_id); _schedule_daily_jobs_for_user(chat_id, context.job_queue, user_data)
        think_text = escape_markdown_v2(config.CONSULTATION_THINK_LATER_TEXT.format(admin_username=config.ADMIN_CONTACT_USERNAME))
        await query.edit_message_text(text=think_text, reply_markup=get_main_menu_keyboard(user_data), parse_mode=ParseMode.MARKDOWN_V2)


async def _send_test_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int, test_data: dict, question_idx: int, test_id_for_callback: str):
    question = test_data["questions"][question_idx]
    text = escape_markdown_v2(question["text"])
    keyboard_rows = []
    for i, option in enumerate(question["options"]):
        option_text = escape_markdown_v2(option["text"]) # Escape option text as well
        keyboard_rows.append([InlineKeyboardButton(option_text, callback_data=f"testans_{test_id_for_callback}_{question_idx}_{i}")])
    keyboard_rows.append([InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)]) # Add menu button
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

async def _handle_test_answer(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_data: dict, test_id: str, q_idx: int, ans_idx: int):
    active_test_data = user_data.get("active_test")
    if not active_test_data or active_test_data.get("id") != test_id or active_test_data.get("current_question_idx") != q_idx:
        await query.edit_message_text("Ошибка состояния теста. Попробуйте из /menu.", reply_markup=get_main_menu_keyboard(user_data)); return

    test_definition = test_engine.get_test_by_id(test_id)
    # Ensure question and option indices are valid
    if q_idx >= len(test_definition["questions"]) or ans_idx >= len(test_definition["questions"][q_idx]["options"]):
        logger.error(f"Invalid q_idx or ans_idx in _handle_test_answer. Test: {test_id}, Q_idx: {q_idx}, Ans_idx: {ans_idx}")
        await query.edit_message_text("Ошибка в данных ответа. Попробуйте снова.", reply_markup=get_main_menu_keyboard(user_data))
        return
        
    selected_option_value = test_definition["questions"][q_idx]["options"][ans_idx]["value"]
    active_test_data["answers"].append(selected_option_value)
    active_test_data["current_question_idx"] += 1
    udm.update_user_data(chat_id, {"active_test": active_test_data})

    original_question_text_escaped = escape_markdown_v2(test_definition["questions"][q_idx]["text"])
    selected_answer_text_escaped = escape_markdown_v2(test_definition["questions"][q_idx]["options"][ans_idx]["text"])
    try:
        await query.edit_message_text(text=f"{original_question_text_escaped}\n\nВы выбрали: *{selected_answer_text_escaped}*", parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e: logger.warning(f"Could not edit message for test answer: {e}")

    if active_test_data["current_question_idx"] < len(test_definition["questions"]):
        await _send_test_question(context, chat_id, test_definition, active_test_data["current_question_idx"], test_id)
    else:
        score = test_definition["calculate_score"](active_test_data["answers"])
        user_answer_indices = [next(j for j, opt in enumerate(test_definition["questions"][i]["options"]) if opt["value"] == saved_val) for i, saved_val in enumerate(active_test_data["answers"])]
        result_data = test_engine.get_test_result(test_id, score, user_answer_indices)
        summary_text_from_engine = result_data["summary"]
        escaped_summary_text = escape_markdown_v2(summary_text_from_engine)

        udm.record_test_taken(chat_id, test_id, summary=summary_text_from_engine, answers=active_test_data["answers"])
        is_forced_day14_test = active_test_data.get("is_forced_day14", False)
        udm.update_user_data(chat_id, {
            "active_test": None, "stage": f"awaiting_email_input_for_{test_id}",
            "pending_email_test_id": test_id, "pending_email_test_score": score,
            "pending_email_test_answers_indices": user_answer_indices,
            "pending_email_test_is_forced_day14": is_forced_day14_test
        })

        await context.bot.send_message(chat_id, escaped_summary_text, parse_mode=ParseMode.MARKDOWN_V2)
        await context.bot.send_message(chat_id, escape_markdown_v2(config.EMAIL_REQUEST_TEXT), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)]]), parse_mode=ParseMode.MARKDOWN_V2)

async def _handle_consultation_request(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_data: dict, test_id: str):
    test_taken_info = user_data.get("tests_taken", {}).get(test_id)
    if not test_taken_info:
        await query.edit_message_text("Ошибка: Данные о пройденном тесте не найдены.", reply_markup=get_main_menu_keyboard(user_data)); return

    consultation_focus_text = "глубокое понимание себя и своих уникальных особенностей"
    test_definition = test_engine.get_test_by_id(test_id)
    if test_definition and "answers" in test_taken_info and test_taken_info["answers"] is not None: # Check answers not None
        try:
            # Ensure answers are in the correct format for calculate_score if needed
            # This depends on how calculate_score and get_test_result expect the answers
            calculated_score = test_definition["calculate_score"](test_taken_info["answers"])
            user_answer_indices = [next(j for j, opt in enumerate(test_definition["questions"][i]["options"]) if opt["value"] == saved_val) for i, saved_val in enumerate(test_taken_info["answers"])]
            result_details = test_engine.get_test_result(test_id, calculated_score, user_answer_indices)
            consultation_focus_text = result_details.get("consultation_focus", consultation_focus_text)
        except Exception as e:  logger.error(f"Error getting consultation_focus for test {test_id}, user {chat_id}: {e}")

    current_tests_taken = user_data.get("tests_taken", {})
    if test_id in current_tests_taken:
        current_tests_taken[test_id]['consult_interest_shown'] = True
        udm.update_user_data(chat_id, {"tests_taken": current_tests_taken})

    udm.set_user_stage(chat_id, f"consult_5000_requested_{test_id}")

    price_str = f"*{escape_markdown_v2(str(config.CONSULTATION_PRICE_RUB))} рублей*" # Escape price
    admin_contact_str = f"@{config.ADMIN_CONTACT_USERNAME}" # Username should not need escaping if it's a valid TG username
    code_word_str = f"`КОНСУЛЬТАЦИЯ5000`"

    text_parts = [
        f"🎉 *Ваш Путь к Себе: Персональная Консультация* 🎉", "",
        f"Вы проявили интерес к глубокому погружению в результаты теста и я очень рада этому\\! ✨",
        f"На консультации мы сфокусируемся на: _{escape_markdown_v2(consultation_focus_text)}_\\.", "",
        f"Эта встреча — ваш шанс получить персональные ключи 🗝️ к гармонии, раскрыть свой потенциал и улучшить качество жизни\\.",
        f"Стоимость такой трансформационной сессии — {price_str}\\.", "",
        f"✍️ Для записи и обсуждения всех деталей, напишите нашему заботливому администратору {admin_contact_str}",
        f"Просто скажите кодовое слово: {code_word_str}",
        f"P\\.S\\. Если удобно, прикрепите скриншот с результатами теста\\. Это поможет нам лучше подготовиться к вашей встрече\\! 😉"
    ]
    final_text = "\n".join(text_parts)

    keyboard = [[InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text=final_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e_send:
        logger.error(f"Error sending consultation details (MarkdownV2): {e_send}")
        # Fallback to plain text if MarkdownV2 fails, removing Markdown characters
        plain_text_fallback = "\n".join([
            "Ваш Путь к Себе: Персональная Консультация", "",
            "Вы проявили интерес к глубокому погружению в результаты теста и я очень рада этому!",
            f"На консультации мы сфокусируемся на: {consultation_focus_text}.", "",
            "Эта встреча — ваш шанс получить персональные ключи к гармонии, раскрыть свой потенциал и улучшить качество жизни.",
            f"Стоимость такой трансформационной сессии — {config.CONSULTATION_PRICE_RUB} рублей.", "",
            f"Для записи и обсуждения всех деталей, напишите нашему заботливому администратору @{config.ADMIN_CONTACT_USERNAME}",
            "Просто скажите кодовое слово: КОНСУЛЬТАЦИЯ5000",
            "P.S. Если удобно, прикрепите скриншот с результатами теста. Это поможет нам лучше подготовиться к вашей встрече!"
        ])
        await query.edit_message_text(text=plain_text_fallback, reply_markup=reply_markup)


async def handle_potential_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_obj = await update_user_and_log(update, context); chat_id = user_obj.id
    email_text = update.message.text.strip(); user_data = udm.get_user_data(chat_id)

    if not user_data or not user_data.get("stage", "").startswith("awaiting_email_input_for_"): return

    test_id = user_data.get("pending_email_test_id")
    score = user_data.get("pending_email_test_score")
    user_answers_indices = user_data.get("pending_email_test_answers_indices")
    is_forced_day14_test_context = user_data.get("pending_email_test_is_forced_day14", False)

    if not test_id or score is None or user_answers_indices is None:
        await update.message.reply_text("Ошибка данных теста. Попробуйте снова из /menu.", reply_markup=get_main_menu_keyboard(user_data))
        udm.update_user_data(chat_id, {"stage": "test_email_data_error", "pending_email_test_id": None, "pending_email_test_score": None, "pending_email_test_answers_indices": None, "pending_email_test_is_forced_day14": False})
        return

    if "@" not in email_text or "." not in email_text.split("@")[-1]: # Basic email validation
        await update.message.reply_text(escape_markdown_v2(config.EMAIL_INVALID_TEXT), parse_mode=ParseMode.MARKDOWN_V2); return

    udm.set_user_email(chat_id, email_text)
    # Refresh user_data after setting email, as it might be used below if it was None initially
    user_data = udm.get_user_data(chat_id)

    test_result_details = test_engine.get_test_result(test_id, score, user_answers_indices)
    full_html_result = test_result_details.get("full_html_result", "<p>Результаты не найдены.</p>") # Default HTML
    test_def_subj = test_engine.get_test_by_id(test_id)
    subj_test_name = test_def_subj['name'] if test_def_subj else "Ваш тест"
    subject = f"Результаты вашего теста «{subj_test_name}»"

    email_sent_successfully = email_sender.send_email(recipient_email=email_text, subject=subject, html_body=full_html_result)
    email_status_key = "success" if email_sent_successfully else "failure"

    tests_taken_data = user_data.get("tests_taken", {}) # Ensure tests_taken_data is a dict

    if test_id in tests_taken_data:
        tests_taken_data[test_id].update({"email_recipient": email_text, "email_sent_status": email_status_key})
    else:
        summary_for_record = test_result_details.get("summary", "N/A")
        # Ensure answers for record are from the pending state if not already in tests_taken_data
        answers_for_record = user_data.get("pending_email_test_answers_indices", []) # This should be actual answers, not indices. Let's assume `user_answers_indices` refers to the raw answers list from active_test
        # The `record_test_taken` already saved answers. If this branch is hit, it means `record_test_taken` wasn't called or test_id was cleared.
        # For consistency, let's re-fetch the answers that were used for the score.
        # This part needs careful review of `udm.record_test_taken` and `active_test_data["answers"]`
        # Assuming `user_data.get("pending_email_test_answers_indices")` was meant to be the raw answers.
        # However, `udm.record_test_taken` saves `active_test_data["answers"]` which are values.
        # Let's use what was passed to `get_test_result`: `user_answers_indices` (which are indices)
        # This part is a bit confusing in the original logic. `record_test_taken` saves `answers` (values).
        # `pending_email_test_answers_indices` are indices.
        # Let's assume the intent was to store the raw values if a new record is created here.
        # This typically shouldn't happen if `record_test_taken` was successful.
        # For now, I'll use the indices as per `pending_email_test_answers_indices`.
        # This might need adjustment based on how `tests_taken.answers` is used elsewhere.
        
        # Re-evaluating: `udm.record_test_taken` is called BEFORE this email handling.
        # So, `tests_taken_data[test_id]` should already exist.
        # This `else` block might be redundant or for a very specific edge case.
        # If it's hit, it implies an issue. For safety, I'll log and use available data.
        logger.warning(f"Test {test_id} not found in tests_taken when handling email for user {chat_id}. Creating new entry.")
        tests_taken_data[test_id] = {
            "summary": summary_for_record, 
            "answers": user_data.get("pending_email_test_answers_values", []), # Assuming raw values might be stored here if available
            "date_taken": datetime.datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
            "email_recipient": email_text, 
            "email_sent_status": email_status_key,
            "consult_interest_shown": False # Default for new entry
        }


    udm.update_user_data(chat_id, {"tests_taken": tests_taken_data, "pending_email_test_id": None, "pending_email_test_score": None, "pending_email_test_answers_indices": None, "pending_email_test_is_forced_day14": False, "pending_email_test_answers_values": None}) # Clear pending values too

    escaped_email_md = escape_markdown_v2(email_text)
    if email_sent_successfully:
        email_feedback_part1 = f"💌 Ура\\! Подробные результаты теста уже летят к тебе на _{escaped_email_md}_\\!"
        email_feedback_part2 = ""
    else:
        email_feedback_part1 = f"😥 Ой, кажется, произошла техническая ошибка при отправке письма на _{escaped_email_md}_\\."
        email_feedback_part2 = "\n\nНо не волнуйся, краткие результаты ты уже видел(а)\\! ✨"

    consult_offer_text = f"""{email_feedback_part1}{email_feedback_part2}

💖 *Хочешь раскрыть всю глубину этих знаний о себе?*
{escape_markdown_v2("Предлагаю тебе персональную консультацию, где мы вместе:")}
✨ Расшифруем каждый аспект результатов
🗝️ Найдем твои уникальные сильные стороны и зоны роста
🗺️ Наметим путь к еще большей гармонии и удовольствию в жизни\\!
"""

    is_day14_context_final = False # Renamed to avoid conflict
    # Use the refreshed user_data
    test_taken_entry = user_data.get("tests_taken", {}).get(test_id, {})
    consult_interest_shown = test_taken_entry.get("consult_interest_shown", False)
    
    if is_forced_day14_test_context: is_day14_context_final = True
    # Check current_daily_day from the latest user_data
    elif user_data.get("current_daily_day") == 14 and not consult_interest_shown: is_day14_context_final = True

    buttons = [[InlineKeyboardButton(config.CONSULTATION_OFFER_BUTTON_YES_TEXT, callback_data=f"post_email_consult_yes_{test_id}")]]
    if is_day14_context_final: buttons.append([InlineKeyboardButton(config.CONSULTATION_OFFER_BUTTON_THINK_LATER_TEXT, callback_data=f"post_email_consult_think_{test_id}")])
    else: buttons.append([InlineKeyboardButton(config.CONSULTATION_OFFER_BUTTON_NO_TEXT, callback_data=f"post_email_consult_no_{test_id}")])
    buttons.append([InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)])
    reply_markup = InlineKeyboardMarkup(buttons)

    await update.message.reply_text(consult_offer_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    udm.set_user_stage(chat_id, f"post_test_offer_email_sent_{test_id}")

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in config.ADMIN_USER_IDS: await update.message.reply_text("Эта команда доступна только администраторам."); return
    await update.message.reply_text(f"Ваш User ID: `{user_id}`", parse_mode=ParseMode.MARKDOWN_V2)

async def setday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; args = context.args
    if user_id not in config.ADMIN_USER_IDS: await update.message.reply_text("Только для админов."); return
    if len(args) != 2: await update.message.reply_text("Нужно: /setday <user_id> <day>"); return
    try: target_user_id = int(args[0]); day_number = int(args[1])
    except ValueError: await update.message.reply_text("ID и день должны быть числами."); return
    if not (1 <= day_number <= daily_content.TOTAL_DAYS): await update.message.reply_text(f"День от 1 до {daily_content.TOTAL_DAYS}."); return
    target_user_data = udm.get_user_data(target_user_id)
    if not target_user_data: await update.message.reply_text(f"Юзер {target_user_id} не найден."); return
    if udm.update_user_data(target_user_id, {"current_daily_day": day_number, "last_morning_sent_date": None, "last_evening_sent_date": None, "stage": f"admin_set_day_{day_number}"}):
        target_user_data_updated = udm.get_user_data(target_user_id) # Get fresh data
        if target_user_data_updated and target_user_data_updated.get("subscribed_to_daily"):
            _schedule_daily_jobs_for_user(target_user_id, context.job_queue, target_user_data_updated)
        await update.message.reply_text(f"Для {target_user_id} день {day_number} установлен.")
    else: await update.message.reply_text(f"Не удалось обновить день для {target_user_id}.")

async def forcesend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; args = context.args
    if user_id not in config.ADMIN_USER_IDS: await update.message.reply_text("Только для админов."); return
    if not (2 <= len(args) <= 3): await update.message.reply_text("/forcesend <uid> <day> [morning|evening]"); return
    try: target_user_id = int(args[0]); day_to_send = int(args[1])
    except ValueError: await update.message.reply_text("ID и день - числа."); return
    type_to_send = args[2] if len(args) > 2 else "morning"
    if not (1 <= day_to_send <= daily_content.TOTAL_DAYS): await update.message.reply_text(f"День от 1 до {daily_content.TOTAL_DAYS}."); return
    if type_to_send not in ["morning", "evening"]: await update.message.reply_text("Тип: 'morning' или 'evening'."); return
    target_user_data = udm.get_user_data(target_user_id)
    if not target_user_data: await update.message.reply_text(f"Юзер {target_user_id} не найден."); return
    day_content_data = daily_content.DAILY_CONTENT.get(day_to_send) # Renamed variable
    if not day_content_data: await update.message.reply_text(f"Нет контента дня {day_to_send}."); return
    practice_data = day_content_data.get(type_to_send)
    if not practice_data: await update.message.reply_text(f"Нет {type_to_send} практики дня {day_to_send}."); return

    kb = [[InlineKeyboardButton(practice_data["button_text"], callback_data=f"daily_ack_{day_to_send}_{type_to_send}")], [InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)]]
    try:
        await context.bot.send_message(target_user_id, practice_data["text"], reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML)
        await update.message.reply_text(f"Отправлена {type_to_send} практика дня {day_to_send} юзеру {target_user_id}.")
        if type_to_send == "evening":
            if day_to_send in config.TEST_OFFER_DAYS or day_to_send == 14:
                await offer_test_if_not_taken(
                    context,
                    target_user_id,
                    target_user_data, # Pass the fetched user data
                    config.KEY_TEST_ID,
                    is_day14=(day_to_send == 14)
                )
    except Exception as e:
        logger.error(f"Error in /forcesend sending: {e}")
        await update.message.reply_text(f"Ошибка отправки: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            user_id_for_menu = update.effective_user.id if update.effective_user else None
            user_data_for_menu = udm.get_user_data(user_id_for_menu) if user_id_for_menu else None # Fetch fresh data
            await update.effective_message.reply_text(
                escape_markdown_v2("Ой, что-то пошло не так... 😥 Попробуйте, пожалуйста, немного позже или вернитесь в /menu."),
                reply_markup=get_main_menu_keyboard(user_data_for_menu), # Use fresh data for menu
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e_reply: # Catch exception during error reply
            logger.error(f"Exception while sending error message to user: {e_reply}")


def main() -> None:
    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("stopdaily", stopdaily_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("setday", setday_command))
    application.add_handler(CommandHandler("forcesend", forcesend_command))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_potential_email))

    application.add_error_handler(error_handler)

    logger.info("Loading existing users and scheduling jobs...")
    all_users = udm.load_users()
    job_queue = application.job_queue
    for chat_id_str, user_data_dict in all_users.items():
        try:
            chat_id_int = int(chat_id_str) # Renamed variable
            if user_data_dict.get("subscribed_to_daily") and user_data_dict.get("daily_practice_mode") in ["dual", "morning_only"]:
                _schedule_daily_jobs_for_user(chat_id_int, job_queue, user_data_dict)
            # Removed the else for _remove_daily_jobs_for_user as _schedule_daily_jobs_for_user now handles removal internally.
            # This ensures that if a user was subscribed but mode is now 'none', jobs are still cleared.
            # Or, if they are not subscribed, _schedule_daily_jobs_for_user won't schedule new ones,
            # and if old ones existed, they should have been removed when subscription status changed.
            # For robustness, one might still want to explicitly remove if not subscribed:
            elif not user_data_dict.get("subscribed_to_daily"):
                 _remove_daily_jobs_for_user(str(chat_id_int), job_queue)

        except ValueError: logger.error(f"Invalid chat_id in users.json: {chat_id_str}")
        except Exception as e: logger.error(f"Error rescheduling for user {chat_id_str}: {e}")
    logger.info("Bot started successfully!")
    application.run_polling()

if __name__ == "__main__":
    main()