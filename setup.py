from os import path
from setuptools import setup


def load_long_descriprion():
    this_directory = path.abspath(path.dirname(__file__))
    with open(path.join(this_directory, "README.rst")) as readme:
        return readme.read()


setup(
    name="Airpixel",
    version="0.5.2",
    url="https://github.com/mmEissen/airpixel",
    author="Moritz Eissenhauer",
    author_email="moritz.eissenhauer@gmail.com",
    description="",
    packages=["airpixel"],
    install_requires=["numpy"],
    extras_require={
        "mock": ["PyQt5"],
        "dev": ["pytest", "pytest-timeout", "pylint", "mypy", "black", "twine"],
    },
    classifiers=[
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    long_description=load_long_descriprion(),
    long_description_content_type="text/x-rst",
)
