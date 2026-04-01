import requests
import json

BASE_URL = "http://localhost:8000"

def test_create_session():
    url = f"{BASE_URL}/api/auth/session"
    data = {"username": "测试用户"}
    response = requests.post(url, json=data)
    print(f"创建会话:")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.json()

def test_create_digital_person(user_id):
    url = f"{BASE_URL}/api/digital-person/"
    data = {
        "user_id": user_id,
        "name": "小明",
        "relationship": "朋友",
        "personality": "开朗、幽默、善解人意",
        "custom_prompt": "你是一个开朗幽默的朋友，总是能给对方带来欢乐。"
    }
    response = requests.post(url, json=data)
    print(f"\n创建数字人:")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.json()

def test_get_digital_persons(user_id):
    url = f"{BASE_URL}/api/digital-person/{user_id}"
    response = requests.get(url)
    print(f"\n获取数字人列表:")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.json()

if __name__ == "__main__":
    session_result = test_create_session()
    if session_result.get("success"):
        user_id = session_result["data"]["user_id"]
        print(f"\n用户ID: {user_id}")
        
        person_result = test_create_digital_person(user_id)
        
        list_result = test_get_digital_persons(user_id)