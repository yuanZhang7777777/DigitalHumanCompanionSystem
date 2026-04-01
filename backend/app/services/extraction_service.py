import ffmpeg
import os
import time
import logging
from dashscope.audio.asr import Transcription

logger = logging.getLogger(__name__)

def convert_media_to_wav(input_path: str) -> str:
    """
    使用 ffmpeg 将任意音视频转换为 16kHz, 单声道, 16bit PCM WAV 格式，
    这是各类语音识别模型（如 SenseVoice, Whisper）的理想输入格式。
    """
    try:
        output_path = f"{input_path}_converted.wav"
        stream = ffmpeg.input(input_path)
        # -ac 1 (单声道), -ar 16000 (16kHz 采样率), -acodec pcm_s16le (16-bit PCM格式)
        stream = ffmpeg.output(stream, output_path, ac=1, ar=16000, acodec='pcm_s16le')
        # 覆写已有文件, 捕获错误输出
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        return output_path
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode('utf8') if e.stderr else str(e)
        logger.error(f"FFmpeg 转换失败: {error_msg}")
        raise RuntimeError(f"音频提取失败：请检查视频或音频格式是否损坏。详细信：{error_msg}")
def transcribe_audio_with_dashscope(audio_path: str, api_key: str) -> str:
    """
    使用阿里云百炼 DashScope 的 Recognition API 接口直接上传识别。
    将本地 WAV 文件转录为文本。如果支持，提取发音人角色。
    """
    from dashscope.audio.asr import Recognition, RecognitionCallback
    import dashscope
    import os
    
    dashscope.api_key = api_key
    
    logger.info(f"开始使用 Recognition API 识别本地音频: {audio_path}")
    
    class SyncCallback(RecognitionCallback):
        def on_complete(self):
            pass
        def on_error(self, message):
            pass
    
    try:
        # 使用 paraformer-8k-v1 需实例化加上 Callback，支持本地文件直接上传
        callback = SyncCallback()
        recognition = Recognition(
            model='paraformer-realtime-v1',
            format='wav',
            sample_rate=16000,
            callback=callback
        )
        
        result = recognition.call(audio_path)
        
        if result.status_code != 200:
            logger.error(f"语音识别失败: {result.code} - {result.message}")
            raise RuntimeError(f"语音云端识别失败: {result.message}")
            
        logger.info("语音识别成功")
        
        # 尝试剥离句子和说话人
        sentences = result.get_sentence()
        if not sentences:
            if 'output' in result and 'text' in result.output:
                return result.output['text']
            return ""
            
        full_text_lines = []
        for s in sentences:
            if 'text' in s:
                # 某些情况下，Sentence 会带有 speaker_id 等属性
                speaker = s.get('speaker_id', 'Unknown')
                text = s['text'].strip()
                if speaker != 'Unknown':
                    full_text_lines.append(f"发音人{speaker}:\n{text}")
                else:
                    full_text_lines.append(text)
                    
        return "\n\n".join(full_text_lines)
            
    except Exception as e:
        logger.error(f"语音转换异常: {str(e)}")
        raise RuntimeError(f"语音云端识别异常: {str(e)}")

async def extract_traits_from_text(text: str, ai_service) -> dict:
    """
    使用 LLM（如 Qwen-Plus）对长文本进行分析，提取人生经历和性格特点。
    返回结构化的 JSON 字典。
    """
    if not text or len(text.strip()) < 5:
        return {"experiences": [], "personality_traits": []}
        
    system_prompt = """你是一个专业的心理学与传记分析专家。
请阅读下面的访谈/对话逐字稿文本（可能是多人对话但没有标注发音人）。
请你根据上下文，推断出对话中包含的“核心发音人/角色”（可能是一个或多个，例如：受访者嘉宾、主持人、特定讲述者等）。
针对识别出的**每一个核心发音人**，分离出他们的发言，并分别提取他们的人生经历和性格特征。

以 JSON 格式返回，包含一个主要键 "speakers"，其值为数组，每个元素代表一个发音人，包含三个键：
- "role": 该发音人的推断身份或特征描述（如："核心人物"、"嘉宾"、"主持人"、"提问者"等，尽量精准简短）
- "experiences": 数组，每项包含 "year"（如"中学时期"、"2018年"），"event"（事件内容，约20字），"type"（只能是 career, education, personal, other 其中之一）
- "personality_traits": 数组，提取出的3-5个描述此人性格的词汇（如"乐观", "坚韧", "随性"）。

请严格保证返回结果为一个合法 JSON 对象，确保 "speakers" 数组存在且格式无误，不要包括多余的 markdown 或其他文字描述。"""
    
    messages = [{"role": "user", "content": f"对话内容如下：\n{text}"}]
    
    logger.info("开始调用 LLM 提取经历特征（支持多发音人拆分）...")
    
    for attempt in range(2):
        try:
            # 借用已经在其他地方初始化的 ai_service
            # 但这里因为要指定必须返回 JSON，可能需要用更灵活的方式。这里复用 chat 方法
            response_text = await ai_service.chat(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.1 # 极低温度保持结构化输出的稳定性
            )
            
            # 清理可能的 markdown 标记
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            
            import json
            result_data = json.loads(clean_text)
            
            # 确保结构正确 (支持多发音人数组)
            if "speakers" not in result_data or not isinstance(result_data["speakers"], list):
                # Fallback format mapping if LLM returns old format
                if "experiences" in result_data or "personality_traits" in result_data:
                    return {"speakers": [{"role": "核心提取人物", "experiences": result_data.get("experiences", []), "personality_traits": result_data.get("personality_traits", [])}]}
                return {"speakers": []}
                
            return result_data
            
        except json.JSONDecodeError as de:
            logger.error(f"LLM 提取结果 JSON 解析失败: {de}\n原文本: {response_text}")
            import asyncio
            await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"LLM 提取特征调用失败: {e}")
            import asyncio
            await asyncio.sleep(1.0)
            
    return {"speakers": []}
