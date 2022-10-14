import asyncio
import random
import aiohttp
import socketio
import uuid
import json

stats = {
    "n_in_waitroom": 0,
    "n_in_chatroom": 0,
    "n_messages_sent": 0,
    "n_messages_received": 0,
}


MESSAGE_WAIT = 1
NUM_MESSAGES = 10
NUM_USERS = 10


async def post_signup(url, session, treatment):
    token = uuid.uuid4().hex
    response = await session.post(
        url + "/signup", json={"linkId": token, "treatment": treatment}
    )
    # print(await response.text())
    assert response.status == 200
    return token


async def post_initial_view(url, session, token, view):
    response = await session.post(
        url + "/initial-view", json={"view": view}, headers={"X-AUTH-CODE": token}
    )
    assert response.status == 200


async def get_user(url, session, token):
    response = await session.get(url + "/user", headers={"X-AUTH-CODE": token})
    return await response.json()


async def connect_to_waiting_room(url, token):
    sio = socketio.AsyncClient()
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    namespace = "/waiting-room"

    @sio.event(namespace=namespace)
    async def connect():
        print("connected to waitroom")
        stats["n_in_waitroom"] += 1

    @sio.event(namespace=namespace)
    async def redirect(data):
        future.set_result(data)

    @sio.event(namespace=namespace)
    async def disconnect():
        print("disconnected from waitroom")
        stats["n_in_waitroom"] -= 1

    await sio.connect(
        url,
        socketio_path="/ws/socket.io",
        wait_timeout=10,
        namespaces=namespace,
        auth={"token": token},
    )
    # await sio.wait()
    redirect_data = await future
    await sio.disconnect()
    return redirect_data


async def connect_to_chatroom(url, user):
    sio = socketio.AsyncClient()

    namespace = "/chatroom"
    logs = []

    @sio.event(namespace=namespace)
    async def connect():
        stats["n_in_chatroom"] += 1

    @sio.event(namespace=namespace)
    async def messages(data):
        for message in data:
            logs.append(message)

    @sio.event(namespace=namespace)
    async def new_message(data):
        logs.append(data)
        stats["n_messages_received"] += 1

    @sio.event(namespace=namespace)
    async def disconnect():
        stats["n_in_chatroom"] -= 1

    # print("about to connect to the chatroom with token", user["response_id"])
    await sio.connect(
        url,
        socketio_path="/ws/socket.io",
        wait_timeout=10,
        namespaces=namespace,
        auth={"token": user["response_id"]},
    )
    for _ in range(NUM_MESSAGES):
        message_id = uuid.uuid4().hex
        await sio.emit("message", {"body": message_id}, namespace=namespace)
        stats["n_messages_sent"] += 1
        await asyncio.sleep(MESSAGE_WAIT + (random.random() - 0.5) * (2 * MESSAGE_WAIT))
    await asyncio.sleep(MESSAGE_WAIT * 2)
    return logs


async def main(url, session, treatment):
    token = await post_signup(url, session, treatment)
    view = uuid.uuid4().hex
    print(token)
    await post_initial_view(url, session, token, view)
    print("going into the waiting room with", treatment, view)
    redirect = await connect_to_waiting_room(url, token)

    # get user id
    user = await get_user(url, session, token)

    if redirect["to"] != "chatroom":
        raise Exception(f"redirected to the wrong place, {redirect['to']}")

    logs = await connect_to_chatroom(url, user)
    return user["id"], logs


async def read_stats():
    for _ in range(MESSAGE_WAIT * NUM_MESSAGES):
        print(stats)
        stats["n_messages_sent"] = 0
        stats["n_messages_received"] = 0
        await asyncio.sleep(MESSAGE_WAIT)


async def make_requests(url):
    # a user is just a treatment #
    users = [3, 6] * (NUM_USERS // 2)
    random.shuffle(users)
    async with aiohttp.ClientSession() as session:
        user_logs = await asyncio.gather(
            *[main(url, session, user) for user in users], read_stats()
        )
    with open("logs.json", "w") as f:
        json.dump(dict(user_logs[:-1]), f)


if __name__ == "__main__":
    url = "http://localhost:8000"
    # url = "http://192.168.200.98:8000"
    asyncio.run(make_requests(url))
