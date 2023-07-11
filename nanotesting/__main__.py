import argparse
import io
import os
import tarfile

import joblib

from nanotesting import *

DUMP_DIRNAME = ".nanonet-dumps"


def save_all():
    nanonet = NanoNet.attach()
    data = nanonet.save()

    os.mkdir(DUMP_DIRNAME)
    joblib.dump(data, f"{DUMP_DIRNAME}/dump", compress=False, protocol=5)


def load_all():
    with open(f"{DUMP_DIRNAME}/dump_fixed", "rb") as f:
        data = joblib.load(f)

    nanonet = NanoNet.load(data)
    nanonet.ensure_all_confirmed()


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


IGNORED_FILES = ["Nano/config-node.toml", "Nano/config-rpc.toml"]


def fix_all():
    with open(f"{DUMP_DIRNAME}/dump", "rb") as f:
        data = joblib.load(f)

    ndata = {}
    for i, (name, d) in enumerate(data.items()):
        print("fixing node:", name, "data:", len(d))
        nd = remove_files_from_tar(d, IGNORED_FILES)
        ndata[name] = nd

    joblib.dump(ndata, f"{DUMP_DIRNAME}/dump_fixed", compress=False, protocol=5)


def stop_all():
    # TODO: Dedicated stop function
    setup_empty()


def main():
    commands = {"stop": stop_all, "save": save_all, "load": load_all, "fix": fix_all}

    parser = argparse.ArgumentParser(description="Save or load NanoNet data.")
    parser.add_argument("command", choices=commands.keys(), help="Specify whether to save or load data.")

    global args
    args = parser.parse_args()

    func = commands[args.command]
    func()


if __name__ == "__main__":
    main()
