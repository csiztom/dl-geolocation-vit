from geojson import load
from geojson import Point
from turfpy.measurement import boolean_point_in_polygon

with open("./data/denmark-adm7.geojson") as f:
    administrative = load(f)

def municipality(lat, lng):
    for shape in administrative['features']:
        if boolean_point_in_polygon(Point((lat,lng)), shape['geometry']):
            return shape['properties']['local_name']
    return None