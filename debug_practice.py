#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
from telegram.ext import Application, CallbackContext, ContextTypes
import bot
import user_data_manager as udm
import config
import daily_content

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def manual_send_practice(user_id, practice_type):
    logger.info(f"====== MANUALLY SENDING {practice_type} PRACTICE TO USER {user_id} ======")
    
    # Инициализация бота
    token = config.BOT_TOKEN
    application = Application.builder().token(token).build()
    
    # Получение данных пользователя
    user_data = udm.get_user_data(user_id)
    if not user_data:
        logger.error(f"User {user_id} not found in database")
        return
    
    # Вывод текущего состояния пользователя
    current_day = user_data.get("current_daily_day", 1)
    logger.info(f"User {user_id} is on day {current_day}")
    logger.info(f"Last morning sent date: {user_data.get('last_morning_sent_date')}")
    logger.info(f"Last evening sent date: {user_data.get('last_evening_sent_date')}")
    
    # Проверка содержимого практик для текущего дня
    day_content = daily_content.DAILY_CONTENT.get(current_day)
    if not day_content:
        logger.error(f"No content found for day {current_day}")
        return
    
    practice_data = day_content.get(practice_type)
    if not practice_data:
        logger.error(f"No {practice_type} practice content for day {current_day}")
        return
    
    logger.info(f"Practice content found for day {current_day}, type {practice_type}")
    logger.info(f"Practice text: {practice_data['text'][:50]}...")
    
    # Создание контекста для отправки сообщения
    context = ContextTypes.DEFAULT_TYPE(application=application, user_data={}, chat_data={}, bot_data={})
    context._bot = application.bot
    
    # Создание фиктивного job объекта
    class MockJob:
        def __init__(self, job_name, job_data):
            self.name = job_name
            self.data = job_data
    
    mock_job = MockJob(f"{user_id}_{practice_type}", {"pt": practice_type})
    context._job = mock_job
    
    # Вызов функции отправки практик
    try:
        await bot.send_daily_practice_job(context)
        logger.info("Practice sending function completed successfully")
    except Exception as e:
        logger.error(f"Error sending practice: {e}", exc_info=True)

async def main():
    user_id = 5965363034  # ID пользователя для теста
    practice_type = "morning"  # тип практики (morning/evening)
    
    await manual_send_practice(user_id, practice_type)

if __name__ == "__main__":
    asyncio.run(main())
