from __future__ import annotations

import io
import json
import multiprocessing
import os
import queue
import random
import signal
import sys
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime
from decimal import *
from pprint import pprint
from random import random
from typing import NamedTuple, Protocol, Tuple, Union

import docker
import dotenv
import nano
import nanolib
from retry import retry

from . import env
from .chain import Block, BlockQueue, Chain
from .common import *


class NanoWalletAccount:
    def __init__(self, wallet: "NanoWallet", account_id, private_key):
        self.node = wallet.node
        self.wallet = wallet
        self.account_id = account_id
        self.private_key = private_key

    def __str__(self):
        return f"[{self.account_id} | balance: {self.balance} | pending: {self.pending}]"

    @property
    def balance(self):
        res = self.node.rpc.account_balance(self.account_id)
        return Decimal(res["balance"])

    @property
    def pending(self):
        res = self.node.rpc.account_balance(self.account_id)
        return Decimal(res["pending"])

    def send(self, account: Union["NanoWalletAccount", Chain, str], amount) -> Block:
        destination_id = account_id_from_account(account)

        block_hash = self.node.rpc.send(
            wallet=self.wallet.wallet_id,
            source=self.account_id,
            destination=destination_id,
            amount=int(amount),
        )

        block = self.node.block(block_hash)
        return block

    def to_chain(self) -> Chain:
        frontier_hash = self.node.rpc.account_info(self.account_id)["frontier"]
        frontier = self.node.block(frontier_hash)
        return Chain(self.account_id, self.private_key, frontier)


class NanoWallet:
    def __init__(self, node: "NanoNode", wallet_id):
        self.node = node
        self.wallet_id = wallet_id

    def create_account(self, private_key=None) -> NanoWalletAccount:
        if not private_key:
            seed = nanolib.generate_seed()
            private_key = nanolib.generate_account_private_key(seed, 0)

        account_id = self.node.rpc.wallet_add(wallet=self.wallet_id, key=private_key)
        return NanoWalletAccount(self, account_id, private_key)

    def set_represenetative(self, account):
        representative_id = account_id_from_account(account)
        self.node.rpc.wallet_representative_set(wallet=self.wallet_id, representative=representative_id)


BlockCount = namedtuple("BlockCount", ["checked", "unchecked", "cemented"])

AecInfo = namedtuple("AecInfo", ["confirmed", "unconfirmed", "confirmations"])


def block_to_json(block):
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        return json.dumps(block)
    return block.json()


class NanoNodeRPC:
    def __init__(self, rpc_address):
        self.rpc = nano.rpc.Client(rpc_address)

    @retry(tries=3, delay=0.5)
    def process_block(self, block: Union[Block, str], async_process=True):
        json = block_to_json(block)
        if async_process:
            payload = {"block": json, "async": async_process}
            res = self.rpc.call("process", payload)
            return res
        else:
            return self.rpc.process(json)

    @retry(tries=3, delay=0.5)
    def broadcast_block(self, block: Union[Block, str]):
        json = block_to_json(block)
        payload = {"block": json}
        res = self.rpc.call("broadcast", payload)
        return res


class NanoNode:
    def __init__(self, container, node_env):
        self.container = container
        self.node_env = node_env

    @property
    def rpc_address(self):
        return f"http://localhost:{self.host_rpc_port}"

    def __str__(self):
        count = self.block_count
        aec = self.aec
        return f"[{self.full_name: <32} | port: {self.host_rpc_port: <5} | peers: {len(self.peers): >4} | checked: {count.checked: >9} | cemented: {count.cemented: >9} | unchecked: {count.unchecked: >9} | aec: {aec.unconfirmed: >5})]"

    def start(self):
        self.container.start()
        self.container.reload()

        # if threre was an immediate error starting the node this will error
        assert self.container.status == "running"

        # for log in self.container.logs(stream=True):
        # print(log)

        # print(container.ports)

        self.rpc = nano.rpc.Client(self.rpc_address)
        self.rpc_node = NanoNodeRPC(self.rpc_address)

        # self.ensure_started()

        print("Starting:", self.name)

    def stop(self):
        print("Stopping:", self.name)

        if self.container.status != "exited":
            self.rpc.stop()

        self.ensure_stopped()

    @retry(tries=50, delay=0.5)
    def ensure_started(self):
        self.rpc.version()
        print("Started:", self.name)

    @retry(delay=0.5)
    def ensure_stopped(self):
        self.container.reload()
        if self.container.status != "exited":
            raise ValueError(f"status: {self.container.status} != exited")
        print("Stopped:", self.name)

    @property
    def host_rpc_port(self):
        return int(self.container.ports[f"{env.RPC_PORT}/tcp"][0]["HostPort"])

    @property
    def host_realtime_port(self):
        return int(self.container.ports[f"{env.REALTIME_PORT}/tcp"][0]["HostPort"])

    @property
    def full_name(self) -> str:
        return self.container.name

    @property
    def name(self) -> str:
        return self.full_name.replace(f"{env.PREFIX}_", "")

    @property
    def block_count(self) -> BlockCount:
        block_count = self.rpc.block_count()
        checked = int(block_count["count"])
        unchecked = int(block_count["unchecked"])
        cemented = int(block_count["cemented"])
        return BlockCount(checked, unchecked, cemented)

    @property
    def peers(self):
        return self.rpc.peers()

    def create_wallet(self, private_key=None, use_as_repr=False):
        wallet_id = self.rpc.wallet_create()
        wallet = NanoWallet(self, wallet_id)
        account = wallet.create_account(private_key=private_key)
        if use_as_repr:
            wallet.set_represenetative(account)
        return wallet, account

    def setup_genesis(self) -> Tuple[NanoWallet, NanoWalletAccount]:
        wallet, account = self.create_wallet(
            private_key=self.node_env["NANO_TEST_GENESIS_PRIV"],
        )
        return wallet, account

    def process_block(self, block: Block, async_process=True):
        return self.rpc_node.process_block(block, async_process=async_process)

    def block(self, hash: str, load_previous=False) -> Block:
        block_nlib = self.__nlib_block(hash)

        if load_previous and block_nlib.previous:
            # TODO: properly extracting previous block based on type
            prev_block = self.block(block_nlib.previous, load_previous=False)
            block = Block(block_nlib, prev_block)
        else:
            block = Block(block_nlib, None)

        return block

    def __nlib_block(self, hash):
        block_dict = self.rpc.block(hash)
        block_nlib = nanolib.Block.from_dict(block_dict, verify=False)
        return block_nlib

    def populate_backlog(self):
        res = self.rpc.call("populate_backlog")
        return True

    def try_populate_backlog(self):
        try:
            self.populate_backlog()
        except:
            print("Could not populate backlog:", self.full_name)

    @property
    def stat_objects(self):
        res = self.rpc.call("stats", {"type": "objects"})
        return res

    @property
    def aec(self):
        res = self.rpc.call("confirmation_active")
        confirmed = int(res["confirmed"])
        unconfirmed = int(res["unconfirmed"])
        confirmations = res["confirmations"]
        return AecInfo(confirmed, unconfirmed, confirmations)

    # TODO: Use pull_data
    def pull_ledger(self):
        self.container.reload()
        assert self.container.status == "exited"

        bits, stat = self.container.get_archive(f"{env.NANO_DATA_PATH}/data.ldb")
        return read_all(bits)

    # TODO: Use push_data
    def push_ledger(self, ledger):
        self.container.reload()
        assert self.container.status in {"exited", "created"}

        self.container.put_archive(f"{env.NANO_DATA_PATH}/", ledger)

    def pull_data(self, path=f"{env.NANO_DATA_PATH}"):
        self.container.reload()
        assert self.container.status == "exited"

        bits, stat = self.container.get_archive(path)
        return read_all(bits)

    def push_data(self, data, path=f"{env.NANO_DATA_PATH}"):
        self.container.reload()
        assert self.container.status in {"exited", "created"}

        self.container.put_archive(os.path.dirname(path), data)

    def print_confirmations(self):
        for root in self.aec.confirmations:
            res = self.rpc.call(
                "confirmation_info",
                {"root": root, "json_block": "true", "representatives": "true"},
            )
            pprint(res)

    def ensure_all_confirmed(self, blocks=None, populate_backlog=False):
        def ensure_synchronized():
            block_count = self.block_count
            if block_count.unchecked != 0:
                raise ValueError("checked not synced")
            if block_count.checked != block_count.cemented:
                raise ValueError("not all cemented")
            if self.aec.unconfirmed != 0:
                raise ValueError("aec unconfirmed not 0")

            if populate_backlog:
                self.try_populate_backlog()

        ensure_synchronized()

        if blocks:
            for block in blocks:
                self.block(hash_from_block(block))


def extract_nodes(nodes: Union[NanoNet, NanoNode, list[NanoNode]]):
    if isinstance(nodes, NanoNet):
        nodes = nodes.nodes
    if isinstance(nodes, NanoNode):
        nodes = [nodes]
    return nodes


@title_bar(name="NODES")
def print_nodes(nodes: Union[NanoNet, NanoNode, list[NanoNode]]):
    nodes = extract_nodes(nodes)
    for node in nodes:
        print(node)


@title_bar(name="ENSURE ALL CONFIRMED")
def ensure_all_confirmed(nodes: Union[NanoNet, NanoNode, list[NanoNode]], blocks=None, populate_backlog=False):
    nodes = extract_nodes(nodes)

    @retry(delay=0.5)
    def ensure_all_confirmed_loop():
        print_nodes(nodes)

        if populate_backlog:
            for node in nodes:
                node.try_populate_backlog()

        cemented_min = min([node.block_count.cemented for node in nodes])
        cemented_max = max([node.block_count.cemented for node in nodes])
        if cemented_min != cemented_max:
            raise ValueError("cemented min != max")

        for node in nodes:
            node.ensure_all_confirmed(blocks)

    ensure_all_confirmed_loop()

    print_nodes(nodes)


class NodeWalletAccountTuple(NamedTuple):
    node: NanoNode
    wallet: NanoWallet
    account: NanoWalletAccount


class NanoNet:
    def __init__(self, network_type="test"):
        self.runid = self.__generate_runid()
        self.nodes: list[NanoNode] = []
        self.__node_containers: list[NanoNode] = []
        self.network_type = network_type
        self.__default_ledger = None
        self.client = docker.from_env()
        self.node_env = dotenv.dotenv_values("node.env")

    def __generate_runid(self):
        dt = datetime.now()
        s = dt.strftime("%Y-%m-%d_%H-%M-%S")
        return f"{env.PREFIX}_{s.replace(' ', '_')}"

    @staticmethod
    def create(network_type="test"):
        nanonet = NanoNet(network_type=network_type)
        nanonet.__setup()
        return nanonet

    @staticmethod
    def attach():
        nanonet = NanoNet()
        nanonet.__attach()
        return nanonet

    @staticmethod
    def load(data):
        nanonet = NanoNet()
        nanonet.__setup()
        nanonet.__load(data)
        return nanonet

    @title_bar(name="ATTACH NANONET")
    def __attach(self):
        for container in self.client.containers.list(all=True, filters={"name": f"{env.PREFIX}_node-"}):
            print("attach node:", container.name)

            self.__node_containers.append(container)
            node = NanoNode(container, self.node_env)
            self.nodes.append(node)

            pass
        pass

    @title_bar(name="SETUP NANONET")
    def __setup(self):
        print("Run ID:", self.runid)

        self.__cleanup_docker()
        self.__setup_network()
        # self.__setup_genesis_node()
        # self.__setup_burn()

    @title_bar(name="SAVE NANONET")
    def save(self):
        data = {}
        for node in self.nodes:
            node.stop()
            d = node.pull_data()
            data[node.name] = d
        return data

    @title_bar(name="LOAD NANONET")
    def __load(self, data):
        for i, (name, d) in enumerate(data.items()):
            print("loading node:", name, "data:", len(d))
            self.create_node(name=name, data=d)

    def stop(self):
        # self.__cleanup_docker()
        pass

    def __setup_burn(self):
        burn_amount = int(self.node_env["NANO_TEST_BURN_AMOUNT_RAW"])
        self.genesis.account.send(env.BURN_ACCOUNT, burn_amount)

    def setup_genesis_node(self, ledger=None):
        node = self.create_node(do_not_peer=True, name="genesis", ledger=ledger)
        wallet, account = node.setup_genesis()
        self.__genesis = NodeWalletAccountTuple(node, wallet, account)

    @property
    def genesis(self) -> NodeWalletAccountTuple:
        return self.__genesis

    def __setup_network(self):
        self.network_name = f"{env.PREFIX}_network"
        try:
            self.network = self.client.networks.get(self.network_name)
        except:
            self.network = self.client.networks.create(self.network_name, check_duplicate=True)

    @title_bar(name="CLEANUP DOCKER")
    def __cleanup_docker(self):
        for cont in self.client.containers.list(all=True):
            if cont.name.startswith(env.PREFIX):
                print("Removing:", cont.name)
                cont.remove(force=True)

    def set_default_ledger(self, ledger):
        self.__default_ledger = ledger

    @title_bar(name="CREATE NODE")
    def create_node(
        self,
        image_name: str = env.NODE_IMAGE,
        node_flags: list[str] = [],
        do_not_peer=False,
        name=None,
        cpu_limit: int = env.CPU_LIMIT,  # None for unlimited
        track=True,
        prom_exporter=True,
        ledger: bytes = None,
        ledger_path: str = None,
        data: bytes = None,
        data_path: str = None,
        redirect_rpc=True,
        rpc_port: int = None,
        redirect_realtime=True,
        realtime_port: int = None,
        use_ramdisk=env.RAMDISK,
        tcpdump=env.TCPDUMP,
    ) -> NanoNode:
        print("name:", name)

        # Ensure that only one of the params is set
        assert sum(x is not None for x in (ledger, ledger_path, data, data_path)) <= 1

        node_flags = [*env.DEFAULT_NODE_FLAGS, *node_flags]

        cli_flags = " ".join([f"--{flag}" for flag in node_flags])

        node_cli_options = f"--network={self.network_type} --data_path {env.NANO_DATA_PATH}"

        if tcpdump:
            node_cli_options = f"delay {node_cli_options}"

        # node_main_command = f"nano_node daemon {node_cli_options} --config node.peering_port=17075 {additional_cli} -l"
        node_main_command = f"nano_node --daemon {node_cli_options} {cli_flags} {env.NODE_FLAGS}"

        node_env = self.node_env

        if not do_not_peer and len(self.nodes) > 0:
            # peer_name = self.genesis.node.container.name
            peer_name = self.nodes[0].container.name
            print("peer name:", peer_name)
            node_env = {
                "NANO_DEFAULT_PEER": peer_name,
                "NANO_TEST_PEER_NETWORK": peer_name,
                **node_env,
            }
        else:
            node_env = {
                "NANO_DEFAULT_PEER": "0",
                "NANO_TEST_PEER_NETWORK": "0",
                **node_env,
            }

        if not name:
            name = f"{env.PREFIX}_node-{len(self.__node_containers)}"
        else:
            name = f"{env.PREFIX}_node-{name}"

        if cpu_limit:
            assert cpu_limit > 0
            nano_cpus = cpu_limit * 1000000000
            node_env = {
                "NANO_HARDWARE_CONCURRENCY": str(cpu_limit),
                **node_env,
            }
        else:
            nano_cpus = None

        volumes = [
            f"{os.path.abspath('./node-config/config-node.toml')}:/root/Nano/config-node.toml",
            f"{os.path.abspath('./node-config/config-rpc.toml')}:/root/Nano/config-rpc.toml",
        ]
        if data_path:
            volumes = [
                f"{os.path.expanduser(data_path)}:/root/Nano/",
                *volumes,
            ]
        if ledger_path:
            volumes = [
                f"{os.path.expanduser(ledger_path)}:/root/Nano/data.ldb",
                *volumes,
            ]
        print("volumes:", volumes)

        ports = {}
        if redirect_rpc:
            if not rpc_port and env.BASE_RPC_PORT:
                rpc_port = env.BASE_RPC_PORT + len(self.__node_containers)
            ports = {
                env.RPC_PORT: rpc_port,
                **ports,
            }
        if redirect_realtime:
            if not realtime_port and env.BASE_REALTIME_PORT:
                realtime_port = env.BASE_REALTIME_PORT + len(self.__node_containers)
            ports = {
                env.REALTIME_PORT: realtime_port,
                **ports,
            }
        print("ports:", ports)

        tmpfs = None
        if use_ramdisk:
            if data_path or ledger_path:
                print("cannot use ramdisk")
            else:
                tmpfs = {"/root/Nano/": ""}

        labels = {"runid": self.runid}

        # network throttling
        labels = {
            "com.docker-tc.enabled": "1",
            "com.docker-tc.limit:": "10mbit",
            "com.docker-tc.delay": "40ms",
            **labels,
        }

        container = self.client.containers.create(
            image_name,
            node_main_command,
            detach=True,
            environment=node_env,
            name=name,
            network=self.network_name,
            ports=ports,
            volumes=volumes,
            nano_cpus=nano_cpus,
            tmpfs=tmpfs,
            labels=labels,
            cap_add=["NET_ADMIN"],
        )

        self.__node_containers.append(container)

        node = NanoNode(container, self.node_env)

        if track:
            self.nodes.append(node)

        if not ledger:
            if self.__default_ledger:
                ledger = self.__default_ledger

        if ledger:
            node.push_ledger(ledger)
        if data:
            node.push_data(data)

        node.start()

        if tcpdump:
            self.create_tcpdump(node)

        if prom_exporter:
            self.create_prom_exporter(node)

        node.ensure_started()

        return node

    def create_prom_exporter(self, node: NanoNode):
        command = (
            f"--host 127.0.0.1 --port {node.host_rpc_port} --hostname {node.name} --interval 1 --runid {self.runid}"
        )

        container_name = f"{env.PREFIX}_promexport_{node.name}"

        container = self.client.containers.run(
            env.PROM_IMAGE,
            command,
            detach=True,
            name=container_name,
            network_mode="host",
            pid_mode=f"container:{node.container.id}",
        )

        print("Started exporter:", container.name)

    def create_tcpdump(self, node: NanoNode):
        command = f"tcpdump -i all -w /data/{node.name}.pcap"

        container_name = f"{env.PREFIX}_tcpdump_{node.name}"

        volumes = [
            f"{env.TCPDUMP_PATH.joinpath(self.runid).expanduser()}/:/data/",
        ]

        container = self.client.containers.run(
            env.NETSHOOT_IMAGE,
            command,
            detach=True,
            name=container_name,
            network_mode=f"container:{node.container.id}",
            volumes=volumes,
        )

        print("Started tcpdump:", container.name)

    def ensure_all_confirmed(self, blocks=None, populate_backlog=False):
        ensure_all_confirmed(self.nodes, blocks=blocks, populate_backlog=populate_backlog)


def random_chain() -> Chain:
    seed = nanolib.generate_seed()
    account_id = nanolib.generate_account_id(seed, 0)
    private_key = nanolib.generate_account_private_key(seed, 0)
    return Chain(account_id, private_key)


def default_nanonet():
    global _default_nanonet
    return _default_nanonet


def initialize(network_type="test"):
    env.print_env_info()

    signal.signal(signal.SIGINT, signal_handler)

    nanonet = NanoNet.create(network_type)

    global _default_nanonet
    _default_nanonet = nanonet

    return nanonet


def signal_handler(signal, frame):
    print("SIGINT or CTRL-C detected. Exiting gracefully")

    global _default_nanonet
    if _default_nanonet:
        _default_nanonet.stop()

    sys.exit(0)


if __name__ == "__main__":
    initialize()
