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
        'rclimit': '500',
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
    for change in changes:
        # print(f"Title: {change['title']}, Revision ID: {change['revid']}, User: {change['user']}, Timestamp: {change['timestamp']}")
        # print all properties of the change
        for key in change:
            print(key, ":", change[key])
            
        print("--------------------------------------------------")
    
    return changes

def compare_changes(api_url, title, old_rev, new_rev):
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
        beautify(diff)
    else:
        print("Comparison data unavailable.")


def beautify(diff_html):
    soup = BeautifulSoup(diff_html, 'html.parser')
    for change in soup.find_all('tr'):
        context = change.find('td', {'class': 'diff-lineno'})
        if context:
            print(f"\nContext: {context.get_text(strip=True)}")
        deleted = change.find('del', {'class': 'diffchange'})
        if deleted:
            text = ' '.join(deleted.stripped_strings)
            print(f"Removed: {parse_detail(text)}")
        added = change.find('ins', {'class': 'diffchange'})
        if added:
            text = ' '.join(added.stripped_strings)
            print(f"Added: {parse_detail(text)}")


def parse_detail(detail):
    if detail:
        # Splitting and cleaning up the details for better readability
        return ' | '.join([part.strip() for part in detail.split(':')])
    return ""

# Example usage:
start_dt = datetime(2024, 5, 4, 0, 0, 0)
end_dt = datetime(2024, 5, 5, 22, 0, 0)
changes = get_wikidata_updates(start_dt, end_dt)
# Calling compare changes with the first change in the list for demonstration
compare_changes("https://www.wikidata.org/w/api.php", "Q42", changes[0]["revid"], changes[0]["old_revid"])