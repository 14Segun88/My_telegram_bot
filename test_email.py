import asyncio
import logging
import config # Make sure config.py is in the same directory or accessible
from email_sender import send_email

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    recipient = "loftglam@gmail.com"
    subject = "Результаты вашего теста \"Тип героини\" (Тест Mail.ru Headers)"
    html_body = """🎉 **Ваш результат: Сильная половая конституция!**<br><br>Ваша сексуальность стабильна, легко пробуждается и имеет выраженную физиологическую основу. Обычно вам требуется регулярная половая жизнь — 4 и более раз в неделю. Настроение сильно зависит от сексуальной активности. Оргазм достигается легко как в паре, так и при самостоятельной стимуляции. Вы хорошо восстанавливаетесь после секса и способны к повторным актам. Ваше тело быстро отзывается на прикосновения и внимание, а влечение может быть устойчивым даже вне романтических отношений.<br><br>📝 *Ваши ответы:*<br>_1\\. 1. В каком возрасте началось половое созревание:_<br>   Ответ: *а) 8–10 лет*<br>_2\\. 2. Первый оргазм от самостимуляции произошел в возрасте:_<br>   Ответ: *а) До 13 лет*<br>_3\\. 3. Первый оргазм с партнёром после начала регулярной половой жизни произошёл:_<br>   Ответ: *а) В первый месяц половой жизни*<br>_4\\. 4. Волосы в интимной зоне:_<br>   Ответ: *а) Вьющиеся, густые*<br>_5\\. 5. Соотношение длины ног к росту:_<br>   Ответ: *а) Ноги длиннее относительно туловища*<br>_6\\. 6. Развитие вторичных половых признаков:_<br>   Ответ: *а) Слабое развитие*<br>_7\\. 7. Гибкость суставов:_<br>   Ответ: *а) Суставы менее гибкие*<br>"""
    
    # Ensure config has all necessary email attributes
    required_attrs = ['EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD', 'EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_SENDER_NAME']
    missing_attrs = [attr for attr in required_attrs if not hasattr(config, attr) or not getattr(config, attr)]
    
    if missing_attrs:
        logger.error(f"Missing required email configuration attributes in config.py: {', '.join(missing_attrs)}")
        return

    logger.info(f"Attempting to send email to {recipient} with subject '{subject}'")
    logger.info(f"Using sender: {config.EMAIL_SENDER_NAME} <{config.EMAIL_HOST_USER}>")
    
    success = send_email(recipient_email=recipient, subject=subject, html_body=html_body)
    
    if success:
        logger.info("Test email script: Email sent successfully!")
    else:
        logger.error("Test email script: Failed to send email.")

if __name__ == "__main__":
    asyncio.run(main())
