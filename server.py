from fastapi import FastAPI
from fastapi_socketio import SocketManager
import time

app = FastAPI()
socket_manager = SocketManager(app=app)

message_sid = None
count = 0
connected = 0

@app.sio.on("connect")
async def handle_connect(sid, *_):
    global message_sid, connected
    if message_sid is None:
        message_sid = sid
    connected += 1


@app.sio.on("disconnect")
async def handle_disconnect(sid, *_):
    global message_sid, connected
    if message_sid == sid:
        message_sid = None
    connected -= 1


@app.sio.on("ping")
async def handle_ping(sid):
    global message_sid, count
    if message_sid == sid:
        print(f"{connected = }, {count = }")
        count = 0

    count += 1

    # simulate blocking action
    time.sleep(0.01)

    await socket_manager.emit("pong", to=sid)
