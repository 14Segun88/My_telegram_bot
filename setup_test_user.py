#!/usr/bin/env python3
# setup_test_user.py - Скрипт для установки определенного дня тестовому пользователю

import user_data_manager as udm
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main(day_to_set):
    """
    Основная функция для установки дня тестовому пользователю.
    """
    test_chat_id = 5965363034  # ID пользователя GoidaSegun

    logger.info(f"Попытка установить день {day_to_set} для пользователя с ID: {test_chat_id}")

    all_users = udm.load_users()

    if test_chat_id in all_users:
        user = all_users[test_chat_id]
        user['current_daily_day'] = day_to_set
        user['last_morning_sent_date'] = None
        user['last_evening_sent_date'] = None

        # Очищаем активный тест, чтобы избежать конфликтов состояния
        if 'active_test' in user:
            user['active_test'] = None
        user['awaiting_email_for_test_id'] = None
        user['subscribed_to_daily'] = True
        stage_val = user.get("stage") or ""
        if isinstance(stage_val, str) and stage_val.startswith("awaiting_email_input_for_"):
            user['stage'] = 'main_menu'  # Сбрасываем этап ожидания email

        udm.save_users(all_users)
        logger.info(f"Пользователю {test_chat_id} успешно установлен день {day_to_set} и сброшены даты последних практик.")
    else:
        logger.warning(f"Пользователь {test_chat_id} не найден. Создайте его, отправив /start боту.")

if __name__ == "__main__":
    day = 3 # Устанавливаем третий день
    logger.info(f"=== Запуск скрипта для установки дня {day} тестовому пользователю ===")
    main(day)
    logger.info("=== Скрипт завершил работу. ===")
