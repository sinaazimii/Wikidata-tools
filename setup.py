from setuptools import setup, find_packages

setup(
    name="wikidata-update", 
    version="0.1.0",
    packages=find_packages(where="src"), 
    package_dir={"": "src"},
    install_requires=[
        "numpy",
        "matplotlib",
        "requests",
        "rdflib",
        "python-dateutil",
        "argcomplete"
    ],
    entry_points={
        "console_scripts": [
            "wikidata-update=wikidata_update.sparql_updates:main", 
        ],
    },
)
