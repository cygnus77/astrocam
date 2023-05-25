import matplotlib.pyplot as plt
import numpy as np
import math
from pymongo import MongoClient
import cv2
import re

def project(ra_deg: float, dec_deg: float, ra_center_deg: float, dec_center_deg: float, fov: float) -> tuple:
  ra_rad = math.radians(ra_deg)
  dec_rad = math.radians(dec_deg)
  ra_center_rad = math.radians(ra_center_deg)
  dec_center_rad = math.radians(dec_center_deg)

  fov_rad = math.radians(fov)
  x = math.cos(dec_rad) * math.sin(ra_rad - ra_center_rad)
  y = math.sin(dec_rad) * math.cos(dec_center_rad) - math.cos(dec_rad) * math.sin(dec_center_rad) * math.cos(ra_rad - ra_center_rad)
  return (x, y)

def magnitude_to_intensity(mag: float) -> int:
  """The scale is reverse logarithmic: the brighter an object is, the lower its magnitude number.
  A difference of 1.0 in magnitude corresponds to a brightness ratio of about 2.512.
  For example, a star of magnitude 2.0 is 2.512 times as bright as a star of magnitude 3.0,
  6.31 times as bright as a star of magnitude 4.0, and 100 times as bright as one of magnitude 7.0."""

  # Brightness 1.0 corresponds to mag 0
  # Brightness 0 corresponds to mag 12
  return np.clip(1.0 - (mag / 12), 0, 1)

def render(ra_center_deg: float, dec_center_deg: float, fov: float):
  with MongoClient("localhost") as mon:
    db = mon.stars
    cursor = db.stars.find({"$and": [{
      "icrs.location": {
        "$geoWithin": {
          "$centerSphere": [[ra_center_deg, dec_center_deg], fov]
        }
      }},
      {"mag": {"$ne": None}},
      # {"mag": {"$lt": 7}}
      ]
    })

    img_size = 1000
    img = np.zeros((img_size, img_size, 3), dtype=np.uint8)

    count = 0
    min_int = 1e5
    max_int = -1e5
    for star in cursor:
      ux,uy = project(star["icrs"]["location"]["coordinates"][0], star["icrs"]["location"]["coordinates"][1], ra_center_deg, dec_center_deg, fov)
      intensity = magnitude_to_intensity(star["mag"])
      if intensity < min_int:
        min_int = intensity
      if intensity > max_int:
        max_int = intensity
      x = int((ux+1) * img_size//2)
      y = int((uy+1) * img_size//2)
      if intensity < 0.5:
        img[x, y, :] += int(intensity * 255)
      elif intensity < 0.75:
        img[x-1:x+1, y-1:y+1, :] += int(intensity * 255)
      elif intensity > 0.75:
        img[x-2:x+2, y-2:y+2, :] += np.array([0, 0, int(intensity * 255)], dtype=np.uint8)

      # if "NAME" in star:
      #   print(star["NAME"], intensity)
      count += 1
    print(count, min_int, max_int)
    cv2.imshow("test", img)
    cv2.waitKey(0)

if __name__ == "__main__":

  with MongoClient("localhost") as mon:
    db = mon.stars
    obj = db.stars.find_one({"id": {"$regex": re.compile("alf Cyg", re.IGNORECASE)}})
    render(obj["icrs"]["location"]["coordinates"][0], obj["icrs"]["location"]["coordinates"][1], 5)
