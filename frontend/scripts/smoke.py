"""Exercise the Vite proxy and local FastAPI with a generated image."""
import os
import time
import cv2
import httpx
import numpy as np

base = os.environ.get('SMOKE_BASE_URL', 'http://127.0.0.1:5173')
token = os.environ['SMOKE_API_TOKEN']
headers = {'Authorization': f'Bearer {token}'}
image = cv2.imencode('.png', np.zeros((8, 8, 3), dtype=np.uint8))[1].tobytes()
with httpx.Client(base_url=base, timeout=60) as client:
    client.get('/').raise_for_status()
    response = client.post('/api/v1/media', headers=headers, data={'authorized': 'true'}, files={'file': ('demo.png', image, 'image/png')})
    response.raise_for_status()
    response = client.post('/api/v1/tasks/analyze', headers=headers, json={'media_id': response.json()['data']['media_id']})
    response.raise_for_status()
    task = response.json()['data']['task_id']
    client.post(f'/api/v1/tasks/{task}/run-demo', headers=headers).raise_for_status()
    for _ in range(60):
        response = client.get(f'/api/v1/tasks/{task}', headers=headers)
        response.raise_for_status()
        state = response.json()['data']
        if state['status'] in ('succeeded', 'failed'):
            break
        time.sleep(0.5)
    if state['status'] != 'succeeded':
        raise RuntimeError(f'Task did not complete: {state}')
    people = client.get('/api/v1/graph/persons', headers=headers, params={'task_id': task})
    edges = client.get('/api/v1/graph/relations', headers=headers, params={'task_id': task})
    audit = client.get('/api/v1/audit/events', headers=headers)
    result = client.get(f'/api/v1/tasks/{task}/result', headers=headers)
    for response in (people, edges, audit, result):
        response.raise_for_status()
    assert len(people.json()['data']) == 2 and len(edges.json()['data']) == 1
    assert audit.json()['data'] and result.json()['data']['synthetic_input'] is True
    print('Vite proxy -> FastAPI: upload, mock analysis, graph and audit passed')
