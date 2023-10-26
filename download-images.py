import io
import time

import matplotlib
import numpy as np
import requests
from dotenv import load_dotenv
import os

from shapely import Point, Polygon
import matplotlib.pyplot as plt
from PIL import Image
import concurrent.futures

IMAGE_SIZE = "256x256"
OUTPUT_DIR = "./streetview_images/"


def check_street_view_image_existence(api_key, location):
    base_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {
        "location": location,
        "radius": 10000,  # Search within # meters of the location
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


def download_images(api_key, locations):
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        executor.map(verify_and_download_image, [api_key] * len(locations), locations)


def verify_and_download_image(api_key, location):
    lat, lng = check_street_view_image_existence(api_key, f"{location[0]},{location[1]}")
    if lat and lng:
        download_street_view_image(api_key, (lat, lng), IMAGE_SIZE, output_dir=OUTPUT_DIR)


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
        filepath = output_dir + filename

        # Save the image to the specified directory
        with open(filepath, "wb") as f:
            f.write(response.content)

        print(f"Image downloaded and saved to {filepath}")
    else:
        print("Image download failed.")


def generate_points_within_polygon(bounding_coordinates, num_points, precision=2):
    # Create a Polygon object from the bounding coordinates
    polygon = Polygon(bounding_coordinates)

    # Calculate the bounding box of the polygon
    min_x, min_y, max_x, max_y = polygon.bounds

    points = []
    while len(points) < num_points:
        # Generate random points within the bounding box
        random_point = Point(
            round(np.random.uniform(min_x, max_x), precision),
            round(np.random.uniform(min_y, max_y), precision)
        )

        # Check if the point is within the polygon
        if random_point.within(polygon):
            points.append((random_point.x, random_point.y))

    return points


def visualize_generated_locations(points, polygon):
    y = [point[0] for point in points]  # Extract the x coordinate from the tuple
    x = [point[1] for point in points]  # Extract the y coordinate from the tuple

    # Extract x and y coordinates of the bounding polygon
    y_polygon = [point[0] for point in polygon]
    x_polygon = [point[1] for point in polygon]

    # Create a plot to visualize the points and the polygon
    plt.figure(figsize=(8, 6))
    plt.scatter(x, y, c='blue', label='Images locations')
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


if __name__ == "__main__":
    load_dotenv()
    api_key = os.getenv("API_KEY")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    matplotlib.use('Agg')

    bounding_coordinates = [
        (57.71235801996257, 10.511603278278011),
        (57.09299707300755, 8.563640295641799),
        (54.948638340532014, 8.669805178100018),
        (54.86653030666335, 9.966191651705254),
        (55.42531058418789, 9.72449247866021),
        (55.219034938904166, 9.955205325657753),
        (55.09349647472793, 10.746220801077895),
        (55.30667692080646, 10.768193453172898),
        (55.31918142491171, 11.185673842977977),
        (54.77791888196491, 11.031865278312948),
        (55.58707567081864, 12.712773163580751),
        (56.111297316227194, 12.251347469585669),
        (55.406602591177425, 11.229619147167982),
        (55.36916001966993, 10.779179779220401),
        (55.61190363970056, 10.350713063367825),
        (55.58086622333195, 9.867314717277736),
        (56.440669583160854, 10.922002017837926),
    ]
    num_points = 1024

    points_within_polygon = generate_points_within_polygon(bounding_coordinates, num_points)
    visualize_generated_locations(points_within_polygon, bounding_coordinates)
    print(points_within_polygon)

    start = time.time()
    download_images(api_key, points_within_polygon)
    end = time.time()
    print(f"Time elapsed: {end - start} seconds")
