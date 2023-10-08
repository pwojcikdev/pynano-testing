import io
import tarfile

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


def remove_files_from_tar(tar_bytes, ignored_files):
    original_tar = tarfile.open(fileobj=io.BytesIO(tar_bytes))
    new_tar_bytes = io.BytesIO()

    # Open a new tarfile to write to
    with tarfile.open(fileobj=new_tar_bytes, mode="w") as new_tar:
        # Go through each member of the tarfile
        for member in original_tar.getmembers():
            # If this member isn't in the list of ignored files
            if member.name not in ignored_files:
                print("keeping:", member.name)
                # Extract the file to the tar buffer
                new_tar.addfile(member, original_tar.extractfile(member))
            else:
                print("skipping:", member.name)

    new_tar_bytes.seek(0)
    result = new_tar_bytes.read()
    original_tar.close()

    return result
