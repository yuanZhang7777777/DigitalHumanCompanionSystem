import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
api_key = os.getenv("AI_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
dashscope.api_key = api_key

def generate_professional_test_audio():
    """
    使用 DashScope CosyVoice 生成高质量测试音频
    内容：1 2 3 4 5 6 7 8 A B C D E F G
    """
    model = "cosyvoice-v1"
    voice = "loongbella" # 优雅专业的女性声音
    text = "1, 2, 3, 4, 5, 6, 7, 8, A, B, C, D, E, F, G."
    
    # 确保目录存在
    target_dir = os.path.join("app", "static")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "generic_speech.mp3")
    
    print(f">>> 正在调用 CosyVoice 生成音频: '{text}'")
    print(f">>> 目标路径: {os.path.abspath(target_path)}")
    
    try:
        synthesizer = SpeechSynthesizer(model=model, voice=voice)
        audio = synthesizer.call(text)
        
        if audio:
            with open(target_path, 'wb') as f:
                f.write(audio)
            print(">>> [成功] 音频已生成！")
        else:
            print(">>> [错误] 未获取到音频数据。")
    except Exception as e:
        print(f">>> [异常] 生成失败: {e}")

if __name__ == "__main__":
    generate_professional_test_audio()
