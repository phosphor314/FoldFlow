"""Setup script for FoldFlow."""

from setuptools import setup, find_packages

with open("foldflow/__init__.py", "r") as f:
    version = None
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"')
            break

setup(
    name="foldflow",
    version=version or "0.1.0",
    description="A DAG-based project workflow engine",
    author="phosphor314",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "argparse",
    ],
    entry_points={
        "console_scripts": [
            "foldflow=foldflow.cli:main",
        ],
    },
)
