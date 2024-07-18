import requests
import json
import new_entity_rdf


def compare_revisions(entity_id, old_rev, new_rev):
    old_json = new_entity_rdf.main(entity_id, old_rev)
    new_json = new_entity_rdf.main(entity_id, new_rev)

    print(entity_id)
    print(old_rev)
    print(new_rev)

    print("Old JSON:")
    print(old_json)
    print("New JSON:")
    print(new_json)



