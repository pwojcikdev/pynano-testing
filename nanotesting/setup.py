from .caching import memory

from . import *
from . import docker
from .common import *


@title_bar(name="INITIALIZE REPRESENTATIVES")
def distribute_voting_weight_uniform(
    node: NanoNode,
    genesis_account: NanoWalletAccount,
    count,
    reserved_raw,
) -> list[Tuple[NanoWallet, NanoWalletAccount]]:
    reps = [node.create_wallet(use_as_repr=True) for n in range(count)]

    print("Genesis:", genesis_account)

    balance_left = genesis_account.balance - reserved_raw
    assert balance_left <= genesis_account.balance

    balance_per_rep = int(balance_left // count)
    assert balance_per_rep * count <= genesis_account.balance

    print("Balance per rep:", balance_per_rep, "x", count)

    def safe_send(source: NanoWalletAccount, target, amount, chunk_size=1000000000000000000000000000000 * 10000000):
        while amount > 0:
            amt = min(amount, chunk_size)
            source.send(target, amt)
            amount -= amt

    for rep_wallet, rep_account in reps:
        print("Seeding:", rep_account, "with:", balance_per_rep)

        # hsh = genesis_account.send(rep_account, balance_per_rep)
        safe_send(genesis_account, rep_account, balance_per_rep)

        ensure_all_confirmed(node, populate_backlog=True)

    return reps


@memory.cache
def setup_voting_weight_uniform_ledger(count, reserved_raw):
    nanonet = default_nanonet()
    setup_node = nanonet.create_node(name="setup", do_not_peer=True, track=False, prom_exporter=False)
    # setup_node = nanonet.create_node(name="setup", do_not_peer=True, track=False)

    genesis_wallet, genesis_account = setup_node.setup_genesis()
    # genesis_account.send(BURN_ACCOUNT, genesis_account.balance / 10)

    setup_reps = distribute_voting_weight_uniform(setup_node, genesis_account, count, reserved_raw)

    rep_keys = [rep_account.private_key for rep_wallet, rep_account in setup_reps]

    setup_node.stop()

    ledger = setup_node.pull_ledger()

    return ledger, rep_keys


@title_bar(name="SETUP VOTING WEIGHT UNIFORM")
def setup_voting_weight_uniform(count, reserved_raw) -> Tuple[NanoNet, list[NanoNode]]:
    nanonet = initialize()

    ledger, rep_keys = setup_voting_weight_uniform_ledger(count, reserved_raw)

    nanonet.set_default_ledger(ledger)

    nanonet.setup_genesis_node()

    def setup_rep_node(idx, key):
        node = nanonet.create_node(name=f"rep_{idx}")
        wallet = node.create_wallet(private_key=key)
        return node, wallet

    reps = [setup_rep_node(idx, key) for idx, key in enumerate(rep_keys)]

    nanonet.ensure_all_confirmed(populate_backlog=True)

    return nanonet, reps, rep_keys


@title_bar(name="SETUP LEDGER")
def setup_ledger(ledger, rep_keys):
    nanonet = initialize()

    nanonet.set_default_ledger(ledger)

    nanonet.setup_genesis_node()

    def setup_rep_node(idx, key):
        node = nanonet.create_node(name=f"rep_{idx}")
        wallet = node.create_wallet(private_key=key)
        return node, wallet

    reps = [setup_rep_node(idx, key) for idx, key in enumerate(rep_keys)]

    return nanonet, reps


@title_bar(name="SETUP EMPTY")
def setup_empty():
    nanonet = initialize()
    # nanonet.setup_genesis_node()
    return nanonet
