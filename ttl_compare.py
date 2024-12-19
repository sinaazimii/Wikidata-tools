import requests
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace
import new_entity_rdf
import argparse
from dateutil.relativedelta import relativedelta
import time
import difflib
from rdflib.term import Literal


DEBUG = False

# Define prefixes for the SPARQL query
WD = "PREFIX wd: <http://www.wikidata.org/entity/>"
WDT = "PREFIX wdt: <http://www.wikidata.org/prop/direct/>"
P = "PREFIX p: <http://www.wikidata.org/prop/>"
PS = "PREFIX ps: <http://www.wikidata.org/prop/statement/>"
PQ = "PREFIX pq: <http://www.wikidata.org/prop/qualifier/>"
PR = "PREFIX pr: <http://www.wikidata.org/prop/reference/>"
PRV = "PREFIX prv: <http://www.wikidata.org/prop/reference/value/>"
PRN = "PREFIX prn: <http://www.wikidata.org/prop/reference/value-normalized/>"
PROV = "PREFIX prov: <http://www.w3.org/ns/prov#>"
SCHEMA = "PREFIX schema: <http://schema.org/>"
SKOS = "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>"
WIKIBASE = "PREFIX wikibase: <http://wikiba.se/ontology#>"
XSD = "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>"
REF = "PREFIX ref: <http://www.wikidata.org/reference/>"
V = "PREFIX v: <http://www.wikidata.org/value/>"
S = "PREFIX s: <http://www.wikidata.org/entity/statement/>"
PSN = "PREFIX psn: <http://www.wikidata.org/prop/statement/value-normalized/>"
WDTN = "PREFIX wdtn: <http://www.wikidata.org/prop/direct-normalized/>"
RDFS = "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>"
DATA = "PREFIX data: <https://www.wikidata.org/wiki/Special:EntityData/>"

# Define namespaces
PREFIXES_1 = (
    WD
    + "\n"
    + WDT
    + "\n"
    + P
    + "\n"
    + PS
    + "\n"
    + PR
    + "\n"
    + PRV
    + "\n"
    + PRN
    + "\n"
    + PQ
    + "\n"
    + PROV
    + "\n"
    + SCHEMA
    + "\n"
    + SKOS
    + "\n"
    + WIKIBASE
    + "\n"
    + XSD
    + "\n"
    + REF
    + "\n"
    + V
    + "\n"
    + S
    + "\n"
    + PSN
    + "\n"
    + WDTN
    + "\n"
    + RDFS
    + "\n"
    + DATA
    + "\n"
)



PREDICATE_BLACKLIST = [
    # "http://schema.org/version",
    # "http://schema.org/dateModified",
    # "http://schema.org/dateCreated",
    # "http://schema.org/about",
    "http://creativecommons.org/ns#license",
    "http://schema.org/softwareVersion",
    "http://www.w3.org/2002/07/owl#complementOf",
    "http://www.w3.org/2002/07/owl#disjointUnionOf",
    "http://www.w3.org/2002/07/owl#members",
    "http://www.w3.org/2002/07/owl#onProperty",
    "http://www.w3.org/2002/07/owl#someValuesFrom",
    "http://www.w3.org/2002/07/owl#unionOf",
    "http://www.w3.org/2002/07/owl#versionIRI",
    "http://www.w3.org/2002/07/owl#Restriction"
]

PREFIXES = {
    "http://www.w3.org/ns/prov#": "prov",
    "http://schema.org/": "schema",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
    "http://www.w3.org/2004/02/skos/core#": "skos",
    "http://wikiba.se/ontology#": "wikibase",
    "http://www.wikidata.org/entity/statement/": "s",
    "http://www.wikidata.org/entity/": "wd",
    "http://www.wikidata.org/prop/direct/": "wdt",
    "http://www.wikidata.org/prop/qualifier/value/" : "pqv",
    "http://www.wikidata.org/prop/qualifier/": "pq",
    "http://www.wikidata.org/prop/statement/value-normalized/" : "psn",
    "http://www.wikidata.org/prop/statement/value/" : "psv",
    "http://www.wikidata.org/prop/direct-normalized/" : "wdtn",
    "http://www.wikidata.org/prop/statement/": "ps",
    "http://www.wikidata.org/prop/reference/value/": "prv",
    "http://www.wikidata.org/prop/reference/value-normalized/": "prn",
    "http://www.wikidata.org/prop/reference/": "pr",
    'http://www.wikidata.org/prop/novalue/': 'wdno',
    "http://www.wikidata.org/prop/": "p",
    "http://www.w3.org/2001/XMLSchema#": "xsd",
    "http://www.w3.org/ns/prov#" : "prov",
    "http://wikiba.se/ontology#Statement": "wikibase:statement",
    "http://wikiba.se/ontology#Reference": "wikibase:reference",
    "http://www.wikidata.org/reference/": "ref",
    "https://www.wikidata.org/wiki/Special:EntityData/" : "data",
    "http://www.wikidata.org/value/" : "v",

}

def get_entity_ttl(entity_id, revision_id):
    api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.ttl?revision={revision_id}"
    if DEBUG:
        curl_command = f"curl -X GET '{api_url}'"
        print(f"DEBUG: Curl command to reproduce the request:\n{curl_command}\n")
    response = requests.get(api_url)
    return response.text

def diff_ttls(old_ttl, new_ttl, entity_id):
    # Load the first TTL file into a graph

    g_old = Graph()
    g_old.parse(data=old_ttl, format="ttl")

    # Load the second TTL file into a graph
    g_new = Graph()
    g_new.parse(data=new_ttl, format="ttl")

    # Calculate differences: triples in g_new but not in g_old are additions
    # and triples in g_old but not in g_new are deletions
    added_triples = g_new - g_old
    removed_triples = g_old - g_new

    delete_commands = triples_to_sparql(removed_triples, "DELETE", entity_id)
    insert_commands = triples_to_sparql(added_triples, "INSERT", entity_id)

    # Combine into a full SPARQL update
    sparql_update = f"{delete_commands}\n{insert_commands}"
    print(sparql_update)
    return sparql_update
    


def triples_to_sparql(triples, operation, entity_id):
    """
    Converts triples to SPARQL update statements.
    """
    commands = []
    for s, p, o in triples:
        if '/owl#' in p or '/owl#' in s or '/owl#' in o:
            continue
        
        # Format subject, predicate, and object to SPARQL-friendly strings
        s_str = f"{s}" if not s.startswith("_:") else s  # Blank nodes as-is
        p_str = f"{p}"

        s_str = replace_prefixes(s_str)

        p_str = replace_prefixes(p_str)
        if p_str == 'rdf:type':
            p_str = 'a'
        o_str = replace_prefixes(o)


        if s_str.startswith('wd:Q') and s_str != f"wd:{entity_id}":
            continue
        if s_str.startswith('wd:P'):
            continue

        # For objects: handle strings (quotes), URIs (angle brackets), and literals
        o_str = format_object_for_sparql(o, o_str)
       
        # Construct the SPARQL command
        commands.append(f"{operation} DATA {{ {s_str} {p_str} {o_str} . }};")

    return "\n".join(commands)


def format_object_for_sparql(o, o_str):
    if isinstance(o, Literal):
            # Handle escaping quotes within literals
        o_str = o_str.replace('"', '\\"')  # Escape any internal double quotes
            
        if o.language:  # Check if it's a language-tagged literal
            o_str = f'"{o_str}"@{o.language}'
        elif o.datatype:  # If it has a datatype (e.g., xsd:string)
            o_str = f'"{o_str}"^^{o.datatype}'
            o_str = o_str.replace("http://www.w3.org/2001/XMLSchema#", "xsd:")
            o_str = o_str.replace("+00:00", "Z")
        else:  # Plain literal
            o_str = f'"{o_str}"'
    else:
        o_str = o_str.replace("<", "").replace(">", "")
            # If object is not a literal (URI or blank node)
        if isinstance(o_str, str) and o_str.startswith("http"):
            o_str = f"<{o_str}>"
        elif isinstance(o_str, str) and has_prefix(o_str):
            o_str = o_str
        else:
            o_str = f"'{o_str}'" if isinstance(o_str, str) and not o.startswith("_:") else o.n3()
    return o_str


def replace_prefixes(url):
    for uri, prefix in PREFIXES.items():
        url = url.replace(uri, f"{prefix}:")
    return url

def has_prefix(element):
    all_prefixes = PREFIXES.values()
    for prefix in all_prefixes:
        if element.startswith(f"{prefix}:"):
            return True
    return False


def main(entity_id, old_revision_id, new_revision_id, debug):
    global DEBUG
    DEBUG = debug

    old_ttl = get_entity_ttl(entity_id, old_revision_id)
    new_ttl = get_entity_ttl(entity_id, new_revision_id)

    if old_revision_id == 0:
        old_ttl = ""

    return diff_ttls(old_ttl, new_ttl, entity_id)


def try_manual():
    global DEBUG
    entity_id = "Q37816733"
    old_revision_id = "2276959296"
    new_revision_id = "2276959315"
    DEBUG = True
    old_ttl = get_entity_ttl(entity_id, old_revision_id)
    new_ttl = get_entity_ttl(entity_id, new_revision_id)

    return diff_ttls(old_ttl, new_ttl, entity_id)

# try_manual()