from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import time
import shutil
import logging
from ..database import get_database
from ..config import settings
from ..services.extraction_service import convert_media_to_wav, transcribe_audio_with_dashscope, extract_traits_from_text
from ..services.ai_service import AIService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/extract",
    tags=["Extraction"],
    responses={404: {"description": "Not found"}},
)

UPLOAD_DIR = "uploaded_media"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/media", summary="从音视频中提取人生经历和性格")
async def extract_from_media(
    file: UploadFile = File(...),
    db=Depends(get_database)
):
    """
    接收音视频文件上传，利用 FFmpeg 提取音频（若为视频），
    通过阿里云 DashScope (SenseVoice) 转录文字，并交由大模型抽取结构化的人生经历和性格标签。
    """
    if not file:
        raise HTTPException(status_code=400, detail="未收到上传的文件")

    # 1. 保存临时文件
    file_ext = os.path.splitext(file.filename)[1].lower()
    temp_filename = f"temp_{int(time.time())}{file_ext}"
    temp_filepath = os.path.join(UPLOAD_DIR, temp_filename)
    wav_filepath = None
    
    try:
        with open(temp_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. FFmpeg 压缩提取音频 (转换为标准的 16kHz WAV)
        logger.info(f"开始使用 FFmpeg 提取/转换音频: {temp_filepath}")
        wav_filepath = convert_media_to_wav(temp_filepath)
        
        # 3. STT 语音转文本
        if not settings.ai_api_key:
            raise RuntimeError("后端未配置百炼 API Key (AI_API_KEY)")
            
        logger.info(f"开始 STT 语音识别...")
        full_text = transcribe_audio_with_dashscope(wav_filepath, settings.ai_api_key)
        
        if not full_text:
            raise RuntimeError("语音识别未能提取出任何文本内容")
            
        logger.info(f"语音识别结果: {full_text[:50]}...")
        
        # 4. LLM 结构化提取
        ai_service = AIService()
        result_data = await extract_traits_from_text(full_text, ai_service)
        
        return {
            "success": True,
            "message": "提取成功",
            "data": result_data,
            "raw_text": full_text # 返回给前端看看，有时候很有趣
        }
        
    except Exception as e:
        logger.error(f"媒体提取失败: {str(e)}")
        return JSONResponse(status_code=500, content={"success": False, "message": f"处理出错: {str(e)}"})
    finally:
        # 清理临时文件
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except:
                pass
        if wav_filepath and os.path.exists(wav_filepath):
            try:
                os.remove(wav_filepath)
            except:
                pass
