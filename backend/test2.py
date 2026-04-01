import dashscope
from dashscope.audio.asr import Recognition

try:
    res = Recognition.call(model='sensevoice-v1', format='wav', sample_rate=16000, file='uploaded_media/temp_1771697839.m4a_converted.wav')
    print("SUCCESS", res.status_code)
except Exception as e:
    print(e)
