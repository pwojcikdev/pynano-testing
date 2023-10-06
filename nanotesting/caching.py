import os

from joblib import Memory

CACHE_DIR = "/data-raid/nanotesting-cache"
os.makedirs(CACHE_DIR, exist_ok=True)

memory = Memory(CACHE_DIR)
