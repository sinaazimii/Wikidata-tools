# Wikidata-tools
Developing some tools around Wikidata

# Retrieve recent changes of the wikidata
The main goal of get_updates.py is to retrieve the latest changes that has been applied to wikidata,
in the format of rdf queries. For this purpose we use wikidata api called recentchanges.
And afterwards they are parsed into rdf format.

e.g.\
INSERT {
    subject predicate object
}

DELETE {
    subject predicate object
}


## Getting Started
```bash
git clone git@github.com:sinaazimii/Wikidata-tools.git
git checkout master
pip install requirements.txt
python3 get_updates.py #run the simple form, get the 5 latest changes of any type
```

There are 4 types of changes:
    edit: Edits to an existing page.
    new: Creation of a new page.
    log: Entries from various administrative and maintenance logs.
    categorize: Changes in the categorization of pages.

Currently we are only interested in edit/new type. 

* if a page is a new entity in wikidata then the resulting rdf should contain
the title, description, and all the properties that have been added. 
The logic that do this operation can be found in new_entity_rdf.py.

* if a page is edited the wikimedia compare api is being called and then
the resulting rdf will be created.


## Arguments
Arguments are:
```bash
"-h" :  "Show help message"
"-f" :  "store the output in a file"
"-l" : "get latest changes"
"-t" : "filter the type of changes. possible values are edit|new, edit, new"
"-n" : "number of changes to get, not setting will get 5 changes"
"-st" : "start date and time, in form of 'YYYY-MM-DD HH:MM:SS, not setting start and end date will get latest changes"
"-et" : "end date and time, in form of 'YYYY-MM-DD HH:MM:SS'"
```
Usage examples:
```bash
python3 get_updates.py -h #show help message
python3 get_updates.py -t edit -n 15 #get 15 of latest updates with type edit
python3 get_updates.py -n 5 -t new -st '2024-07-22 11:56:10' -et '2024-07-22 11:56:15' #get 5 of updates with type new with time interval between 2024-07-22 11:56:10 and 2024-07-22 11:56:15
```

## Contact
email: sinaazm15@gmail.com 