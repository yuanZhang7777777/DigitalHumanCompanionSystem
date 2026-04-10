import asyncio
import httpx
import os

async def test_dashscope():
    api_key = "sk-b13fc0297caf427c9bb3a6f14d8969f4"
    image_url = "https://lxczai.oss-cn-beijing.aliyuncs.com/avatars/test.jpg" # dummy
    
    api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": "wan2.6-i2v-flash",
        "input": {
            "image_url": image_url,
            "prompt": "a person speaking naturally, slight head movement, realistic, cinematic",
        },
        "parameters": {
            "size": "480*832",
            "duration": 5,
        },
    }
    
    print("Sending POST request to dashscope...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(api_url, headers=headers, json=payload)
        
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_dashscope())
