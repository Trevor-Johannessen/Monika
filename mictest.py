import sounddevice as sd
import librosa
import numpy as np

# 1. Load the file
# sr=None preserves the original speed, but we can also set sr=48000 
# to force it to match the standard Linux audio rate.
filename = 'test.mp3'
data, fs = librosa.load(filename, sr=48000) 

# 2. Find your Virtual Device (Null Sink)
# If you created it with the 'pactl' command from before
target_device = "VirtualMic" 

devices = sd.query_devices()
device_id = None
for i, dev in enumerate(devices):
    if target_device in dev['name']:
        device_id = i
    print(dev['name'])

if device_id is None:
    print(f"Could not find {target_device}. Please ensure it is created.")
else:
    print(f"Playing to {target_device} at {fs}Hz...")
    # 3. Play (Note: sounddevice expects samples as rows, librosa provides them as rows)
    sd.play(data, fs, device=device_id)
    sd.wait()

