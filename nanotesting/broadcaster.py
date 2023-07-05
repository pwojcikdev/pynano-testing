from concurrent.futures import ProcessPoolExecutor
from typing import Protocol
from .common import title_bar
from .docker import NanoNet, NanoNode

from nanoprotocol.blocks import BlockWrapper
from nanoprotocol import channel
from nanoprotocol import blocks
from nanoprotocol.channel import Channel


class NanoBroadcaster(Protocol):
    def publish(self, block: dict):
        pass

    def publish_all(self, blocks: list[dict]):
        pass


class NanoNodeBroadcaster:
    def __init__(self, node: NanoNode, parallelism=4):
        self.node = node
        self.pool = ProcessPoolExecutor(
            initializer=NanoNodeBroadcaster.setup_channel,
            initargs=(node.host_realtime_port,),
            max_workers=parallelism,
        )

    @staticmethod
    def setup_channel(port):
        print("connect:", port)
        global node_broadcaster_channel
        node_broadcaster_channel = Channel.connect("localhost", port)

    def publish(self, block_dict: dict):
        self.pool.submit(NanoNodeBroadcaster.publish_block, block_dict)

    @staticmethod
    def publish_block(block_dict: dict):
        # print("publish block:", block_dict)
        try:
            global node_broadcaster_channel
            block_wrapper = blocks.block_from_dict(block_dict)
            node_broadcaster_channel.publish_block(block_wrapper)
        except Exception as e:
            print("publish_block error:", e)
            raise

    @staticmethod
    def publish_all_blocks(blocks):
        print("publish_all_blocks:", len(blocks))
        for block in blocks:
            NanoNodeBroadcaster.publish_block(block)

    def publish_all(self, blocks: list[dict]):
        print("node publish:", len(blocks))
        # self.pool.map(NanoNodeBroadcaster.publish_block, blocks, chunksize=1024)
        # self.pool.map(NanoNodeBroadcaster.publish_block, blocks, chunksize=128)
        # self.pool.map(NanoNodeBroadcaster.publish_block, blocks, chunksize=16)
        return self.pool.submit(NanoNodeBroadcaster.publish_all_blocks, blocks)


class NanoNetBroadcaster:
    def __init__(self, nanonet: NanoNet, parallelism=4):
        self.broadcasters = [
            NanoNodeBroadcaster(node, parallelism=parallelism) for node in nanonet.nodes
        ]

    def publish(self, block: dict):
        for broadcaster in self.broadcasters:
            broadcaster.publish(block)

    def publish_all(self, blocks: list[dict]):
        print("net broadcasting:", len(blocks))

        # for broadcaster in self.broadcasters:
        #     broadcaster.publish_all(blocks)
        futures = [broadcaster.publish_all(blocks) for broadcaster in self.broadcasters]
        results = [future.result() for future in futures]

        print("done net broadcasting:", len(blocks))


@title_bar(name="BROADCAST PARALLEL")
def broadcast_parallel(nanonet: NanoNet, blocks: list[dict]):
    print("Broadcasting:", len(blocks))
    global broadcaster  # to avoid python bug where it just hangs when exiting function
    broadcaster = NanoNetBroadcaster(nanonet)
    broadcaster.publish_all(blocks)


class InMemoryBroadcaster:
    def __init__(self):
        self.__blocks = []

    def publish(self, block: dict):
        self.__blocks.append(block)

    def publish_all(self, blocks: list[dict]):
        self.__blocks += blocks

    def get_all(self):
        return self.__blocks
