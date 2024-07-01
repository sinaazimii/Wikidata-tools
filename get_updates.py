import requests
from datetime import datetime
from bs4 import BeautifulSoup
import readline
from rdflib import Graph, Namespace

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
    }

    # Make the request
    response = requests.get(api_url, params=params)
    data = response.json()

    # Check for errors in the response
    if 'error' in data:
        print("Error:", data['error']['info'])
        return
    
    # Print the changes
    changes = data.get('query', {}).get('recentchanges', [])
    # for change in changes:
    #     # print all properties of the change
    #     for key in change:
    #         print(key, ":", change[key])
            
    #     print("--------------------------------------------------")
    
    return changes

def compare_changes(api_url, change):
    new_rev = change["revid"]
    old_rev = change["old_revid"]
    params = {
        'action': 'compare',
        'fromrev': old_rev,
        'torev': new_rev,
        'format': 'json'
    }
    
    response = requests.get(api_url, params=params)
    comparison_data = response.json()

    # access the comparison data
    # comparison_data['compare']['totitle']
    # comparison_data['compare']['fromrevid']
    # comparison_data['compare']['torevid']


    if 'compare' in comparison_data:
        # Fetch The HTML diff of the changes using compare API
        diff = comparison_data['compare']['*']  
        convert_to_rdf(diff, change['title'])
    else:
        print("Comparison data unavailable.")

def convert_to_rdf(diff_html, entity_id):
    soup = BeautifulSoup(diff_html, 'html.parser')

    deletes = []
    inserts = []
    diff_html = '<tr><td colspan="2" class="diff-lineno">description / bar</td><td colspan="2" class="diff-lineno">description / bar</td></tr><tr><td colspan="2"> </td><td class="diff-marker" data-marker="+"></td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline">Wikimedia-Vorlog</ins></div></td></tr>'
    rows = soup.find_all('tr')
    for row in rows:
        current_predicate = None
        # Check if the row contains a property (predicate)
        if 'Property' in row.text:
            property_link = row.find('a', href=True)
            if property_link:
                property_name = property_link.text
                property_url = property_link['href']
                current_predicate = property_url.split(':')[-1]
                print(f'Predicate: {property_name} ({current_predicate})')
            
        # Process deleted values
        if row.find('td', class_='diff-deletedline'):
            value = row.find('del', class_='diffchange')
            if value and current_predicate:
                deleted_value = value.text.strip()
                deletes.append((current_predicate, deleted_value))
                print(f'Deleted value: {deleted_value}')
        
        # Process added values
        if row.find('td', class_='diff-addedline'):
            value = row.find('ins', class_='diffchange')
            if value and current_predicate:
                added_value = value.text.strip()
                inserts.append((current_predicate, added_value))
                print(f'Added value: {added_value}')

    # Construct DELETE and INSERT statements
    delete_statements = []
    insert_statements = []

    for prop, val in deletes:
        delete_statements.append(f"  wd:{entity_id} wdt:{prop} \"{val}\" .")

    for prop, val in inserts:
        insert_statements.append(f"  wd:{entity_id} wdt:{prop} \"{val}\" .")

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
    print("@prefix wd: <https://www.wikidata.org/wiki/> .\n"
        "@prefix wdt: <http://www.wikidata.org/property/> .\n\n")
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



def fetch_rdf(entity_id, revision_id):
    """
    Fetch RDF data for a Wikidata entity at a specific revision.
    """
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.ttl"
    if revision_id:
        url += f"?revision={revision_id}"
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def parse_rdf(data):
    """
    Parse RDF data into an RDFLib Graph.
    """
    graph = Graph()
    graph.parse(data=data, format='turtle')
    return graph

def diff_graphs(old_graph, new_graph):
    """
    Compute the differences between two RDF graphs.
    """
    added = new_graph - old_graph
    removed = old_graph - new_graph
    return added, removed

def format_sparql_statements(added, removed):
    """
    Format the differences into SPARQL DELETE DATA and INSERT DATA statements.
    """
    graph = Graph()
    # Define namespaces
    WD = Namespace("http://www.wikidata.org/entity/")
    WDT = Namespace("http://www.wikidata.org/prop/direct/")

    # Bind namespaces to the graph
    graph.bind("wd", WD)
    graph.bind("wdt", WDT)

    delete_data = ""
    insert_data = ""

    for s, p, o in removed:
        delete_data += f"DELETE DATA {{ wd:{s.n3(graph.namespace_manager)} wdt:{p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)} . }}\n"

    for s, p, o in added:
        insert_data += f"INSERT DATA {{ wd:{s.n3(graph.namespace_manager)} wdt:{p.n3(graph.namespace_manager)} {o.n3(graph.namespace_manager)} . }}\n"


    return delete_data,  insert_data




def main ():
    print("To get updates from Wikidata, please provide "
    "the start and end date and time, for example: 2024-05-04 00:00:00")

    # start_dt = get_datetime_from_user("Enter the start date and time (YYYY-MM-DD HH:MM:SS): ")
    # end_dt = get_datetime_from_user("Enter the end date and time (YYYY-MM-DD HH:MM:SS): ")

    # put dummy inpout for testing
    start_dt = datetime(2024, 6, 1, 0, 0, 0)
    end_dt = datetime(2024, 7, 23, 0, 0, 1)

    changes = get_wikidata_updates(start_dt, end_dt)
    print((changes[1]))

    # # Calling compare changes with the first change in the list for demonstration
    # compare_changes("https://www.wikidata.org/w/api.php", changes[0])



    # # Entity ID and revision IDs
    entity_id = changes[1]["title"]
    old_revision_id = changes[1]["old_revid"]
    new_revision_id =  changes[1]["revid"]

    # Fetch RDF data
    old_rdf = fetch_rdf(entity_id, old_revision_id)
    new_rdf = fetch_rdf(entity_id, new_revision_id)

    # Parse RDF data into graphs
    old_graph = parse_rdf(old_rdf)
    new_graph = parse_rdf(new_rdf)

    # Compute differences
    added, removed = diff_graphs(old_graph, new_graph)

    # Format SPARQL statements with namespaces
    delete_data, insert_data = format_sparql_statements(added, removed)

    # Output the SPARQL statements
    print(delete_data)
    print(insert_data)


main()