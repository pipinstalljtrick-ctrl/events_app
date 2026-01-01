"""
Local Events Calendar Application
==================================
This application displays events within a 5-mile radius of Swampscott, Massachusetts (01907)
in a calendar format organized by date.

Features:
- Fetches events from multiple sources (Eventbrite, Ticketmaster)
- Filters events by 5-mile proximity from zip code 01907
- Displays events in calendar format
- Shows event details (name, date, time, location, distance)
- Web-based interface for easy navigation

Author: Claude
Date: December 31, 2025
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import os
from dotenv import load_dotenv
import geopy.distance
from geopy.geocoders import Nominatim
import folium
from folium.plugins import MarkerCluster
import webbrowser

# Load environment variables
load_dotenv()

class EventsCalendar:
    """
    Local events calendar for Swampscott, Massachusetts area.
    """
    
    # Swampscott, MA coordinates
    SWAMPSCOTT_ZIP = "01907"
    SWAMPSCOTT_COORDS = (42.4825, -70.8800)  # Latitude, Longitude
    RADIUS_MILES = 5
    
    def __init__(self):
        """Initialize the events calendar."""
        self.events = []
        self.geocoder = Nominatim(user_agent="events_calendar")
        self.ticketmaster_api_key = os.getenv('TICKETMASTER_API_KEY', '')
        self.eventbrite_api_key = os.getenv('EVENTBRITE_API_KEY', '')
        
    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance in miles between two coordinates.
        
        Parameters:
        -----------
        lat1, lon1 : float
            Starting coordinates (latitude, longitude)
        lat2, lon2 : float
            Ending coordinates (latitude, longitude)
            
        Returns:
        --------
        float : Distance in miles
        """
        coords1 = (lat1, lon1)
        coords2 = (lat2, lon2)
        distance_km = geopy.distance.geodesic(coords1, coords2).kilometers
        return distance_km * 0.621371  # Convert km to miles
    
    def fetch_ticketmaster_events(self) -> List[Dict]:
        """
        Fetch events from Ticketmaster Discovery API.
        
        Returns:
        --------
        list : List of event dictionaries
        """
        if not self.ticketmaster_api_key:
            print("⚠ Ticketmaster API key not found. Skipping Ticketmaster events.")
            return []
        
        print("Fetching events from Ticketmaster...")
        events = []
        
        try:
            # Convert radius from miles to kilometers
            radius_km = self.RADIUS_MILES * 1.60934
            
            url = "https://app.ticketmaster.com/discovery/v2/events.json"
            params = {
                'latlong': f'{self.SWAMPSCOTT_COORDS[0]},{self.SWAMPSCOTT_COORDS[1]}',
                'radius': radius_km,
                'unit': 'km',
                'apikey': self.ticketmaster_api_key,
                'size': 200
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if '_embedded' in data and 'events' in data['embedded']:
                for event in data['_embedded']['events']:
                    event_dict = self._parse_ticketmaster_event(event)
                    if event_dict:
                        events.append(event_dict)
            
            print(f"✓ Found {len(events)} events from Ticketmaster")
            
        except Exception as e:
            print(f"✗ Error fetching Ticketmaster events: {e}")
        
        return events
    
    def _parse_ticketmaster_event(self, event: Dict) -> Dict:
        """Parse Ticketmaster event data."""
        try:
            name = event.get('name', 'Unknown Event')
            event_date = event['dates']['start'].get('dateTime', event['dates']['start'].get('localDate', ''))
            
            # Extract location
            venue = event['_embedded']['venues'][0] if '_embedded' in event and 'venues' in event['_embedded'] else {}
            location = venue.get('name', 'Unknown Venue')
            lat = float(venue.get('location', {}).get('latitude', 0))
            lon = float(venue.get('location', {}).get('longitude', 0))
            
            # Calculate distance
            distance = self.calculate_distance(self.SWAMPSCOTT_COORDS[0], self.SWAMPSCOTT_COORDS[1], lat, lon)
            
            # Filter by radius
            if distance > self.RADIUS_MILES:
                return None
            
            url = event.get('url', '')
            
            return {
                'name': name,
                'date': event_date,
                'location': location,
                'latitude': lat,
                'longitude': lon,
                'distance': round(distance, 2),
                'url': url,
                'source': 'Ticketmaster'
            }
        
        except Exception as e:
            print(f"Error parsing event: {e}")
            return None
    
    def fetch_eventbrite_events(self) -> List[Dict]:
        """
        Fetch events from Eventbrite API.
        
        Returns:
        --------
        list : List of event dictionaries
        """
        if not self.eventbrite_api_key:
            print("⚠ Eventbrite API key not found. Skipping Eventbrite events.")
            return []
        
        print("Fetching events from Eventbrite...")
        events = []
        
        try:
            # Eventbrite uses different coordinate format
            # We need to calculate bounding box from center point and radius
            lat_offset = (self.RADIUS_MILES / 69.0)  # Rough conversion
            lon_offset = (self.RADIUS_MILES / (69.0 * abs(__import__('math').cos(__import__('math').radians(self.SWAMPSCOTT_COORDS[0])))))
            
            min_lat = self.SWAMPSCOTT_COORDS[0] - lat_offset
            max_lat = self.SWAMPSCOTT_COORDS[0] + lat_offset
            min_lon = self.SWAMPSCOTT_COORDS[1] - lon_offset
            max_lon = self.SWAMPSCOTT_COORDS[1] + lon_offset
            
            url = "https://www.eventbriteapi.com/v3/events/search"
            headers = {'Authorization': f'Bearer {self.eventbrite_api_key}'}
            params = {
                'location.latitude': self.SWAMPSCOTT_COORDS[0],
                'location.longitude': self.SWAMPSCOTT_COORDS[1],
                'location.within': '8km',  # Approximately 5 miles
                'sort_by': 'date',
                'expand': 'venue'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            for event in data.get('events', []):
                event_dict = self._parse_eventbrite_event(event)
                if event_dict:
                    events.append(event_dict)
            
            print(f"✓ Found {len(events)} events from Eventbrite")
            
        except Exception as e:
            print(f"✗ Error fetching Eventbrite events: {e}")
        
        return events
    
    def _parse_eventbrite_event(self, event: Dict) -> Dict:
        """Parse Eventbrite event data."""
        try:
            name = event.get('name', {}).get('text', 'Unknown Event')
            event_date = event.get('start', {}).get('local', '')
            url = event.get('url', '')
            
            # Extract venue location
            venue = event.get('venue', {})
            location = venue.get('name', 'Unknown Venue')
            lat = float(venue.get('latitude', 0))
            lon = float(venue.get('longitude', 0))
            
            # Calculate distance
            distance = self.calculate_distance(self.SWAMPSCOTT_COORDS[0], self.SWAMPSCOTT_COORDS[1], lat, lon)
            
            # Filter by radius
            if distance > self.RADIUS_MILES:
                return None
            
            return {
                'name': name,
                'date': event_date,
                'location': location,
                'latitude': lat,
                'longitude': lon,
                'distance': round(distance, 2),
                'url': url,
                'source': 'Eventbrite'
            }
        
        except Exception as e:
            print(f"Error parsing event: {e}")
            return None
    
    def fetch_all_events(self) -> List[Dict]:
        """
        Fetch events from all sources.
        
        Returns:
        --------
        list : Combined list of all events
        """
        print(f"\n{'='*70}")
        print("FETCHING EVENTS FOR SWAMPSCOTT, MA (01907)")
        print(f"Radius: {self.RADIUS_MILES} miles")
        print(f"Coordinates: {self.SWAMPSCOTT_COORDS}")
        print(f"{'='*70}\n")
        
        all_events = []
        
        # Fetch from Ticketmaster
        all_events.extend(self.fetch_ticketmaster_events())
        
        # Fetch from Eventbrite
        all_events.extend(self.fetch_eventbrite_events())
        
        # Remove duplicates and sort by date
        unique_events = {event['name'] + event['date']: event for event in all_events}
        self.events = sorted(unique_events.values(), key=lambda x: x['date'])
        
        return self.events
    
    def get_events_by_date(self) -> Dict[str, List[Dict]]:
        """
        Group events by date.
        
        Returns:
        --------
        dict : Events organized by date
        """
        events_by_date = {}
        
        for event in self.events:
            try:
                # Parse date
                event_datetime = datetime.fromisoformat(event['date'].replace('Z', '+00:00'))
                date_key = event_datetime.strftime('%Y-%m-%d')
                
                if date_key not in events_by_date:
                    events_by_date[date_key] = []
                
                events_by_date[date_key].append(event)
            
            except Exception as e:
                print(f"Error parsing date for {event['name']}: {e}")
        
        return events_by_date
    
    def print_calendar(self):
        """Print events in calendar format."""
        events_by_date = self.get_events_by_date()
        
        if not events_by_date:
            print("\n⚠ No events found in the specified area.")
            return
        
        print(f"\n{'='*100}")
        print("EVENTS CALENDAR - SWAMPSCOTT, MA (01907) - 5 MILE RADIUS")
        print(f"{'='*100}\n")
        
        for date_key in sorted(events_by_date.keys()):
            date_obj = datetime.strptime(date_key, '%Y-%m-%d')
            day_name = date_obj.strftime('%A')
            
            print(f"\n{'─'*100}")
            print(f"📅 {date_key} ({day_name})")
            print(f"{'─'*100}")
            
            for idx, event in enumerate(events_by_date[date_key], 1):
                print(f"\n  {idx}. {event['name']}")
                print(f"     📍 Location: {event['location']}")
                print(f"     🕐 Time: {event['date']}")
                print(f"     📏 Distance: {event['distance']} miles")
                print(f"     🌐 Source: {event['source']}")
                if event['url']:
                    print(f"     🔗 URL: {event['url']}")
        
        print(f"\n{'='*100}")
        print(f"Total Events Found: {len(self.events)}")
        print(f"{'='*100}\n")
    
    def generate_map(self, output_file: str = 'events_map.html'):
        """
        Generate interactive map with events.
        
        Parameters:
        -----------
        output_file : str
            Output HTML file name
        """
        if not self.events:
            print("No events to map.")
            return
        
        print(f"\nGenerating interactive map...")
        
        # Create base map centered on Swampscott
        map_center = [self.SWAMPSCOTT_COORDS[0], self.SWAMPSCOTT_COORDS[1]]
        m = folium.Map(
            location=map_center,
            zoom_start=13,
            tiles='OpenStreetMap'
        )
        
        # Add center marker
        folium.Marker(
            location=map_center,
            popup='Swampscott, MA (01907)',
            icon=folium.Icon(color='blue', icon='info-sign'),
            tooltip='Center Point'
        ).add_to(m)
        
        # Add circle for 5-mile radius
        folium.Circle(
            location=map_center,
            radius=self.RADIUS_MILES * 1609.34,  # Convert miles to meters
            popup=f'{self.RADIUS_MILES} Mile Radius',
            color='blue',
            fill=True,
            fillColor='lightblue',
            fillOpacity=0.2,
            weight=2
        ).add_to(m)
        
        # Add event markers with cluster
        marker_cluster = MarkerCluster().add_to(m)
        
        for event in self.events:
            popup_text = f"""
            <b>{event['name']}</b><br>
            {event['location']}<br>
            {event['date']}<br>
            Distance: {event['distance']} mi<br>
            <a href='{event['url']}' target='_blank'>More Info</a>
            """
            
            folium.Marker(
                location=[event['latitude'], event['longitude']],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=event['name'],
                icon=folium.Icon(color='red', icon='calendar')
            ).add_to(marker_cluster)
        
        # Save map
        m.save(output_file)
        print(f"✓ Map saved as '{output_file}'")
        
        return output_file
    
    def export_json(self, output_file: str = 'events.json'):
        """
        Export events to JSON file.
        
        Parameters:
        -----------
        output_file : str
            Output JSON file name
        """
        with open(output_file, 'w') as f:
            json.dump(self.events, f, indent=2)
        print(f"✓ Events exported to '{output_file}'")
    
    def export_csv(self, output_file: str = 'events.csv'):
        """
        Export events to CSV file.
        
        Parameters:
        -----------
        output_file : str
            Output CSV file name
        """
        import csv
        
        if not self.events:
            print("No events to export.")
            return
        
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['name', 'date', 'location', 'latitude', 'longitude', 'distance', 'source', 'url']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerows(self.events)
        
        print(f"✓ Events exported to '{output_file}'")


def main():
    """
    Main execution function.
    """
    # Create calendar
    calendar = EventsCalendar()
    
    # Fetch all events
    events = calendar.fetch_all_events()
    
    # Print calendar
    calendar.print_calendar()
    
    # Generate map
    if events:
        map_file = calendar.generate_map('events_map.html')
        
        # Export to JSON
        calendar.export_json('events.json')
        
        # Export to CSV
        calendar.export_csv('events.csv')
        
        print("\n✓ Analysis complete!")
        print(f"\nGenerated files:")
        print(f"  - events_map.html (Interactive map)")
        print(f"  - events.json (JSON data)")
        print(f"  - events.csv (CSV data)")
        
        # Ask to open map
        try:
            response = input("\nOpen events map in browser? (y/n): ").lower()
            if response == 'y':
                webbrowser.open(map_file)
        except:
            pass
    else:
        print("\n⚠ No events found. Make sure API keys are configured.")


if __name__ == "__main__":
    main()
