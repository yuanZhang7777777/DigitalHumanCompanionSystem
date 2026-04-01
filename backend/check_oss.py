import asyncio, os, sys
from motor.motor_asyncio import AsyncIOMotorClient
from app.services.video_service import VideoService
import logging

logging.basicConfig(level=logging.INFO)

async def check():
    db = AsyncIOMotorClient('mongodb://localhost:27017')['digital_companion']
    user = await db.users.find_one({})
    if not user:
        print('No user found.')
        return
        
    print(f"User: {user.get('username')} ({user['_id']})")
    
    dps = await db.digital_persons.find({'user_id': user['_id']}).to_list(100)
    print(f"\nFound {len(dps)} digital persons:")
    for dp in dps:
        print(f"- {dp.get('name')}: avatar={dp.get('avatar')}, video={dp.get('speaking_video_url')}")
        
    print('\nEnvironment:')
    
    # We check `.env` if available
    from dotenv import load_dotenv
    load_dotenv()
    
    ep = os.environ.get('OSS_ENDPOINT')
    bucket = os.environ.get('OSS_BUCKET_NAME')
    ak = os.environ.get('OSS_ACCESS_KEY_ID')
    
    print(f"OSS_ENDPOINT: {ep}")
    print(f"OSS_BUCKET_NAME: {bucket}")
    print(f"OSS_ACCESS_KEY_ID: {'Set (length ' + str(len(ak)) + ')' if ak else 'Not Set'}")
    
    if ak and ep and bucket:
        print("\nAttempting to connect to OSS...")
        try:
            service = VideoService()
            bucket_obj = service._get_oss_bucket()
            # Just do a simple list objects to verify connectivity
            print("Listing OSS objects (max 5):")
            for i, obj in enumerate(oss2.ObjectIterator(bucket_obj)):
                print(f" - {obj.key}")
                if i >= 4:
                    break
            print("OSS connection SUCCESSful.")
        except Exception as e:
            print(f"OSS connection FAILED: {e}")
            
if __name__ == '__main__':
    asyncio.run(check())
