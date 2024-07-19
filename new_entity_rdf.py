import requests
import json

def main(entity_id, revision_id=0):
    # Define namespaces
    PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wikibase: <http://wikiba.se/ontology#>
    PREFIX schema: <http://schema.org/>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    """
    
    # Fetch JSON data for the entity
    if revision_id == 0:
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
    else:
        print("revision_id", revision_id)
        url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={entity_id}&format=json&revision={revision_id}"
    response = requests.get(url)
    data = response.json()

    entity = data['entities'][entity_id]

    # Initialize the INSERT DATA statement
    insert_data = "INSERT DATA {\n"

    # Add the main entity with type
    insert_data += f"  wd:{entity['id']} a schema:Thing ;\n"

    # Add labels
    for lang, label in entity['labels'].items():
        insert_data += f"    schema:name \"{label['value']}\"@{lang} ;\n"

    # Add descriptions
    for lang, desc in entity['descriptions'].items():
        insert_data += f"    schema:description \"{desc['value']}\"@{lang} ;\n"

    # Add aliases
    for lang, aliases in entity['aliases'].items():
        for alias in aliases:
            insert_data += f"    skos:altLabel \"{alias['value']}\"@{lang} ;\n"

    # create simpler entity object
    simple_entity = {
        'id': entity['id'],
        'labels': entity.get('labels', {}),
        'descriptions': entity.get('descriptions', {}),
        'aliases': entity.get('aliases', {}),
    }

    # Add claims
    for prop, claims in entity['claims'].items():
        for claim in claims:
            if 'mainsnak' in claim and 'datavalue' in claim['mainsnak']:
                value = claim['mainsnak']['datavalue']['value']
                if claim['mainsnak']['datavalue']['type'] == 'wikibase-entityid':
                    insert_data += f"    wdt:{prop} wd:{value['id']} ;\n"
                    simple_entity[prop] = value['id']
                elif claim['mainsnak']['datavalue']['type'] == 'string':
                    insert_data += f"    wdt:{prop} \"{value}\" ;\n"
                    simple_entity[prop] = value
                elif claim['mainsnak']['datavalue']['type'] == 'time':
                    insert_data += f"    wdt:{prop} \"{value['time']}\"^^xsd:dateTime ;\n"
                    simple_entity[prop] = value['time']
                elif claim['mainsnak']['datavalue']['type'] == 'quantity':
                    insert_data += f"    wdt:{prop} \"{value['amount']}\"^^xsd:decimal ;\n"
                    simple_entity[prop] = value['amount']
                else:
                    # add without type
                    insert_data += f"    wdt:{prop} {value} ;\n"

    # Remove the last semicolon and add a period
    insert_data = insert_data.rstrip(' ;\n') + " .\n"

    # Close the INSERT DATA statement
    insert_data += "}\n"

    # Combine with prefixes
    sparql_insert = PREFIXES + insert_data

    # Print the SPARQL insert statement
    print(sparql_insert)
    return entity
