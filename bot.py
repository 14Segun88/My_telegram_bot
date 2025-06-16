# bot.py
import logging
import datetime
import pytz
import re
import asyncio
import html
import traceback
import json
import importlib

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeChat,
    CallbackQuery,
    Message,
    Chat
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ApplicationBuilder,
    JobQueue
)

import config
import daily_content
import test_engine
import user_data_manager as udm
import email_sender
from admin_commands import force_send_practice_command

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

    # "Купить консультацию" теперь третья кнопка
    keyboard.append([InlineKeyboardButton("Купить консультацию", callback_data="post_email_consult_yes_menu")])
    
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

    # Send the first video note
    try:
        await context.bot.send_video_note(
            chat_id=user.id,
            video_note="DQACAgIAAxkBAAEBcnxoP05JC_1pBGgw2Ie34uMed5gcsQAC3YkAAsIT8Unip--0-JqmqjYE"
        )
        logger.info(f"Sent start video note to user {user.id}")
    except Exception as e_video:
        logger.error(f"Failed to send start video note: {e_video}")

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

async def send_daily_practice_job(context: ContextTypes.DEFAULT_TYPE):
    """Отправка ежедневной практики по расписанию"""
    job = context.job
    if not job or not job.name:
        logger.error(f"Invalid job: {getattr(job, 'name', 'No job name')}")
        return
        
    logger.info(f"===== Запуск задачи: {job.name} =====")
    logger.info(f"Job data: {job.data}")
    
    try:
        # Исправление: используем job.data для получения типа практики
        user_id = int(job.name.split('_')[0])  # Извлекаем ID пользователя из имени задачи
        practice_type = job.data.get('pt', 'morning')  # Используем данные из job.data
        
        # Получаем данные пользователя
        user_data = udm.get_user_data(user_id)
        if not user_data:
            logger.warning(f"User {user_id} not found in database")
            return
            
        # Проверяем, не отправляли ли уже сегодня практику этого типа
        from datetime import datetime  # Добавляем импорт datetime
        today = datetime.now().date().isoformat()
        last_sent_date = user_data.get(f'last_{practice_type}_sent_date')
        if last_sent_date == today:
            logger.info(f"Already sent {practice_type} practice to user {user_id} today")
            return
            
        current_day = user_data.get("current_daily_day", 1)
        if user_data.get("daily_practice_mode") == "morning_only" and practice_type == "evening":
            logger.info(f"Skipping evening practice for user {user_id} in morning_only mode")
            return
            
        # Определяем chat_id для дальнейшего использования
        chat_id = user_id
        
    except Exception as e:
        logger.error(f"Error in send_daily_practice_job: {e}", exc_info=True)
        return  # Добавляем return, чтобы прервать выполнение при ошибке

    # Получаем контент для текущего дня и типа практики
    day_content = daily_content.DAILY_CONTENT.get(current_day)
    practice_data = day_content.get(practice_type) if day_content else None
    
    logger.info(f"Sending {practice_type} practice for day {current_day} to user {chat_id}")

    if not practice_data:
        if practice_type == "morning" and current_day == 14 and not (day_content and day_content.get("morning")):
            logger.info(f"No morning practice content for day 14, user {chat_id}, offering test.")
            await offer_test_if_not_taken(context, chat_id, user_data, config.KEY_TEST_ID, is_day14=True, test_for_day=current_day)
            udm.update_last_sent_date(chat_id, "morning")
        else:
            logger.warning(f"No practice_data for day {current_day}, type {practice_type}, user {chat_id}.")
        return

    # Main practice message
    # Send practice message
    kb = [
        [InlineKeyboardButton(practice_data["button_text"], callback_data=f"daily_ack_{current_day}_{practice_type}")],
        [
            InlineKeyboardButton("Купить консультацию", callback_data="post_email_consult_yes_practice"),
            InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)
        ]
    ]
    try:
        # Send practice with a longer timeout
        await context.bot.send_message(
            chat_id=chat_id,
            text=practice_data["text"],
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.HTML,
            write_timeout=30
        )
        udm.update_last_sent_date(chat_id, practice_type)

        # Предложение о консультации теперь встроено в клавиатуру
        


        if practice_type == "evening":
            if current_day in config.TEST_OFFER_DAYS or current_day == 14:
                await offer_test_if_not_taken(context, chat_id, user_data, config.KEY_TEST_ID, is_day14=(current_day==14), test_for_day=current_day)

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
    
    # 0. Запускаем отладочную информацию - сколько задач уже есть в планировщике
    all_jobs = job_queue_instance.jobs()
    logger.info(f"[SCHEDULER DEBUG] Всего задач при входе: {len(all_jobs)}")
    for j in all_jobs:
        logger.info(f"[SCHEDULER DEBUG] Существующая задача: {j.name}, следующий запуск: {j.next_t}")
    
    # 1. Принудительно удаляем все старые задачи для этого пользователя
    removed_jobs = 0
    for job in job_queue_instance.jobs():
        if job.name and job.name.startswith(job_name_prefix):
            job.schedule_removal()
            removed_jobs += 1
            logger.info(f"Удалена старая задача: {job.name}")
    logger.info(f"[SCHEDULER DEBUG] Удалено задач для пользователя {chat_id}: {removed_jobs}")
    
    current_day = user_data.get("current_daily_day", 0)
    
    # 2. Устанавливаем время по умолчанию
    morning_time_to_use = config.MORNING_PRACTICE_TIME_UTC
    evening_time_to_use = config.EVENING_PRACTICE_TIME_UTC

    # 3. Проверяем, есть ли особое время для текущего дня (например, День 3)
    if current_day == 3: 
        try:
            morning_time_val = config.DAY3_KEY_TEST_OFFER_MORNING_UTC
            evening_time_val = config.DAY3_KEY_TEST_OFFER_EVENING_UTC

            # Обрабатываем и str ('HH:MM'), и datetime.time из конфига
            if isinstance(morning_time_val, str):
                h, m = map(int, morning_time_val.split(':'))
                morning_time_to_use = datetime.time(hour=h, minute=m, tzinfo=pytz.UTC)
            else:
                morning_time_to_use = morning_time_val

            if isinstance(evening_time_val, str):
                h, m = map(int, evening_time_val.split(':'))
                evening_time_to_use = datetime.time(hour=h, minute=m, tzinfo=pytz.UTC)
            else:
                evening_time_to_use = evening_time_val
            
            logger.info(f"День 3 (тест.предложение): Используем специальное время: {morning_time_to_use.strftime('%H:%M:%S%z')}, {evening_time_to_use.strftime('%H:%M:%S%z')}")
        
        except Exception as e:
            logger.error(f"Ошибка при использовании времени для Дня 3 из config: {e}. Используем стандартное время.")
            morning_time_to_use = config.MORNING_PRACTICE_TIME_UTC
            evening_time_to_use = config.EVENING_PRACTICE_TIME_UTC
            logger.info(f"День 3 (тест.предложение): Откат к стандартному времени: {morning_time_to_use.strftime('%H:%M:%S%z')}, {evening_time_to_use.strftime('%H:%M:%S%z')}")

    # 4. Логируем итоговое время, которое будет использоваться
    logger.info(f"=== ВРЕМЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ {chat_id} (День {current_day}) ===")
    logger.info(f"Утром: {morning_time_to_use.strftime('%H:%M:%S%z')}")
    logger.info(f"Вечером: {evening_time_to_use.strftime('%H:%M:%S%z')}")
    
    # 5. Создаем новые задачи с актуальным временем
    mode = user_data.get("daily_practice_mode", "both")
    logger.info(f"[DEBUG] Режим практики пользователя {chat_id}: {mode}")
    if mode in ["both", "morning_only"]:
        job_queue_instance.run_daily(
            send_daily_practice_job, 
            morning_time_to_use,
            chat_id=chat_id, 
            name=f"{job_name_prefix}_morning", 
            data={"pt": "morning"},
            job_kwargs={'misfire_grace_time': 60}
        )
        logger.info(f"✅ Создана утренняя задача на {morning_time_to_use.strftime('%H:%M:%S%z')}")
        
    if mode in ["dual", "both"]:
        job_queue_instance.run_daily(
            send_daily_practice_job, 
            evening_time_to_use,
            chat_id=chat_id, 
            name=f"{job_name_prefix}_evening", 
            data={"pt": "evening"},
            job_kwargs={'misfire_grace_time': 60}
        )
        logger.info(f"✅ Создана вечерняя задача на {evening_time_to_use.strftime('%H:%M:%S%z')}")
    
    # Проверка успешного создания задач - должны быть видны в планировщике
    final_jobs = job_queue_instance.jobs()
    logger.info(f"[SCHEDULER DEBUG] Итоговое количество задач: {len(final_jobs)}")
    user_jobs = [j for j in final_jobs if j.name and j.name.startswith(job_name_prefix)]
    logger.info(f"[SCHEDULER DEBUG] Создано задач для пользователя {chat_id}: {len(user_jobs)}")
    
    for j in user_jobs:
        logger.info(f"[SCHEDULER DEBUG] Итоговая задача: {j.name}")
    
    return len(user_jobs) > 0 # Возвращаем True если задачи созданы

async def offer_test_if_not_taken(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_data: dict, test_id: str, is_day14: bool = False, test_for_day: int = None):
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
    callback_action_payload = f"{test_id}_day{test_for_day}" if test_for_day is not None else test_id
    callback_action = f"start_test_{callback_action_payload}_forced" if is_day14 else f"offer_test_yes_{callback_action_payload}"

    text = escape_markdown_v2(prompt_text_template.format(test_name=test_info['name']))
    keyboard_rows = [[InlineKeyboardButton(button_text, callback_data=callback_action)]]
    if not is_day14:
        keyboard_rows.append([InlineKeyboardButton(config.TEST_BUTTON_NO_TEXT, callback_data=f"offer_test_no_{test_id}")])
    keyboard_rows.append([InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)])

    await context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN_V2)
    udm.set_user_stage(chat_id, f"day14_forced_test_offered_{test_id}" if is_day14 else f"daily_test_offered_{test_id}")


async def _start_test_logic(query_object_or_message, context: ContextTypes.DEFAULT_TYPE, chat_id: int, test_id: str, user_data: dict, is_forced: bool = False, test_for_day_arg: int = None):
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
    if test_for_day_arg is not None: active_test_payload["test_for_day"] = test_for_day_arg
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
        parts = query.data.rsplit('_', 2); day_acked = int(parts[1]); type_acked = parts[2]
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
        raw_payload = data.replace("start_test_", "")
        is_forced = raw_payload.endswith("_forced")
        main_payload = raw_payload[:-len("_forced")] if is_forced else raw_payload
        parts = main_payload.split("_day")
        test_id = parts[0]
        test_day_for_offer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        await _start_test_logic(query, context, chat_id, test_id, user_data, is_forced=is_forced, test_for_day_arg=test_day_for_offer)
    elif data.startswith("offer_test_yes_"):
        main_payload = data.replace("offer_test_yes_", "")
        parts = main_payload.split("_day")
        test_id = parts[0]
        test_day_for_offer = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        await _start_test_logic(query, context, chat_id, test_id, user_data, test_for_day_arg=test_day_for_offer)
    elif data.startswith("offer_test_no_"):
        udm.set_user_stage(chat_id, f"daily_test_declined_{data.replace('offer_test_no_', '')}")
        await query.edit_message_text(text=escape_markdown_v2(config.TEST_BUTTON_NO_TEXT) + "\n\nПрактики продолжатся\\. 😊", reply_markup=get_main_menu_keyboard(user_data), parse_mode=ParseMode.MARKDOWN_V2)
    elif data.startswith("testans_"):
        data_payload = data[len("testans_"):]; parts = data_payload.rsplit("_", 2)
        logger.info(f"testans_ callback_data: {data}")
        logger.info(f"data_payload: {data_payload}")
        logger.info(f"parts after rsplit: {parts}")
        if len(parts) >= 3:
            ans_idx_str = parts[2]; q_idx_str = parts[1]; test_id_from_cb = "_".join(parts[:-2])
            logger.info(f"ans_idx_str: {ans_idx_str}, q_idx_str: {q_idx_str}, test_id_from_cb: {test_id_from_cb}")
            q_idx = int(q_idx_str); ans_idx = int(ans_idx_str)
            await _handle_test_answer(query, context, chat_id, user_data, test_id_from_cb, q_idx, ans_idx)
        else: logger.error(f"Invalid format for testans: {data_payload}. Parts: {len(parts)}"); await query.edit_message_text("Ошибка ответа(F).")
    elif data.startswith("post_email_consult_yes_"):
        await send_payment_info(update, context)
    elif data.startswith("post_email_consult_no_"):
        udm.set_user_stage(chat_id, f"consult_declined_after_email_{data.replace('post_email_consult_no_', '')}")
        await query.edit_message_text(text=escape_markdown_v2(config.CONSULTATION_DECLINED_TEXT), reply_markup=get_main_menu_keyboard(user_data),parse_mode=ParseMode.MARKDOWN_V2)
    elif data.startswith("post_email_consult_think_"):
        test_id_from_cb = data.replace("post_email_consult_think_", "")
        udm.update_user_data(chat_id, {"stage": f"consult_thinking_day14_{test_id_from_cb}", "daily_practice_mode": "morning_only"})
        user_data = udm.get_user_data(chat_id); _schedule_daily_jobs_for_user(chat_id, context.job_queue, user_data)
        think_text = escape_markdown_v2(config.CONSULTATION_THINK_LATER_TEXT.format(admin_username=config.ADMIN_CONTACT_USERNAME))
        await query.edit_message_text(text=think_text, reply_markup=get_main_menu_keyboard(user_data), parse_mode=ParseMode.MARKDOWN_V2)
    elif data == "offer_consultation":
        await _handle_consultation_request(query, context, chat_id, user_data, test_id=user_data.get("pending_email_test_id"))
        return


async def _send_test_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int, test_data: dict, question_idx: int, test_id_for_callback: str):
    question = test_data["questions"][question_idx]
    text = escape_markdown_v2(question["text"])
    keyboard_rows = []
    for i, option in enumerate(question["options"]):
        option_text = escape_markdown_v2(option["text"]) # Escape option text as well
        keyboard_rows.append([InlineKeyboardButton(option_text, callback_data=f"testans_{test_id_for_callback}_{question_idx}_{i}")])
    keyboard_rows.append([InlineKeyboardButton("📖 В меню", callback_data=MENU_CALLBACK_MAIN)]) # Add menu button
    reply_markup = InlineKeyboardMarkup(keyboard_rows)
    if "image_path" in question:
        try:
            with open(question["image_path"], 'rb') as photo_file:
                await context.bot.send_photo(chat_id, photo_file)
            logger.info(f"Sent image {question['image_path']} for question {question_idx} to chat_id {chat_id}")
        except Exception as e:
            logger.error(f"Error sending image {question['image_path']}: {e}")
    await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

async def _handle_test_answer(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_data: dict, test_id: str, q_idx: int, ans_idx: int):
    logger.info(f"Handling answer for test {test_id}, question {q_idx}, answer index {ans_idx}")
    active_test_data = user_data.get("active_test")
    if not active_test_data or active_test_data.get("id") != test_id or active_test_data.get("current_question_idx") != q_idx:
        await query.edit_message_text("Ошибка состояния теста. Попробуйте из /menu.", reply_markup=get_main_menu_keyboard(user_data)); return

    test_definition = test_engine.get_test_by_id(test_id)
    # Ensure question and option indices are valid
    if q_idx >= len(test_definition["questions"]) or ans_idx >= len(test_definition["questions"][q_idx]["options"]):
        logger.error(f"Invalid q_idx or ans_idx in _handle_test_answer. Test: {test_id}, Q_idx: {q_idx}, Ans_idx: {ans_idx}")
        await query.edit_message_text("Ошибка в данных ответа. Попробуйте снова.", reply_markup=get_main_menu_keyboard(user_data))
        return
    
    # Сохраняем индекс выбранного ответа
    logger.info(f"Saving answer: ans_idx={ans_idx} for question {q_idx} of test {test_id}")
    active_test_data["answers"].append(ans_idx)  # Сохраняем индекс выбранного ответа
    active_test_data["current_question_idx"] += 1
    udm.update_user_data(chat_id, {"active_test": active_test_data})

    original_question_text_escaped = escape_markdown_v2(test_definition["questions"][q_idx]["text"])
    selected_answer_text_escaped = escape_markdown_v2(test_definition["questions"][q_idx]["options"][ans_idx]["text"])
    try:
        await query.edit_message_text(text=f"{original_question_text_escaped}\n\nВы выбрали: *{selected_answer_text_escaped}*", parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e: logger.warning(f"Could not edit message for test answer: {e}")

    total_questions = len(test_definition["questions"])
    if active_test_data["current_question_idx"] < total_questions:
        await _send_test_question(context, chat_id, test_definition, active_test_data["current_question_idx"], test_id)
    else:
        # Тест завершен, вычисляем результат
        if test_id == "gender_selector":
            # Это тест выбора пола, получаем ID следующего теста из score выбранного ответа
            selected_option = test_definition["questions"][0]["options"][ans_idx]
            next_test_id = selected_option["score"]
            logger.info(f"Gender selector completed for user {chat_id}, starting test: {next_test_id}")
            
            # Сбрасываем активный тест и запускаем новый
            udm.update_user_data(chat_id, {"active_test": None})
            
            # Запускаем выбранный тест
            test_for_day = active_test_data.get("test_for_day", user_data.get("current_daily_day", 0))
            await _start_test_logic(query, context, chat_id, next_test_id, user_data, False, test_for_day)
            return
        else:
            # Обычный тест, получаем результат
            score = 0
            for q_idx_in_answers, ans_idx_in_answers in enumerate(active_test_data["answers"]):
                # Получаем определение теста заново, чтобы убедиться в актуальности данных
                current_test_def = test_engine.get_test_by_id(test_id)
                if current_test_def and q_idx_in_answers < len(current_test_def["questions"]) and \
                   ans_idx_in_answers < len(current_test_def["questions"][q_idx_in_answers]["options"]):
                    score += current_test_def["questions"][q_idx_in_answers]["options"][ans_idx_in_answers]["score"]
                else:
                    logger.error(f"Error calculating score: Invalid question or answer index. q_idx_in_answers={q_idx_in_answers}, ans_idx_in_answers={ans_idx_in_answers}")
            logger.info(f"Final score for test {test_id}: {score}")
            # Тест завершен, вычисляем результат
            test_result = test_engine.get_test_result(test_id, score, active_test_data["answers"])
            if not test_result:
                logger.error(f"Failed to get test result for test_id: {test_id}, score: {score}")
                await context.bot.send_message(
                    chat_id,
                    "Произошла ошибка при обработке результатов теста. Пожалуйста, попробуйте позже.",
                    reply_markup=get_main_menu_keyboard(user_data)
                )
                return
                
            # Формируем текст результата
            result_summary = test_result["summary"]
            logger.info(f"Got test result: {result_summary[:100]}...")
            
            # Экранируем спецсимволы для MarkdownV2
            escaped_result_text = escape_markdown_v2(result_summary)
            
            # Отправляем результат пользователю
            try:
                await context.bot.send_message(
                    chat_id,
                    escaped_result_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=get_main_menu_keyboard(user_data)
                )
            except Exception as e:
                logger.error(f"Error sending test result: {e}")
                # Пробуем отправить без форматирования, если возникла ошибка
                await context.bot.send_message(
                    chat_id,
                    "Произошла ошибка при отображении результата теста. Вот ваш результат (без форматирования):\n" + result_summary,  # Оригинальный текст без экранирования
                    reply_markup=get_main_menu_keyboard(user_data)
                )
            
            # Записываем, что тест пройден (один раз)
            udm.record_test_taken(chat_id, test_id, summary=result_summary, answers=active_test_data["answers"])
            
            is_forced_day14_test = active_test_data.get("is_forced_day14", False)
            
            # Обновляем данные пользователя: сбрасываем активный тест, устанавливаем стадию для ввода email,
            # и сохраняем данные, необходимые для отправки email.
            udm.update_user_data(chat_id, {
                "active_test": None, 
                "stage": f"awaiting_email_input_for_{test_id}",
                "pending_email_test_id": test_id, 
                "pending_email_test_score": score,
                "pending_email_test_answers_indices": active_test_data["answers"],
                "pending_email_test_is_forced_day14": is_forced_day14_test
            })

            # Отправляем пользователю запрос на ввод email с кнопкой консультации
            await context.bot.send_message(
                chat_id, 
                escape_markdown_v2(config.EMAIL_REQUEST_TEXT), 
                parse_mode=ParseMode.MARKDOWN_V2
            )

            # Отправляем предложение о консультации после теста
            await send_consultation_offer(context, chat_id)

        # Логика отправки второго видеокружка (обновлено для новых тестов)
        day_test_was_for = active_test_data.get("test_for_day", user_data.get("current_daily_day", 0))
        logger.info(f"[VideoNoteCheck] User {chat_id}, Test ID: {test_id}, Day Test Was For: {day_test_was_for}, Current User Day: {user_data.get('current_daily_day', 0)}, Target Test ID: {config.KEY_TEST_ID}")
        
        # Проверяем, является ли завершенный тест одним из тестов конституции и был ли он предложен в день 3
        constitution_test_ids = ["male_constitution_test", "female_constitution_test", "heroine_type"]  # Включаем старый тест для совместимости
        if test_id in constitution_test_ids and day_test_was_for == 3:
            logger.info(f"[VideoNoteCheck] Conditions MET for user {chat_id} to send 2nd video note.")
            try:
                await context.bot.send_video_note(
                    chat_id=chat_id,
                    video_note="DQACAgIAAxkBAAEBcn1oP05JTiwan2zPQWUoDfcrl4wfKgAC8IkAAsIT8UlCWZjM36ExGjYE"  # ID второго видео
                )
                logger.info(f"Successfully sent 2nd video note (constitution test, day 3) to user {chat_id}")
            except TelegramError as e_video2:
                logger.error(f"TelegramError sending 2nd video note for user {chat_id}: {e_video2}")


async def _handle_consultation_request(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_data: dict, test_id: str):
    test_taken_info = user_data.get("tests_taken", {}).get(test_id)
    if not test_taken_info:
        await query.edit_message_text("Ошибка: Данные о пройденном тесте не найдены.", reply_markup=get_main_menu_keyboard(user_data)); return

    consultation_focus_text = "глубокое понимание себя и своих уникальных особенностей"
    
    if "answers" in test_taken_info and test_taken_info["answers"] is not None:
        try:
            # Используем новый формат для получения результатов
            user_answer_indices = test_taken_info["answers"]  # Уже сохранены как индексы
            test_result = test_engine.get_test_result(test_id, sum(user_answer_indices), user_answer_indices)
            result_text = test_result["summary"]
            
            if not is_next_test:  # Обычный тест, не селектор пола
                result_details = test_engine.get_test_result(test_id, score, user_answer_indices)
                consultation_focus_text = result_details.get("consultation_focus", consultation_focus_text)
        except Exception as e:  
            logger.error(f"Error getting consultation_focus for test {test_id}, user {chat_id}: {e}")

    current_tests_taken = user_data.get("tests_taken", {})
    if test_id in current_tests_taken:
        current_tests_taken[test_id]['consult_interest_shown'] = True
        udm.update_user_data(chat_id, {"tests_taken": current_tests_taken})

    udm.set_user_stage(chat_id, f"consult_5000_requested_{test_id}")

    price_str = f"*{escape_markdown_v2(str(config.CONSULTATION_PRICE_RUB))} рублей*"
    admin_contact_str = f"@{config.ADMIN_CONTACT_USERNAME}"
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
        # Fallback to plain text if MarkdownV2 fails
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
    # Refresh user_data after setting email
    user_data = udm.get_user_data(chat_id)

    test_result_details = test_engine.get_test_result(test_id, score, user_answers_indices)
    full_html_result = test_result_details.get("full_html_result", "<p>Результаты не найдены.</p>")
    test_def_subj = test_engine.get_test_by_id(test_id)
    subj_test_name = test_def_subj['name'] if test_def_subj else "Ваш тест"
    subject = f"Результаты вашего теста «{subj_test_name}»"

    email_sent_successfully = email_sender.send_email(recipient_email=email_text, subject=subject, html_body=full_html_result)
    email_status_key = "success" if email_sent_successfully else "failure"

    # Update tests_taken with email status
    tests_taken_data = user_data.get("tests_taken", {})
    if test_id not in tests_taken_data:
        logger.warning(f"Test {test_id} not found in tests_taken for user {chat_id} when trying to log email status. Creating a minimal entry for email logging.")
        tests_taken_data[test_id] = { 
            "summary": f"Entry for {test_id} created during email status update.",
            "answers": [],
            "date_taken": datetime.datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
            "consult_interest_shown": False
        }
    
    if test_id not in tests_taken_data: 
         tests_taken_data[test_id] = {}

    tests_taken_data[test_id].update({
        "email_recipient": email_text, 
        "email_sent_status": email_status_key
    })

    # Отправляем подтверждение пользователю
    if email_sent_successfully:
        message_to_user = config.EMAIL_SENT_SUCCESS_TEXT.format(user_email=email_text)
    else:
        message_to_user = config.EMAIL_SENT_FAILURE_TEXT.format(user_email=email_text, admin_username=config.ADMIN_CONTACT_USERNAME)
    
    await update.message.reply_text(escape_markdown_v2(message_to_user), parse_mode=ParseMode.MARKDOWN_V2)

    # Admin notification
    escaped_email_md = escape_markdown_v2(email_text) 
    if email_sent_successfully:
        admin_message = f"✅ Успешно отправлены результаты теста «{subj_test_name}» пользователю {chat_id} ({user_obj.username or 'NoUsername'}) на email: {escaped_email_md}."
    else:
        admin_message = f"❌ Ошибка при отправке результатов теста «{subj_test_name}» пользователю {chat_id} ({user_obj.username or 'NoUsername'}) на email: {escaped_email_md}."
    
    if config.ADMIN_NOTIFICATION_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=config.ADMIN_NOTIFICATION_CHAT_ID, text=admin_message, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e_admin_notify:
            logger.error(f"Failed to send admin notification about email status: {e_admin_notify}")

    # Очищаем временное состояние
    udm.update_user_data(chat_id, {
        "tests_taken": tests_taken_data,
        "pending_email_test_id": None,
        "pending_email_test_score": None,
        "pending_email_test_answers_indices": None,
        "pending_email_test_is_forced_day14": False,
        "stage": None
    })

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

    is_day14_context_final = False
    test_taken_entry = user_data.get("tests_taken", {}).get(test_id, {})
    consult_interest_shown = test_taken_entry.get("consult_interest_shown", False)
    
    if is_forced_day14_test_context: is_day14_context_final = True
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
        target_user_data_updated = udm.get_user_data(target_user_id)
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
    day_content_data = daily_content.DAILY_CONTENT.get(day_to_send)
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
                    target_user_data,
                    config.KEY_TEST_ID,
                    is_day14=(day_to_send == 14),
                    test_for_day=day_to_send
                )
    except Exception as e:
        logger.error(f"Error in /forcesend sending: {e}")
        await update.message.reply_text(f"Ошибка отправки: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            user_id_for_menu = update.effective_user.id if update.effective_user else None
            user_data_for_menu = udm.get_user_data(user_id_for_menu) if user_id_for_menu else None
            await update.effective_message.reply_text(
                escape_markdown_v2("Ой, что-то пошло не так... 😥 Попробуйте, пожалуйста, немного позже или вернитесь в /menu."),
                reply_markup=get_main_menu_keyboard(user_data_for_menu),
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e_reply:
            logger.error(f"Exception while sending error message to user: {e_reply}")

async def send_consultation_offer(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Отправляет предложение о консультации с кнопкой."""
    text = "Хотите получить персональную консультацию, чтобы глубже понять себя и свои отношения?"
    keyboard = [
        [InlineKeyboardButton("Да, хочу консультацию", callback_data="post_email_consult_yes_practice")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id, text, reply_markup=reply_markup)
    logger.info(f"Отправлено предложение о консультации пользователю {chat_id}")

async def send_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет пользователю информацию для оплаты консультации."""
    query = update.callback_query
    chat_id = update.effective_chat.id
    
    if query:
        await query.answer()
        try:
            await query.edit_message_text(text=query.message.text + "\n\n*Готовим для вас информацию...*", parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.info(f"Не удалось отредактировать сообщение перед отправкой оплаты: {e}")

    price = config.CONSULTATION_PRICE
    payment_link = config.PAYMENT_LINK
    qr_code_path = config.PAYMENT_QR_CODE_PATH

    text = f"""✨ **Вы на пороге глубоких открытий о себе!**

Персональная консультация — это ваш шанс не просто получить результаты теста, а превратить их в реальные изменения в жизни. Вместе с экспертом вы:

- **Расшифруете** самые тонкие нюансы вашей сексуальной конституции и архетипа.
- **Поймете**, как эти знания влияют на ваши отношения, желания и выбор партнера.
- **Получите персональные рекомендации** и ответы на самые сокровенные вопросы.

Это не просто консультация, это инвестиция в вашу счастливую и гармоничную личную жизнь.

Стоимость: **{price}₽**

Выберите удобный способ оплаты:"""

    keyboard = [
        [InlineKeyboardButton("💳 Оплатить по ссылке (Карта РФ и СНГ)", url=payment_link)],
        [InlineKeyboardButton("✅ Я оплатил(а)", callback_data="payment_confirmed")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        with open(qr_code_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        logger.info(f"Отправлена информация для оплаты с QR-кодом пользователю {chat_id}")
    except FileNotFoundError:
        logger.warning(f"Файл QR-кода не найден по пути: {qr_code_path}. Отправляется текстовая версия.")
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при отправке информации для оплаты пользователю {chat_id}: {e}")

async def payment_confirmed_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие кнопки 'Я оплатил(а)'."""
    query = update.callback_query
    user = update.effective_user
    chat_id = update.effective_chat.id

    await query.answer()

    user_message = "🙏 Спасибо! Мы получили ваше уведомление об оплате. В ближайшее время администратор проверит информацию и свяжется с вами для согласования времени консультации."
    await context.bot.send_message(chat_id, user_message)

    admin_message = f"🔔 Новое уведомление об оплате!\n\nПользователь: @{user.username} (ID: {user.id})\nНажал(а) кнопку '✅ Я оплатил(а)'.\n\nПожалуйста, проверьте поступление средств и свяжитесь с клиентом."
    
    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_message)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об оплате админу {admin_id}: {e}")
    
    logger.info(f"Пользователь {user.id} сообщил об оплате консультации.")


async def main() -> None:
    # Принудительно перезагружаем модуль config, чтобы подхватить последние изменения
    importlib.reload(config)
    logger.info("=== Начало запуска бота ===")
    
    # Логируем текущее время из конфига
    logger.info("=== ВРЕМЯ ИЗ CONFIG.PY ===")
    logger.info(f"Утреннее время: {config.MORNING_PRACTICE_TIME_UTC}")
    logger.info(f"Вечернее время: {config.EVENING_PRACTICE_TIME_UTC}")

    # Создание приложения с увеличенными таймаутами
    logger.info("=== Создание приложения ===")
    application = ApplicationBuilder().token(config.BOT_TOKEN)\
        .connect_timeout(30)\
        .read_timeout(30)\
        .write_timeout(30)\
        .pool_timeout(60)\
        .connection_pool_size(50)\
        .build()
    job_queue = application.job_queue
    
    # ПРИНУДИТЕЛЬНО очищаем ВСЕ задачи планировщика
    logger.info("=== ОЧИСТКА ВСЕХ ЗАДАЧ ===")
    for job in job_queue.jobs():
        job.schedule_removal()
        logger.info(f"Удалена старая задача: {job.name}")

    # Загружаем существующих пользователей и планируем задачи
    logger.info("Loading existing users and scheduling jobs...")
    for user_id, user_data in udm.load_users().items():
        if user_data.get("subscribed_to_daily"):
            logger.info(f"=== ВРЕМЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ {user_id} ===")
            logger.info(f"Утром: {config.MORNING_PRACTICE_TIME_UTC}")
            logger.info(f"Вечером: {config.EVENING_PRACTICE_TIME_UTC}")
            _schedule_daily_jobs_for_user(int(user_id), job_queue, user_data)

    # Обработчики команд
    logger.info("=== Добавление обработчиков команд ===")
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("stopdaily", stopdaily_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("setday", setday_command))
    application.add_handler(CommandHandler("forcesend", forcesend_command))
    application.add_handler(CommandHandler("forcepractice", force_send_practice_command))

    # Обработчик кнопок
    logger.info("=== Добавление обработчика кнопок ===")
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CallbackQueryHandler(payment_confirmed_handler, pattern='^payment_confirmed$'))

    # Обработчик текстовых сообщений
    logger.info("=== Добавление обработчика текстовых сообщений ===")
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_potential_email))

    # Обработчик ошибок
    logger.info("=== Добавление обработчика ошибок ===")
    application.add_error_handler(error_handler)

    # Запуск бота
    logger.info("=== Инициализация и запуск компонентов бота ===")
    application_for_shutdown = application
    try:
        await application_for_shutdown.initialize()
        await application_for_shutdown.start()
        await application_for_shutdown.updater.start_polling(drop_pending_updates=True)
        logger.info(f"=== Бот запущен и слушает обновления. Токен: {config.BOT_TOKEN[:6]}...{config.BOT_TOKEN[-4:]} ===")
        stop_event = asyncio.Event()
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("=== Получен сигнал KeyboardInterrupt/SystemExit, начинаю остановку бота... ===")
    except Exception as e:
        logger.error(f"=== Произошла ошибка в главном цикле работы бота: {str(e)} ===")
        logger.error(f"Подробности ошибки: {traceback.format_exc()}")
    finally:
        logger.info("=== Начало процедуры остановки бота... ===")
        if application_for_shutdown.updater and application_for_shutdown.updater.running:
            logger.info("Остановка Updater...")
            await application_for_shutdown.updater.stop()
            logger.info("Updater остановлен.")
        if application_for_shutdown.running:
            logger.info("Остановка Application...")
            await application_for_shutdown.stop()
            logger.info("Application остановлен.")
        logger.info("Вызов application.shutdown()...")
        await application_for_shutdown.shutdown()
        logger.info("=== Бот полностью остановлен. ===")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())