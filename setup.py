from setuptools import setup, find_packages

setup(
    name="nanotesting",
    version="1.0",
    packages=find_packages(),
    entry_points={"console_scripts": ["nanotesting = nanotesting.__main__:main"]},
)
