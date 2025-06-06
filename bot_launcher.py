import logging
import sys
import traceback

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

async def run_bot():
    logger.info("=== Запуск бота ===")
    try:
        from bot import main
        await main()
        logger.info("=== Бот запущен успешно ===")
    except Exception as e:
        logger.error(f"=== Критическая ошибка при запуске бота: {str(e)} ===")
        logger.error(f"=== Подробный трейсбэк: ===\n{traceback.format_exc()}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_bot())
