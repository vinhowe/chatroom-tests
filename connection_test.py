import asyncio
import socketio
from multiprocessing import Pool


async def main():
    sio = socketio.AsyncClient()
    url = "http://localhost:8080"

    @sio.event
    async def connect():
        # print("connection established")
        await sio.emit("ping")

    @sio.event
    async def pong():
        # print("pong received; sending pingin 1s")
        await sio.sleep(1)
        await sio.emit("ping")

    @sio.event
    async def disconnect():
        print("disconnected from server")

    await sio.connect(url, socketio_path="/ws/socket.io")
    await sio.wait()


async def gatherer(n):
    await asyncio.gather(*[main() for _ in range(n)])


def connect_n(n: int, batch: int):
    print(f"making {batch * n}-{(batch + 1) * n} connections")
    asyncio.run(gatherer(n))


if __name__ == "__main__":
    # Run on a bunch of different processes
    num_pools = 10
    batch_size = 50
    with Pool(num_pools) as pool:
        a = pool.starmap(connect_n, [(batch_size, i) for i in range(num_pools)])
