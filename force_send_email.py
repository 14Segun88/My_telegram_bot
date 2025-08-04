import user_data_manager as udm
import test_engine
import email_sender
import config
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

USER_ID_TO_FIX = 5965363034  # ID пользователя для исправления

def force_resend_last_test_email():
    """Принудительно переотправляет email с результатами последнего теста."""
    logger.info(f"--- Запуск принудительной отправки email для пользователя {USER_ID_TO_FIX} ---")
    
    user_data = udm.get_user_data(USER_ID_TO_FIX)
    
    if not user_data:
        logger.error(f"Пользователь с ID {USER_ID_TO_FIX} не найден.")
        return

    # Получаем данные, сохраненные для отправки email
    test_id = user_data.get("pending_email_test_id")
    score = user_data.get("pending_email_test_score")
    user_answers_indices = user_data.get("pending_email_test_answers_indices")
    email_address = user_data.get("email")

    if not all([test_id, score is not None, user_answers_indices, email_address]):
        logger.error(f"Недостаточно данных для отправки email. test_id: {test_id}, score: {score}, email: {email_address}")
        return

    logger.info(f"Найдены данные для теста '{test_id}' (счет: {score}), email: {email_address}")

    # 1. Получаем полные результаты теста (уже с исправленной логикой)
    test_result_data = test_engine.get_test_result(test_id, score, user_answers_indices)
    if not test_result_data:
        logger.error("Не удалось сгенерировать данные результатов теста.")
        return

    full_html_result = test_result_data.get('full_html_result')
    if not full_html_result:
        logger.error("HTML-версия результата не найдена в данных теста.")
        return

    # 2. Формируем тему письма
    test_def = test_engine.get_test_by_id(test_id)
    test_name = test_def['name'] if test_def else "Ваш тест"
    subject = f"Результаты вашего теста «{test_name}» (повторная отправка)"

    # 3. Отправляем email
    logger.info(f"Попытка отправить email на адрес {email_address}...")
    success = email_sender.send_email(
        recipient_email=email_address,
        subject=subject,
        html_body=full_html_result
    )

    if success:
        logger.info(f"✅ Email успешно отправлен на {email_address}.")
    else:
        logger.error(f"❌ Не удалось отправить email.")

if __name__ == "__main__":
    force_resend_last_test_email()
