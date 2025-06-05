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

try:
    logger.info("=== Запуск бота ===")
    import bot
    logger.info("=== Импортирован модуль bot ===")
    bot.main()
    logger.info("=== Бот запущен успешно ===")
except Exception as e:
    logger.error(f"=== Критическая ошибка при запуске бота: {str(e)} ===")
    raise
