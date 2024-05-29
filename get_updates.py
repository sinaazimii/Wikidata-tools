import requests
from datetime import datetime
from bs4 import BeautifulSoup

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
        # 'rclimit': '5', # Limit the number of changes returned up to 500
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
    for change in changes:
        # print(f"Title: {change['title']}, Revision ID: {change['revid']}, User: {change['user']}, Timestamp: {change['timestamp']}")
        # print all properties of the change
        for key in change:
            print(key, ":", change[key])
            
        print("--------------------------------------------------")
    
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

    if 'compare' in comparison_data:
        diff = comparison_data['compare']['*']
        print("Changes:")
        # old_beauty(diff)
        convert_to_rdf(diff)
    else:
        print("Comparison data unavailable.")


def old_beauty(diff_html):
    print(diff_html)
    soup = BeautifulSoup(diff_html, 'html.parser')
    for change in soup.find_all('tr'):
        context = change.find('td', {'class': 'diff-lineno'})
        if context:
            print(f"\nContext: {context.get_text(strip=True)}")
        deleted = change.find('del', {'class': 'diffchange'})
        if deleted:
            text = ' '.join(deleted.stripped_strings)
            print(f"Deleted: {(text)}")

        added = change.find('ins', {'class': 'diffchange'})
        if added:
            text = ' '.join(added.stripped_strings)
            print(f"Added: {(text)}")


def convert_to_rdf(diff_html):
    html_content = diff_html

    soup = BeautifulSoup(html_content, 'html.parser')

    entity_id = "Q10457069"  # The ID of the Wikidata entity you're updating

    deletes = []
    inserts = []

    rows = soup.find_all('tr')
    for row in rows:
        if 'Property' in row.text:
            property_link = row.find('a', href=True)
            if property_link:
                property_name = property_link.text
                property_url = property_link['href']
                property_id = property_url.split(':')[-1]
                print(f'Property: {property_name} ({property_id})')

        deleted_cell = row.find('td', class_='diff-deletedline')
        if deleted_cell:
            value = deleted_cell.find('del', class_='diffchange')
            if value:
                deleted_value = value.text.strip()
                deletes.append((property_id, deleted_value))
                print(f'Deleted value: {deleted_value}')

        added_cell = row.find('td', class_='diff-addedline')
        if added_cell:
            value = added_cell.find('ins', class_='diffchange')
            if value:
                added_value = value.text.strip()
                inserts.append((property_id, added_value))
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


# Example usage:
start_dt = datetime(2024, 5, 4, 0, 0, 0)
end_dt = datetime(2024, 5, 5, 22, 0, 0)
changes = get_wikidata_updates(start_dt, end_dt)
# Calling compare changes with the first change in the list for demonstration
compare_changes("https://www.wikidata.org/w/api.php", changes[0])