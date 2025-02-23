import inspect
import os
import sys
from setuptools import setup, find_packages


# Be very visible with the requires Python version!
_v = sys.version_info
if (_v.major, _v.minor) != (3, 9):
    print("\n\n============================================")
    print("============================================")
    print("        Inversionson requires Python 3.9!        ")
    print("============================================")
    print("============================================\n\n")
    raise Exception("Inversionson requires Python 3.9")


# Import the version string.
path = os.path.join(
    os.path.abspath(os.path.dirname(inspect.getfile(inspect.currentframe()))),
    "inversionson",
)
sys.path.insert(0, path)
# from version import get_git_version  # noqa


setup_config = dict(
    name="inversionson",
    version="0.0.2",
    description="",
    author="Solvi Thrastarson",
    author_email="soelvi.thrastarson@erdw.ethz.ch",
    url="https://github.com/solvithrastar/Inversionson",
    packages=find_packages(),
    license="MIT License",
    platforms="OS Independent",
    classifiers=[
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Physics",
    ],
    install_requires=["pyasdf", "toml", "numpy", "numexpr", "emoji==1.7"],
)


if __name__ == "__main__":
    setup(**setup_config)
