import io
import nanolib
from decorator import decorator


def account_id_from_account(account):
    if hasattr(account, "account_id"):
        account_id = account.account_id
    else:
        account_id = account
    return account_id


def env_data_to_list(env: dict) -> list:
    return [f"{key}={value}" for (key, value) in env.items()]


def hash_from_block(block):
    if isinstance(block, dict):
        block_nlib = nanolib.Block.from_dict(block, verify=False)
        return block_nlib.block_hash
    raise ValueError("unknown block type")


def strike(text):
    result = ""
    for c in text:
        result = result + c + "\u0336"
    return result


@decorator
def title_bar(func, name=None, no_header=False, no_footer=False, *args, **kw):
    if not no_header:
        print(f"================ {name} ================")

    result = func(*args, **kw)

    if not no_footer:
        print(f"================ {strike(name)}")

    return result


def read_all(bits):
    with io.BytesIO() as f:
        for chunk in bits:
            f.write(chunk)
        f.seek(0)
        data = f.read()
        return data
