"""
Script cropping downloaded images to 224x224 pixels. Only the bottom part is removed as it contains a watermark.
"""

import os
import cv2

# Path to the downloaded images
import numpy

path = 'streetview_images/'

# Path to the cropped images
path_cropped = 'streetview_images_cropped/'

target_width = 224
target_height = 224

# Create the directory if it does not exist
if not os.path.exists(path_cropped):
    os.makedirs(path_cropped)


print("Cropping and resizing images...")

for root, dirs, files in os.walk(path):
    for file in files:
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Construct the full path to the image
            image_path = os.path.join(root, file)

            stream = open(image_path, "rb")
            bytes = bytearray(stream.read())
            numpyarray = numpy.asarray(bytes, dtype=numpy.uint8)
            image = cv2.imdecode(numpyarray, cv2.IMREAD_UNCHANGED)

            if image is not None:
                # Get the dimensions of the image
                height, width, _ = image.shape

                # Calculate the cropping coordinates to remove the bottom part
                top_left = (0, 0)
                bottom_right = (width, min(height, target_height))

                # Crop the image
                cropped_image = image[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]

                # Resize the cropped image to the target size
                cropped_image = cv2.resize(cropped_image, (target_width, target_height))

                # Construct the output path maintaining the same directory structure
                output_path = os.path.join(path_cropped, os.path.relpath(image_path, path))
                # Make dirs if they don't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Save the cropped image (may contain special characters and cv2 does not support that) Do not use cv2.imwrite
                cv2.imencode(os.path.splitext(output_path)[1], cropped_image)[1].tofile(output_path)


print("Cropping and resizing completed.")
