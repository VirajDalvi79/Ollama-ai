import sounddevice as sd
import queue
import vosk
import json
import pyttsx3
import subprocess
import requests
import os

# -------------------
# CONFIG
# -------------------

#OPEN CMD ----> 1. adb tcpip 5555
#               2. connect your phone using usb 
#               3. adb connect "your_ip-address:5555"
DEVICE = "YOUR_IP_ADDRESS:5555"
VOSK_MODEL_PATH = r"ADD_YOUR_PATH"

# -------------------
# INIT
# -------------------
model = vosk.Model(VOSK_MODEL_PATH)
q = queue.Queue()
engine = pyttsx3.init()

def ask_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "jarvis:latest",
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        data = response.json()
        return data.get("response", "No response from Ollama, Sir.")
    except Exception as e:
        return f"Ollama API error: {e}"

# -------------------
# SPEAK
# -------------------
def speak(text):
    print("Jarvis:", text)
    engine.say(text)
    engine.runAndWait()

# -------------------
# ADB HELPER
# -------------------
def adb_run(cmd):
    return subprocess.run(
        ["adb", "-s", DEVICE] + cmd,
        capture_output=True,
        text=True
    )

def adb_open_app(package, activity):
    result = adb_run([
        "shell",
        "am", "start",
        "-n", f"{package}/{activity}"
    ])

    if "Error" in result.stderr:
        return f"ADB failed to launch {package}, Sir."

    return f"Opening {package} on your phone, Sir."

def adb_type_text(text):
    safe_text = text.replace(" ", "%s")
    adb_run([
        "shell",
        "input",
        "text",
        safe_text
    ])

def adb_send_message():
    # Tap input box
    adb_run(["shell", "input", "tap", "540", "1770"])
    # Press ENTER / send
    adb_run(["shell", "input", "keyevent", "66"])

# -------------------
# LISTEN (VOICE)
# -------------------
def callback(indata, frames, time, status):
    q.put(bytes(indata))

def listen(timeout=10):
    import time
    with sd.RawInputStream(
        samplerate=16000,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback
    ):
        rec = vosk.KaldiRecognizer(model, 16000)
        start = time.time()
        while True:
            if time.time() - start > timeout:
                return ""
            if not q.empty():
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    return result.get("text", "")

# -------------------
# COMMAND EXECUTOR
# -------------------
def execute_command(command):
    command = command.lower()

    # ---- PC ----
    if "open chrome" in command:
        os.system("start chrome")
        return "Opening Chrome, Sir."

    if "open notepad" in command:
        os.system("start notepad")
        return "Opening Notepad, Sir."

    if "shutdown" in command:
        os.system("shutdown /s /t 5")
        return "Shutting down, Sir."

    if "restart" in command:
        os.system("shutdown /r /t 5")
        return "Restarting, Sir."

    # ---- PHONE ----
    if "open whatsapp" in command:
        return adb_open_app("com.whatsapp", "com.whatsapp.Main")


    if "open youtube" in command:
        return adb_open_app("com.google.android.youtube", "com.google.android.youtube.HomeActivity")

    if "take screenshot" in command:
        adb_run(["shell", "screencap", "/sdcard/screen.png"])
        adb_run(["pull", "/sdcard/screen.png", "."])
        return "Screenshot saved, Sir."

    if "lock phone" in command:
        adb_run(["shell", "input", "keyevent", "26"])
        return "Phone locked, Sir."

    if "send message" in command:
        speak("Sir, do you want to speak your message or type it? (say 'speak' or 'type')")
        choice = input("You (speak/type): ").strip().lower()

        message = ""
        if choice == "speak":
            speak("Listening, Sir...")
            message = listen()
            if not message:
                speak("I did not catch anything, Sir. Please type it.")
                message = input("You: ").strip()
        elif choice == "type":
            message = input("You: ").strip()
        else:
            speak("Invalid choice, Sir. Defaulting to type.")
            message = input("You: ").strip()

        if message:
            adb_type_text(message)
            adb_send_message()
            return "Message sent on WhatsApp, Sir."
        else:
            return "No message to send, Sir."

    # ---- FALLBACK ----
    return ask_ollama(command)

# -------------------
# MAIN LOOP
# -------------------
print("Jarvis: Jarvis is online, Sir.")
print("Type your command (voice optional). Type 'exit' to quit.\n")

while True:
    try:
        user_input = input("You: ").strip()

        if user_input.lower() in ["exit", "quit", "bye"]:
            speak("Shutting down, Sir.")
            break

        if not user_input:
            continue

        response = execute_command(user_input)
        speak(response)

    except KeyboardInterrupt:
        speak("Interrupted, Sir.")
        break

