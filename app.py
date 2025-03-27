from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import requests
from flask import Flask, jsonify, request
from data_pb2 import AccountPersonalShowInfo
from google.protobuf.json_format import MessageToDict
import uid_generator_pb2
import threading
import time

app = Flask(__name__)

# متغيرات JWT
jwt_token = None
jwt_lock = threading.Lock()

# دالة لاستخراج التوكن من الاستجابة
def extract_token_from_response(data, region):
    if region == "IND":
        if data.get('status') in ['success', 'live']:
            return data.get('token')
    elif region in ["BR", "US", "SAC", "NA"]:
        if isinstance(data, dict) and 'token' in data:
            return data['token']
    else: 
        if data.get('status') == 'success':
            return data.get('token')
    return None

# دالة لجلب التوكن
def get_jwt_token_sync(region):
    global jwt_token
    endpoints = {
        "IND": "https://jwtgenerater.vercel.app/token?uid=3828066210&password=C41B0098956AE7B79F752FCA873C747060C71D3C17FBE4794F5EB9BD71D4DA95",
        "BR": "https://tokenalljwt.onrender.com/api/oauth_guest?uid=3787481313&password=JlOivPeosauV0l9SG6gwK39lH3x2kJkO",
        "US": "https://tokenalljwt.onrender.com/api/oauth_guest?uid=3787481313&password=JlOivPeosauV0l9SG6gwK39lH3x2kJkO",
        "SAC": "https://tokenalljwt.onrender.com/api/oauth_guest?uid=3787481313&password=JlOivPeosauV0l9SG6gwK39lH3x2kJkO",
        "NA": "https://tokenalljwt.onrender.com/api/oauth_guest?uid=3787481313&password=JlOivPeosauV0l9SG6gwK39lH3x2kJkO",
        "default": "https://projects-fox-x-get-jwt.vercel.app/get?uid=3763606630&password=7FF33285F290DDB97D9A31010DCAA10C2021A03F27C4188A2F6ABA418426527C"
    }    
    url = endpoints.get(region, endpoints["default"])
    with jwt_lock:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                token = extract_token_from_response(data, region)
                if token:
                    jwt_token = token
                    print(f"JWT Token for {region} updated successfully: {token[:50]}...")
                    return jwt_token
                else:
                    print(f"Failed to extract token from response for {region}")
            else:
                print(f"Failed to get JWT token for {region}: HTTP {response.status_code}")
        except Exception as e:
            print(f"Request error for {region}: {e}")   
    return None

# دالة لضمان الحصول على التوكن
def ensure_jwt_token_sync(region):
    global jwt_token
    if not jwt_token:
        print(f"JWT token for {region} is missing. Attempting to fetch a new one...")
        return get_jwt_token_sync(region)
    return jwt_token

# دالة لتحديث التوكن بشكل دوري
def jwt_token_updater(region):
    while True:
        get_jwt_token_sync(region)
        time.sleep(300)

# دالة لجلب رابط الـ API بناءً على المنطقة
def get_api_endpoint(region):
    endpoints = {
        "IND": "https://client.ind.freefiremobile.com/GetPlayerPersonalShow",
        "BR": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "US": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "SAC": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "NA": "https://client.us.freefiremobile.com/GetPlayerPersonalShow",
        "default": "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
    }
    return endpoints.get(region, endpoints["default"])

# مفاتيح التشفير
key = "Yg&tc%DEuh6%Zc^8"
iv = "6oyZDr22E3ychjM%"

# دالة لتشفير البيانات باستخدام AES
def encrypt_aes(hex_data, key, iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

# دالة لاستدعاء الـ API
def apis(idd, region):
    global jwt_token    
    token = ensure_jwt_token_sync(region)
    if not token:
        raise Exception(f"Failed to get JWT token for region {region}")    
    endpoint = get_api_endpoint(region)    
    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB48',
        'Content-Type': 'application/x-www-form-urlencoded',
    }    
    try:
        data = bytes.fromhex(idd)
        response = requests.post(
            endpoint,
            headers=headers,
            data=data,
            timeout=10
        )
        response.raise_for_status()
        return response.content.hex()
    except requests.exceptions.RequestException as e:
        print(f"API request to {endpoint} failed: {e}")
        raise

# دالة لتوفير المعلومات الخاصة باللاعب
@app.route('/accinfo', methods=['GET'])
def get_player_info():
    try:
        uid = request.args.get('uid')
        region = request.args.get('region', 'default').upper()
        custom_key = request.args.get('key', key)
        custom_iv = request.args.get('iv', iv)

        if not uid:
            return jsonify({"error": "UID parameter is required"}), 400

        threading.Thread(target=jwt_token_updater, args=(region,), daemon=True).start()

        # إنشاء طلب UID
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        protobuf_data = message.SerializeToString()

        hex_data = binascii.hexlify(protobuf_data).decode()
        encrypted_hex = encrypt_aes(hex_data, custom_key, custom_iv)

        # استدعاء الـ API
        api_response = apis(encrypted_hex, region)
        if not api_response:
            return jsonify({"error": "Empty response from API"}), 400

        # معالجة الاستجابة
        message = AccountPersonalShowInfo()
        message.ParseFromString(bytes.fromhex(api_response))

        # استخراج avatarId و equipedSkills فقط
        avatar_id = message.profile_info.avatar_id
        equiped_skills = list(message.profile_info.equiped_skills)

        # تكوين حقل "ID"
        id_list = [avatar_id] + equiped_skills

        # طباعة الاستجابة المعدلة
        return jsonify({"ID": id_list})

    except ValueError:
        return jsonify({"error": "Invalid UID format"}), 400

    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"error": f"Failure to process the data: {str(e)}"}), 500

# دالة لتوجيه الـ favicon
@app.route('/favicon.ico')
def favicon():
    return '', 404

if __name__ == "__main__":
    ensure_jwt_token_sync("default")
    app.run(host="0.0.0.0", port=5529)