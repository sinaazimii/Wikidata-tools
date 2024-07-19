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

# Define prefixes for the SPARQL query
WD = "PREFIX wd: <http://www.wikidata.org/entity/>"
WDT = "PREFIX wdt: <http://www.wikidata.org/prop/direct/>"
SCHEMA = "PREFIX schema: <http://schema.org/>"

def format_time_for_wikidata(dt):
    return dt.strftime('%Y%m%d%H%M%S')

def get_wikidata_updates(start_time, end_time):
    # Format the timestamps for API compatibility
    start = format_time_for_wikidata(start_time)
    end = format_time_for_wikidata(end_time)

    # Construct the API request URL
    api_url = "https://www.wikidata.org/w/api.php"
    params = {
        'action': 'query',
        'list': 'recentchanges',
        'rcstart': end,
        'rcend': start,
        'rclimit': '5', # Limit the number of changes returned up to 500, default 10
        'rcprop': 'title|ids|sizes|flags|user|timestamp',
        'format': 'json',
        'rctype': 'edit|new' # Limit the type of changes to edits and new entities
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

    new_rev = change["revid"]
    old_rev = change["old_revid"]
    print(change['title'])
    if change['type'] == 'new':
        # Fetch the JSON data for the new entity
        new_entity_rdf.main(change['title'])
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
            print("Comparison data unavailable.")

def convert_to_rdf(diff_html, entity_id):
    # need a subject, predicate and object for each change
    subject = entity_id
    soup = BeautifulSoup(diff_html, 'html.parser')
    # Construct DELETE and INSERT statements
    delete_statements = []
    insert_statements = []
    prefixes = WD + "\n"
    rows = soup.find_all('tr')
    current_predicate = None
    for row in rows:
        # Process property names
        if row.find('td', class_='diff-lineno'):
            value = row.find('a')
            if value:
                current_predicate = f"wdt:{value.text.strip()}"
                if ('wdt' not in prefixes): prefixes += WDT + "\n"
            else:
                # add schema
                if ('schema' not in prefixes): prefixes += SCHEMA + "\n"
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
    print("\nRDF:\n")
    print(prefixes)
    if(delete_statements != []):
        print(delete_rdf)
    if (insert_statements != []):
        print(insert_rdf)


def get_datetime_from_user(prompt):
    date_str = input(prompt)
    try:
        user_datetime = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return user_datetime
    except ValueError:
        print("Incorrect format. Please enter the date and time in 'YYYY-MM-DD HH:MM:SS' format.")
        return get_datetime_from_user(prompt)


def check_args_type(args):
    if args.type:
        if  args.type not in ['edit', 'new']:
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
        if args.number is not int:
            print("Invalid number argument. Please provide a valid number.")
            return False
        else:
            CHANGE_COUNT = args.number
    if args.start:
        if not verify_date_format(args.start):
            print("Invalid start date argument. Please provide a valid date.")
            return False
        else:
            start_dt = datetime.strptime(args.start, '%Y-%m-%d %H:%M:%S')
    if args.end:
        if not verify_date_format(args.end):
            print("Invalid end date argument. Please provide a valid date.")
            return False
        else:
            end_dt = datetime.strptime(args.end, '%Y-%m-%d %H:%M:%S')
    return True

def verify_date_format(date):
    if type(date) is not str or len(date) != 19 or date[10] != ' ' \
        or date[13] != ':' or date[16] != ':' or date[4] != '-' or date[7] != '-' \
        or int(date[0:4]) not in range(1000, 9999) or int(date[5:7]) not in range(1, 12) \
        or int(date[8:10]) not in range(1, 31) or int(date[11:13]) not in range(0, 24) \
        or int(date[14:16]) not in range(0, 60) or int(date[17:19]) not in range(0, 60):
        return False
    return True


def print_differences(str1, str2):
    # Create a Differ object
    differ = difflib.Differ()

    # Compare the two strings
    diff = list(differ.compare(str1.splitlines(), str2.splitlines()))

    # Print the differences
    print('\n'.join(diff))

def main ():
    # define some command line arguments that rqurie flags and then values
    parser = argparse.ArgumentParser(
    description="This script retrieves recent changes of the wikidata, allowing you to store the output in a file")
    parser.add_argument("-f", "--file", help = "store the output in a file")
    parser.add_argument("-l", "--latest", help = "get latest changes")
    parser.add_argument("-t", "--type", help = "filter the type of changes. possible values are edit, new")
    parser.add_argument("-n", "--number", help = "number of changes to get, not setting will get 5 changes")
    parser.add_argument("-st", "--start", help = "start date and time, in form of 'YYYY-MM-DD HH:MM:SS'"
                        "not setting start and end date will get latest changes")
    parser.add_argument("-et", "--end", help = "end date and time, in form of 'YYYY-MM-DD HH:MM:SS'")
    args = parser.parse_args()
    
    # TODO make sure if latest is set, start and end date are not set, 
    # if start and end date are set, latest is not set
    # and if latest, sort to actually retrieve get latest 

    # verify the arguments type
    if check_args_type(args):

        # put dummy inpout for testing
        start_dt = datetime(2024, 7, 1, 8, 20, 0)
        end_dt = datetime(2024, 7, 18, 0, 0, 1)

        # TODO hanlde time like above bc user enter string
        # of make user enter in paranthesis like above

        print("Getting updates from Wikidata...")
        # print(args.latest)
        return

        changes = get_wikidata_updates(start_dt, end_dt)
        print(changes[1])
        # # Calling compare changes with the first change in the list for demonstration
        compare_changes("https://www.wikidata.org/w/api.php", changes[1])

main()