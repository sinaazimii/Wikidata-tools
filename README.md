# Wikidata-tools
Developing some tools around Wikidata

# Retrieve recent changes of the wiidata using wikimedia query:recentchanges api

There are 4 types of changes:
    edit: Edits to existing pages.
    new: Creation of new pages.
    log: Entries from various administrative and maintenance logs.
    categorize: Changes in the categorization of pages.

Currently we are only interested in edit/new type. 
    
    if a page is a new entity in wikidata then the resulting rdf should contain
    the title, description, and all the properties that have been added.

    if a page is edited the wikimedia compare api is being called and then
    the resulting rdf will be created.