import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime

URL = "https://www.meetup.com/find/?location=us--ma--swampscott"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def parse_event_jsonld(event_url: str):
    try:
        r = requests.get(event_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.content, 'html.parser')
        for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
            try:
                data = json.loads(script.string or '')
            except Exception:
                continue
            items = data if isinstance(data, list) else [data]
            for obj in items:
                if obj.get('@type') in ('Event', 'SocialEvent'):
                    start = obj.get('startDate')
                    name = obj.get('name')
                    if not start:
                        continue
                    try:
                        dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    except Exception:
                        dt = None
                    return {
                        'title': name,
                        'date': dt,
                        'url': event_url
                    }
        return None
    except Exception:
        return None

if __name__ == '__main__':
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')
    anchors = soup.find_all('a', href=True)
    event_urls = []
    for a in anchors:
        href = a.get('href')
        if not href:
            continue
        if href.startswith('/'):
            href = 'https://www.meetup.com' + href
        if 'meetup.com' in href and '/events/' in href:
            event_urls.append(href)
    event_urls = list(dict.fromkeys(event_urls))
    print(f"Found {len(event_urls)} event URLs on search page")
    events = []
    for u in event_urls[:30]:
        info = parse_event_jsonld(u)
        if info and info['date']:
            events.append(info)
    print(f"Parsed {len(events)} event details from event pages")
    for e in events[:10]:
        print(f"- {e['date'].strftime('%Y-%m-%d %H:%M')} | {e['title']} | {e['url']}")
