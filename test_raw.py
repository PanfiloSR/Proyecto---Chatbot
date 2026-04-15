# test_raw.py
import requests
import time
from config import TELEGRAM_TOKEN

TOKEN = TELEGRAM_TOKEN
BASE = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = 0

print("🔍 Monitoreo CRUDO - Muestra TODO lo que Telegram envía")
print("="*60)

# Primero, enviar un mensaje con botones a tu chat
def send_test_menu():
    # Obtener tu chat_id del último mensaje
    resp = requests.get(f"{BASE}/getUpdates", params={"limit": 1})
    if resp.status_code == 200:
        data = resp.json()
        if data.get("result"):
            chat_id = data["result"][0]["message"]["chat"]["id"]
            keyboard = {
                "inline_keyboard": [
                    [{"text": "TEST", "callback_data": "test"}]
                ]
            }
            requests.post(f"{BASE}/sendMessage", json={
                "chat_id": chat_id,
                "text": "MENÚ DE PRUEBA - Haz clic en el botón",
                "reply_markup": keyboard
            })
            print(f"✅ Menú enviado a chat_id: {chat_id}")
            return chat_id
    print("❌ No se pudo obtener chat_id. Envía /start primero.")
    return None

# Enviar menú
send_test_menu()

print("\n📡 Esperando callbacks (30 segundos)...")
print("👉 Haz clic en el botón de Telegram AHORA")

# Monitorear por 30 segundos
start_time = time.time()
while time.time() - start_time < 30:
    try:
        response = requests.get(f"{BASE}/getUpdates", params={
            "timeout": 5,
            "offset": last_update_id + 1
        })
        
        if response.status_code == 200:
            data = response.json()
            if data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"]
                    print(f"\n📦 UPDATE COMPLETO:")
                    print(update)
                    print("-" * 60)
        time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")

print("\n✅ Monitoreo terminado")