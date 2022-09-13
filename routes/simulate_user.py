import asyncio
import random
import aiohttp
import socketio
import uuid

stats = {
    "n_in_waitroom": 0,
    "n_in_chatroom": 0, 
}

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


async def get_user(url, session, token):
    response = await session.get(
        url + "/user", headers={"X-AUTH-CODE": token}
    )
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
        print(stats)

    @sio.event(namespace=namespace)
    async def redirect(data):
        future.set_result(data)

    @sio.event(namespace=namespace)
    async def disconnect():
        print("disconnected from waitroom")
        stats["n_in_waitroom"] -= 1
        print(stats)

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

    @sio.event(namespace=namespace)
    async def connect():
        print("connected to chatroom")
        stats["n_in_chatroom"] += 1
        print(stats)
        rand = random.randint(0, 1000)
        await sio.emit(
            "message", {"body": f"first message {rand}"}, namespace=namespace
        )

    @sio.event(namespace=namespace)
    async def messages(data):
        print("messages:", data)

    @sio.event(namespace=namespace)
    async def new_message(data):
        # check if the message is from my sparing mate
        if user["id"] != data["user_id"]:
            # print("new message:", data)
            await asyncio.sleep(1)
            rand = random.randint(0, 1000)
            # print("sending message")
            await sio.emit(
                "message", {"body": f"another message! {rand}"}, namespace=namespace
            )

    @sio.event(namespace=namespace)
    async def disconnect():
        print("disconnected from chatroom")
        stats["n_in_chatroom"] -= 1
        print(stats)

    print("about to connect to the chatroom with token", user["response_id"])
    await sio.connect(
        url,
        socketio_path="/ws/socket.io",
        wait_timeout=10,
        namespaces=namespace,
        auth={"token": user["response_id"]},
    )
    await sio.wait()
    # redirect_data = await future
    # await sio.disconnect()
    # return redirect_data


async def main(url, session, treatment, view):
    # wait = random.randint(1, 5)
    # await asyncio.sleep(wait)

    token = await post_signup(url, session, treatment)
    print(token)
    await post_initial_view(url, session, token, view)
    print("going into the waiting room with", treatment, view)
    redirect = await connect_to_waiting_room(url, token)

    # get user id
    user = await get_user(url, session, token)

    locations = {
        "view": lambda: post_initial_view(url, session, token, view),
        "chatroom": lambda: connect_to_chatroom(url, user),
    }

    print(f"redirecting to {redirect['to']}")

    if redirect["to"] not in locations:
        raise Exception(f"Unknown redirect: {redirect['to']}")

    await locations[redirect["to"]]()


async def make_requests(url):
    users = [
        {"treatment": 1, "view": "guns don't kill people, people do."},
        {
            "treatment": 5,
            "view": "guns are too danguous to be in the hands of lunatics",
        },
    ] * 10
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            *[main(url, session, user["treatment"], user["view"]) for user in users]
        )


if __name__ == "__main__":
    url = "http://localhost:8005"
    # url = "http://192.168.200.98:8000"
    asyncio.run(make_requests(url))
