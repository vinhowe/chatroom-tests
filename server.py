from fastapi import FastAPI
from fastapi_socketio import SocketManager

app = FastAPI()
socket_manager = SocketManager(app=app)


@app.sio.on("ping")
async def handle_ping(sid):
    print("handling message")
    await socket_manager.emit("pong", to=sid)
