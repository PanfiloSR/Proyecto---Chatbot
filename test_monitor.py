# test_monitor.py
import requests
import time
from config import TELEGRAM_TOKEN

TOKEN = TELEGRAM_TOKEN
BASE = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = 0

print("🔍 Monitoreando mensajes y callbacks...")
print("Presiona un botón en Telegram\n")

while True:
    try:
        # Obtener updates
        params = {"timeout": 30, "offset": last_update_id + 1}
        response = requests.get(f"{BASE}/getUpdates", params=params, timeout=35)
        data = response.json()
        
        if data.get("ok") and data.get("result"):
            for update in data["result"]:
                last_update_id = update["update_id"]
                
                # Verificar si es callback
                if "callback_query" in update:
                    callback = update["callback_query"]
                    print(f"\n🎯 CALLBACK RECIBIDO!")
                    print(f"   Data: {callback['data']}")
                    print(f"   From: {callback['from']['first_name']}")
                    
                    # Responder al callback
                    answer = requests.post(f"{BASE}/answerCallbackQuery", json={
                        "callback_query_id": callback["id"],
                        "text": "¡Recibido!"
                    })
                    
                    # Editar mensaje
                    msg = callback["message"]
                    edit = requests.post(f"{BASE}/editMessageText", json={
                        "chat_id": msg["chat"]["id"],
                        "message_id": msg["message_id"],
                        "text": f"✅ Seleccionaste: {callback['data']}"
                    })
                    print(f"   Respuesta enviada: {answer.status_code}")
                
                # Verificar si es mensaje de texto
                elif "message" in update and "text" in update["message"]:
                    msg = update["message"]
                    print(f"\n📝 Mensaje: {msg['text']} de {msg['from']['first_name']}")
        
        time.sleep(0.5)
        
    except KeyboardInterrupt:
        print("\n👋 Deteniendo...")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(2)