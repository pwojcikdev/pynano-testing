import asyncio
from typing import Protocol
from .common import title_bar

from nanoprotocol.blocks import BlockWrapper
from nanoprotocol import channel
from nanoprotocol import blocks
from nanoprotocol.channel import Channel

from tqdm.asyncio import tqdm


class NanoBroadcaster(Protocol):
    async def publish(self, block: dict):
        pass

    async def publish_all(self, blocks: list[dict]):
        pass


class NanoNodeBroadcaster:
    def __init__(self, node: "NanoNode"):
        self.node = node

    async def connect(self):
        self.channel = await self.__setup_channel()

    async def __setup_channel(self):
        print("connect:", self.node.host_realtime_port)
        return await Channel.connect("localhost", self.node.host_realtime_port)

    async def publish(self, block_dict: dict):
        try:
            block_wrapper = blocks.block_from_dict(block_dict)
            await self.channel.publish_block(block_wrapper)
        except Exception as e:
            print("publish_block error:", e)
            raise

    async def publish_all(self, blocks: list[dict]):
        print("publish_all:", len(blocks))

        # async with tqdm(total=len(blocks), desc="Publishing Blocks") as pbar:  # Initialize the progress bar
        # for block in blocks:
        #     await self.publish(block)
        #     pbar.update(1)  # Update the progress bar after each block is published

        for block in blocks:
            await self.publish(block)


class NanoNetBroadcaster:
    def __init__(self, nanonet: "NanoNet"):
        self.broadcasters = [NanoNodeBroadcaster(node) for node in nanonet.nodes]
        asyncio.run(self.async_connect_all())

    async def async_connect_all(self):
        tasks = [broadcaster.connect() for broadcaster in self.broadcasters]
        await asyncio.gather(*tasks)

    async def async_publish_all(self, blocks: list[dict]):
        print("net broadcasting:", len(blocks))

        # async with tqdm(total=len(blocks) * len(self.broadcasters), desc="Net Broadcasting") as pbar:
        #     tasks = [self.__publish_blocks_with_progress(broadcaster, blocks, pbar) for broadcaster in self.broadcasters]
        #     await asyncio.gather(*tasks)

        tasks = [self.__publish_blocks(broadcaster, blocks) for broadcaster in self.broadcasters]
        await asyncio.gather(*tasks)

        print("done net broadcasting")

    async def __publish_blocks_with_progress(self, broadcaster, blocks, pbar):
        await broadcaster.publish_all(blocks)

    async def __publish_blocks(self, broadcaster, blocks):
        await broadcaster.publish_all(blocks)

    def publish_all(self, blocks: list[dict]):
        asyncio.run(self.async_publish_all(blocks))
