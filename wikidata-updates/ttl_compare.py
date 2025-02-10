import requests
import re
import sys
from rdflib import Graph
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
    "http://www.w3.org/2002/07/owl#Restriction",
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
    "http://www.wikidata.org/prop/qualifier/value/": "pqv",
    "http://www.wikidata.org/prop/qualifier/": "pq",
    "http://www.wikidata.org/prop/statement/value-normalized/": "psn",
    "http://www.wikidata.org/prop/statement/value/": "psv",
    "http://www.wikidata.org/prop/direct-normalized/": "wdtn",
    "http://www.wikidata.org/prop/statement/": "ps",
    "http://www.wikidata.org/prop/reference/value/": "prv",
    "http://www.wikidata.org/prop/reference/value-normalized/": "prn",
    "http://www.wikidata.org/prop/reference/": "pr",
    "http://www.wikidata.org/prop/novalue/": "wdno",
    "http://www.wikidata.org/prop/": "p",
    "http://www.w3.org/2001/XMLSchema#": "xsd",
    "http://www.w3.org/ns/prov#": "prov",
    "http://wikiba.se/ontology#Statement": "wikibase:statement",
    "http://wikiba.se/ontology#Reference": "wikibase:reference",
    "http://www.wikidata.org/reference/": "ref",
    "https://www.wikidata.org/wiki/Special:EntityData/": "data",
    "http://www.wikidata.org/value/": "v",
}


def get_entity_ttl(entity_id, revision_id):
    """
    Fetches the Turtle (TTL) representation of a Wikidata entity for a specific revision.

    Args:
        entity_id (str): The ID of the Wikidata entity.
        revision_id (str): The revision ID of the entity.

    Returns:
        str: The TTL representation of the entity.

    Raises:
        requests.exceptions.RequestException: If the request to the Wikidata API fails.
    """
    api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.ttl?revision={revision_id}&flavor=dump"
    if DEBUG:
        curl_command = f"curl -X GET '{api_url}'"
        print(f"DEBUG: Curl command to reproduce the request:\n{curl_command}\n")
    response = requests.get(api_url)
    return response.text


def diff_ttls(old_ttl, new_ttl, entity_id):
    """
    Calculate the differences between two Turtle (TTL) files and generate SPARQL update commands.
    This function takes two TTL files as input, compares them, and identifies the triples that have been added or removed.
    It then generates SPARQL DELETE and INSERT commands to reflect these changes.
    Args:
        old_ttl (str): The content of the old TTL file.
        new_ttl (str): The content of the new TTL file.
        entity_id (str): The ID of the entity being updated.
    Returns:
        str: A SPARQL update command string that includes both DELETE and INSERT commands.
    """

    g_old = Graph()
    g_new = Graph()

    old_ttl_fixed, old_bce_dates = preprocess_bce_dates(old_ttl)
    new_ttl_fixed, old_bce_dates = preprocess_bce_dates(new_ttl)

    try:
        g_old.parse(data=old_ttl_fixed, format="ttl")
        g_new.parse(data=new_ttl_fixed, format="ttl")
    except :
        print(f"Error parsing TTL data: {sys.exc_info()[0]}")

    # Calculate differences: triples in g_new but not in g_old are additions
    # and triples in g_old but not in g_new are deletions
    added_triples = g_new - g_old
    removed_triples = g_old - g_new

    delete_commands = triples_to_sparql(removed_triples, "DELETE", entity_id)
    insert_commands = triples_to_sparql(added_triples, "INSERT", entity_id)

    # Combine into a full SPARQL update
    # sparql_update = f"{delete_commands}\n{insert_commands}"
    # print(sparql_update)
    # return sparql_update


def triples_to_sparql(triples, operation, entity_id):
    """
    Converts a list of RDF triples into SPARQL commands.
    Args:
        triples (list of tuples): A list of RDF triples, where each triple is a tuple (subject, predicate, object).
        operation (str): The SPARQL operation to perform (e.g., "INSERT", "DELETE").
        entity_id (str): The entity ID to filter subjects by.
    Returns:
        str: A string containing the SPARQL commands.
    Notes:
        - Triples containing '/owl#' in the subject, predicate, or object are skipped.
        - Subjects starting with 'wd:Q' that do not match the given entity_id are skipped.
        - Subjects starting with 'wd:P' are skipped.
        - Blank nodes in subjects are preserved as-is.
        - Predicates are formatted to replace prefixes and 'rdf:type' is replaced with 'a'.
        - Objects are formatted to handle strings, URIs, and literals appropriately.
    """
    commands = []
    parsed_triples = []
    for s, p, o in triples:
        if "/owl#" in p or "/owl#" in s or "/owl#" in o:
            continue

        # Format subject, predicate, and object to SPARQL-friendly strings
        s_str = f"{s}" if not s.startswith("_:") else s  # Blank nodes as-is
        p_str = f"{p}"

        s_str = replace_prefixes(s_str)

        p_str = replace_prefixes(p_str)
        if p_str == "rdf:type":
            p_str = "a"
        o_str = replace_prefixes(o)

        if s_str.startswith("wd:Q") and s_str != f"wd:{entity_id}":
            continue
        if s_str.startswith("wd:P"):
            continue

        # For objects: handle strings (quotes), URIs (angle brackets), and literals
        o_str = format_object_for_sparql(o, o_str)

        parsed_triples.append(f" {s_str} {p_str} {o_str} .")

        # Construct the SPARQL command
        commands.append(f"{operation} DATA {{ {s_str} {p_str} {o_str} . }};")

    print(f"\n{operation} {{\n" + "\n".join(parsed_triples) + "\n}")
    return "\n".join(commands)


def format_object_for_sparql(o, o_str):
    """
    Formats an RDF object for use in a SPARQL query.
    Args:
        o (rdflib.term.Identifier): The RDF object to format. This can be a Literal, URIRef, or BNode.
        o_str (str): The string representation of the RDF object.
    Returns:
        str: The formatted string suitable for inclusion in a SPARQL query.
    The function handles different types of RDF objects:
    - Literals: Escapes internal double quotes and formats according to language tags or datatypes.
    - URIs: Ensures proper angle bracket notation.
    - Blank nodes: Uses n3 notation.
    - Other strings: Ensures proper formatting, including handling of prefixed names.
    """
    if isinstance(o, Literal):
        # Handle escaping quotes within literals
        o_str = o_str.replace('"', '\\"')  # Escape any internal double quotes

        if o.language:  # Check if it's a language-tagged literal
            o_str = f'"{o_str}"@{o.language}'
        elif o.datatype:  # If it has a datatype (e.g., xsd:string)
            o_str = f'"{o_str}"^^{o.datatype}'
            o_str = o_str.replace("http://www.w3.org/2001/XMLSchema#", "xsd:")
            o_str = o_str.replace("+00:00", "Z")
        elif o_str.startswith("_:"):  # Blank node
            o_ost = o_str
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
            o_str = (
                f"'{o_str}'"
                if isinstance(o_str, str) and not o.startswith("_:")
                else o.n3()
            )
    return o_str


def replace_prefixes(url):
    """
    Replaces known URI prefixes in the given URL with their corresponding shorthand notation.

    Args:
        url (str): The URL in which to replace the prefixes.

    Returns:
        str: The URL with the prefixes replaced by their shorthand notation.
    """
    for uri, prefix in PREFIXES.items():
        url = url.replace(uri, f"{prefix}:")
    return url


def has_prefix(element):
    """
    Check if the given element starts with any of the prefixes defined in PREFIXES.

    Args:
        element (str): The string to check for a prefix.

    Returns:
        bool: True if the element starts with any prefix, False otherwise.
    """
    all_prefixes = PREFIXES.values()
    for prefix in all_prefixes:
        if element.startswith(f"{prefix}:"):
            return True
    return False


def main(entity_id, old_revision_id, new_revision_id, debug):
    """
    Compare the TTL (Terse Triple Language) representations of two revisions of an entity.
    Args:
        entity_id (str): The ID of the entity to compare.
        old_revision_id (int): The ID of the old revision. If 0, the old TTL will be an empty string.
        new_revision_id (int): The ID of the new revision.
        debug (bool): Flag to enable or disable debug mode.
    Returns:
        str: The differences between the TTL representations of the old and new revisions.
    """
    global DEBUG
    DEBUG = debug

    old_ttl = get_entity_ttl(entity_id, old_revision_id)
    new_ttl = get_entity_ttl(entity_id, new_revision_id)

    if old_revision_id == 0:
        old_ttl = ""

    return diff_ttls(old_ttl, new_ttl, entity_id)

def preprocess_bce_dates(ttl_data):
    """
    Converts BCE dates in Turtle data into a custom string format (BCE_YYYY-MM-DDTHH:MM:SSZ).
    This prevents RDFLib from failing due to unsupported negative years.
    """
    # Dictionary to store original BCE dates
    bce_date_map = {}

    # Regex pattern to find negative xsd:dateTime literals
    pattern = r'"(-\d{4,}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)"\^\^xsd:dateTime'

    def replace_bce(match):
        original_date = match.group(1)  # Extract full "-YYYY-MM-DDTHH:MM:SSZ"
        custom_date = f'"BCE_{original_date[1:]}"'  # Remove "-" and prefix with "BCE_"
        bce_date_map[custom_date] = original_date  # Store mapping
        print(f"Warning: Altered BCE date during ttl parsing {original_date} -> {custom_date}\n The date in no longer in xsd:dateTime format")

        return custom_date  # Replace it in TTL data

    # Replace BCE dates
    modified_ttl = re.sub(pattern, replace_bce, ttl_data)

    return modified_ttl, bce_date_map  # Return modified TTL and mapping


def try_manual():
    global DEBUG
    entity_id = "Q37816733"
    old_revision_id = "2276959296"
    new_revision_id = "2276959315"
    DEBUG = True
    old_ttl = get_entity_ttl(entity_id, old_revision_id)
    new_ttl = get_entity_ttl(entity_id, new_revision_id)

    return diff_ttls(old_ttl, new_ttl, entity_id)


if __name__ == "__main__":
    main()
