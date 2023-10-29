import io
import json
import sys
import time
import logging

import matplotlib
import requests
from dotenv import load_dotenv
import os

import matplotlib.pyplot as plt
from PIL import Image
import concurrent.futures

THREADS = 32
IMAGE_SIZE = "224x224"
COORDINATES_PRECISION = 5  # Number of decimals to keep for the coordinates. 5 decimals is about 1 meter precision
OUTPUT_DIR = "./streetview_images/"
LOCATIONS_FILE = "./data/locations.json"
METADATA_DESTINATION = "./data/metadata.json"
LOGS_FILE = "./data/logs.log"
IMAGES_PER_CELL = 50
# Set None to process all locations
CHOSEN_CELLS = [
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
# CHOSEN_CELLS = None

downloaded_images = {}
collisions = {"exact": 0, "close": 0}
fails = {"request_failed": 0, "download_failed": 0, "no_image": 0, "no_lat_lng": 0}


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOGS_FILE, encoding='utf-8'), logging.StreamHandler(sys.stdout)],
    )

    logging.info('Download images started')

    load_dotenv()
    api_key = os.getenv("API_KEY")

    locations = load_locations_from_file('locations.json')

    visualize_generated_locations(
        [(location["lat"], location["lng"]) for cell in locations.values() for location in cell]
    )

    start = time.time()
    for cell_name, locations in locations.items():
        logging.info(f"Downloading images for {cell_name}...")
        output_dir = os.path.join(OUTPUT_DIR, cell_name)
        os.makedirs(output_dir, exist_ok=True)
        download_images(api_key, locations, output_dir)
    end = time.time()
    logging.info(f"Images downloaded in {end - start} seconds")
    logging.info(f"Downloaded images: {len(downloaded_images)}")
    logging.info(f"Collisions: {collisions}")
    logging.info(f"Fails: {fails}")
    save_metadata(METADATA_DESTINATION)


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
        cell_name = item['municipality']
        if not cell_name:
            continue  # Skip if no municipality
        if CHOSEN_CELLS and cell_name not in CHOSEN_CELLS:
            continue
        location = {"cell": cell_name, "lat": item['location'][1], "lng": item['location'][0]}
        if cell_name in locations:
            if len(locations[cell_name]) >= IMAGES_PER_CELL:
                continue
            locations[cell_name].append(location)
        else:
            locations[cell_name] = [location]
    for cell_name in locations:
        logging.info(f"{cell_name}: {len(locations[cell_name])} locations")
    return locations


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


def download_images(api_key, locations, output_dir):
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        executor.map(verify_and_download_image, [api_key] * len(locations), locations,
                     [output_dir] * len(locations))


def verify_and_download_image(api_key, location, output_dir):
    lat, lng, pano_id = check_street_view_image_existence(api_key, lat_lng_to_string(location['lat'], location['lng']))
    if lat and lng:
        key = f"{round(lat, COORDINATES_PRECISION)},{round(lng, COORDINATES_PRECISION)}"
        if key not in downloaded_images:
            # if download_street_view_image(api_key, lat, lng, IMAGE_SIZE, 0, output_dir):
            downloaded_images[key] = {
                "lat": lat,
                "lng": lng,
                "pano_id": pano_id,
                "heading": 0,
                "cell": location['cell']
            }
        else:
            if downloaded_images[key]["lat"] == lat and downloaded_images[key]["lng"] == lng:
                collisions["exact"] += 1
            else:
                collisions["close"] += 1
            logging.warning(f"Image for {key} already downloaded ({downloaded_images[key]}); new image: lat={lat}, lng={lng}, cell={location['cell']}")


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
        metadata_loc = metadata.get("location")
        if metadata.get("status") == "OK" and metadata_loc:
            lat = metadata_loc.get("lat")
            lng = metadata_loc.get("lng")
            if lat and lng:
                return lat, lng, metadata.get("pano_id")
            else:
                logging.warning(f"No latitude or longitude found in metadata ({metadata}); image: {location}")
                fails["no_lat_lng"] += 1
                return None, None, None  # Street View image does not exist
        else:
            logging.warning(f"No image found. Status code {metadata.get('status')}; image: {location}")
            fails["no_image"] += 1
            return None, None, None  # Street View image does not exist
    logging.warning(f"Request failed. Status code {response.status_code}; image: {location}")
    fails["request_failed"] += 1
    return None, None, None  # Request was not successful or failed


def download_street_view_image(api_key, lat, lng, size, heading=0, output_dir="./"):
    base_url = "https://maps.googleapis.com/maps/api/streetview"

    # Define the parameters for the request
    params = {
        "location": lat_lng_to_string(lat, lng),
        "size": size,
        "heading": heading,
        "pitch": 0,
        "fov": 90,
        "source": "outdoor",
        "return_error_codes": True,
        "key": api_key,
    }

    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        # Create a filename for the saved image
        filename = lat_lng_to_string(lat, lng)
        filepath = os.path.join(output_dir, filename)

        # Save the image to the specified directory
        with open(filepath, "wb") as f:
            f.write(response.content)
        return True
    else:
        logging.warning(f"Image download failed. Status code {response.status_code} url: {response.url}")
        fails["download_failed"] += 1
        return False


def lat_lng_to_string(lat, lng):
    return f"{lat},{lng}"


def save_metadata(output_file):
    # Create the output directory if it does not exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(os.path.join(output_file), 'w') as f:
        json.dump(downloaded_images, f)


if __name__ == "__main__":
    main()
