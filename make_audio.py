from gtts import gTTS

tts = gTTS(text="Hello", lang="en")
tts.save("hello.mp3")
print("Audio saved successfully as hello.mp3")