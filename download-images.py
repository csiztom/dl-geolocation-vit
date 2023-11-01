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
VISUALIZATION_FILE = "./data/visualization.png"
LOGS_FILE = "./data/logs.log"
IMAGES_PER_CELL = 2

downloaded_images = {}
collisions = {"exact": 0, "close": 0}
fails = {"request_failed": 0, "download_failed": 0, "no_image": 0, "no_lat_lng": 0}

load_dotenv()
api_key = os.getenv("API_KEY")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOGS_FILE, encoding='utf-8'), logging.StreamHandler(sys.stdout)],
    )

    logging.info('Download images started')

    locations = load_locations_from_file(LOCATIONS_FILE)

    visualize_generated_locations(
        [(location["lat"], location["lng"]) for cell in locations.values() for location in cell]
    )

    start = time.time()
    for cell_name, locations in locations.items():
        logging.info(f"Downloading images for {cell_name}...")
        output_dir = os.path.join(OUTPUT_DIR, cell_name)
        os.makedirs(output_dir, exist_ok=True)
        download_images(locations, output_dir)
    end = time.time()
    logging.info(f"Images downloaded in {end - start} seconds")
    logging.info(f"Downloaded images: {len(downloaded_images)}")
    logging.info(f"Collisions: {collisions}")
    logging.info(f"Fails: {fails}")
    save_metadata(METADATA_DESTINATION)

    # Count number of downloaded images in each cell
    downloaded_images_per_cell = {}
    for image in downloaded_images:
        cell = image["cell"]
        if not downloaded_images_per_cell.get(cell):
            downloaded_images_per_cell[cell] = 0
        downloaded_images_per_cell[cell] += 1

    # Print number of downloaded images in each cell
    logging.info("Number of downloaded images in each cell:")
    for cell in downloaded_images_per_cell:
        logging.info(f"{cell}: {downloaded_images_per_cell[cell]}")


def load_locations_from_file(file_path):
    """
    File format:
    [
        {
            "location": [
                10.0307112,
                55.9739344
            ],
            "municipality": "Odder Kommune",
            "city": "Odder C"
        },
        ...
    ]
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    locations = {}
    for item in data:
        cell_name = item['municipality']
        city = item['city']
        if not cell_name:
            continue  # Skip if no municipality
        location = {"cell": cell_name, "lat": item['location'][1], "lng": item['location'][0]}
        if not locations.get(cell_name):
            locations[cell_name] = {"cities": {}, "count": 0}
        if not locations[cell_name]["cities"].get(city):
            locations[cell_name]["cities"][city] = {"locations": [], "count": 0}

        locations[cell_name]["cities"][city]["locations"].append(location)
        locations[cell_name]["count"] += 1
        locations[cell_name]["cities"][city]["count"] += 1

    sampled_locations = {}
    for cell_name in locations:
        cell_count = locations[cell_name]["count"]
        sampled_locations[cell_name] = []
        sampled_location_count = 0
        for city in locations[cell_name]["cities"]:
            city_count = locations[cell_name]["cities"][city]["count"]
            ratio = city_count / cell_count
            city_locations = locations[cell_name]["cities"][city]["locations"]
            # logging.info(f"{cell_name} - {city}: {city_count} locations")
            number_of_locations_to_sample = min(max(round(ratio * IMAGES_PER_CELL), 1), city_count)
            # logging.info(f"{cell_name} - {city}: {number_of_locations_to_sample}/{city_count} locations")
            sampled_locations[cell_name] += sample_locations(city_locations, number_of_locations_to_sample)
            sampled_location_count += number_of_locations_to_sample
        logging.info(f"{cell_name}: {sampled_location_count} locations sampled")

    return sampled_locations


def sample_locations(locations, number_of_locations_to_sample):
    """
    Uniformly sample locations from a list of locations
    """
    if number_of_locations_to_sample >= len(locations):
        return locations
    sampled_locations = []
    step = len(locations) / number_of_locations_to_sample
    for i in range(number_of_locations_to_sample):
        sampled_locations.append(locations[int(i * step)])
    return sampled_locations


def visualize_generated_locations(points, polygon=None):
    matplotlib.use('Agg')

    y = [point[0] for point in points]  # Extract the x coordinate from the tuple
    x = [point[1] for point in points]  # Extract the y coordinate from the tuple

    # Create a plot to visualize the points and the polygon
    plt.figure(figsize=(16, 12))
    plt.scatter(x, y, c='blue', s=1, alpha=0.1, label='Images locations')
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
    # Save to file
    plt.savefig(VISUALIZATION_FILE, format='png', dpi=300)


def download_images(locations, output_dir):
    with concurrent.futures.ThreadPoolExecutor(max_workers=THREADS) as executor:
        executor.map(verify_and_download_image, locations, [output_dir] * len(locations))


def verify_and_download_image(location, output_dir):
    lat, lng, pano_id = check_street_view_image_existence(lat_lng_to_string(location['lat'], location['lng']))
    if lat and lng:
        key = f"{round(lat, COORDINATES_PRECISION)},{round(lng, COORDINATES_PRECISION)}"
        if key not in downloaded_images:
            if download_street_view_image(lat, lng, IMAGE_SIZE, 0, output_dir):
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


def check_street_view_image_existence(location):
    base_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {
        "location": location,
        "radius": 100,  # Search within # meters of the location
        "key": api_key,
    }

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


def download_street_view_image(lat, lng, size, heading=0, output_dir="./"):
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
        filepath = os.path.join(output_dir, filename + ".jpg")

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
