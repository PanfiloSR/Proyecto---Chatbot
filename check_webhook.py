# check_webhook.py
import requests
from config import TELEGRAM_TOKEN

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo"
response = requests.get(url)
print("Webhook info:")
print(response.json())