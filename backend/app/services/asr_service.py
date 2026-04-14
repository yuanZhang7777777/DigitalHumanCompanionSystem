import logging
import os
import tempfile
import asyncio
import io
from app.config import settings

logger = logging.getLogger(__name__)


class ASRService:
    """
    语音识别服务 — 使用 DashScope SDK Recognition API
    前端录音上传 → 转码 WAV → DashScope Paraformer → 返回文字
    """
    def __init__(self):
        self.api_key = settings.ai_api_key

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """
        将音频字节流传给 DashScope，返回识别文本。

        :param audio_bytes: 音频文件的原始字节
        :param filename:    文件名（带后缀，用于判断格式）
        :return: 识别出的文字
        """
        if not self.api_key:
            raise ValueError("DashScope API Key 未配置，请在 .env 中设置 AI_API_KEY")

        # 保存到临时文件
        ext = os.path.splitext(filename)[1].lower() or ".wav"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
            f.write(audio_bytes)
            temp_input = f.name

        wav_path = None
        try:
            # 如果不是 WAV 格式，用 PyAV 转换为 16kHz 单声道 WAV
            if ext not in (".wav", ".wave"):
                wav_path = await asyncio.to_thread(self._convert_to_wav, temp_input)
            else:
                wav_path = temp_input

            # 调用 DashScope SDK 进行识别
            text = await asyncio.to_thread(self._recognize_sync, wav_path)
            return text
        finally:
            # 清理临时文件
            for path in (temp_input, wav_path):
                if path:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass

    def _convert_to_wav(self, input_path: str) -> str:
        """使用 PyAV 将任意音频格式转换为 16kHz 单声道 16bit PCM WAV"""
        import av

        output_path = input_path + "_converted.wav"
        try:
            input_container = av.open(input_path)
            audio_stream = next(s for s in input_container.streams if s.type == 'audio')

            output_container = av.open(output_path, mode='w')
            output_stream = output_container.add_stream('pcm_s16le', rate=16000)
            output_stream.layout = 'mono'

            resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)

            for frame in input_container.decode(audio_stream):
                resampled_frames = resampler.resample(frame)
                for resampled in resampled_frames:
                    for packet in output_stream.encode(resampled):
                        output_container.mux(packet)

            # Flush
            for packet in output_stream.encode(None):
                output_container.mux(packet)

            output_container.close()
            input_container.close()
            logger.info("音频转换完成: %s → %s", input_path, output_path)
            return output_path
        except Exception as e:
            logger.error("PyAV 音频转换失败: %s", e)
            raise RuntimeError(f"音频格式转换失败: {e}")

    def _recognize_sync(self, audio_path: str) -> str:
        """同步调用 DashScope Recognition API"""
        from dashscope.audio.asr import Recognition, RecognitionCallback
        import dashscope

        dashscope.api_key = self.api_key

        logger.info("开始 DashScope Recognition 识别: %s", audio_path)

        class _Callback(RecognitionCallback):
            def __init__(self):
                self.error = None
            def on_complete(self):
                pass
            def on_error(self, message):
                self.error = str(message)

        callback = _Callback()
        recognition = Recognition(
            model='paraformer-realtime-v1',
            format='wav',
            sample_rate=16000,
            callback=callback,
        )

        result = recognition.call(audio_path)

        if callback.error:
            raise RuntimeError(f"语音识别失败: {callback.error}")

        if result.status_code != 200:
            logger.error("语音识别失败: status=%s code=%s msg=%s",
                         result.status_code, result.code, result.message)
            raise RuntimeError(f"语音识别服务返回错误 ({result.status_code}): {result.message}")

        # 提取识别文本
        sentences = result.get_sentence()
        if sentences:
            texts = [s['text'].strip() for s in sentences if 'text' in s and s['text'].strip()]
            text = ''.join(texts)
            logger.info("ASR 识别结果 (sentences): %s", text)
            return text

        output = result.output if result.output is not None else {}
        if isinstance(output, dict) and output.get('text'):
            text = output['text'].strip()
            logger.info("ASR 识别结果 (output): %s", text)
            return text

        logger.warning("ASR 未返回任何文本")
        return ""


# 全局单例
asr_service = ASRService()
