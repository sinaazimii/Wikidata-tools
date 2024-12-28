import requests
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace
import new_entity_rdf
import ttl_compare
import argparse
from dateutil.relativedelta import relativedelta
import time
import difflib

# default values
CHANGES_TYPE = "edit|new"
CHANGE_COUNT = 5
LATEST = False
START_DATE = None
END_DATE = None
FILE_NAME = None
TARGET_ENTITY_ID = None
PRINT_OUTPUT = True
DEBUG = False
SPECIFIC = False


# Define prefixes for the SPARQL query
WD = "PREFIX wd: <http://www.wikidata.org/entity/>"
WDT = "PREFIX wdt: <http://www.wikidata.org/prop/direct/>"
P = "PREFIX p: <http://www.wikidata.org/prop/>"
PS = "PREFIX ps: <http://www.wikidata.org/prop/statement/>"
PQ = "PREFIX pq: <http://www.wikidata.org/prop/qualifier/>"
PR = "PREFIX pr: <http://www.wikidata.org/prop/reference/>"
PRN = "PREFIX prn: <http://www.wikidata.org/prop/reference/value-normalized/>"
PRV = "PREFIX prv: <http://www.wikidata.org/prop/reference/value/>"
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
PREFIXES = (
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
    + PRN
    + "\n"
    + PRV
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

SEPERATOR = "\n" + 80 * "=" + "\n"


def get_wikidata_updates(start_time, end_time):
    """
    Fetches recent changes from Wikidata within the specified time range.
    Args:
        start_time (str): The start time for fetching updates in ISO 8601 format.
        end_time (str): The end time for fetching updates in ISO 8601 format.
    Returns:
        list: A list of recent changes from Wikidata, where each change is represented as a dictionary.
              Returns an empty list if no changes are found or if an error occurs.
    Raises:
        requests.exceptions.RequestException: If there is an issue with the network request.
    Notes:
        - The function constructs a query to the Wikidata API to fetch recent changes.
        - The query parameters include the type of changes, the limit on the number of changes, and other properties.
        - If the DEBUG flag is set, the function prints the curl request for debugging purposes.
        - If the TARGET_ENTITY_ID is set, the function filters changes to only include those related to the specified entity.
    """
    # Construct the API request URL
    api_url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "query",
        "list": "recentchanges",
        "rcstart": end_time,
        "rcend": start_time,
        "rclimit": CHANGE_COUNT,
        "rcprop": "title|ids|sizes|flags|user|timestamp",
        "format": "json",
        "rctype": CHANGES_TYPE,  # Limit the type of changes to edits and new entities
    }
    if TARGET_ENTITY_ID:
        params["rctitle"] = TARGET_ENTITY_ID

    # create curl request for debug
    if DEBUG:
        curl_request = f"curl -G '{api_url}'"
        for key, value in params.items():
            if value is not None:
                curl_request += f" --data-urlencode '{key}={value}'"
        print("DEBUG: Query changes curl request: ", curl_request, "\n")

    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            print("Error:", data["error"]["info"])
            return
    except requests.exceptions.RequestException as e:
        print("Request failed:", e)
        return

    changes = data.get("query", {}).get("recentchanges", [])
    return changes


def verify_args(args):
    """
    Verifies and processes command-line arguments.
    Args:
        args: An argparse.Namespace object containing the command-line arguments.
    Returns:
        bool: True if all arguments are valid, False otherwise.
    Validates the following arguments:
        - latest: Ensures it is not set with start or end date.
        - start: Ensures it is set with end date and is a valid date.
        - end: Ensures it is set with start date and is a valid date.
        - type: Ensures it is one of ["edit|new", "edit", "new"].
        - file: Ensures it has a .ttl or .txt extension.
        - number: Ensures it is an integer between 1 and 500.
        - id: Ensures it starts with "Q" followed by digits.
        - omit_print: Sets PRINT_OUTPUT to False if provided.
        - debug: Sets DEBUG to True if provided.
        - specific: Sets SPECIFIC to True if provided.
    Sets global variables based on the provided arguments:
        - CHANGES_TYPE
        - CHANGE_COUNT
        - LATEST
        - START_DATE
        - END_DATE
        - FILE_NAME
        - TARGET_ENTITY_ID
        - PRINT_OUTPUT
        - DEBUG
        - SPECIFIC
    """
    global CHANGES_TYPE, CHANGE_COUNT, LATEST, START_DATE, END_DATE, FILE_NAME, TARGET_ENTITY_ID, PRINT_OUTPUT, DEBUG, SPECIFIC
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
        if args.type not in ["edit|new", "edit", "new"]:
            print(
                "Invalid type argument. Please provide 'edit' or 'new, not setting means both of them'."
            )
            return False
        else:
            CHANGES_TYPE = args.type

    if args.latest:
        LATEST = True

    if args.file:
        if not args.file.endswith(".ttl") and not args.file.endswith(".txt"):
            print(
                "Invalid file name. Please provide a file with .ttl or .txt extension."
            )
            return False
        FILE_NAME = args.file

    if args.number:
        try:
            if not int(args.number) or int(args.number) not in range(1, 501):
                print(
                    "Invalid number argument. Please provide a valid number between 1 and 501."
                )
                return False
            else:
                CHANGE_COUNT = args.number
        except ValueError:
            print(
                "Invalid number argument. Please provide a valid number between 1 and 500."
            )
            return False

    if args.id:
        if args.id.startswith("Q") and args.id[1:].isdigit():
            TARGET_ENTITY_ID = args.id
        else:
            print("Invalid entity argument. Please provide a valid entity id.")
            return False

    if args.start:
        if verify_date(args.start):
            START_DATE = datetime.strptime(args.start, "%Y-%m-%d %H:%M:%S")
        else:
            print("Invalid start date argument. Please provide a valid date.")
            return False
    if args.end:
        if verify_date(args.end):
            END_DATE = datetime.strptime(args.end, "%Y-%m-%d %H:%M:%S")
        else:
            print("Invalid end date argument. Please provide a valid date.")
            return False
    if not args.start or not args.end:
        LATEST = True

    if START_DATE and END_DATE:
        if (END_DATE - START_DATE).days < 0:
            print("Start date cannot be later than end date.")
            return False

    if args.omit_print:
        PRINT_OUTPUT = False

    if args.debug:
        DEBUG = True

    return True


def verify_date(date):
    """
    Verifies if the given date string is in the correct format and within the valid range.

    The date string must be in the format "YYYY-MM-DD HH:MM:SS" and must not be earlier than one month ago from the current date or later than the current date.

    Args:
        date (str): The date string to verify.

    Returns:
        bool: True if the date is valid, False otherwise.
    """
    if (
        type(date) is not str
        or len(date) != 19
        or date[10] != " "
        or date[13] != ":"
        or date[16] != ":"
        or date[4] != "-"
        or date[7] != "-"
        or int(date[0:4]) not in range(1000, 9999)
        or int(date[5:7]) not in range(1, 13)
        or int(date[8:10]) not in range(1, 32)
        or int(date[11:13]) not in range(0, 24)
        or int(date[14:16]) not in range(0, 60)
        or int(date[17:19]) not in range(0, 60)
    ):
        return False
    print(date)
    # check if date is not earlier than 1 month ago from now
    formatted_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    one_month_ago = now - relativedelta(months=1)
    if formatted_date < one_month_ago:
        print("The date cannot be earlier than 1 month ago.")
        return False
    if formatted_date > now:
        print("The date cannot be later than the current date.")
        return False
    return True


def write_to_file(data, file_name, prefixes):
    """
    Writes a list of entity changes to a file.

    This function takes a list of entity changes, writes predefined prefixes to the file,
    and then writes each entity change followed by two newline characters.

    Args:
        data (list): A list of strings, where each string represents an entity change.

    Raises:
        IOError: If the file cannot be opened or written to.
    """
    print("Writing changes to file...")
    with open(file_name, "w") as file:
        file.write(prefixes)
        file.write("\n")
        for entity_change in data:
            file.write(entity_change)
            file.write("\n\n")
    print("Changes written to file.")


def main():
    """
    Main function to retrieve recent changes from Wikidata and optionally store the output in a file.
    This script allows you to specify various parameters to filter the changes retrieved from Wikidata,
    such as the type of changes, the number of changes, specific entity IDs, and date ranges. The changes
    can be printed to the console or written to a file.
    Command-line Arguments:
        -f, --file: str
            Filename to store the output in.
        -l, --latest: bool
            Get the latest changes.
        -t, --type: str
            Filter the type of changes. Possible values are 'edit|new', 'edit', 'new'.
        -n, --number: int
            Number of changes to get. Default is 5. Maximum is 501.
        -id: str
            Get changes for a specific entity by providing the entity ID.
        -st, --start: str
            Start date and time in the format 'YYYY-MM-DD HH:MM:SS'. If not set, the latest changes are retrieved.
        -et, --end: str
            End date and time in the format 'YYYY-MM-DD HH:MM:SS'.
        -op, --omit-print: bool
            Omit printing the changes to the console.
        -d, --debug: bool
            Print API calls being used as curl requests.
        -sp, --specific: bool
            Get specific changes for the entity.
    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="This script retrieves recent changes of the wikidata, allowing you to store the output in a file"
        "not setting a time period will get the latest changes"
    )
    parser.add_argument("-f", "--file", help="filename to store the output in")
    parser.add_argument(
        "-l",
        "--latest",
        help="get latest changes",
        action="store_true",
    )
    parser.add_argument(
        "-t",
        "--type",
        help="filter the type of changes. possible values are edit|new, edit, new",
    )
    parser.add_argument(
        "-n",
        "--number",
        help="number of changes to get, not setting will get 5 changes, Maximum number of changes is 501",
    )
    parser.add_argument(
        "-id",
        help="get changes for a specific entity, provide the entity id",
    )
    parser.add_argument(
        "-st",
        "--start",
        help="start date and time, in form of 'YYYY-MM-DD HH:MM:SS, not setting start and end date will get latest changes",
    )
    parser.add_argument(
        "-et", "--end", help="end date and time, in form of 'YYYY-MM-DD HH:MM:SS'"
    )
    parser.add_argument(
        "-op",
        "--omit-print",
        help="omit printing the changes in the console.",
        action="store_true",
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="print api calls that are being used as curl requests",
        action="store_true",
    )
    args = parser.parse_args()

    # verify the arguments type and values
    if verify_args(args):
        print("Getting updates from Wikidata...")
        print("Type: ", CHANGES_TYPE)
        print("Latest: ", LATEST)
        print("Number: ", CHANGE_COUNT)
        print("Entity: ", TARGET_ENTITY_ID)
        print("Start Date: ", START_DATE)
        print("End Date: ", END_DATE)
        print("File Name: ", FILE_NAME)
        print("Debug: ", DEBUG)
        print("Specific node ids: ", SPECIFIC)
        print("Print: ", PRINT_OUTPUT)
        print("\n")
        start_time = time.time()
        changes = get_wikidata_updates(START_DATE, END_DATE)
        if PRINT_OUTPUT == True:
            print(PREFIXES)
        else:
            print(
                "Retrieving wikidata changes...\nChanges will not be printed to console."
            )
        all_changes = []
        for change in changes:
            if change["title"].startswith("Q") and change["title"][1:].isdigit():
                change_info = f'changes for entity: {change["title"]} between old_revid: {change["old_revid"]} and new_revid: {change["revid"]}'
                print(change_info)
                print()
                all_changes.append(change_info)
                all_changes.append(
                    ttl_compare.main(
                        change["title"], change["old_revid"], change["revid"], DEBUG
                    )
                )
                all_changes.append(SEPERATOR)
                print(SEPERATOR)

        if FILE_NAME:
            write_to_file(all_changes, FILE_NAME, PREFIXES)
        end_time = time.time()
        print(f"Execution time: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()
