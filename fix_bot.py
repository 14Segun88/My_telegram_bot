import requests

TOKEN = "7759872103:AAFYDOohOBmIc3XithiuVwpbMA9OB-XD_Yw"  # Замените на реальный токен

# Удалить webhook
response = requests.post(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook")
print("Webhook удален:", response.json())

# Проверить статус
response = requests.get(f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo")
print("Статус webhook:", response.json())