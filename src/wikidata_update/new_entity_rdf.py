import requests
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set default logging level to INFO
    format="%(asctime)s [%(levelname)s] %(message)s",  # Define format
)

logger = logging.getLogger(__name__)  # Create a logger


def main(entity_id, debug=False):
    # check if entity_id is correct format
    if not entity_id.startswith("Q"):
        print("\n")
        logger.error("Invalid entity ID")
        print(
            "one reason could be that the entity ID is not yet set in the correct format,"
            "this happens for entities that are very new and have not been indexed yet"
        )
        print("\n")
        return None
    # Fetch JSON data for the entity
    # url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
    # else:
    url = f"https://www.wikidata.org/w/api.php"
    response = requests.get(
        url,
        params={
            "action": "wbgetentities",
            "ids": entity_id,
            "format": "json",
            "languages": "en",
        },
    )

    if debug:
        logger.setLevel(logging.DEBUG)
        curl_command = f"curl -G '{url}?action=wbgetentities&ids={entity_id}&format=json&languages=en'"
        logger.debug("Get new entity data curl command:", curl_command)

    data = response.json()

    # Check for errors in the response
    try:
        entity = data["entities"][entity_id]
    except KeyError:
        print("\n")
        logger.error("Entity not found")
        print("\n")
        return None
    # Initialize the INSERT DATA statement
    insert_data = "INSERT DATA {\n"

    # Add the main entity with type
    insert_data += f"  wd:{entity['id']} a schema:Thing ;\n"

    # Add labels
    for lang, label in entity["labels"].items():
        insert_data += f"    schema:name \"{label['value']}\"@{lang} ;\n"

    # Add descriptions
    for lang, desc in entity["descriptions"].items():
        insert_data += f"    schema:description \"{desc['value']}\"@{lang} ;\n"

    # Add aliases
    for lang, aliases in entity["aliases"].items():
        for alias in aliases:
            insert_data += f"    skos:altLabel \"{alias['value']}\"@{lang} ;\n"

    # create simpler entity object
    simple_entity = {
        "id": entity["id"],
        "labels": entity.get("labels", {}),
        "descriptions": entity.get("descriptions", {}),
        "aliases": entity.get("aliases", {}),
    }
    # Add claims
    for prop, claims in entity["claims"].items():
        for claim in claims:
            if "mainsnak" in claim and "datavalue" in claim["mainsnak"]:
                value = claim["mainsnak"]["datavalue"]["value"]
                if claim["mainsnak"]["datavalue"]["type"] == "wikibase-entityid":
                    insert_data += f"    wdt:{prop} wd:{value['id']} ;\n"
                    simple_entity[prop] = value["id"]
                elif claim["mainsnak"]["datavalue"]["type"] == "string":
                    insert_data += f'    wdt:{prop} "{value}" ;\n'
                    simple_entity[prop] = value
                elif claim["mainsnak"]["datavalue"]["type"] == "time":
                    insert_data += (
                        f"    wdt:{prop} \"{value['time']}\"^^xsd:dateTime ;\n"
                    )
                    simple_entity[prop] = value["time"]
                elif claim["mainsnak"]["datavalue"]["type"] == "quantity":
                    insert_data += (
                        f"    wdt:{prop} \"{value['amount']}\"^^xsd:decimal ;\n"
                    )
                    simple_entity[prop] = value["amount"]
                elif claim["mainsnak"]["datavalue"]["type"] == "monolingualtext":
                    insert_data += (
                        f"    wdt:{prop} \"{value['text']}\"@{value['language']} ;\n"
                    )
                    simple_entity[prop] = value["text"]
                else:
                    # add without type
                    insert_data += f'    wdt:{prop} "{value}" ;\n'

    # Remove the last semicolon and add a period
    insert_data = insert_data.rstrip(" ;\n") + " .\n"

    # Close the INSERT DATA statement
    insert_data += "};\n"

    return insert_data
