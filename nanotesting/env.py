from environs import Env

from .common import *

env = Env()
env.read_env()

# prefix for all docker container names
PREFIX = env("NANO_FULLNET_PREFIX", default="fullnet")

# RPC
RPC_PORT = 17076
BASE_RPC_PORT = env.int("NANO_FULLNET_RPC_PORT", default=28000)
# REALTIME
REALTIME_PORT = 17075
BASE_REALTIME_PORT = env.int("NANO_FULLNET_REALTIME_PORT", default=38000)

if BASE_RPC_PORT == 0:
    BASE_RPC_PORT = None
if BASE_REALTIME_PORT == 0:
    BASE_REALTIME_PORT = None

BURN_ACCOUNT = "nano_1111111111111111111111111111111111111111111111111111hifc8npp"
DEFAULT_REPR = BURN_ACCOUNT
DIFFICULTY = "0000000000000000"

NODE_IMAGE = env("NANO_FULLNET_NODE_IMAGE", default="nano-node")
PROM_IMAGE = env("NANO_FULLNET_PROM_IMAGE", default="nano-prom-exporter")
NETSHOOT_IMAGE = env("NANO_FULLNET_NETSHOOT_IMAGE", default="nicolaka/netshoot")

NANO_DATA_PATH = "/root/Nano"

CPU_LIMIT = env.int("NANO_FULLNET_CPU_LIMIT", 4)
if CPU_LIMIT == 0:
    CPU_LIMIT = None

RAMDISK = env.bool("NANO_FULLNET_RAMDISK", False)
TCPDUMP = env.bool("NANO_FULLNET_TCPDUMP", False)

TCPDUMP_PATH = env.path("NANO_FULLNET_TCPDUMP_PATH", default="/data-raid/fullnet-tcpdump/")

DEFAULT_NODE_FLAGS = [
    # "disable_max_peers_per_ip",
    # "disable_max_peers_per_subnetwork",
]

NODE_FLAGS = env("NANO_FULLNET_NODE_FLAGS", default="")


@title_bar(name="ENV INFO")
def print_env_info():
    print("PREFIX:", PREFIX)
    print("NODE_IMAGE:", NODE_IMAGE)
    print("PROM_IMAGE:", PROM_IMAGE)
    print("NETSHOOT_IMAGE:", NETSHOOT_IMAGE)
    print("BASE_RPC_PORT:", BASE_RPC_PORT)
    print("BASE_REALTIME_PORT:", BASE_REALTIME_PORT)
    print("BURN_ACCOUNT:", BURN_ACCOUNT)
    print("DIFFICULTY:", DIFFICULTY)
    print("CPU_LIMIT:", CPU_LIMIT)
    print("RAMDISK:", RAMDISK)
    print("DEFAULT_NODE_FLAGS:", DEFAULT_NODE_FLAGS)
    print("NODE_FLAGS:", NODE_FLAGS)
