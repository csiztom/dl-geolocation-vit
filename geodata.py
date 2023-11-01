from geojson import load
from geojson import Point
from turfpy.measurement import boolean_point_in_polygon

with open("./data/denmark-adm7.geojson") as f:
    administrative = load(f)

cities = {}

def municipality(lng, lat, city=None):
    if city and city in cities:
        return cities[city]
    for shape in administrative['features']:
        if boolean_point_in_polygon(Point((lng,lat)), shape['geometry']):
            if city:
                cities[city] = shape['properties']['local_name']
            return shape['properties']['local_name']
    return None