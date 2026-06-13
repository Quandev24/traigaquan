import urllib.request
import json

BASE = 'http://127.0.0.1:5000'

# Login
login_data = json.dumps({"username": "admin", "password": "admin123"}).encode()
req = urllib.request.Request(f'{BASE}/api/auth/login', data=login_data,
    headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
token_data = json.loads(resp.read())
token = token_data.get('access_token') or token_data.get('token')
print('=== LOGIN ===')
print(f'Token: {token[:40]}...' if token else 'No token!')
print()

def api_call(path):
    url = f'{BASE}{path}'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

print('=== HEALTH ===')
print(json.dumps(api_call('/health'), indent=2))
print()

print('=== CAMERA 2 LIST ===')
cameras = api_call('/api/camera/camera2/list')
for c in cameras:
    w = c.get('worker')
    status = 'RUNNING' if w and w.get('running') else 'STOPPED'
    print(f'  [{status}] {c["name"]} (ID: {c["device_id"]})')
    print(f'         Coop:   {c["coop_name"]}')
    print(f'         URL:    {c["stream_url"]}')
    print(f'         Enable: {c["stream_enabled"]}')
    print(f'         Skip:   {c["frame_skip"]}')
    print(f'         Worker: {json.dumps(w, indent=4) if w else "None"}')
    print()

print('=== DETECTION STATUS ALL ===')
data = api_call('/api/camera/detection/status-all')
print(f'Health: {json.dumps(data.get("health"), indent=2)}')
for cam in data.get('cameras', []):
    s = 'RUNNING' if cam.get('running') else 'STOPPED'
    print(f'  [{s}] Cam {cam["device_id"]} - Frames: {cam.get("frame_count", 0)}, Proc: {cam.get("processed_count", 0)}')
print()

if data.get('cameras'):
    first = data['cameras'][0]
    print(f'Worker keys: {list(first.keys())}')
