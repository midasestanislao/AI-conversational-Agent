from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from pydantic import BaseModel
from pyngrok import ngrok
import google.generativeai as genai
import os
from dotenv import load_dotenv
from pathlib import Path
import random

# Load environment variables
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

# In-call memory
active_chats = {}
call_transcriptions = {} # Dictionary to store transcriptions

# Validation model
class AIResponse(BaseModel):
    text: str

# Define different initial prompts for different English accents
accent_prompts = [
    {
        "role": "user", "parts": [
            "Simulate an American person calling about a plumbing problem. "
            "Use common American English phrases. "
            "Provide realistic fake data like name, address, phone, and zip code when asked. "
            "Your name can be John Smith, you live at 123 Main St in Anytown, CA 90210, phone 555-123-4567. "
            "Vary your tone based on the context: sound more urgent if the problem is serious. Speak with natural pauses. "
            "Sometimes hesitate, ask to repeat, or give unclear answers like 'I think it was yesterday', 'mmm I'm not sure'."
        ]
    },
    {
        "role": "user", "parts": [
            "Simulate a Hispanic person with a noticeable accent speaking English about a plumbing problem. "
            "Incorporate some Spanish loanwords or phrasing occasionally (e.g., 'un momento', 'sí'). "
            "Provide realistic fake data like name, address, phone, and zip code when asked. "
            "Your name can be Carlos Rodriguez, you live at 456 Oak Ave in Somecity, FL 33101, phone 305-555-1212. "
            "Vary your tone based on the urgency. Speak with natural pauses and a slight accent. "
            "Sometimes hesitate or ask for clarification."
        ]
    },
    {
        "role": "user", "parts": [
            "Simulate an Asian person with a noticeable accent speaking English about a plumbing issue. "
            "Use slightly more formal English and common filler words. "
            "Provide realistic fake data like name, address, phone, and postal code when asked. "
            "Your name can be Kenji Tanaka, you live at 789 Pine Ln in Techville, CA 94086, phone 408-555-3434. "
            "Vary your tone depending on the situation. Speak with some natural pauses and a slight accent. "
            "Occasionally ask for clarification or give vague responses."
        ]
    }
]

# Starts the chat simulating a human client with a random accent
def get_chat(call_sid):
    if call_sid not in active_chats:
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        initial_prompt = random.choice(accent_prompts)
        chat = model.start_chat(history=[initial_prompt])
        active_chats[call_sid] = chat
        call_transcriptions[call_sid] = [] # Initialize transcription list for this call
    return active_chats[call_sid]

@app.route("/english-voice", methods=["GET", "POST"])
def english_voice():
    call_sid = request.values.get("CallSid")
    speech = request.values.get("SpeechResult")
    twiml = VoiceResponse()
    chat = get_chat(call_sid)

    if speech:
        print(f"🗣️ User said: {speech}")
        call_transcriptions[call_sid].append(f"Client: {speech}") # Add client speech to transcription

        try:
            response = chat.send_message(speech)
            ai_text = response.text.strip()
            validated = AIResponse(text=ai_text)
            print(f"🤖 AI said: {validated.text}")
            call_transcriptions[call_sid].append(f"Support: {validated.text}") # Add AI response to transcription
        except Exception as e:
            print("❌ Error with Gemini:", e)
            validated = AIResponse(text="Sorry, I think I misunderstood. Could you repeat that?")
            call_transcriptions[call_sid].append(f"Support: Sorry, I think I misunderstood. Could you repeat that?")

        # Remove or reduce artificial pauses for faster conversation
        ssml_text = validated.text # Removed the replace operations that added pauses

        voice = "Polly.Joanna" # Default English voice
        language = "en-US"

        # Attempt to choose a voice that might align with the simulated accent
        initial_message_content = None
        if chat.history and chat.history[0]:
            print(f"DEBUG: chat.history[0] = {chat.history[0]}") # ADD THIS LINE
            if hasattr(chat.history[0], 'parts'):
                for part in chat.history[0].parts: # Access 'parts' as an attribute
                    initial_message_content = part.text if hasattr(part, 'text') else str(part)
                    break
            elif isinstance(chat.history[0], dict) and 'parts' in chat.history[0]:
                for part in chat.history[0]['parts']:
                    initial_message_content = part
                    break

        if initial_message_content:
            if "Hispanic person" in initial_message_content:
                voice = "Polly.Penelope" # US Spanish voice often used for Hispanic English accent
            elif "Asian person" in initial_message_content:
                voice = "Polly.Ivy"

        twiml.say(f"<speak>{ssml_text}</speak>", voice=voice, language=language)
        gather = Gather(input="speech", action="/english-voice", method="POST", language=language, timeout=8)
        gather.say("What else do you need to know?", voice=voice, language=language)
        twiml.append(gather)
        return Response(str(twiml), mimetype="application/xml")

    else:
        # Start of call
        initial_message_content = None
        if call_sid in active_chats and active_chats[call_sid].history and active_chats[call_sid].history[0]:
            print(f"DEBUG (Initial): active_chats[{call_sid}].history[0] = {active_chats[call_sid].history[0]}") # ADD THIS LINE
            if hasattr(active_chats[call_sid].history[0], 'parts'):
                for part in active_chats[call_sid].history[0].parts: # Access 'parts' as an attribute
                    initial_message_content = part.text if hasattr(part, 'text') else str(part)
                    break
            elif isinstance(active_chats[call_sid].history[0], dict) and 'parts' in active_chats[call_sid].history[0]:
                for part in active_chats[call_sid].history[0]['parts']:
                    initial_message_content = part
                    break

        voice = "Polly.Joanna"
        language = "en-US"
        initial_greeting = "Hi, I'm calling because I have a plumbing issue at my house."

        if initial_message_content:
            if "Hispanic person" in initial_message_content:
                initial_greeting = "Hello, I am calling because I have a problem with the plumbing here, sí?"
                voice = "Polly.Penelope"
            elif "Asian person" in initial_message_content:
                initial_greeting = "Hello, I am calling to report a problem with the water pipes."
                voice = "Polly.Ivy"

        gather = Gather(input="speech", action="/english-voice", method="POST", language=language, timeout=8)
        gather.say(initial_greeting, voice=voice, language=language)
        twiml.append(gather)

        twiml.say("I didn't hear anything. I will call back later, thank you.", voice="Polly.Joanna", language="en-US")
        twiml.hangup()
        return Response(str(twiml), mimetype="application/xml")


@app.route("/save-transcript/<call_sid>")
def save_transcript(call_sid):
    if call_sid in call_transcriptions:
        filename = f"transcript_{call_sid}.txt"
        with open(filename, "w") as f:
            for line in call_transcriptions[call_sid]:
                f.write(line + "\n")
        return f"Transcription saved to {filename}"
    else:
        return "Call SID not found."

# Start ngrok server
def start_ngrok(port=5000):
    ngrok.set_auth_token(os.getenv("NGROK_AUTH_TOKEN"))
    ngrok.kill()
    public_url = ngrok.connect(port, bind_tls=True)
    print("\n✅ Flask server running at http://localhost:5000")
    print(f'🌐 NgrokTunnel: "{public_url}" -> "http://localhost:{port}"')

    print(f"👉 Use this URL for Twilio: {public_url}/english-voice\n")
    with open("ngrok_url.txt", "w") as f:
        f.write(public_url.public_url)
    return public_url

if __name__ == "__main__":
    start_ngrok(port=5000)
    app.run(host="0.0.0.0", port=5000)