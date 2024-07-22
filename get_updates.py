import requests
from datetime import datetime
from bs4 import BeautifulSoup
import readline
from rdflib import Graph, Namespace
import new_entity_rdf
import argparse
import difflib

# default values
CHANGES_TYPE = 'edit|new'
CHANGE_COUNT = 5
LATEST = 'false'
START_DATE = None
END_DATE = None
FILE_NAME = None

# Define prefixes for the SPARQL query
WD = "PREFIX wd: <http://www.wikidata.org/entity/>"
WDT = "PREFIX wdt: <http://www.wikidata.org/prop/direct/>"
SCHEMA = "PREFIX schema: <http://schema.org/>"
SKOS = "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>"
WIKIBASE = "PREFIX wikibase: <http://wikiba.se/ontology#>"

# Define namespaces
PREFIXES = WD + "\n" + WDT + "\n" + SCHEMA + "\n" + SKOS + "\n" + WIKIBASE + "\n" 

EDIT_DELETE_RDFS = []
EDIT_INSERT_RDFS = []
NEW_INSERT_RDFS = []

def get_wikidata_updates(start_time, end_time):
    # Construct the API request URL
    api_url = "https://www.wikidata.org/w/api.php"
    params = {
        'action': 'query',
        'list': 'recentchanges',
        'rcstart': end_time,
        'rcend': start_time,
        'rclimit': CHANGE_COUNT,
        'rcprop': 'title|ids|sizes|flags|user|timestamp',
        'format': 'json',
        'rctype': CHANGES_TYPE # Limit the type of changes to edits and new entities
    }
    # Make the request
    response = requests.get(api_url, params=params)
    data = response.json()
    # Check for errors in the response
    if 'error' in data:
        print("Error:", data['error']['info'])
        return
    changes = data.get('query', {}).get('recentchanges', [])
    return changes

def compare_changes(api_url, change):
    global NEW_INSERT_RDFS
    new_rev = change["revid"]
    old_rev = change["old_revid"]
    diff = ""
    if change['type'] == 'new':
        # Fetch the JSON data for the new entity
        new_insert_statement = new_entity_rdf.main(change['title'])
        print(new_insert_statement)
        NEW_INSERT_RDFS.append(new_insert_statement)
        return
    elif change['type'] != 'edit':
        # TODO: Handle changes with type categorize?
        print("Unsupported change type:", change['type'])
        return
    elif change['type'] == 'edit':        
        params = {
            'action': 'compare',
            'fromrev': old_rev,
            'torev': new_rev,
            'format': 'json'
        }
        
        response = requests.get(api_url, params=params)
        comparison_data = response.json()
        if 'compare' in comparison_data:
            # Fetch The HTML diff of the changes using compare API
            diff = comparison_data['compare']['*'] 
            convert_to_rdf(diff, change['title'])
        else:
            # TODO: Handle cases where comparison data is not available
            # happens time to time and should be showed what is the problem
            print("Comparison data unavailable.")
    return diff

def convert_to_rdf(diff_html, entity_id):
    # need a subject, predicate and object for each change
    subject = entity_id
    soup = BeautifulSoup(diff_html, 'html.parser')
    # Construct DELETE and INSERT statements
    delete_statements = []
    insert_statements = []
    global PREFIXES, EDIT_DELETE_RDFS, INSEERT_RDFS
    rows = soup.find_all('tr')
    current_predicate = None
    for row in rows:
        # Process property names
        if row.find('td', class_='diff-lineno'):
            value = row.find('a')
            if value:
                current_predicate = f"wdt:{value.text.strip()}"
                if ('wdt' not in PREFIXES): PREFIXES += WDT + "\n"
            else:
                # add schema
                if ('schema' not in PREFIXES): PREFIXES += SCHEMA + "\n"
                current_predicate = f"schema:{row.find('td', class_='diff-lineno').text.strip()}"
                    
        # Process deleted values
        if row.find('td', class_='diff-deletedline'):
            value = row.find('del', class_='diffchange')
            if value and current_predicate:
                deleted_value = value.text.strip()
                delete_statements.append(f"  wd:{subject} {current_predicate} \"{deleted_value}\" .")

        
        # Process added values
        elif row.find('td', class_='diff-addedline'):
            value = row.find('ins', class_='diffchange')
            if value and current_predicate:
                added_value = value.text.strip()
                insert_statements.append(f"  wd:{subject} {current_predicate} \"{added_value}\" .")


    delete_rdf = (
        "DELETE DATA {\n"
        + "\n".join(delete_statements) +
        "\n};"
    )

    insert_rdf = (
        "INSERT DATA {\n"
        + "\n".join(insert_statements) +
        "\n};"
    )
    if(delete_statements != []):
        EDIT_DELETE_RDFS.append(delete_rdf)
        print(delete_rdf)
        print("\n")
    if (insert_statements != []):
        EDIT_INSERT_RDFS.append(insert_rdf)
        print(insert_rdf)
        print("\n")

def get_datetime_from_user(prompt):
    date_str = input(prompt)
    try:
        user_datetime = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return user_datetime
    except ValueError:
        print("Incorrect format. Please enter the date and time in 'YYYY-MM-DD HH:MM:SS' format.")
        return get_datetime_from_user(prompt)


def verify_args(args):
    global CHANGES_TYPE, CHANGE_COUNT, LATEST, START_DATE, END_DATE, FILE_NAME
    if args.latest and (args.start or args.end):
        print("Cannot set latest and start or end date at the same time.")
        return False
    if args.start and not args.end:
        print("Cannot set start date without end date.")
        return False
    if args.end and not args.start:
        print("Cannot set end date without start date.")
        return False
    if args.type:
        if  args.type not in ['edit|new','edit', 'new']:
            print("Invalid type argument. Please provide 'edit' or 'new, not setting means bith of them'.")
            return False
        else:
            CHANGES_TYPE = args.type
    if args.latest:
        if args.latest not in ['true', 'false']:
            print("Invalid type argument. Please provide 'true' or 'false'.")
            return False
        else:
            LATEST = args.latest
    if args.file:
        if args.file is not str:
            print("Invalid file argument. Please provide a valid file name.")
            return False
        else:
            FILE_NAME = args.file
    if args.number:
        if not int(args.number):
            print("Invalid number argument. Please provide a valid number.")
            return False
        else:
            CHANGE_COUNT = args.number
    if args.start:
        if not verify_date_format(args.start):
            print("Invalid start date argument. Please provide a valid date.")
            return False
        else:
            START_DATE = datetime.strptime(args.start, '%Y-%m-%d %H:%M:%S')
    if args.end:
        if not verify_date_format(args.end):
            print("Invalid end date argument. Please provide a valid date.")
            return False
        else:
            END_DATE = datetime.strptime(args.end, '%Y-%m-%d %H:%M:%S')
    if not args.start or not args.end:
        LATEST = 'true'
    return True

def verify_date_format(date):
    if type(date) is not str or len(date) != 19 or date[10] != ' ' \
        or date[13] != ':' or date[16] != ':' or date[4] != '-' or date[7] != '-' \
        or int(date[0:4]) not in range(1000, 9999) or int(date[5:7]) not in range(1, 12) \
        or int(date[8:10]) not in range(1, 31) or int(date[11:13]) not in range(0, 24) \
        or int(date[14:16]) not in range(0, 60) or int(date[17:19]) not in range(0, 60):
        return False
    return True

def main ():
    # define some command line arguments that rqurie flags and then values
    parser = argparse.ArgumentParser(
    description="This script retrieves recent changes of the wikidata, allowing you to store the output in a file"
                "not setting a time period will get the latest changes"
    )
    parser.add_argument("-f", "--file", help = "store the output in a file")
    parser.add_argument("-l", "--latest", help = "get latest changes")
    parser.add_argument("-t", "--type", help = "filter the type of changes. possible values are edit|new, edit, new")
    parser.add_argument("-n", "--number", help = "number of changes to get, not setting will get 5 changes")
    parser.add_argument("-st", "--start", help = "start date and time, in form of 'YYYY-MM-DD HH:MM:SS, not setting start and end date will get latest changes")
    parser.add_argument("-et", "--end", help = "end date and time, in form of 'YYYY-MM-DD HH:MM:SS'")
    args = parser.parse_args()

    # verify the arguments type and values
    if verify_args(args):
        print("Getting updates from Wikidata...")
        print("Type: ", CHANGES_TYPE)
        print("Latest: ", LATEST)
        print("Number: ", CHANGE_COUNT)
        print("Start Date: ", START_DATE)
        print("End Date: ", END_DATE)
        print("File Name: ", FILE_NAME)
        print('\n')
        print(PREFIXES)
        changes = get_wikidata_updates(START_DATE, END_DATE)
        print(changes)
        # Calling compare changes with the first change in the list for demonstration
        for change in changes:
            compare_changes("https://www.wikidata.org/w/api.php", change)
        

main()