# load_test.py — Submit this with your project
import concurrent.futures
import requests
import time

BASE_URL = 'http://16.176.5.125:8080'

def make_request(i):
    start = time.time()
    # Hitting the /health endpoint to guarantee a 200 OK response
    resp = requests.get(f'{BASE_URL}/health')
    elapsed = time.time() - start
    return {'id': i, 'status': resp.status_code, 'time': round(elapsed, 3)}

print(f"Starting load test on {BASE_URL}...")
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
    results = list(pool.map(make_request, range(20)))

for r in results:
    print(f"Request {r['id']}: [{r['status']}] in {r['time']}s")

# All 20 requests should complete successfully