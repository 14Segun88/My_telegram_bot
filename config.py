# config.py
import datetime
import pytz 
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Telegram Bot Token ===
BOT_TOKEN = "7759872103:AAFYDOohOBmIc3XithiuVwpbMA9OB-XD_Yw"  # ВАШ ТОКЕН

# === Admin Configuration ===
ADMIN_USER_IDS = [5965363034] 
ADMIN_NOTIFICATION_CHAT_ID = None  # Отключаем уведомления админу

# === Links ===
MAIN_CHANNEL_LINK = "https://t.me/sexandmind" 
ADMIN_CONTACT_USERNAME = "GoidaSegun" 

# === Daily Content Timing (UTC) ===
# Время практик в UTC (для МСК отнимите 3 часа)
MORNING_PRACTICE_TIME_UTC = datetime.time(hour=3, minute=3, tzinfo=pytz.UTC)  # 06:03 МСК
EVENING_PRACTICE_TIME_UTC = datetime.time(hour=3, minute=4, tzinfo=pytz.UTC)  # 06:04 МСК

# === Test Offering Days ===
TEST_OFFER_DAYS = [3, 5, 7, 9, 11, 13]
KEY_TEST_ID = "heroine_type"

# === Consultation ===
CONSULTATION_PRICE_RUB = 5000

# === Email (SMTP) Configuration ===
EMAIL_SENDER_NAME = "Женская Психология Бот"
EMAIL_HOST_USER = "sexxxandmind@gmail.com"
EMAIL_HOST_PASSWORD = "GalinaTamara2025!"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# === Texts for Bot (Gender Neutral) ===
WELCOME_TEXT = (
    "Привет! 👋 Я твой личный гид в увлекательный мир психологии и сексуальности. 🌺\n\n"
    "Каждый день — новые практики для сияющего настроения, глубокого самопознания и раскрытия твоей невероятной чувственности. ✨\n"
    "А еще — увлекательные тесты, чтобы ты смог(ла) увидеть себя с новой, удивительной стороны! 😉\n\n"
    "Готов(а) к волшебству и ежедневной порции вдохновения?"
)

# Текст главного меню
MENU_TEXT = (
    "📖 *Главное меню*\n\n"
    "Здесь ты можешь запустить ежедневные практики или узнать больше о нашем канале.\n"
    "Выбери, что тебе интересно! ✨"
)

SUBSCRIBE_BUTTON_TEXT = "✨ Запустить подписку на практики"
MAIN_CHANNEL_BUTTON_TEXT = "А что у вас в главном канале? ➡️"

SUBSCRIPTION_SUCCESS_TEXT = (
    "Ура! 🥳 Ты в нашей теплой компании! Подписка на ежедневную магию активирована.\n"
    "Утром и вечером тебя ждут маленькие секреты для большого счастья и гармонии. ☀️🌙\n"
    "Не забывай нажимать кнопочку под практикой, чтобы я знал(а), что ты со мной и всё получается! 👇"
)
SUBSCRIPTION_ALREADY_ACTIVE_TEXT = "Ты уже наш(а) волшебник(ца)! 💫 Продолжай в том же духе, всё идет отлично! 😉"
UNSUBSCRIBE_TEXT = "Жаль расставаться... 😢 Ты отписался(лась) от ежедневной магии. Если передумаешь, я всегда здесь – просто напиши /start и возвращайся! Удачи и света! 🌸"
UNSUBSCRIBE_NOT_SUBSCRIBED_TEXT = "Кажется, ты еще не подписан(а) на ежедневные практики. Хочешь начать? Нажми /start."

TEST_INTRO_TEXT_TEMPLATE = "🔮 Время заглянуть в себя! Хочешь узнать кое-что интересное о своей уникальности с помощью теста «{test_name}»?"
TEST_BUTTON_YES_TEXT = "✨ Да, хочу пройти!"
TEST_BUTTON_NO_TEXT = "Позже, спасибо 🌸"
NO_TESTS_AVAILABLE_TEXT = "Пока доступных тестов нет, но они обязательно появятся! ⏳ Следи за новостями!"
SELECT_TEST_TEXT = "Выбери тест, который раскроет твои новые грани:"

EMAIL_REQUEST_TEXT = "🎉 Супер! Тест пройден! 💌\nЧтобы получить ПОЛНУЮ расшифровку с сочными деталями прямо на почту, просто напиши свой email ниже 👇"
EMAIL_INVALID_TEXT = "Ой, кажется, это не совсем похоже на email... 🙈 Попробуешь еще разок, пожалуйста? 😊"

CONSULTATION_OFFER_BUTTON_YES_TEXT = f"Да, хочу консультацию ({CONSULTATION_PRICE_RUB}₽) 💖"
CONSULTATION_OFFER_BUTTON_NO_TEXT = "Спасибо, не сейчас 🙏"
CONSULTATION_OFFER_BUTTON_THINK_LATER_TEXT = "Мне нужно подумать... 🤔"

CONSULTATION_DECLINED_TEXT = "Понимаю тебя! 🥰 Если что-то изменится или появятся вопросики – я тут! Продолжай наслаждаться практиками! 💖"
CONSULTATION_THINK_LATER_TEXT = (
    "Конечно, время подумать – это важно! 🧘‍♀️\n"
    "Я буду рядом и продолжу присылать тебе утренние лучики вдохновения. ☀️\n"
    "Если решишься на глубокое погружение с консультацией, просто напиши нашему администратору @{admin_username}. Она всё подскажет! 😉"
)
DAY14_FORCED_TEST_PROMPT_TEXT = (
    "🌷 Две недели волшебства пролетели незаметно! Надеюсь, эти дни наполнили тебя светом и теплом. ✨\n"
    "Чтобы наше путешествие стало еще глубже, предлагаю тебе особенный тест «{test_name}». Даже если ты его уже проходил(а), сейчас он может раскрыться по-новому! "
    "Его результаты – это ключик к самому важному для твоего сияния. 🗝️💖"
)
DAY14_FORCED_TEST_BUTTON_TEXT = "✨ Пройти тест сейчас!"