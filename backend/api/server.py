"""
Pont entre le moteur Python et l'interface Tauri, via WebSocket sur
localhost uniquement (aucune exposition réseau externe).
"""
import json
from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()
connected_clients: list[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        connected_clients.remove(websocket)


async def broadcast_event(event: dict):
    payload = json.dumps(event, ensure_ascii=False)
    for client in connected_clients:
        await client.send_text(payload)


def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
