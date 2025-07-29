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
# Channel ID (use @username_to_id_bot to get it if needed)
MAIN_CHANNEL_ID = "@sexandmind"  # This might need to be the numeric ID if @ prefix doesn't work
ADMIN_CONTACT_USERNAME = "GoidaSegun" 

# === Daily Content Timing (UTC) ===
# Время отправки утренней практики (UTC) - 09:00 MSK (06:00 UTC)
MORNING_PRACTICE_TIME_UTC = datetime.time(hour=6, minute=0, tzinfo=pytz.UTC)
# Время отправки вечерней практики (UTC) - 18:00 MSK (15:00 UTC)
EVENING_PRACTICE_TIME_UTC = datetime.time(hour=15, minute=0, tzinfo=pytz.UTC)

# === Day 3 test offer times (in UTC as string) ===
DAY3_KEY_TEST_OFFER_MORNING_UTC = datetime.time(hour=6, minute=0, tzinfo=pytz.UTC)  # 09:00 MSK
DAY3_KEY_TEST_OFFER_EVENING_UTC = datetime.time(hour=15, minute=0, tzinfo=pytz.UTC)  # 18:00 MSK

# === Test Offering Days ===
TEST_OFFER_DAYS = [3, 5, 7, 9, 11, 13]
KEY_TEST_ID = "gender_selector"

# === Consultation Payment ===
CONSULTATION_PRICE = 5000  # Цена в рублях
PAYMENT_LINK = "https://www.tinkoff.ru/rm/r_YlujHwdHxX.WmqISDwRzN/a5XDV14317"
PAYMENT_QR_CODE_PATH = "payment_qr.png"

# === Other Settings ===
ONBOARDING_VIDEO_NOTE_FILE_ID = "DQACAgIAAxkBAAIJ_GZgB2Pz82u9v0gWBb0s4u8yBAwvAAJgPQAC9GZBSAMj3YJp6qGYNQQ"
ONBOARDING_VIDEO_DURATION_SECONDS = 55

# === Email (SMTP) Configuration ===
EMAIL_SENDER_NAME = "Команда Sexandmind"
EMAIL_HOST_USER = "sexandmind@bk.ru"
EMAIL_HOST_PASSWORD = "62kWyXCWa63990nfzJAC"  # Пароль приложения для sexandmind@bk.ru
EMAIL_HOST = "smtp.mail.ru"  # SMTP для Mail.ru Group (включая bk.ru)
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# === Texts for Bot (Gender Neutral) ===
WELCOME_TEXT = (
    "Привет! \n"
    "С тобой Тамара и Галина.\n\n"
    "Мы здесь, чтобы поддерживать тебя на пути изменений🔝\n"
    "Ты будешь получать небольшие задания каждый день💬\n"
    "Они помогут тебе обрести уверенность, \n"
    "раскрыть свою сексуальность и двигаться на встречу к мечтам.\n"
    "Ты обретешь интерес к себе, телу и близости.\n\n"
    "В нашем боте тебя ждут тесты, которые помогут лучше узнать себя.\n\n"
    "Так же ты всегда будешь заранее узнавать о наших онлайн встречах, \n"
    "где мы в прямом эфире будем отвечать на вопросы 📢"
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
    "Ты активировал мотивационного помощника 🤖\n"
    "Мы знаем, что работать над собой порой бывает сложно 😣\n"
    "Поэтому мы здесь, чтобы напоминать о маленьких и простых ежедневных шагах 📍\n"
    "Так небольшими действия можно будет придти к своим большим результатам🎯 \n"
    "Ежедневно ты будешь получать утренние практики для работы с мышлением 🧠 и чтобы зарядиться бодростью на целый день,\n"
    "а во второй половине дня практики для погружения в телесность и сексуальность ✨\n"
    "Чтобы не пропускать сообщения с практиками, закрепи бота 📌 и включи уведомления со звуком 🔊\n\n"
    "Здесь еще кнопка для включения уведомлений (звук и напоминание) и кнопка закрепить бот наверху списка сообщений:"
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

EMAIL_SENT_SUCCESS_TEXT = "💌 Отлично! Подробные результаты теста уже летят на твою почту {user_email}. Проверяй входящие (и папку 'Спам', на всякий случай 😉)!"
EMAIL_SENT_FAILURE_TEXT = "Ой, что-то пошло не так при отправке письма на {user_email}... 😥 Пожалуйста, попробуй еще раз чуть позже или свяжись с администратором @{admin_username}, если проблема повторится."

CONSULTATION_OFFER_BUTTON_YES_TEXT = f"Да, хочу консультацию ({CONSULTATION_PRICE}₽) 💖"
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