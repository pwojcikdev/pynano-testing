import multiprocessing
import queue
from typing import Protocol, Union
import nanolib

from .block_queue import BlockQueue

from . import env

from .common import *


class Block:
    def __init__(self, block_nlib: nanolib.Block, prev_block: "Block"):
        self.block_nlib = block_nlib
        self.prev_block = prev_block

    @property
    def balance(self):
        return self.block_nlib.balance

    @property
    def account(self):
        return self.block_nlib.account

    @property
    def representative(self):
        return self.block_nlib.representative

    @property
    def block_hash(self):
        return self.block_nlib.block_hash

    @property
    def send_amount(self):
        diff = self.prev_block.balance - self.balance
        if diff <= 0:
            raise ValueError("Not a send block")
        return diff

    def json(self) -> str:
        return self.block_nlib.json()

    def to_dict(self) -> dict:
        return self.block_nlib.to_dict()


class AccountId(Protocol):
    @property
    def account_id() -> str:
        # 'nano_(...) account str
        pass


class Chain:
    DEFAULT_WORK = "0000000000000000"

    def __init__(self, account_id, private_key, frontier=None):
        self.account_id = account_id
        self.private_key = private_key
        self.frontier = frontier

    @property
    def balance(self):
        return self.frontier.balance

    def send(
        self,
        account: Union["NanoWalletAccount", "Chain", str],
        amount,
        fork=False,
    ) -> Block:
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if not self.frontier:
            raise ValueError("Account not opened")

        destination_id = account_id_from_account(account)

        block_nlib = nanolib.Block(
            block_type="state",
            account=self.account_id,
            representative=self.frontier.representative,
            previous=self.frontier.block_hash,
            link_as_account=destination_id,
            balance=self.frontier.balance - amount,
        )
        block_nlib.sign(self.private_key)
        # block_nlib.solve_work(env.DIFFICULTY)
        block_nlib.set_work(self.DEFAULT_WORK)

        block = Block(block_nlib, self.frontier)
        BlockQueue.default().put(block)
        if not fork:
            self.frontier = block
        return block

    def receive(
        self,
        block: Block,
        representative=None,
        fork=False,
    ) -> Block:
        if not self.frontier:
            # open account

            if not representative:
                representative_id = env.DEFAULT_REPR
            else:
                representative_id = representative.account_id

            block_nlib = nanolib.Block(
                block_type="state",
                account=self.account_id,
                representative=representative_id,
                previous=None,
                link=block.block_hash,
                balance=block.send_amount,
            )
            block_nlib.sign(self.private_key)
            # block_nlib.solve_work(env.DIFFICULTY)
            block_nlib.set_work(self.DEFAULT_WORK)

            block = Block(block_nlib, None)

        else:
            if not representative:
                representative_id = self.frontier.representative
            else:
                representative = representative.account_id

            block_nlib = nanolib.Block(
                block_type="state",
                account=self.account_id,
                representative=representative_id,
                previous=self.frontier.block_hash,
                link=block.block_hash,
                balance=int(self.frontier.balance + block.send_amount),
            )
            block_nlib.sign(self.private_key)
            # block_nlib.solve_work(env.DIFFICULTY)
            block_nlib.set_work(self.DEFAULT_WORK)

            block = Block(block_nlib, self.frontier)

        BlockQueue.default().put(block)
        if not fork:
            self.frontier = block
        return block
