from setuptools import setup


setup(
    name="Airpixel",
    version="0.1.1",
    url="https://github.com/mmEissen/airpixel",
    author="Moritz Eissenhauer",
    author_email="moritz.eissenhauer@gmail.com",
    description="",
    packages=["airpixel"],
    install_requires=["numpy"],
    extras_require={
        "mock": ["PyQt5"],
        "dev": ["pytest", "pylint", "mypy", "black", "twine"],
    },
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
