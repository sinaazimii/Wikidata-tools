import requests
from datetime import datetime
from bs4 import BeautifulSoup
import readline
from rdflib import Graph, Namespace
import new_entity_rdf
import compare

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
        'format': 'json'
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

    # if change['type'] == 'new':
        # new_entity_rdf.main(change['title'], change['revid'])
    compare.compare_revisions(change['title'], old_rev, new_rev)
    

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
    print("----------------------------------------------------------")
    print(comparison_data)
    print("----------------------------------------------------------")

    if 'compare' in comparison_data:
        # Fetch The HTML diff of the changes using compare API
        diff = comparison_data['compare']['*'] 
        convert_to_rdf(diff, change['title'])
    else:
        print("Comparison data unavailable.")

def convert_to_rdf(diff_html, entity_id):
    # need a subject, predicate and object for each change
    subject = entity_id
    # diff_html =  '<tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P6127" href="/wiki/Property:P6127">Letterboxd film ID</a></td></tr><tr><td colspan="2">\xa0</td><td class="diff-marker" data-marker="+"></td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span><a class="wb-external-id external" href="https://letterboxd.com/film/carved-the-slit-mouthed-woman/" rel="nofollow">carved-the-slit-mouthed-woman</a></span></ins></div></td></tr><tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P6127" href="/wiki/Property:P6127">Letterboxd film ID</a>: <a class="wb-external-id external" href="https://letterboxd.com/film/carved-the-slit-mouthed-woman/" rel="nofollow">carved-the-slit-mouthed-woman</a> / rank</td></tr><tr><td colspan="2">\xa0</td><td class="diff-marker" data-marker="+"></td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span>Normal rank</span></ins></div></td></tr><tr><td colspan="2" class="diff-lineno"></td><td colspan="2" class="diff-lineno">Property / <a title="Property:P6127" href="/wiki/Property:P6127">Letterboxd film ID</a>: <a class="wb-external-id external" href="https://letterboxd.com/film/carved-the-slit-mouthed-woman/" rel="nofollow">carved-the-slit-mouthed-woman</a> / reference</td></tr><tr><td colspan="2">\xa0</td><td class="diff-marker" data-marker="+"></td><td class="diff-addedline"><div><ins class="diffchange diffchange-inline"><span><a title="Property:P854" href="/wiki/Property:P854">reference URL</a>: <a rel="nofollow" class="external free" href="https://letterboxd.com/tmdb/25744">https://letterboxd.com/tmdb/25744</a></span></ins></div></td></tr>'
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



def main ():
    print("To get updates from Wikidata, please provide "
    "the start and end date and time, for example: 2024-05-04 00:00:00")

    # start_dt = get_datetime_from_user("Enter the start date and time (YYYY-MM-DD HH:MM:SS): ")
    # end_dt = get_datetime_from_user("Enter the end date and time (YYYY-MM-DD HH:MM:SS): ")

    # put dummy inpout for testing
    start_dt = datetime(2024, 7, 1, 8, 20, 0)
    end_dt = datetime(2024, 7, 18, 0, 0, 1)

    changes = get_wikidata_updates(start_dt, end_dt)
    for change in changes:
        print(change)
    # # Calling compare changes with the first change in the list for demonstration
    compare_changes("https://www.wikidata.org/w/api.php", changes[1])

main()