from typing import Union
from .docker import NanoNode, NanoNodeRPC
from .queue import BlockQueue


def process_block_queue(block_queue: BlockQueue, node: Union[NanoNode, NanoNodeRPC], async_process=True):
    cnt, hashes = block_queue.flush(lambda block: node.process_block(block, async_process=async_process))
    return cnt, hashes


def process_blocks(blocks: list, node: Union[NanoNode, NanoNodeRPC], async_process=False):
    for block in blocks:
        node.process_block(block, async_process=async_process)


# TODO: REMOVE, USES CUSTOM EXPERIMENTAL RPC
def broadcast_block_queue(block_queue: BlockQueue, node: Union[NanoNode, NanoNodeRPC]):
    cnt, hashes = block_queue.flush(lambda block: node.broadcast_block(block))
    return cnt, hashes
