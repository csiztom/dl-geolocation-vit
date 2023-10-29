import io
import json
import time

import matplotlib
import requests
from dotenv import load_dotenv
import os

import matplotlib.pyplot as plt
from PIL import Image
import concurrent.futures

THREADS = 32
IMAGE_SIZE = "224"
OUTPUT_DIR = "./streetview_images/"
LOCATIONS_FILE = "./data/locations.json"
IMAGES_PER_LOCATION = 300
# Set None to process all locations
CHOSEN_LOCATIONS = [
    "Randers Kommune",
    "Silkeborg Kommune",
    "Horsens Kommune",
    "Gladsaxe Kommune",
    "Roskilde Kommune",
    "Kalundborg Kommune",
    "Esbjerg Kommune",
    "Kolding Kommune",
    "Slagelse Kommune",
    "Gentofte Kommune"
]


def check_street_view_image_existence(api_key, location):
    base_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {
        "location": location,
        "radius": 100,  # Search within # meters of the location
        "key": api_key
    }

    # Make the API request to retrieve metadata
    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        metadata = response.json()

        # Check the "status" field in the metadata
        location = metadata.get("location")
        if metadata.get("status") == "OK" and location:
            lat = location.get("lat")
            lng = location.get("lng")
            if lat and lng:
                return location.get("lat"), location.get("lng")
            else:
                print(f"ERROR: No latitude or longitude found in metadata. {metadata}")
                return None, None  # Street View image does not exist
        else:
            print(f"ERROR: No image found. Status code {metadata.get('status')}")
            return None, None  # Street View image does not exist
    print(f"ERROR: Request failed. Status code {response.status_code}")
    return None, None  # Request was not successful or failed


def download_images(api_key, locations, output_dir):
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        executor.map(verify_and_download_image, [api_key] * len(locations), locations, [output_dir] * len(locations))


def verify_and_download_image(api_key, location, output_dir):
    lat, lng = check_street_view_image_existence(api_key, f"{location[0]},{location[1]}")
    if lat and lng:
        download_street_view_image(api_key, (lat, lng), IMAGE_SIZE, output_dir=output_dir)


def download_street_view_image(api_key, location, size, heading=0, pitch=0, fov=90, output_dir="./"):
    base_url = "https://maps.googleapis.com/maps/api/streetview"

    # Define the parameters for the request
    params = {
        "location": f"{location[0]},{location[1]}",
        "size": size,
        "heading": heading,
        "pitch": pitch,
        "fov": fov,
        "return_error_codes": True,
        "key": api_key,
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        # Create a filename for the saved image
        filename = f"streetview_{location[0]}_{location[1]}.jpg"
        filepath = os.path.join(output_dir, filename)

        # Save the image to the specified directory
        with open(filepath, "wb") as f:
            f.write(response.content)
    else:
        print("ERROR: Image download failed.")


def visualize_generated_locations(points, polygon=None):
    matplotlib.use('Agg')

    y = [point[0] for point in points]  # Extract the x coordinate from the tuple
    x = [point[1] for point in points]  # Extract the y coordinate from the tuple

    # Create a plot to visualize the points and the polygon
    plt.figure(figsize=(8, 6))
    plt.scatter(x, y, c='blue', label='Images locations')
    if polygon:
        y_polygon = [point[0] for point in polygon]
        x_polygon = [point[1] for point in polygon]
        plt.plot(x_polygon + [x_polygon[0]], y_polygon + [y_polygon[0]], c='red', label='Region')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Coordinates of images')
    plt.legend()
    plt.grid(True)
    fig_io = io.BytesIO()
    plt.savefig(fig_io, format='png', dpi=300)
    fig_io.seek(0)

    # Display the saved figure
    Image.open(fig_io).show()


def load_locations_from_file(file_path):
    """
    File format:
    [
        {
            "location": [
                9.0617879,
                55.1878028
            ],
            "municipality": "T\u00f8nder Kommune"
        },
        {
            "location": [
                10.0307112,
                55.9739344
            ],
            "municipality": "Odder Kommune"
        },
        ...
    ]

    Result:
    [
        "Kommune_Name": [
            (56.156767293273234, 10.168922740310927),
            (56.10563022646918, 10.168311008571386),
        ]
        ...
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    locations = {}
    for item in data:
        municipality = item['municipality']
        if CHOSEN_LOCATIONS and municipality not in CHOSEN_LOCATIONS:
            continue
        location = tuple(item['location'])
        if municipality in locations:
            if len(locations[municipality]) >= IMAGES_PER_LOCATION:
                continue
            locations[municipality].append((location[1], location[0]))
        else:
            locations[municipality] = [(location[1], location[0])]
    for location in locations:
        print(f"{location}: {len(locations[location])} locations")
    return locations


if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("API_KEY")

    locations = load_locations_from_file('locations.json')

    visualize_generated_locations([value for values in locations.values() for value in values])

    start = time.time()
    for municipality, locations in locations.items():
        print(f"Downloading images for {municipality}...")
        output_dir = os.path.join(OUTPUT_DIR, municipality)
        os.makedirs(output_dir, exist_ok=True)
        download_images(api_key, locations, output_dir)
    end = time.time()
    print(f"Images downloaded in {end - start} seconds")
