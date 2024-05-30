#--- Imports and Initial Setup ---
import pyttsx3
import datetime
import speech_recognition as sr
import pyjokes
import schedule
import time
from plyer import notification
import re
import json
from dateutil import parser as date_parser
import google.generativeai as genai
import requests
import os
from dotenv import load_dotenv
import wave
import pyaudio

# Load environment variables from .env file
load_dotenv()

ASR_API_URL = "https://translation-api.ghananlp.org/asr/v1/transcribe"
language = "tw"  # Example: "tw" for Twi
subscription_key = os.getenv("TRANSLATION_API_KEY")

# Request headers for ASR
asr_headers = {
    "Content-Type": "audio/mpeg",
    "Ocp-Apim-Subscription-Key": 'ed30ff439c9d47c8ade057712b9f6e20',
}

# Request parameters for ASR
asr_params = {
    "language": language,
    "wav": "true"
}

#--- Initialize Pyttsx3 Engine ---
engine = pyttsx3.init()
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)  # Female voice
rate = engine.getProperty('rate')
engine.setProperty('rate', rate - 50)

#--- Function to Speak Out Text ---
def speak(audio):
    engine.say(audio)
    engine.runAndWait()

#--- Function to Recognize User Speech ---
def listen():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=5)  # Timeout set to 5 seconds
        except sr.WaitTimeoutError:
            speak("Sorry, I didn't hear anything. Please try again.")
            return None

    try:
        print("Recognizing...")
        query = recognizer.recognize_google(audio, language='en-us')
        print("You said:", query)
        return query.lower()
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that. Can you please repeat?")
    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition service; {0}".format(e))
    
    return None

#--- Function to Record and Transcribe Local Speech ---
def transcribe_local_speech():
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    CHUNK = 1024
    RECORD_SECONDS = 5
    WAVE_OUTPUT_FILENAME = "output.wav"

    audio = pyaudio.PyAudio()

    # Start recording
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    print("Recording...")

    frames = []

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("Recording finished.")

    # Stop recording
    stream.stop_stream()
    stream.close()
    audio.terminate()

    # Save the recorded audio as a .wav file
    waveFile = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    waveFile.setnchannels(CHANNELS)
    waveFile.setsampwidth(audio.get_sample_size(FORMAT))
    waveFile.setframerate(RATE)
    waveFile.writeframes(b''.join(frames))
    waveFile.close()

    # Read binary audio file
    with open(WAVE_OUTPUT_FILENAME, "rb") as file:
        audio_data = file.read()

    # Send POST request to ASR API
    asr_response = requests.post(
        ASR_API_URL,
        params=asr_params,
        headers=asr_headers,
        data=audio_data
    )

    # Check if the ASR request was successful
    if asr_response.status_code == 200:
        try:
            asr_json_response = asr_response.json()
            print("ASR JSON Response:", asr_json_response)
            
            # Check if response is in expected dictionary format
            if isinstance(asr_json_response, dict):
                transcription = asr_json_response.get("transcription", "")
                print("Transcription:", transcription)
                return transcription
            else:
                # Handle unexpected format as raw text
                transcription = str(asr_json_response)
                print("Unexpected format, treated as transcription:", transcription)
                return transcription
        except ValueError:
            print("Error: Unable to parse JSON response")
            print(asr_response.text)
    else:
        print(f"Error in ASR request: {asr_response.text}")
    return None

#--- Function to Translate Twi to English ---
def translate_to_english(input_text):
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "tw",
        "tl": "en",
        "dt": "t",
        "q": input_text
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        translation = response.json()[0][0][0]
        return translation
    else:
        print("Translation failed with status code:", response.status_code)
        return None

#--- Function to Perform Action Based on Input ---
def perform_action(input_text):
    print("Performing action for input:", input_text)
    if "how are you" in input_text.lower():
        speak("me ho yɛ")
    elif "thank you" in input_text.lower():
        speak("ɛnna ase")
    elif "time" in input_text.lower():
        speak(f"Mprempren bere no ne {datetime.datetime.now().strftime('%I:%M %p')}.")
    elif "what is" in input_text.lower():
        return handle_conversational_ai_command(input_text)
    else:
        return handle_conversational_ai_command(input_text)

#--- Function to Handle Conversational AI Command ---
model = genai.GenerativeModel('gemini-pro')
talk = []

def handle_conversational_ai_command(query):
    global talk
    talk.append({'role': 'user', 'parts': [query]})
    response = model.generate_content(talk, stream=True)
    answer_found = False
    num_lines = 0
    for chunk in response:
        if hasattr(chunk, 'text'):
            answer = chunk.text.strip()
            if answer:
                if not answer_found:
                    print("AI Assistant:", answer)
                    speak(answer)
                    answer_found = True
                num_lines += 1
                if num_lines >= 5:  # Speak only the first 5 lines
                    break
    if not answer_found:
        speak("Sorry, I couldn't find an answer to your question.")

#--- Function to Set a Reminder ---
REMINDERS_FILE = "reminders.json"
reminders = []

def set_reminder():
    speak("What would you like to be reminded about?")
    title = listen()
    if not title:
        speak("Sorry, I didn't catch that. Please try again.")
        return

    speak("When would you like to be reminded?")
    time_str = listen()
    if not time_str:
        speak("Sorry, I didn't catch that. Please try again.")
        return

    try:
        reminder_time = date_parser.parse(time_str)
        reminder = {'title': title, 'time': reminder_time.strftime('%Y-%m-%d %H:%M'), 'notified': False}
        reminders.append(reminder)
        save_reminders(reminders)
        schedule_reminder(title, time_str)
        speak(f"Reminder set for {title} at {reminder_time.strftime('%I:%M %p on %B %d, %Y')}.")
    except ValueError:
        speak("Sorry, I couldn't understand the date and time. Please try again.")

def parse_time_expression(input_text):
    time_regex = r'(\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?|\b(?:today|tomorrow|next week|in|after|morning|afternoon|evening|night)\b|\b\d+\s+\w+\b)'
    match = re.search(time_regex, input_text, re.IGNORECASE)
    if match:
        time_expression = match.group(0)
        title = input_text.replace(time_expression, '')
    else:
        time_expression = ''
        title = input_text
    return title, time_expression

def check_overdue_reminders():
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    for reminder in reminders:
        if not reminder['notified'] and reminder['time'] <= now:
            speak(f"Reminder: {reminder['title']}")
            notification.notify(
                title='Reminder',
                message=reminder['title'],
                app_name='AI Assistant'
            )
            reminder['notified'] = True
            save_reminders(reminders)

def schedule_reminder(title, time_str):
    schedule_time = date_parser.parse(time_str)
    now = datetime.datetime.now()
    delay = (schedule_time - now).total_seconds()
    if delay > 0:
        schedule.enter(delay, 1, speak, (f"Reminder: {title}",))

def load_reminders():
    try:
        with open(REMINDERS_FILE, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_reminders(reminders):
    with open(REMINDERS_FILE, 'w') as file:
        json.dump(reminders, file)

#--- Greeting Function ---
def greet():
    hour = datetime.datetime.now().hour
    if 6 <= hour < 12:
        speak("Good morning user") 
    elif 12 <= hour < 18:
        speak("Good afternoon user")
    elif 18 <= hour < 24:
        speak("Good evening user")
    else:
        speak("Hello user")

#--- Date Requests Function ---
def get_date(query):
    today = datetime.date.today()
    if 'tomorrow' in query:
        return today + datetime.timedelta(days=1)
    elif 'next week' in query:
        return today + datetime.timedelta(weeks=1)
    else:
        return today

#--- Main Function ---
def main():
    greet()
    global reminders
    reminders = load_reminders()

    while True:
        speak("I am your personal AI assistant")
        speak("Do you prefer English or the local language?")
        language = listen()
        if language is not None:
            break
        else:
            speak("Failed to recognize language. Let's try again.")

    if 'local' in language:
        while True:
            schedule.run_pending()
            check_overdue_reminders()
            speak("Please say your Twi text.")
            input_text = transcribe_local_speech()
            if input_text:
                print("Transcribed text:", input_text)
                english_translation = translate_to_english(input_text)
                if english_translation:
                    print("English translation:", english_translation)
                    perform_action(english_translation)
                else:
                    speak("Translation failed.")
            else:
                speak("Failed to transcribe the speech.")

    elif 'english' in language:
        speak("How can I help you")
        while True:
            schedule.run_pending()
            check_overdue_reminders()
            query = listen()
            if query:
                if 'the time' in query:
                    speak(f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}.")
                elif 'how are you' in query:
                    speak("I'm doing just fine. Thank you for asking!")
                elif 'today\'s date' in query:
                    today = datetime.datetime.now().strftime("%A, %B %d, %Y")
                    speak(f"Today's date is {today}.")
                elif 'tomorrow\'s date' in query:
                    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)
                    tomorrow_formatted = tomorrow.strftime("%A, %B %d, %Y")
                    speak(f"Tomorrow's date is {tomorrow_formatted}.")
                elif 'next week\'s date' in query:
                    next_week = datetime.datetime.now() + datetime.timedelta(weeks=1)
                    next_week_formatted = next_week.strftime("%A, %B %d, %Y")
                    speak(f"The date next week will be {next_week_formatted}.")
                elif 'set a reminder' in query:
                    set_reminder()
                elif 'do I have any reminders' in query:
                    if reminders:
                        speak("Yes, Here are your reminders:")
                        for reminder in reminders:
                            speak(f"Reminder for {reminder['title']} at {reminder['time']}.")
                    else:
                        speak("You have no reminders.")
                elif 'joke' in query:
                    speak(pyjokes.get_joke())
                elif 'thank you' in query:
                    speak("You're welcome!")
                elif 'go offline' in query or 'goodbye' in query:
                    speak("Alright, I'll be here if you need me. Later")
                    save_reminders(reminders)
                    quit()
                else:
                    handle_conversational_ai_command(query)
    else:
        speak("Unsupported language. Let us try again.")
        main()

if __name__ == "__main__":
    main()
