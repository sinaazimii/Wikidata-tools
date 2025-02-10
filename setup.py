from setuptools import setup, find_packages

setup(
    name="wikidata-tools",
    version="0.1.0",
    packages=find_packages(),  # Automatically finds `my_project/` package
    install_requires=[
        "numpy",  # Example dependencies
        "matplotlib"
    ],
)