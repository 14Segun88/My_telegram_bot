#!/usr/bin/env python3
# Скрипт для просмотра активных задач в планировщике

import logging
import datetime
import pytz
from telegram.ext import Application, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

from config import BOT_TOKEN

async def print_jobs(context):
    """Выводит список всех задач и их следующих запланированных выполнений"""
    jobs = context.job_queue.jobs()
    now = datetime.datetime.now(pytz.UTC)
    
    logger.info(f"=== ТЕКУЩЕЕ ВРЕМЯ: {now} ===")
    logger.info(f"Всего задач: {len(jobs)}")
    
    if not jobs:
        logger.info("Нет активных задач!")
        return
    
    for job in jobs:
        next_run = job.next_t
        time_left = (next_run - now).total_seconds() if next_run else "N/A"
        
        logger.info(f"Задача: {job.name}")
        logger.info(f"  Следующий запуск: {next_run}")
        logger.info(f"  Осталось времени: {time_left} секунд")
        logger.info(f"  Данные задачи: {job.data}")
        logger.info(f"  Интервал: {job.interval}")
        logger.info(f"  Активные дни: {getattr(job, 'days', 'ежедневно')}")
        logger.info("---")

async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Ждем инициализации планировщика
    await application.initialize()
    await application.start()
    
    # Запрашиваем информацию о задачах
    logger.info("Запрос информации о запланированных задачах...")
    await print_jobs(application)
    
    # Останавливаем приложение
    await application.stop()
    await application.shutdown()
    
    logger.info("Завершено!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
