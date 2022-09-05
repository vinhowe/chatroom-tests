import asyncio
import random
import aiohttp
import socketio
import uuid


async def post_signup(url, session, treatment):
    token = uuid.uuid4().hex
    response = await session.post(
        url + "/signup", json={"linkId": token, "treatment": treatment}
    )
    assert response.status == 200
    return token


async def post_initial_view(url, session, token, view):
    response = await session.post(
        url + "/initial-view", json={"view": view}, headers={"X-AUTH-CODE": token}
    )
    assert response.status == 200


async def connect_to_waiting_room(url, token):
    sio = socketio.AsyncClient()

    @sio.event
    async def connect():
        print("connected to waitroom")

    @sio.event
    async def redirect(data):
        print(data, "from waitroom")

    @sio.event
    async def disconnect():
        print("disconnected from waitroom")

    print("URL:", url + "/waiting-room", "/ws/socket.io")

    await sio.connect(
        url + "/waiting-room",
        socketio_path="/ws/socket.io",
        wait_timeout=10,
        auth={"token": token},
    )
    await sio.wait()


async def main(url, session, treatment, view):
    wait = random.randint(1, 5)
    await asyncio.sleep(wait)

    token = await post_signup(url, session, treatment)
    print(token)
    await post_initial_view(url, session, token, view)
    print("going into the waiting room with", treatment, view)
    await connect_to_waiting_room(url, token)


async def make_requests(url):
    users = [
        {"treatment": 1, "view": "guns don't kill people, people do."},
        {
            "treatment": 5,
            "view": "guns are too danguous to be in the hands of lunatics",
        },
    ]
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            *[main(url, session, user["treatment"], user["view"]) for user in users]
        )


if __name__ == "__main__":
    # url = "http://localhost:8005"
    url = "http://192.168.200.98:8000"
    asyncio.run(make_requests(url))
