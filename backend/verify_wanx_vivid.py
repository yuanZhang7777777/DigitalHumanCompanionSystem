import os
import asyncio
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

async def verify_wanx_vivid():
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("Error: Missing API Key")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-DashScope-Async": "enable",
        "Content-Type": "application/json"
    }

    # Test inputs (using Wikipedia Obama as a reliable source)
    image_url = "https://upload.wikimedia.org/wikipedia/commons/8/8d/President_Barack_Obama.jpg"
    audio_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"

    # The refined prompt we implemented in video_service.py
    refined_prompt = (
        "The person in the portrait is talking naturally, "
        "vivid eye contact, warm and friendly gaze, "
        "subtle facial micro-expressions including gentle blinking and slight smiles, "
        "natural lip-syncing with the audio, "
        "slow and graceful head motion, high quality, realistic cinematic lighting."
    )

    payload = {
        "model": "wan2.2-s2v",
        "input": {
            "image_url": image_url,
            "audio_url": audio_url,
            "prompt": refined_prompt
        },
        "parameters": {
            "resolution": "480P"
        }
    }

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"
    
    print("Testing Wanx with new vivid prompt...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        print(f"Status: {r.status_code}")
        print("Response:", json.dumps(r.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(verify_wanx_vivid())
