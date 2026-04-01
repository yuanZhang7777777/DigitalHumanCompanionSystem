"""
TTS 服务处理
与本地部署的 GPT-SoVITS 语音合成服务端进行交互。
"""
import logging
import asyncio
import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# 配置 GPT-SoVITS 的外接地址（从环境变量获取），注意此 URL 通常指向域的根基址。
# 例如配置为: http://localhost:9880
GPT_SOVITS_API_URL = settings.gpt_sovits_api_url.removesuffix("/tts")

class TTSService:
    @staticmethod
    async def _switch_model(weights_path: str, endpoint: str):
        if not weights_path:
            return
        try:
            url = f"{GPT_SOVITS_API_URL}/{endpoint}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.get(url, params={"weights_path": weights_path})
        except Exception as e:
            logger.warning(f"Failed to switch {endpoint} to {weights_path}: {e}")

    @staticmethod
    async def generate_speech_stream(text: str, language: str = "zh", tts_config: dict | None = None):
        """
        异步请求 GPT-SoVITS API 接口，并返回音频流。
        使用 httpx 捕获前端掉线带来的 CancelledError 并彻底掐断底层 TCP 请求，防止后端的堆积报错压力。
        """
        params = {
            "text": text,
            "text_lang": language, # api_v2.py 使用的是 text_lang
            "streaming_mode": True # 设置流模式返回分块数据
        }
        has_custom_weights = False
        if tts_config:
            # 1. 切换 GPT / SoVITS 模型权重
            gpt_path = tts_config.get("gpt_weights")
            sovits_path = tts_config.get("sovits_weights")
            
            if gpt_path or sovits_path:
                has_custom_weights = True
                
            if gpt_path:
                await TTSService._switch_model(gpt_path, "set_gpt_weights")
            if sovits_path:
                await TTSService._switch_model(sovits_path, "set_sovits_weights")
                
            # 2. 注入推理参数
            if tts_config.get("ref_audio_path"):
                params["ref_audio_path"] = tts_config["ref_audio_path"]
            if tts_config.get("prompt_text"):
                params["prompt_text"] = tts_config["prompt_text"]
            if tts_config.get("prompt_lang"):
                params["prompt_lang"] = tts_config["prompt_lang"]

        # 如果没有配置专属声音模型，直接使用 DashScope 默认声音
        if not has_custom_weights:
            logger.info("未配置专属声音模型，直接使用 DashScope 默认声音")
            async for chunk in TTSService._generate_default_speech(text):
                yield chunk
            return

        tts_url = f"{GPT_SOVITS_API_URL}/tts"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                async with client.stream("GET", tts_url, params=params) as response:
                    response.raise_for_status()


                    # 以生成器形式流式返回音频块
                    async for chunk in response.aiter_bytes(chunk_size=4096):
                        if chunk:
                            yield chunk

        except asyncio.CancelledError:
            # 当请求方（如前端的 audio.src = '' 或页面销毁）关闭连接时，
            # FastAPI 的 StreamingResponse 会向其生成器抛出 CancelledError
            logger.info("客户端切断了语音请求，释放底层 HTTP 资源 (CancelledError)")
            raise  # 必须抛出以彻底结束当前 Task
        
        except httpx.RequestError as e:
            logger.warning(f"GPT-SoVITS 网络请求失败，降级使用默认语音: {e}")
            async for chunk in TTSService._generate_default_speech(text):
                yield chunk
            
        except Exception as e:
            logger.error(f"TTS 生成出现未知异常: {e}")
            raise Exception(f"语音生成抛出异常: {str(e)}")

    @staticmethod
    async def _generate_default_speech(text: str):
        """
        使用阿里云 DashScope 的基础 TTS 模型作为默认和降级声音。
        保证用户未训练自己的模型时系统依然可以发声。
        """
        import dashscope
        from dashscope.audio.tts_v2 import SpeechSynthesizer
        from dashscope.api_entities.dashscope_response import SpeechSynthesisResponse
        
        dashscope.api_key = settings.ai_api_key
        
        # 使用清越女声或稳重男声，此处选用一个常用的有效模型（需确保该模型可用）
        model = "cosyvoice-v1"
        voice = "longxiaochun"

        try:
            # 使用同步流式接口并在后台异步执行（或者若提供异步客户端则直接使用）
            # DashScope Python SDK v2 目前是同步阻塞生成流，使用 asyncio.to_thread 防止阻塞主循环
            synthesizer = SpeechSynthesizer(
                model=model,
                voice=voice,
            )
            
            # 由于 synthesizer.stream_call 在某些版本可能有差异，我们直接用 call
            # 注：这里为了快速响应用 call 获取完整 byte 后 chunk 吐出
            audio_bytes = await asyncio.to_thread(synthesizer.call, text)
            
            # 分块 yield 模拟流式
            chunk_size = 4096
            for i in range(0, len(audio_bytes), chunk_size):
                yield audio_bytes[i:i + chunk_size]
                await asyncio.sleep(0.01) # 模拟流式传输间隔
                
        except Exception as e:
            logger.error(f"默认语音(DashScope)生成失败: {e}")
            raise Exception(f"默认语音生成失败，请检查 AI API 配置: {str(e)}")

