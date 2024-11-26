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

def get_entity_ttl(entity_id, revision_id):
    api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.ttl?revision={revision_id}"
    response = requests.get(api_url)
    return response.text

def text_diff(text1, text2, enity_id):
    """
    Compare two TTL strings and return their differences in a readable format.
    
    Parameters:
    text1 (str): First TTL string.
    text2 (str): Second TTL string.
    
    Returns:
    str: Formatted string showing the differences.
    """
    # Split the text into lines for line-by-line comparison
    text1_lines = text1.splitlines()
    text2_lines = text2.splitlines()

    # Generate a unified diff
    diff = difflib.unified_diff(
        text1_lines,
        text2_lines,
        fromfile='text1',
        tofile='text2',
        lineterm=''
    )
    # Join diff output and return as a string
    
    where_list = []
    found_diff = False
    where = None
    for i, line in enumerate(diff):
        if not check_line_validity(line):
            continue
        if line.startswith('+'):
            # line is added
            found_diff = True
            predicate_object = line[1:]
            if (predicate_object == '++ text2' or predicate_object == '++ text1'):
                continue

            
            if predicate_object.startswith('\t'):
                if predicate_object.startswith('wd:'):
                    predicate_object = predicate_object.split(' ', 1)[1]
                predicate_object = predicate_object.strip()
                
                if (where is not None):
                    where_predicate_obj = where
                    subject = where.strip().split(' ')[0]
                elif len(where_list) > 0:
                    where_predicate_obj = where_list[0]
                    subject = where_list[0].strip().split(' ')[0]
                else:
                    where_predicate_obj = None
    
                insert_rdf = (
                    "INSERT DATA {\n"
                    + subject + " "
                    + predicate_object
                    + "\n};"
                    + "\nWHERE {\n "
                    + where_predicate_obj
                    + "\n};\n"
                    )
            else:
                insert_rdf = (
                    "INSERT DATA {\n"
                    + predicate_object
                    + "\n};\n"
                    )
                print("setting where: ", predicate_object)
                where = predicate_object
            print(insert_rdf)

        elif line.startswith('-'):
            # line is removed
            found_diff = True
            predicate_object = line[1:]
            if (predicate_object == '-- text2' or predicate_object == '-- text1'):
                continue
            if predicate_object.startswith('\t'):
                if predicate_object.startswith('wd:'):
                    predicate_object = predicate_object.split(' ', 1)[1]
                predicate_object = predicate_object.strip()
                if (where is not None):
                    where_predicate_obj = where
                    subject = where.strip().split(' ')[0]
                elif len(where_list) > 0:
                    where_predicate_obj = where_list[0]
                    subject = where_list[0].strip().split(' ')[0]
                else:
                    where_predicate_obj = None
                delete_rdf = (
                    "DELETE DATA {\n"
                    + subject + " "
                    + predicate_object
                    + "\n};"
                    + "\nWHERE {\n "
                    + where_predicate_obj
                    + "\n};\n"
                    )
            else:
                delete_rdf = (
                    "DELETE DATA {\n"
                    + predicate_object
                    + "\n};\n"
                    )
                print("setting where: ", predicate_object)
                where = predicate_object
            print(delete_rdf)

        elif not line[1:].startswith('\t'):
            # line is unchanged and
            # can help in building the block
            if (found_diff):
                found_diff = False
                where_list = []
                where = None
            where_list.append(line.strip())


def check_line_validity(line):
    if (line.startswith('---') or line.startswith('+++')):
        return False
    if line.startswith('@@'): return False
    if line.startswith('+') or line.startswith('-'):
        line = line[1:].strip()
    line = line.strip()
    if (line == ""): return False
    if (line.startswith('schema:version')) \
        or (line.startswith("schema:dateModified")) \
        or (line.startswith('schema:dateCreated') \
        or (line.startswith('schema:about')) \
        or (line.startswith('cc:license')) \
        or (line.startswith('schema:softwareVersion')) \
        or (line.startswith('wikibase:statements')) \
        or (line.startswith('wikibase:sitelinks')) \
        or (line.startswith('wikibase:identifiers'))):
        return False
    return True


def diff_ttls(old_ttl, new_ttl):
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

    delete_commands = triples_to_sparql(removed_triples, "DELETE")
    insert_commands = triples_to_sparql(added_triples, "INSERT")

    # Combine into a full SPARQL update
    sparql_update = f"{delete_commands}\n{insert_commands}"
    print(sparql_update)


def triples_to_sparql(triples, operation):
    """
    Converts triples to SPARQL update statements.
    """
    commands = []
    for s, p, o in triples:
        # Format subject, predicate, and object to SPARQL-friendly strings
        s_str = f"<{s}>" if not s.startswith("_:") else s  # Blank nodes as-is
        p_str = f"<{p}>"
        o_str = f"<{o}>" if isinstance(o, str) and not o.startswith("_:") else f'"{o}"' if isinstance(o, str) else o.n3()
        
        # Construct the SPARQL command
        commands.append(f"{operation} DATA {{ {s_str} {p_str} {o_str} . }};")

    return "\n".join(commands)


def manipulate_ttl(ttl_text):
    g = Graph()
    g.parse(data=ttl_text, format="turtle")

    # Define namespaces to use in SPARQL query
    WD = Namespace("http://www.wikidata.org/entity/")
    P = Namespace("http://www.wikidata.org/prop/")

   # Step 1: Query for triples with predicate p:P12222
    initial_query = """
        PREFIX p: <http://www.wikidata.org/prop/>
        SELECT ?object
        WHERE {
            ?subject p:P12222 ?object .
        }
    """

    # Execute the first query
    initial_results = g.query(initial_query)

    # Get the object from the first query result (we assume there's one result here)
    # If there are multiple, you'd handle this by looping or filtering further
    for row in initial_results:
        target_subject = row.object  # This will be the subject for the next query
        break

    # Step 2: Query for all triples with the subject obtained from the first query
    secondary_query = """
        SELECT ?predicate ?object
        WHERE {
            <""" + str(target_subject) + """> ?predicate ?object .
        }
    """

    # Execute the second query
    secondary_results = g.query(secondary_query)

    # Display results
    print(f"Triples with subject {target_subject.n3(g.namespace_manager)}:")
    for row in secondary_results:
        print(f"{target_subject.n3(g.namespace_manager)} {row.predicate.n3(g.namespace_manager)} {row.object.n3(g.namespace_manager)} .")


def print_text_diff(text1, text2):
    # Split the text into lines for line-by-line comparison
    text1_lines = text1.splitlines()
    text2_lines = text2.splitlines()

    # Generate a unified diff
    diff = difflib.unified_diff(
        text1_lines,
        text2_lines,
        fromfile='text1',
        tofile='text2',
        lineterm=''
    )
    # Join diff output and return as a string
    
    # keep store diff and also print it
    print('\n'.join(diff))
    return


def main():
    # 7 days to vegas
    # old_ttl = get_entity_ttl("Q73536234", "2268889365")
    # new_ttl = get_entity_ttl("Q73536234", "2268889369")

    # Schema changes
    old_ttl = get_entity_ttl("Q83425111", "2270482724")
    new_ttl = get_entity_ttl("Q83425111", "2271283264")

    # comlicated structures, works fine
    # old_ttl = get_entity_ttl("Q108987708", "2271282756")
    # new_ttl = get_entity_ttl("Q108987708", "2271282759")

    
    # if debug is needed
    print_text_diff(old_ttl, new_ttl)

    # diff_ttls(old_ttl, new_ttl)
    text_diff(old_ttl, new_ttl, "Q73536234")

    # manipulate_ttl(new_ttl)

main()