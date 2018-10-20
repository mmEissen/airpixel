from setuptools import setup


setup(
    name = "Airpixel",
    version = "0.1.0",
    url = "",
    author = "Moritz Eissenhauer",
    author_email = "moritz.eissenhauer@gmail.com",
    description = "",
    packages = ["airpixel"],
    install_requires = ["numpy"],
    extras_require={
        "mock": ["PyQt5"],
        "dev": ["pytest", "pylint", "mypy", "black"],
    }
)
