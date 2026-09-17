import wave
import math
import struct

sample_rate = 8000
duration = 0.45
num_samples = int(sample_rate * duration)

with wave.open("hello_tiny.wav", "w") as f:
    f.setnchannels(1)
    f.setsampwidth(1)
    f.setframerate(sample_rate)
    
    for i in range(num_samples):
        t = i / sample_rate
        val = int(128 + 120 * math.sin(2 * math.pi * 440 * t) * math.exp(-3 * t))
        f.writeframes(struct.pack('B', max(0, min(255, val))))

print("Saved hello_tiny.wav")