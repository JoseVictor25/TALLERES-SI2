import requests

try:
    res = requests.post("http://localhost:8000/api/v1/auth/web/login", json={"email": "jvua2001.jvua@gmail.com", "password": "wrongpassword"}, timeout=5)
    print("Status:", res.status_code)
    print("Response:", res.text)
except Exception as e:
    print("Error:", e)
