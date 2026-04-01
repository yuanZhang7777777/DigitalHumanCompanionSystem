from fastapi import APIRouter, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from bson import ObjectId
import logging

from ..database import get_database
from ..services.tts_service import TTSService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tts", tags=["语音合成 (TTS)"])

@router.get("/generate", summary="生成文字语音流")
async def generate_tts(
    person_id: str = Query(..., description="数字人ID，用于加载特定声音配置"),
    text: str = Query(..., description="要转换为语音的文本内容"),
    lang: str = Query("zh", description="语言，默认中文 zh"),
    db=Depends(get_database)
):
    """
    接收前端文字，查询当前数字人的声音配置参数，
    调用本地的 GPT-SoVITS 服务器生成音频流返回。
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="文本不可为空")

    tts_config = None
    if ObjectId.is_valid(person_id):
        person = await db["digital_persons"].find_one({"_id": ObjectId(person_id)})
        if person and "tts_config" in person:
            tts_config = person["tts_config"]

    try:
        return StreamingResponse(
            TTSService.generate_speech_stream(text, lang, tts_config),
            media_type="audio/wav" 
        )
    except Exception as e:
        logger.error(f"语音请求失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
