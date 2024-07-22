# Wikidata-tools
Developing some tools around Wikidata

# Retrieve recent changes of the wikidata
The main goal of get_updates.py is to retrieve the latest changes that has been applied to wikidata,
in the format of rdf queries. For this purpose we use wikidata api called recentchanges.
And afterwards they are parsed into rdf format.

e.g. 
INSERT {
    subject predicate object
}

DELETE {
    subject predicate object
}


## Getting Started
```bash
git clone git@github.com:sinaazimii/Wikidata-tools.git
pip install requirements.txt
python3 get_updates.py


```

There are 4 types of changes:
    edit: Edits to an existing page.
    new: Creation of a new page.
    log: Entries from various administrative and maintenance logs.
    categorize: Changes in the categorization of pages.

Currently we are only interested in edit/new type. 
    
    if a page is a new entity in wikidata then the resulting rdf should contain
    the title, description, and all the properties that have been added. 
    The logic that do this operation can be found in new_entity_rdf.py.

    if a page is edited the wikimedia compare api is being called and then
    the resulting rdf will be created.