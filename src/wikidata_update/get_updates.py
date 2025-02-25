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

EDIT_DELETE_RDFS = []
EDIT_INSERT_RDFS = []
NEW_INSERT_RDFS = []

ADD_REMOVE_CLAIM = False
OLD_REV_ID = None
NEW_REV_ID = None
STATEMENT_ID = None

def get_wikidata_updates(start_time, end_time):
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

    # Make the request
    response = requests.get(api_url, params=params)
    data = response.json()
    # Check for errors in the response
    if "error" in data:
        print("Error:", data["error"]["info"])
        return
    changes = data.get("query", {}).get("recentchanges", [])
    return changes


def compare_changes(api_url, change):
    global NEW_INSERT_RDFS, OLD_REV_ID, NEW_REV_ID
    NEW_REV_ID = change["revid"]
    OLD_REV_ID = change["old_revid"]
    diff = ""
    if change["type"] == "new":
        # Fetch the JSON data for the new entity
        new_insert_statement = new_entity_rdf.main(change["title"], debug=DEBUG)
        if PRINT_OUTPUT == True:
            print(new_insert_statement)
        NEW_INSERT_RDFS.append(
            (change["title"], new_insert_statement, change["timestamp"])
        )
        return
    elif change["type"] != "edit":
        print("Unsupported change type:", change["type"])
        return
    elif change["type"] == "edit":
        params = {
            "action": "compare",
            "fromrev": OLD_REV_ID,
            "torev": NEW_REV_ID,
            "format": "json",
        }

        if DEBUG:
            curl_request = f"curl -G '{api_url}'"
            for key, value in params.items():
                if value is not None:
                    curl_request += f" --data-urlencode '{key}={value}'"
            print("\nCompare revisions curl request: ", curl_request, "\n")

        response = requests.get(api_url, params=params)
        comparison_data = response.json()
        if "compare" in comparison_data:
            # Fetch The HTML diff of the changes using compare API
            diff = comparison_data["compare"]["*"]
            # store the whole json of the new revision for later use
            if DEBUG:
                print("Entity ID: ", change["title"])
                print("new revision ID: ", NEW_REV_ID)
                print("old revision ID: ", OLD_REV_ID)
                print(
                    "URL to compare revisions page: ",
                    f"https://www.wikidata.org/w/index.php?title={change['title']}&diff={NEW_REV_ID}&oldid={OLD_REV_ID}\n",
                )
            convert_to_rdf(diff, change)
        else:
            print("Comparison data unavailable.")
    return diff


def convert_to_rdf(diff_html, change):
    global PREFIXES, EDIT_DELETE_RDFS, EDIT_INSERT_RDFS, ADD_REMOVE_CLAIM
    entity_id = change["title"]
    timestamp = change["timestamp"]
    new_rev_id = change["revid"]
    old_rev_id = change["old_revid"]
    # need a subject, predicate and object for each change
    subject = entity_id
    soup = BeautifulSoup(diff_html, "html.parser")
    # Construct DELETE and INSERT statements
    delete_statements = []
    insert_statements = []
    ADD_REMOVE_CLAIM = False
    current_predicate = None
    main_predicate = None
    main_predicate_type = None
    language = ""
    # change_statements = []
    rows = soup.find_all("tr")
    for row in rows:
        # Process property names
        if row.find("td", class_="diff-lineno"):
            (
                delete_statements,
                insert_statements,
                current_predicate,
                main_predicate,
                main_predicate_type,
                language,
                predicate_a_tags,
            ) = extract_and_normalize_main_predicate(
                timestamp,
                subject,
                delete_statements,
                insert_statements,
                main_predicate,
                main_predicate_type,
                row,
            )

        current_predicate = normalize_predicate(current_predicate, main_predicate)
        # print("insert_statements at loop start", insert_statements)
        change_statements = []
        target_class = None
        # process added/removed claim first
        if (row.find("td", class_="diff-deletedline")):
            target_class = "diff-deletedline"
            change_statements = delete_statements
        elif (row.find("td", class_="diff-addedline")):
            target_class = "diff-addedline"
            change_statements = insert_statements
        handle_claim_updates(
            subject, change_statements, current_predicate, row, target_class
        )
        # Process deleted values
        if row.find("td", class_="diff-deletedline"):            
            value = aggregated_text = None
            try: 
                inline_changes = row.find_all("td", class_="diff-deletedline")
                aggregated_text = '"' + ' '.join(tag.get_text() for tag in inline_changes) + '"'
            except:
                value = row.find("del", class_="diffchange")
            value = row.find("del", class_="diffchange")
            if value:
                # remove extra tables from the value
                remove_wb_details(value)
                span_tags = value.find_all("span")
                delete_nested_tags = []
                aggregate_nested_elements(span_tags, delete_nested_tags)

                if len(delete_nested_tags) > 0 and len(delete_nested_tags) % 2 == 0:
                    delete_statements.append(
                        handle_nested(
                            delete_nested_tags,
                            current_predicate,
                            entity_id,
                            old_rev_id,
                            main_predicate,
                            action="delete",
                            timestamp=timestamp,
                        )
                    )
                # if some nested tags are not handled by the current logic, continue with the rest
                elif len(delete_nested_tags) > 2 and len(delete_nested_tags) % 2 != 0:
                    delete_statements.append(
                        handle_nested(
                            delete_nested_tags[:-1],
                            current_predicate,
                            entity_id,
                            old_rev_id,
                            main_predicate,
                            action="delete",
                            timestamp=timestamp,
                        )
                    )
                elif current_predicate:
                    # if no nested tags
                    process_flat_changes(
                        subject,
                        delete_statements,
                        current_predicate,
                        language,
                        value,
                        aggregated_text,
                    )

        # Process added values
        if row.find("td", class_="diff-addedline"):
            value = aggregated_text = None
            try: 
                inline_changes = row.find_all("td", class_="diff-addedline")
                aggregated_text = '"' + ' '.join(tag.get_text() for tag in inline_changes) +'"'            
            except: 
                value = row.find("del", class_="diffchange")
            value = row.find("ins", class_="diffchange")
            if value:
                # remove extra tables from the value
                remove_wb_details(value)
                span_tags = value.find_all("span")
                add_nested_tags = []
                aggregate_nested_elements(span_tags, add_nested_tags)
                if len(add_nested_tags) > 1 and len(add_nested_tags) % 2 == 0:
                    insert_statements.append(
                        handle_nested(
                            add_nested_tags,
                            current_predicate,
                            entity_id,
                            new_rev_id,
                            main_predicate,
                            action="add",
                            timestamp=timestamp,
                        )
                    )
                # if some nested tags are not handled by the current logic, continue with the rest
                elif len(add_nested_tags) > 2 and len(add_nested_tags) % 2 != 0:
                    insert_statements.append(
                        handle_nested(
                            add_nested_tags[:-1],
                            current_predicate,
                            entity_id,
                            new_rev_id,
                            main_predicate,
                            action="add",
                            timestamp=timestamp,
                        )
                    )
                elif current_predicate:
                    # if no nested tags
                    process_flat_changes(
                        subject,
                        insert_statements,
                        current_predicate,
                        language,
                        value,
                        aggregated_text
                    )


    generate_rdf(
        subject,
        delete_statements,
        insert_statements,
        main_predicate_type,
        main_predicate,
        timestamp,
    )
    delete_statements = []
    insert_statements = []

def normalize_predicate(current_predicate, main_predicate):
    global ADD_REMOVE_CLAIM
    if current_predicate == "reference" or current_predicate == "prov:wasDerivedFrom":
        current_predicate = "prov:wasDerivedFrom"
    elif current_predicate == "rank" or current_predicate == "wikibase:rank":
        current_predicate = "wikibase:rank"
    elif current_predicate.startswith("p:"):
        current_predicate = current_predicate.replace("p:", "ps:")
    elif current_predicate.startswith("ps:"):
        current_predicate = current_predicate
        ADD_REMOVE_CLAIM = True
    elif current_predicate != "qualifier":
        current_predicate = main_predicate
    return current_predicate


def process_flat_changes(
    subject, statements, current_predicate, language, value, aggregated_text=None
):
    if current_predicate:
        adde_or_deleted_value = extract_href(value)
        if current_predicate == "qualifier":
            current_predicate = "pq:" + adde_or_deleted_value
            statements.append(f"  ?statement {current_predicate} {adde_or_deleted_value} .")
            adde_or_deleted_value = value.find("span").text.split(":")[1].strip()
        elif current_predicate == "wikibase:rank":
            adde_or_deleted_value = "wikibase:" + to_camel_case(adde_or_deleted_value)
            statements.append(f"  ?statement {current_predicate} {adde_or_deleted_value} .")
        elif current_predicate.startswith("ps"):
            statements.append(
                f"  ?statement {current_predicate} {adde_or_deleted_value} ."
            )
        elif aggregated_text and current_predicate.startswith('schema'):
            statements.append(
                f"  wd:{subject} {current_predicate} {aggregated_text}{language} ."
            )
        else:
            statements.append(
                f"  wd:{subject} ll{current_predicate} {adde_or_deleted_value}{language} ."
            )

    return current_predicate


def aggregate_nested_elements(span_tags, nested_tags):
    for span in span_tags:
        nested_tuple = span.find_all(
            lambda tag: (tag.name in ["a", "b"])
            or (
                tag.name == "span"
                and "wb-monolingualtext-value" in tag.get("class", [])
            )
        )
        if len(nested_tuple) == 2:
            nested_tags += nested_tuple
        elif len(nested_tuple) == 1 and len(span.text.strip().split(":")) > 1:
            obj = span.text.strip().split(":")[1].strip()
            nested_tags.extend(nested_tuple)
            nested_tags.append(create_a_tag(obj))


def remove_wb_details(value):
    wb_details = value.find("table", class_="wb-details wb-time-details")
    if wb_details:
        wb_details.extract()


def extract_and_normalize_main_predicate(
    timestamp,
    subject,
    delete_statements,
    insert_statements,
    main_predicate,
    main_predicate_type,
    row,
):
    generate_rdf(
        subject,
        delete_statements,
        insert_statements,
        main_predicate_type,
        main_predicate,
        timestamp,
    )
    delete_statements = []
    insert_statements = []
    value = None
    td_tag_text = row.get_text(strip=True)
    value = row.find("a")  # Find first <a> tag in the current row
    predicate_a_tags = row.find_all("a")
    if ":" in td_tag_text:
        predicate_a_tags.append(
            create_a_tag(td_tag_text.split(":", 1)[1].split("/")[0].strip())
        )
    if value:
        pattern = re.compile(r"/wiki/Property:(P\d+)")
        if value and pattern.search(value.prettify()):
            # Extract the property ID from the match
            property_id = pattern.search(value.prettify()).group(1)
            current_predicate = f"p:{property_id}"
            main_predicate = current_predicate
            sub_props = td_tag_text.split("/")[2:]
            for sub_prop in sub_props:
                current_predicate = sub_prop.strip()
        main_predicate_type = "property"
        language = ""
    else:
        current_predicate = f"schema:{row.find('td', class_='diff-lineno').text.strip().replace(' ', '')}"
        language_list = current_predicate.split("/")[1:]
        language = ""
        if len(language_list) > 0 and (
            "name" in current_predicate.lower() or "label" in current_predicate.lower()
        ):
            language = "@" + language_list[0]
            language = language.replace("_", "-")
        # current_predicate = current_predicate.replace("/", ":")
        current_predicate = current_predicate.split("/")[0]
        main_predicate = current_predicate
        main_predicate_type = "schema"
    return (
        delete_statements,
        insert_statements,
        current_predicate,
        main_predicate,
        main_predicate_type,
        language,
        predicate_a_tags,
    )


def handle_claim_updates(
    subject, change_statements, current_predicate, row, target_class
):
    global ADD_REMOVE_CLAIM
    if ADD_REMOVE_CLAIM:
        if row.find("td", class_=target_class):
            change_statements.append(f"  ?statement a wikibase:Statement .")
            change_statements.append(f"  ?statement a wikibase:BestRank .")
            change_statements.append(
                f'  wd:{subject} {current_predicate.replace("ps:","p:")} ?statement .'
            )
            statement_values_tags = row.find("td", class_=target_class).find("a")
            if statement_values_tags and statement_values_tags["href"]:
                link = "<" + statement_values_tags["href"].replace("https","http") + ">"
                change_statements.append(
                    f'  ?statement {current_predicate.replace("ps:","psn:")} {link} .'
                )
                change_statements.append(
                    f'  wd:{subject} {current_predicate.replace("ps:","wdtn:")} {link} .'
                )
            if statement_values_tags and statement_values_tags.text:
                change_statements.append(
                    f'  wd:{subject} {current_predicate.replace("ps:","wdt:")} "{statement_values_tags.text}" .'
                )
        ADD_REMOVE_CLAIM = False


def generate_rdf(
    subject,
    delete_statements,
    insert_statements,
    main_predicate_type,
    main_predicate,
    timestamp,
):
    global STATEMENT_ID
    if delete_statements == [] and insert_statements == []:
        return
    if main_predicate_type == "schema":
        delete_rdf = "DELETE DATA {\n" + "\n\t\t".join(delete_statements) + "\n};"
        insert_rdf = "INSERT DATA {\n" + "\n\t\t".join(insert_statements) + "\n};"

    else:
        for insert in insert_statements:
            if insert.startswith("  ?statement"):
                object = get_third_element(insert)
                statement = "?statement"
                if object:
                    STATEMENT_ID = get_statement_id(subject, NEW_REV_ID, main_predicate[2:], object)

        for delete in delete_statements:
            if delete.startswith("  ?statement"):
                object = get_third_element(delete)
                statement = "?statement"
                if object:
                    STATEMENT_ID = get_statement_id(subject, OLD_REV_ID, main_predicate[2:], object)

        if STATEMENT_ID: 
            insert_statements = replace_statements(STATEMENT_ID, insert_statements)
            delete_statements = replace_statements(STATEMENT_ID, delete_statements)

        insert_rdf = (
            "INSERT DATA {\n"
            + "\n".join(insert_statements)
            + "\n};"
        )
        delete_rdf = (
            "DELETE DATA{\n"
            + "\n".join(delete_statements)
            + "\n};"
        )

    if delete_statements != []:
        EDIT_DELETE_RDFS.append((subject, delete_rdf, timestamp))
        if PRINT_OUTPUT == True:
            print(delete_rdf)
            print("\n")
    if insert_statements != []:
        EDIT_INSERT_RDFS.append((subject, insert_rdf, timestamp))
        if PRINT_OUTPUT == True:
            print(insert_rdf)
            print("\n")
    return


def handle_nested(
    nested_tags, current_predicate, entity_id, rev_id, main_predicate, action, timestamp
):
    prefix = "ps"
    change_statement = ""
    ref_hash = None
    snaks_group = None
    if current_predicate == "prov:wasDerivedFrom":
        prefix = "pr"
        entity_json = get_entity_json(entity_id, rev_id)
        ref_hash = get_reference_hash(entity_id, entity_json, main_predicate[2:])
        change_statement += "  ?statement " + current_predicate + " " + "ref:" + ref_hash + " .\n"
        change_statement += "  ref:" + ref_hash + " a wikibase:Reference .\n"
        snaks_group = "references"
    elif current_predicate == "qualifier":
        prefix = "pq"
        snaks_group = "qualifiers"
    elif current_predicate.startswith("ps:"):
        predicate = current_predicate
        object = extract_href(nested_tags[0])
        return f"  ?statement {predicate} {object} ."

    for i in range(0, len(nested_tags), 2):
        predicate = extract_href(nested_tags[i])
        time_node_id = None
        object = None
        if (
            nested_tags[i + 1].name == "b"
            and "wb-time-rendered" in nested_tags[i + 1].get("class", [])
            and snaks_group
        ):
            try:
                time_object = get_datetime_object(
                    entity_json, entity_id, main_predicate, predicate, snaks_group
                )
                object = f'"{time_object["time"]}"^^xsd:dateTime'
                if SPECIFIC:
                    time_node_id = "v:" + get_time_node(
                        entity_id, rev_id, ref_hash, main_predicate[2:]
                    )
            except:
                object = extract_href(nested_tags[i + 1])
        else:
            object = extract_href(nested_tags[i + 1])
        if ref_hash:
            change_statement += "  " + "ref:" + ref_hash + f" {prefix}:{predicate} {object} .\n"
        elif current_predicate == "qualifier":
            change_statement += "  ?statement " + f"{prefix}:{predicate} {object} .\n"
        else:
            change_statement += "  " + f"wd:{entity_id} {prefix}:{predicate} {object} .\n"
        if time_node_id:
            change_statement += f"  ref:{ref_hash} prv:{predicate} {time_node_id} .\n"
            handle_time_node(time_object, time_node_id, action, timestamp)

    return change_statement


def handle_time_node(object, time_node_id, action, change_timestamp):
    if action == "delete":
        operation = "DELETE"
    elif action == "add":
        operation = "INSERT"

    change_statement = f"{operation} DATA {{\n"
    change_statement += f"  {time_node_id} a wikibase:TimeValue .\n"
    if object and object["time"]:
        change_statement += (
            f"  {time_node_id} wikibase:timeValue '{object['time']}'^^xsd:dateTime .\n"
        )
    if object and object["precision"] or object["precision"] == 0:
        change_statement += f"  {time_node_id} wikibase:timePrecision '{object['precision']}'^^xsd:integer .\n"
    if object and object["timezone"] or object["timezone"] == 0:
        change_statement += f"  {time_node_id} wikibase:timeTimezone '{object['timezone']}'^^xsd:integer .\n"
    if object and object["calendarmodel"]:
        change_statement += f"  {time_node_id} wikibase:timeCalendarModel '{object['calendarmodel']}' .\n"
    change_statement += "};\n"

    if action == "delete":
        EDIT_DELETE_RDFS.append((time_node_id, change_statement, change_timestamp))
    elif action == "add":
        EDIT_INSERT_RDFS.append((time_node_id, change_statement, change_timestamp))
    if PRINT_OUTPUT == True:
        print(change_statement)
    return


def replace_statements(statement_id, changes_statements):
    result = []
    for change_statement in changes_statements:
        result.append(change_statement.replace("?statement", statement_id))
    return result


def get_entity_json(entity_id, revision_id):
    api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json?revision={revision_id}"
    response = requests.get(api_url)
    if DEBUG:
        print("\nRetrieving entity JSON API...")
        print("Entity JSON API URL: ", api_url, "\n")
    return response


def replace_prefixes(text):
    if text.startswith("http://www.wikidata.org/entity/"):
        return text.replace("http://www.wikidata.org/entity/", "wd:")
    elif text.startswith("http://www.wikidata.org/prop/statement/"):
        return text.replace("http://www.wikidata.org/prop/statement/", "ps:")
    elif text.startswith("http://www.wikidata.org/prop/qualifier/"):
        return text.replace("http://www.wikidata.org/prop/qualifier/", "pq:")
    elif text.startswith("http://www.wikidata.org/prop/reference/value/"):
        return text.replace("http://www.wikidata.org/prop/reference/value/", "prv:")
    elif text.startswith("http://www.wikidata.org/prop/reference/"):
        return text.replace("http://www.wikidata.org/prop/reference/", "pr:")
    elif text.startswith("http://www.wikidata.org/prop/"):
        return text.replace("http://www.wikidata.org/prop/", "p:")
    elif text.startswith("http://www.wikidata.org/value/"):
        return text.replace("http://www.wikidata.org/value/", "v:")
    return text


def get_reference_hash(entity_id, entity_json, property_id):
    property_objects = entity_json.json()["entities"][entity_id]["claims"][property_id]
    for property_obj in property_objects:
        if property_obj.get("references"):
            # for now assume there is only one reference
            node_hash = property_obj.get("references")[0].get("hash")
    return node_hash

def get_third_element(triplet):
    # Regex to capture the third member, accounting for quoted strings
    match = re.search(r'(\S+)\s(\S+)\s((".*?"|\S+))', triplet)
    if match and match.group(2).startswith("ps:"):
            return match.group(3)  # The third captured group includes quotes if present
    return None

def get_datetime_object(new_json, entity_id, main_predicate, predicate, snaks_group):
    if snaks_group == "references":
        # Some properties have multiple references, for now assume there is only one reference
        # I take last one for now but this is not the correct way to handle it.
        references = new_json.json()["entities"][entity_id]["claims"][
            main_predicate[2:]
        ][-1][snaks_group]
        for reference in references:
            snaks = reference["snaks"]
            if predicate in snaks:
                return snaks[predicate][0]["datavalue"]["value"]
    elif snaks_group == "qualifiers":
        qualifiers = new_json.json()["entities"][entity_id]["claims"][
            main_predicate[2:]
        ][-1][snaks_group]
        if len(qualifiers) == 1:
            if predicate in qualifiers:
                return qualifiers[predicate][0]["datavalue"]["value"]
        else:
            for qualifier in qualifiers:
                if predicate in qualifier:
                    return qualifier[predicate][0]["datavalue"]["value"]


def get_time_node(entity_id, revision_id, reference_id, property_id):
    """
    Queries the Wikidata SPARQL endpoint for a specific triple where the predicate is property_id
    for a given reference node ID, ensuring it belongs to the specified entity and property.
    """
    # SPARQL query to retrieve the specific triple for prv:
    sparql_query = f"""
        PREFIX ref: <http://www.wikidata.org/reference/>
        PREFIX prv: <http://www.wikidata.org/prop/reference/value/>

        SELECT ?predicate ?value
        WHERE {{
        ref:{reference_id} ?predicate ?value .
        FILTER(STRSTARTS(STR(?predicate), STR(prv:)))
        }}
    """

    sparql_endpoint = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MyWikidataQueryBot/1.0; +https://www.example.com/bot)"
    }
    response = requests.get(
        sparql_endpoint,
        params={"query": sparql_query, "format": "json"},
        headers=headers,
    )
    if response.status_code == 200:
        data = response.json()
        if data["results"]["bindings"]:
            # Extract the value from the response
            value = data["results"]["bindings"][0]["value"]["value"]
            return value.split("/")[-1]
    else:
        print(f"Error querying Wikidata SPARQL endpoint: {response.status_code}")

    # return None

    # Problem with this approach is if the data is not available in the SPARQL endpoint (e.g deleted nodes),
    # it will return None, so we move to the second appoaach to get the time node value for deleted nodes
    # Another approach is to fetch the TTL data of the entity and parse it to get the time node value
    # this approach is much slower but the last resort to get the datetime node value

    api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.ttl?revision={revision_id}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching TTL data: {e}")
        return None

    if DEBUG:
        print("\nRetrieving entity TTL API...")
        print("Entity TTL API URL: ", api_url, "\n")

    # Parse the TTL data
    g = Graph()
    try:
        g.parse(data=response.text, format="ttl")
    except Exception as e:
        print(f"Error parsing TTL data: {e}")
        return None

    try:
        results = g.query(sparql_query)
        for row in results:
            return replace_prefixes(str(row.value))
    except Exception as e:
        print(f"Error executing SPARQL query: {e}")

    return None


def get_statement_id(entity_id, revision_id, property_id, object_value):
    """
    Retrieves the statement ID where ps:<property_id> equals object_value.
    Tries the Wikidata SPARQL endpoint first, then falls back to TTL parsing.
    """
    # The SPARQL query is defined once and reused
    sparql_query = f"""
        PREFIX wd: <http://www.wikidata.org/entity/>
        PREFIX p: <http://www.wikidata.org/prop/>
        PREFIX ps: <http://www.wikidata.org/prop/statement/>
        SELECT ?statement
        WHERE {{
          wd:{entity_id} p:{property_id} ?statement .
          ?statement ps:{property_id} {object_value} .
        }}
    """
    
    sparql_endpoint = "https://query.wikidata.org/sparql"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; MyWikidataQueryBot/1.0; +https://www.example.com/bot)"
    }

    # Query the SPARQL endpoint
    if DEBUG:
        print("SPARQL Query:\n", sparql_query)

    response = requests.get(
        sparql_endpoint,
        params={"query": sparql_query, "format": "json"},
        headers=headers,
    )

    if response.status_code == 200:
        try:
            data = response.json()
            if data["results"]["bindings"]:
                # Extract the first statement value
                statement = data["results"]["bindings"][0]["statement"]["value"]
                return statement.split("/")[-1]  # Return only the statement ID
        except KeyError as e:
            print(f"Error processing SPARQL response: {e}")
    else:
        print(f"SPARQL query failed with status: {response.status_code}")

    # Fallback to TTL Parsing
    print("Fallback to TTL parsing...")
    api_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.ttl?revision={revision_id}"
    try:
        ttl_response = requests.get(api_url)
        ttl_response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching TTL data: {e}")
        return None

    if DEBUG:
        print("TTL Data URL: ", api_url)

    g = Graph()
    try:
        g.parse(data=ttl_response.text, format="ttl")
    except Exception as e:
        print(f"Error parsing TTL data: {e}")
        return None

    # Use the same SPARQL query on the RDF graph
    try:
        results = g.query(sparql_query)
        for row in results:
            if DEBUG:
                print("Statement ID found in TTL:", "s:" + str(row["statement"]).split("/")[-1])
            return "s:" + str(row["statement"]).split("/")[-1]
    except Exception as e:
        print(f"Error executing SPARQL query on TTL data: {e}")

    print("Statement ID not found.\n")
    return None

def extract_href(tag):
    # Check for href with "Property:"
    a_tag = tag.find("a")
    b_tag = tag.find("b", class_=["wb-time-rendered", "wb-quantity-rendered"])
    if tag.name == "a":
        a_tag = tag
    if tag.name == "b":
        b_tag = tag

    # print(a_tag)

    # assumed b_tag never has href, never seen otherwise in the diff html so far
    if a_tag and a_tag.has_attr("href") and "Property:" in a_tag["href"]:
        return a_tag["href"].split("Property:")[1]

    if a_tag and a_tag.has_attr("href") and a_tag["href"].startswith("/wiki/Q"):
        return "wd:" + a_tag["href"].split("/")[2]

    # Check for title attribute with "Property:"
    if tag.has_attr("title") and "Property:" in tag["title"]:
        return tag["title"].split("Property:")[1]

    # Check for P: in the tag value
    if "P:" in tag.text:
        return tag.text.split("P:")[1].strip()

    if b_tag:
        # escape quotes in the text
        quote_escaped_text = b_tag.text.strip().replace('"', '\\"')
        return f'"{quote_escaped_text}"'

    # If none of the above, return the tag's text in ""
    quote_escaped_text = tag.text.strip().replace('"', '\\"')
    return f'"{quote_escaped_text}"'


def extract_span_plaintext(value):
    nested_tags = []
    # Find all `span` tags that have an `a` tag and some direct text
    target_spans = value.find_all(
        lambda tag: (
            tag.name == "span"
            and tag.find("a")  # Must contain an `a` tag
            and tag.find("a").next_sibling  # Must have direct text after the `a` tag
        )
    )
    for span in target_spans:
        # Extract the `a` tag
        a_tag = span.find("a")
        # Extract the text after the `a` tag (the sibling text node)
        direct_text = a_tag.next_sibling.strip() if a_tag.next_sibling else ""
        # Create a new `a` tag with the text
        if direct_text != ":":
            # check if the direct text starts with colon, if so, remove it
            if direct_text.startswith(":"):
                direct_text = direct_text[2:]
            nested_tags.append(create_a_tag(direct_text))

    return nested_tags


def create_a_tag(text):
    soup = BeautifulSoup("", "html.parser")
    new_tag = soup.new_tag("a")
    new_tag.string = text
    return new_tag


def to_camel_case(s):
    # Remove quotes and trim whitespace
    s = s.strip('"').strip()
    # Split the string into words
    words = s.split()
    # Capitalize the first letter of each word and join them
    camel_case_string = "".join(word.capitalize() for word in words)
    return camel_case_string


def verify_args(args):
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

    if args.specific:
        SPECIFIC = True

    return True


def verify_date(date):
    if (
        type(date) is not str
        or len(date) != 19
        or date[10] != " "
        or date[13] != ":"
        or date[16] != ":"
        or date[4] != "-"
        or date[7] != "-"
        or int(date[0:4]) not in range(1000, 9999)
        or int(date[5:7]) not in range(1, 12)
        or int(date[8:10]) not in range(1, 31)
        or int(date[11:13]) not in range(0, 24)
        or int(date[14:16]) not in range(0, 60)
        or int(date[17:19]) not in range(0, 60)
    ):
        return False
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


def write_to_file(data):
    print("Writing changes to file...")
    with open(FILE_NAME, "w") as file:
        file.write(PREFIXES)
        file.write("\n")
        for subject, change, time in data:
            file.write(change)
            file.write("\n\n")
    print("Changes written to file.")


def main():
    # define some command line arguments
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
    parser.add_argument(
        "-sp",
        "--specific",
        help="get specific changes for the entity",
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
                compare_changes("https://www.wikidata.org/w/api.php", change)
        # write the changes to a file
        if FILE_NAME:
            # merge all the changes into one list sorted by timestamp
            all_changes = sorted(
                EDIT_INSERT_RDFS + EDIT_DELETE_RDFS + NEW_INSERT_RDFS,
                key=lambda x: x[2],
                reverse=True,
            )
            write_to_file(all_changes)
        end_time = time.time()
        print(f"Execution time: {end_time - start_time} seconds")


main()
