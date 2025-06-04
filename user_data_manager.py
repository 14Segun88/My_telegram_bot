# user_data_manager.py
import json
import os
import datetime
import logging

USERS_FILE = "users.json"
logger = logging.getLogger(__name__)

# --- User Data Structure (commented out for brevity, assume it's known) ---
# chat_id: int
# username: str | None
# ... (all other fields)

def load_users():
    if not os.path.exists(USERS_FILE):
        logger.info(f"{USERS_FILE} not found. Creating and initializing with {{}}.")
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        return {}
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                logger.warning(f"{USERS_FILE} is empty. Initializing with {{}}.")
                with open(USERS_FILE, 'w', encoding='utf-8') as fw:
                    json.dump({}, fw)
                return {}
            data = json.loads(content)
            return {int(k): v for k, v in data.items()}
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading users from {USERS_FILE}: {e}. Attempting to reset.")
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f_reset:
                json.dump({}, f_reset)
            logger.info(f"{USERS_FILE} has been reset to {{}}.")
            return {}
        except Exception as reset_e:
            logger.error(f"Failed to reset {USERS_FILE}: {reset_e}")
            return {} # Fallback to empty if reset fails

def save_users(users_data):
    try:
        data_to_save = {str(k): v for k, v in users_data.items()}
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        logger.debug(f"Users data saved to {USERS_FILE}")
    except IOError as e:
        logger.error(f"IOError saving users to {USERS_FILE}: {e}")
    except Exception as e_gen:
        logger.error(f"Generic error saving users to {USERS_FILE}: {e_gen}")

def get_user_data(chat_id: int):
    users = load_users()
    return users.get(chat_id)

def create_or_update_user(chat_id: int, username: str = None, first_name: str = None, initial_stage: str = "greeted"):
    users = load_users()
    user_data = users.get(chat_id)
    
    current_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if user_data is None:
        user_data = {
            "chat_id": chat_id,
            "username": username,
            "first_name": first_name,
            "subscribed_to_daily": False,
            "daily_practice_mode": "none",
            "current_daily_day": 0,
            "last_morning_sent_date": None,
            "last_evening_sent_date": None,
            "stage": initial_stage,
            "email": None,
            "active_test": None,
            "tests_taken": {},
            "created_at": current_time_iso,
            "last_interaction_date": current_time_iso
        }
        logger.info(f"New user created: {chat_id} ({username or 'NoUsername'})")
    else:
        if username is not None: # Allow updating username, even to None if user removes it
            user_data["username"] = username
        if first_name: # Only update if a new first_name is provided
            user_data["first_name"] = first_name
        user_data["last_interaction_date"] = current_time_iso
        # Don't reset stage if user already exists, unless specified by initial_stage and different from default
        if initial_stage != "greeted" or "stage" not in user_data:
            user_data["stage"] = initial_stage
        # Ensure essential keys exist if loading an old user_data structure
        for key, default_value in [
            ("subscribed_to_daily", False), ("daily_practice_mode", "none"),
            ("current_daily_day", 0), ("active_test", None), ("tests_taken", {})
        ]:
            if key not in user_data:
                user_data[key] = default_value


    users[chat_id] = user_data
    save_users(users)
    return user_data

def update_user_data(chat_id: int, new_data_dict: dict):
    users = load_users()
    user = users.get(chat_id)
    if user:
        for key, value in new_data_dict.items():
            user[key] = value
        user["last_interaction_date"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        users[chat_id] = user
        save_users(users)
        logger.debug(f"User data updated for {chat_id}: {new_data_dict}")
        return True
    logger.warning(f"Attempted to update non-existent user: {chat_id}")
    return False

def set_user_subscribed(chat_id: int, subscribed_status: bool = True):
    mode = "dual" if subscribed_status else "none"
    # При подписке начинаем с дня 1, при отписке current_daily_day можно не менять или сбросить в 0
    current_day_on_sub = 1 if subscribed_status else get_user_data(chat_id).get("current_daily_day", 0)

    return update_user_data(chat_id, {
        "subscribed_to_daily": subscribed_status,
        "daily_practice_mode": mode,
        "current_daily_day": current_day_on_sub, 
        "stage": "daily_subscribed" if subscribed_status else "unsubscribed_daily", # или более конкретный stage
        "last_morning_sent_date": None, # Сброс при новой подписке
        "last_evening_sent_date": None  # Сброс при новой подписке
    })

def set_user_stage(chat_id: int, stage: str):
    return update_user_data(chat_id, {"stage": stage})

def set_user_email(chat_id: int, email: str):
    return update_user_data(chat_id, {"email": email})

def increment_user_daily_day(chat_id: int, total_days: int):
    user = get_user_data(chat_id)
    if user:
        current_day = user.get("current_daily_day", 0)
        next_day = current_day + 1
        if next_day > total_days:
            next_day = 1 # Зацикливание
            logger.info(f"User {chat_id} completed {total_days} day cycle, looping to day 1.")
        return update_user_data(chat_id, {"current_daily_day": next_day})
    return False

def record_test_taken(chat_id: int, test_id: str, summary: str, answers: list, email_recipient: str = None, email_sent_status: str = None):
    user = get_user_data(chat_id)
    if user:
        if "tests_taken" not in user or user["tests_taken"] is None:
            user["tests_taken"] = {}
        
        user["tests_taken"][test_id] = {
            "summary": summary,
            "answers": answers,
            "date_taken": datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
            "email_recipient": email_recipient,
            "email_sent_status": email_sent_status,
            "consult_interest_shown": False # Инициализируем по умолчанию
        }
        # Сбрасываем активный тест после записи
        return update_user_data(chat_id, {"tests_taken": user["tests_taken"], "active_test": None})
    return False

def get_subscribed_users():
    users = load_users()
    return [
        data for data in users.values() 
        if data.get("subscribed_to_daily") and data.get("daily_practice_mode") in ["dual", "morning_only"]
    ]

def update_last_sent_date(chat_id: int, practice_type: str):
    """practice_type: "morning" or "evening" """
    today_str = datetime.date.today().isoformat()
    if practice_type == "morning":
        return update_user_data(chat_id, {"last_morning_sent_date": today_str})
    elif practice_type == "evening":
        return update_user_data(chat_id, {"last_evening_sent_date": today_str})
    return False