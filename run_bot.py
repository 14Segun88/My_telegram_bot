import asyncio
import logging
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("=== Запуск бота ===")
        import bot
        logger.info("=== Импортирован модуль bot ===")
        await bot.main()
        logger.info("=== Бот запущен успешно ===")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)

if __name__ == '__main__':
    asyncio.run(main())
