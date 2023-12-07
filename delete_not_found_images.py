"""
Deletes images saying "Sorry, we have no imagery here" and updates the metadata file accordingly.
"""
import json
import os
import shutil

# Path to the downloaded images

METADATA_DESTINATION = "./data/metadata.json"
IMAGES_PATH = 'streetview_images/'
BACKUP_PATH = 'streetview_images_backup/'
COORDINATES_PRECISION = 5


def lat_lng_to_key(lat, lng):
    return f"{round(lat, COORDINATES_PRECISION)},{round(lng, COORDINATES_PRECISION)}"


print("Deleting images...")

# Open metadata file
with open(METADATA_DESTINATION, 'r') as f:
    metadata = json.load(f)

for root, dirs, files in os.walk(IMAGES_PATH):
    for file in files:
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(root, file)
            # Get file size
            file_size = os.path.getsize(image_path)
            if file_size == 3810:
                # Save an image copy to a backup folder
                output_path = os.path.join(BACKUP_PATH, os.path.relpath(image_path, IMAGES_PATH))
                # Make dirs if they don't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy(image_path, output_path)

                os.remove(image_path)

                lat_lng = os.path.splitext(os.path.basename(image_path))[0]
                lat = float(lat_lng.split(",")[0])
                lng = float(lat_lng.split(",")[1])
                key = lat_lng_to_key(lat, lng)
                del metadata[key]

# Save the updated metadata file
with open(METADATA_DESTINATION, 'w') as f:
    json.dump(metadata, f, indent=4)



print("Deleting completed.")
