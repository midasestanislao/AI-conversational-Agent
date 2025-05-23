from twilio.rest import Client
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
client = Client(account_sid, auth_token)

# Get URL of ngrok
with open("ngrok_url.txt", "r") as f:
    url = f.read().strip()

# ⚠️ IMPORTANTE: Cambia la URL al servidor Flask que corre local o en la nube
call = client.calls.create(
    url=f'{url}/english-voice',  # Aquí usamos la interpolación de la URL
    from_='+1',        # Número Twilio
    to='+52'           # Número de destino
)


print(f"✅ Llamada iniciada. SID: {call.sid}")
