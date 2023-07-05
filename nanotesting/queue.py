from contextlib import contextmanager
import multiprocessing
import queue


class BlockQueue:
    _instance = None

    def __init__(self):
        self.__queue = multiprocessing.Queue()
        self.__all = None

    def close(self):
        self.__all = self.__wait_all()
        self.__queue.close()

    @classmethod
    @contextmanager
    def create(cls):
        prev = cls._instance
        cls._instance = BlockQueue()
        try:
            yield cls._instance
        finally:
            cls._instance.close()
            cls._instance = prev

    @classmethod
    def default(cls):
        if cls._instance is None:
            raise Exception("Missing BlockQueue context")
        return cls._instance

    def put(self, block):
        # print("  put:", block.block_hash)
        self.__queue.put(block.to_dict())

    def __wait_all(self) -> list[dict]:
        q = []
        # print("begin blocks awaiting")
        try:
            while True:
                block = self.__queue.get(timeout=1)
                q.append(block)
        except queue.Empty:
            pass
        print("blocks awaited:", len(q))
        return q

    def get_all(self) -> list[dict]:
        if not self.__all:
            raise Exception("BlockQueue not ready")
        else:
            return self.__all

    def flush(self, sink):
        l = self.get_all()
        print("flushing blockqueue:", len(l))
        hashes = [sink(block) for block in l]
        return len(l), hashes
