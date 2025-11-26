import os, json
import pyaudio
from dotenv import load_dotenv
from vosk import Model, KaldiRecognizer

# Simple voice → text → (display). You can wire this into GUI/CLI or directly
# call your parse/execute loop if you refactor it into a function.

def main():
    load_dotenv()
    model_path=os.getenv('VOSK_MODEL_PATH','./models/vosk-model-en-us-0.22-lgraph')
    if not os.path.isdir(model_path):
        print('Vosk model missing. Set VOSK_MODEL_PATH in .env'); return
    model=Model(model_path)

    # Optional: bias to your common commands
    # COMMANDS = ["create folder", "open folder", "install htop", "show top", "ping", "set volume", "play", "pause", "clone repository", "docker ps"]
    # rec = KaldiRecognizer(model, 16000, json.dumps(COMMANDS))

    rec = KaldiRecognizer(model, 16000)
    pa=pyaudio.PyAudio()
    stream=pa.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
    stream.start_stream()
    print('🎤 Speak… (e.g. "Create a folder Projects") — press Ctrl+C to stop')
    try:
        while True:
            data=stream.read(4000, exception_on_overflow=False)
            if len(data)==0: continue
            if rec.AcceptWaveform(data):
                j=json.loads(rec.Result())
                text=j.get('text','').strip()
                if text:
                    print(f"You said: {text}")
    except KeyboardInterrupt:
        pass

if __name__=='__main__':
    main()