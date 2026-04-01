import os
import asyncio
import httpx
from dotenv import load_dotenv
import json
import time

load_dotenv()

async def debug_wanx_response():
    api_key = os.environ.get("AI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("Error: Missing API Key")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-DashScope-Async": "enable",
        "Content-Type": "application/json"
    }

    # Test inputs
    image_url = "https://upload.wikimedia.org/wikipedia/commons/8/8d/President_Barack_Obama.jpg"
    audio_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
    refined_prompt = "A person talking naturally."

    payload = {
        "model": "wan2.2-s2v",
        "input": {
            "image_url": image_url,
            "audio_url": audio_url,
            "prompt": refined_prompt
        }
    }

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image2video/video-synthesis"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Submitting task...")
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            print(f"Failed to submit: {r.text}")
            return
            
        task_id = r.json()["output"]["task_id"]
        print(f"Task ID: {task_id}")

        while True:
            await asyncio.sleep(10)
            poll_resp = await client.get(f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}", headers={"Authorization": f"Bearer {api_key}"})
            data = poll_resp.json()
            status = data["output"]["task_status"]
            print(f"Status: {status}")
            
            if status in ["SUCCEEDED", "FAILED"]:
                print("Full Response Data:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                break

if __name__ == "__main__":
    asyncio.run(debug_wanx_response())
