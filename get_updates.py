import requests
from datetime import datetime

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


# Example usage:
start_dt = datetime(2024, 5, 4, 0, 0, 0)
end_dt = datetime(2024, 5, 5, 22, 0, 0)
get_wikidata_updates(start_dt, end_dt)
