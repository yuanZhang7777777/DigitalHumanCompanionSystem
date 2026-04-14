"""
语音识别 (ASR) 路由
前端录音上传 → DashScope Paraformer → 返回识别文本
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.asr_service import asr_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/asr", tags=["语音识别"])


@router.post("/transcribe", summary="语音转文字")
async def transcribe_audio(file: UploadFile = File(..., description="音频文件 (wav/mp3/webm)")):
    """
    接收前端上传的音频文件，调用 DashScope Paraformer 进行语音识别，
    返回识别出的文字。
    """
    # 读取音频字节
    audio_bytes = await file.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="上传的音频文件为空")

    # 限制文件大小 10MB
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="音频文件不能超过 10MB")

    # 获取原始文件名后缀
    filename = file.filename or "audio.wav"

    try:
        text = await asr_service.transcribe(audio_bytes, filename)
        return {"text": text}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("语音识别异常")
        raise HTTPException(status_code=500, detail="语音识别服务内部错误")
