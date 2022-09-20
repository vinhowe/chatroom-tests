import asyncio
import random
import aiohttp
import socketio
import uuid

stats = {
    "n_in_waitroom": 0,
    "n_in_chatroom": 0,
    "n_messages_sent": 0,
    "n_messages_received_from_partner": 0,
    "n_messages_received_from_self": 0,
    "partners": [],
}

MESSAGE_WAIT = 5
NUM_USERS = 500


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
    partner_id = None

    @sio.event(namespace=namespace)
    async def connect():
        print("connected to chatroom")
        stats["n_in_chatroom"] += 1
        rand = random.randint(0, 1000)
        await sio.emit(
            "message", {"body": f"first message {rand}"}, namespace=namespace
        )
        stats["n_messages_sent"] += 1

    @sio.event(namespace=namespace)
    async def messages(data):
        print("messages:", data)
        # find the partner id
        for message in data:
            if message["user_id"] != user["id"]:
                nonlocal partner_id
                partner_id = message["user_id"]
                stats["partners"].append((user["id"], partner_id))
                break

    @sio.event(namespace=namespace)
    async def new_message(data):

        # stats["n_messages"] += 1

        message_sender = data["user_id"]

        # make sure the message is from me or my partner
        nonlocal partner_id
        # if data["user_id"] not in [user["id"], partner_id]:
        #     print("message from unknown user", data, user, partner_id)
        assert message_sender in [user["id"], partner_id]
        assert (user["id"], partner_id) in stats["partners"]

        # check if the message is from my sparing mate
        if message_sender == partner_id:
            stats["n_messages_received_from_partner"] += 1
        else:
            stats["n_messages_received_from_self"] += 1

    @sio.event(namespace=namespace)
    async def disconnect():
        print("disconnected from chatroom")
        stats["n_in_chatroom"] -= 1

    print("about to connect to the chatroom with token", user["response_id"])
    await sio.connect(
        url,
        socketio_path="/ws/socket.io",
        wait_timeout=10,
        namespaces=namespace,
        auth={"token": user["response_id"]},
    )
    for message_id in range(100):
        await sio.emit(
            "message", {"body": f"message {message_id}"}, namespace=namespace
        )
        stats["n_messages_sent"] += 1
        await asyncio.sleep(MESSAGE_WAIT + (random.random() - 0.5) * (2 * MESSAGE_WAIT))
    await sio.wait()
    # redirect_data = await future
    # await sio.disconnect()
    # return redirect_data


async def main(url, session, treatment):
    # wait = random.randint(1, 5)
    # await asyncio.sleep(wait)

    token = await post_signup(url, session, treatment)
    view = "am i for gun control or against it? ask me a riddle and i'll tell you"
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


async def read_stats():
    while True:
        for key in [
            "n_in_waitroom",
            "n_in_chatroom",
            "n_messages_sent",
            "n_messages_received_from_partner",
            "n_messages_received_from_self",
        ]:
            print(key, ":", stats[key])
        stats["n_messages_sent"] = 0
        stats["n_messages_received_from_partner"] = 0
        stats["n_messages_received_from_self"] = 0
        await asyncio.sleep(MESSAGE_WAIT)


async def make_requests(url):
    # a user is just a treatment #
    users = [3, 6] * (NUM_USERS // 2)
    random.shuffle(users)
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(
            *[main(url, session, user) for user in users], read_stats()
        )


if __name__ == "__main__":
    url = "http://localhost:8005"
    # url = "http://192.168.200.98:8000"
    asyncio.run(make_requests(url))
