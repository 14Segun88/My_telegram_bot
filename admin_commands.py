# admin_commands.py
import logging
from datetime import date, timedelta, time, timezone # Добавили time, timezone
from telegram import Update
from telegram.ext import ContextTypes # Application НЕ импортируем здесь, используем context.application

import user_data_manager as udm
from config import ADMIN_USER_IDS, MORNING_CONTENT_SEND_HOUR_UTC, MORNING_CONTENT_SEND_MINUTE_UTC, \
                   EVENING_CONTENT_SEND_HOUR_UTC, EVENING_CONTENT_SEND_MINUTE_UTC # Импортируем время
import daily_content

# Импортируем функции для планирования из bot.py.
# ВНИМАНИЕ: Это может создать циклический импорт, если bot.py также импортирует admin_commands.
# Если это проблема, эти функции нужно вынести в отдельный утилитный модуль.
# НО! Мы будем вызывать методы job_queue напрямую, копируя логику, чтобы избежать импорта bot.
# from bot import _remove_user_jobs as bot_remove_user_jobs # НЕ ИСПОЛЬЗУЕМ ЭТОТ ПОДХОД
# from bot import send_morning_content_job, send_evening_content_job # НЕ ИСПОЛЬЗУЕМ ЭТОТ ПОДХОД

logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS

async def get_my_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(f"Твой User ID: {user_id}")

async def _admin_remove_user_jobs(job_queue, user_id: int):
    """ Локальная копия _remove_user_jobs для использования в admin_commands. """
    jobs_to_remove = []
    job_name_patterns = [
        f"morning_content_{user_id}", f"evening_content_{user_id}",
        f"ext_morning_content_{user_id}", f"ext_evening_content_{user_id}",
        f"daily_practice_{user_id}"
    ]
    for pattern_base in job_name_patterns:
        jobs_to_remove.extend(job_queue.get_jobs_by_name(pattern_base))
            
    if jobs_to_remove:
        removed_job_names = [j.name for j in jobs_to_remove]
        for job in jobs_to_remove: job.schedule_removal()
        logger.info(f"[Admin SetDay] Removed existing jobs for user {user_id}: {removed_job_names}")
        return True
    return False

async def _admin_schedule_daily_jobs_for_user(job_queue, user_id: int, is_extended: bool, 
                                         send_morning_func, send_evening_func): # Передаем функции для джобов
    """ Локальная копия schedule_daily_jobs_for_user. """
    await _admin_remove_user_jobs(job_queue, user_id) # Сначала удаляем старые
    
    user_data = udm.get_user(user_id) # Получаем актуальные данные
    if not (user_data and user_data.get("subscribed_to_daily")):
        logger.info(f"[Admin SetDay] User {user_id} not subscribed, no jobs scheduled by admin.")
        return

    if is_extended and not user_data.get("extended_daily_active"):
        logger.info(f"[Admin SetDay] User {user_id} not set for extended daily, jobs not scheduled by admin.")
        return
    if not is_extended and user_data.get("extended_daily_active"): # Если активен доп. цикл, не создаем основные
        logger.info(f"[Admin SetDay] User {user_id} is on extended daily cycle, main cycle jobs not scheduled by admin.")
        return

    m_time = time(hour=MORNING_CONTENT_SEND_HOUR_UTC, minute=MORNING_CONTENT_SEND_MINUTE_UTC, tzinfo=timezone.utc)
    e_time = time(hour=EVENING_CONTENT_SEND_HOUR_UTC, minute=EVENING_CONTENT_SEND_MINUTE_UTC, tzinfo=timezone.utc)
    
    job_prefix = "ext_" if is_extended else ""
    job_morning_name = f"{job_prefix}morning_content_{user_id}"
    job_evening_name = f"{job_prefix}evening_content_{user_id}"

    job_queue.run_daily(send_morning_func, time=m_time, chat_id=user_id, name=job_morning_name)
    logger.info(f"[Admin SetDay] Scheduled {'extended ' if is_extended else ''}morning job for user {user_id} (job: {job_morning_name}).")
    
    job_queue.run_daily(send_evening_func, time=e_time, chat_id=user_id, name=job_evening_name)
    logger.info(f"[Admin SetDay] Scheduled {'extended ' if is_extended else ''}evening job for user {user_id} (job: {job_evening_name}).")


async def set_user_day_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    args = context.args
    if not (2 <= len(args) <= 3):
        await update.message.reply_text(
            "Используйте: /setday <ID_пользователя> <Номер_следующего_дня> [true/false для доп.цикла (опц.)]"
        )
        return

    try:
        target_user_id = int(args[0])
        day_to_receive_next = int(args[1])
        is_extended_str = args[2].lower() if len(args) == 3 else "false"
        is_extended = (is_extended_str == "true")
    except ValueError:
        await update.message.reply_text("ID пользователя и номер дня должны быть числами.")
        return

    user_data = udm.get_user(target_user_id)
    if not user_data:
        user_data = udm.create_or_update_user(target_user_id, target_user_id) 
        if not user_data:
             await update.message.reply_text(f"Не удалось найти или создать пользователя с ID {target_user_id}.")
             return
        await update.message.reply_text(f"Пользователь ID {target_user_id} не был найден, создан новый. Устанавливаем день...")

    max_days = daily_content.TOTAL_EXTENDED_CONTENT_DAYS if is_extended else daily_content.TOTAL_CONTENT_DAYS_NEW
    if max_days == 0 and is_extended:
        await update.message.reply_text("Дополнительный контент не настроен. Не могу установить день.")
        return
    if not (1 <= day_to_receive_next <= max_days): 
        await update.message.reply_text(f"Номер дня должен быть от 1 до {max_days} для выбранного цикла.")
        return

    current_day_to_set = day_to_receive_next - 1
    yesterday_iso = (date.today() - timedelta(days=1)).isoformat()

    udm.update_user_field(target_user_id, "subscribed_to_daily", True)

    if is_extended:
        udm.update_user_field(target_user_id, "extended_daily_active", True)
        udm.update_user_field(target_user_id, "current_extended_daily_day", current_day_to_set)
        udm.update_user_field(target_user_id, "last_extended_morning_sent_date", yesterday_iso)
        udm.update_user_field(target_user_id, "current_daily_day", daily_content.TOTAL_CONTENT_DAYS_NEW) 
        udm.update_user_field(target_user_id, "last_morning_sent_date", yesterday_iso)
        cycle_type_msg = "дополнительного"
    else:
        udm.update_user_field(target_user_id, "extended_daily_active", False)
        udm.update_user_field(target_user_id, "current_daily_day", current_day_to_set)
        udm.update_user_field(target_user_id, "last_morning_sent_date", yesterday_iso)
        udm.update_user_field(target_user_id, "current_extended_daily_day", 0)
        udm.update_user_field(target_user_id, "last_extended_morning_sent_date", None)
        cycle_type_msg = "основного"

    reply_msg = (
        f"Для пользователя ID {target_user_id} установлен день {day_to_receive_next} {cycle_type_msg} цикла как СЛЕДУЮЩИЙ.\n"
        f"current_..._day: {current_day_to_set}, last_sent_date: вчера.\n"
    )
    
    job_q = context.application.job_queue
    if job_q:
        # Нам нужны реальные функции send_morning_content_job и send_evening_content_job из bot.py
        # Это самый сложный момент для избежания циркулярного импорта.
        # ПРОСТОЙ ВАРИАНТ: Не перепланировывать из админки, а требовать /start от пользователя или перезапуска бота.
        # БОЛЕЕ СЛОЖНЫЙ, НО ЛУЧШИЙ: Вынести job-функции и планировщик в отдельный модуль.

        # ПОКА ОСТАВИМ ПРОСТОЙ ВАРИАНТ, чтобы не ломать структуру сильно:
        reply_msg += "ВАЖНО: Чтобы изменения в расписании вступили в силу, попросите пользователя (ID: {target_user_id}) нажать /start или перезапустите бота."
        logger.info(f"Admin {admin_id} set day for user {target_user_id}. User /start or bot restart needed.")
        # Если бы мы могли импортировать:
        # from bot import send_morning_content_job, send_evening_content_job # ПРИВЕДЕТ К ЦИКЛ. ИМПОРТУ
        # await _admin_schedule_daily_jobs_for_user(job_q, target_user_id, is_extended, send_morning_content_job, send_evening_content_job)
        # reply_msg += "Задачи для пользователя были перепланированы."
        # logger.info(f"Admin {admin_id} set day for user {target_user_id} and rescheduled jobs via admin command.")
    else:
        reply_msg += "Не удалось получить доступ к JobQueue для немедленного перепланирования."
        logger.warning(f"Admin {admin_id} set day for user {target_user_id}, but JobQueue not found in context.")
        
    await update.message.reply_text(reply_msg)


async def force_send_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (код force_send_daily_command остается таким же, как в моем предыдущем ответе)
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        await update.message.reply_text("Эта команда доступна только администратору.")
        return

    args = context.args
    if len(args) != 2: 
        await update.message.reply_text("Используйте: /forcesend <ID_пользователя> <Номер_дня_практики_основного_цикла>")
        return

    try:
        target_user_id = int(args[0])
        day_to_send = int(args[1])
    except ValueError:
        await update.message.reply_text("ID пользователя и номер дня должны быть числами.")
        return

    if not (1 <= day_to_send <= daily_content.TOTAL_CONTENT_DAYS_NEW):
        await update.message.reply_text(f"Номер дня для основного цикла должен быть от 1 до {daily_content.TOTAL_CONTENT_DAYS_NEW}.")
        return

    user_data = udm.get_user(target_user_id)
    if not user_data:
        await update.message.reply_text(f"Пользователь с ID {target_user_id} не найден.")
        return
    
    sent_something = False
    from telegram.constants import ParseMode 

    morning_text = daily_content.get_morning_content_for_day(day_to_send)
    if morning_text and not ("Контент для этого" in morning_text and "не найден" in morning_text):
        full_morning_text = f"☀️ <b>[ТЕСТ АДМИНА] Утренняя практика (День {day_to_send}/{daily_content.TOTAL_CONTENT_DAYS_NEW})</b>\n\n{morning_text}"
        try:
            await context.bot.send_message(chat_id=target_user_id, text=full_morning_text, parse_mode=ParseMode.HTML)
            sent_something = True
        except Exception as e: 
            logger.error(f"Admin force send morning error to {target_user_id}: {e}")
            await update.message.reply_text(f"Ошибка при отправке утреннего контента: {e}")
    elif not morning_text or ("Контент для этого" in morning_text and "не найден" in morning_text):
         await update.message.reply_text(f"Утренний контент для дня {day_to_send} отсутствует или не заполнен.")

    evening_text = daily_content.get_evening_content_for_day(day_to_send)
    if evening_text and not ("Контент для этого" in evening_text and "не найден" in evening_text):
        full_evening_text = f"🌙 <b>[ТЕСТ АДМИНА] Вечерняя практика (День {day_to_send}/{daily_content.TOTAL_CONTENT_DAYS_NEW})</b>\n\n{evening_text}"
        try:
            await context.bot.send_message(chat_id=target_user_id, text=full_evening_text, parse_mode=ParseMode.HTML)
            sent_something = True
        except Exception as e: 
            logger.error(f"Admin force send evening error to {target_user_id}: {e}")
            await update.message.reply_text(f"Ошибка при отправке вечернего контента: {e}")
    elif not evening_text or ("Контент для этого" in evening_text and "не найден" in evening_text):
        await update.message.reply_text(f"Вечерний контент для дня {day_to_send} отсутствует или не заполнен.")

    if sent_something:
        await update.message.reply_text(f"Принудительно отправлен контент основного цикла для дня {day_to_send} пользователю {target_user_id}.")