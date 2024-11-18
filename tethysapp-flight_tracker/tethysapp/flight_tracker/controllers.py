from django.shortcuts import render
from django.http import JsonResponse

from tethys_sdk.routing import controller
from tethys_sdk.gizmos import CesiumMapView, SelectInput, TextInput, DatePicker, Button 

from datetime import datetime, timedelta
from pathlib import Path
import json
import requests
from requests.auth import HTTPBasicAuth

from .app import FlightTracker as App

def get_timestamps(start_date, start_time, end_date, end_time):
    """Get Unix timestamps for datetimes."""
    start_datetime = datetime.strptime(f"{start_date} {start_time}", '%m-%d-%Y %H:%M')
    end_datetime = datetime.strptime(f"{end_date} {end_time}", '%m-%d-%Y %H:%M')
    
    begin_timestamp = int(start_datetime.timestamp())
    end_timestamp = int(end_datetime.timestamp())

    return begin_timestamp, end_timestamp

@controller(name='home', url='home', app_workspace=True)
def cesium_map_view_controller(request, app_workspace):
    cesium_ion_token = App.get_custom_setting('cesium_ion_token')
    # Load airports geojson to display airports on the map
    geojson_file_path = Path(app_workspace.path) / 'flight_tracker' / 'data' / 'airports.geojson'
    with open(geojson_file_path, 'r') as f:
        airports_geojson_data = json.load(f)

    # Create a list to store the airport names and codes for the SelectInput gizmo's options
    airports = []

    for feature in airports_geojson_data['features']:
        airports.append({'code': feature['properties']['gps_code'], 'name': feature['properties']['name_en']})
        # Prepare the feature properties for display
        feature['properties'] = {
            'marker-symbol': 'airport',
            'marker-size': 'small',
            'Name': feature['properties']['name_en'],
            'Abbreviation': feature['properties']['iata_code'],
            'ICAO Code': feature['properties']['gps_code'],
            'More Information': feature['properties']['wikipedia'],
            'Latitude': feature['geometry']['coordinates'][1],
            'Longitude': feature['geometry']['coordinates'][0],
            'type': 'airport',
        }
    # Create a geojson layer to display the airports on the map
    geojson_layer = {
        'source': 'geojson',
        'options': airports_geojson_data
    }
    # Create a Cesium Map View gizmo
    cesium_map_view = CesiumMapView(
        height='100%',
        cesium_ion_token=cesium_ion_token,
        entities=[geojson_layer],
    )

    # Get default time values for form input Gizmos.
    today = datetime.now().strftime('%m-%d-%Y')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%m-%d-%Y')

    # Create form input gizmos
    airport_name = SelectInput(display_text='Airport Name', name='airport_name', multiple=False, options=[(airport['name'], airport['code']) for airport in airports], attributes={"class": "form-input"})
    place = SelectInput(display_text='Place', name='place', multiple=False, options=[('Departure', 'departure'), ('Arrival', 'arrival')], attributes={"class": "form-input"})
    start_date = DatePicker(name='start_date', display_text='Start Date', autoclose=True, format='mm-dd-yyyy', start_date='01-01-2010', end_date=today, initial=yesterday, attributes={"class": "form-input"})
    end_date = DatePicker(name='end_date', display_text='End Date', autoclose=True, format='mm-dd-yyyy', start_date='01-01-2010', end_date=today, initial=today, attributes={"class": "form-input"})
    flights_from_airport_button = Button(display_text='Find Flights', name='flights', submit=True, style='success', attributes={'form': 'flights-from-airport-form'})
    
    aircraft_number = TextInput(display_text='Aircraft ICAO24 Number', name='aircraft_number')
    aircraft_start_date = DatePicker(name='aircraft_start_date', display_text='Start Date', autoclose=True, format='mm-dd-yyyy', start_date='01-01-2010', end_date=today, initial=yesterday, attributes={"class": "form-input"})
    aircraft_end_date = DatePicker(name='aircraft_end_date', display_text='End Date', autoclose=True, format='mm-dd-yyyy', start_date='01-01-2010', end_date=today, initial=today, attributes={"class": "form-input"})
    aircraft_number_button = Button(display_text='Submit', name='submit', submit=True, style='success', attributes={'form': 'aircraft-tracker-form', 'id':'aircraft-number-button'})
    
    # Form the context to pass to the template
    context = {
        'cesium_map_view': cesium_map_view,
        'cesium_ion_token': cesium_ion_token,
        'airport_name': airport_name,
        'place': place,
        'start_date': start_date,
        'end_date': end_date,
        'flights_from_airport_button': flights_from_airport_button,
        'aircraft_number': aircraft_number,
        'aircraft_number_button': aircraft_number_button,
        'aircraft_start_date': aircraft_start_date,
        'aircraft_end_date': aircraft_end_date
    }

    return render(request, 'flight_tracker/home.html', context)

@controller(name='get_flights_endpoint', url='get-flights')
def get_flights(request):
    # Get data from the POST request sent in the form
    request_data = request.POST
    start_date = request_data.get('start_date')
    start_time = request_data.get('start_time')
    end_date = request_data.get('end_date')
    end_time = request_data.get('end_time')
    airport_name = request_data.get('airport_name')
    place = request_data.get('place').lower()
    if place not in ['arrival', 'departure']:
        return JsonResponse({'error': 'Invalid place value. Must be "arrival" or "departure".'}, status=400)

    # Get Unix timestamps for datetimes
    start_timestamp, end_timestamp = get_timestamps(start_date, start_time, end_date, end_time)

    if (end_timestamp - start_timestamp) > 7 * 24 * 60 * 60:
        return JsonResponse({'error': 'The time difference cannot be more than 7 days.'}, status=400)
    
    # Query OpenSky API
    username = App.get_custom_setting('open_sky_username')
    password = App.get_custom_setting('open_sky_password')
    api_response = requests.get(f'https://opensky-network.org/api/flights/{place}?airport={airport_name}&begin={start_timestamp}&end={end_timestamp}', 
                            auth=HTTPBasicAuth(username, password))
    
    if api_response.status_code == 404:
        return JsonResponse({'error': 'No flights found.'}, status=404)
    elif api_response.status_code != 200:       
        return JsonResponse({'error': 'An error occurred while querying OpenSky.'}, status=500)
    
    # Form the JSON response with the desired data from the API response
    json_response = {"flights": []}
    for flight in api_response.json():
        json_response['flights'].append({
            "departure_airport": flight['estDepartureAirport'],
            "arrival_airport": flight['estArrivalAirport'],
            "departure_time": datetime.fromtimestamp(flight['firstSeen']).strftime('%Y-%m-%d %H:%M:%S'),
            "arrival_time": datetime.fromtimestamp(flight['lastSeen']).strftime('%Y-%m-%d %H:%M:%S'),
            "flight_id": flight['callsign'],
            "icao24": flight['icao24']
        })

    return JsonResponse(json_response)

@controller(name='get_aircraft_endpoint', url='track-aircraft')
def get_aircraft(request):
    # Get data from the POST request sent in the form
    request_data = request.POST
    aircraft_number = request_data.get('aircraft_number')
    start_date = request_data.get('aircraft_start_date')
    start_time = request_data.get('aircraft_start_time')
    end_date = request_data.get('aircraft_end_date')
    end_time = request_data.get('aircraft_end_time')

    start_timestamp, end_timestamp = get_timestamps(start_date, start_time, end_date, end_time)

    if (end_timestamp - start_timestamp) > 30 * 24 * 60 * 60:
        return JsonResponse({'error': 'The time difference cannot be more than 30 days.'}, status=400)

    # Query OpenSky API
    username = App.get_custom_setting('open_sky_username')
    password = App.get_custom_setting('open_sky_password')
    api_response = requests.get(f'https://opensky-network.org/api/flights/aircraft?icao24={aircraft_number}&begin={start_timestamp}&end={end_timestamp}', 
                            auth=HTTPBasicAuth(username, password))
    
    # Form the JSON response with the desired data from the API response
    json_response = {"flights": []}
    for flight in api_response.json():
        if flight['estDepartureAirport'] is not None and flight['estArrivalAirport'] is not None:
            json_response['flights'].append({
                "departure_airport": flight['estDepartureAirport'],
                "arrival_airport": flight['estArrivalAirport'],
                "departure_time": datetime.fromtimestamp(flight['firstSeen']).strftime('%Y-%m-%d %H:%M:%S'),
                "arrival_time": datetime.fromtimestamp(flight['lastSeen']).strftime('%Y-%m-%d %H:%M:%S'),
                "flight_id": flight['callsign'],
                "icao24": flight['icao24']
            })

    return JsonResponse(json_response)

    
