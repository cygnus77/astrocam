import re
from pymongo import MongoClient
import math

from pymongo.message import _batched_write_command_impl

def hms2deg(h,m,s):
  d = 360.0/24*(h+m/60+s/3600)
  return d if d<=180 else (d-360)

def dms2deg(d,m,s):
  return d + m/60 + s/3600

def str2coord(l):
  m = re.match(r"([\.\d]+)h\s*([\.\d]+)m\s*([\.\d]+)s\s+([\+\-][\.\d]+)°\s*([\.\d]+)′\s*([\.\d]+)″", l)
  if m is not None:
    return hms2deg(float(m.group(1)),float(m.group(2)),float(m.group(3))), dms2deg(float(m.group(4)),float(m.group(5)),float(m.group(6)))
  raise ValueError("Invalid RA/DEC")

def findStar1(coll, ra, dec, r=0.001):
  return db.stars.find({
    "loc": {
      "$nearSphere": [ ra, dec ], "$maxDistance": r
    }
  })

def findStar2(coll, ra, dec):
  return db.stars.find({
    "loc": {
      "$nearSphere": {
          "$geometry": {
            "type":"Point",
            "coordinates":[ra, dec]
          },
          "$minDistance": 0.0,
          "$maxDistance": 1000
      }
    }
  })

def deltaAngle(x,y):
  return 180-math.fabs(math.fmod(math.fabs(x-y), 360) - 180)

def distStars(ra1,dec1, ra2,dec2):
  return math.sqrt(math.pow(deltaAngle(ra1, ra2),2) + math.pow(deltaAngle(dec1, dec2),2))

def degPerPixel(pxPitch_μm, focal_len_mm):
  return (pxPitch_μm / 1000 / focal_len_mm) * (180/math.pi)

def arcSecPerPixel(pxPitch_μm, focal_len_mm):
  return degPerPixel(pxPitch_μm,focal_len_mm) * 3600

def fov_deg(sensor_width_mm, focal_len_mm):
  return (sensor_width_mm / focal_len_mm) * (180/math.pi)

def print_star(star):
  print(star['loc']['coordinates'], star['mag'])

if __name__ == "__main__":

  starCoords = [
    "20h0m6.24s 22°42′16.6″",
    "19h59m4.10s 22°37′42.4″",
    "19h59m20.78s 22°36′51.7″",
    "20h0m11.74s 22°42′46.8″"
  ]

  ra, dec = str2coord("19h59m36.340s +22°43′16.09″")
  star_distances_pixels = [1347, 1060, 125]
  dpx = degPerPixel(5.51, 2800*0.63)
  fov = fov_deg(23.6, 2800*0.63)
  
  mon = MongoClient("localhost")
  db = mon.stars

  stars_in_fov = db.stars.find({
      "loc": {
        "$nearSphere": [ra, dec],
        "$maxDistance": math.radians( fov )
      }
    })
  print(stars_in_fov.count())
  for x in stars_in_fov:
    score = 0
    for sdpx in star_distances_pixels:
      if db.stars.find( {
          "loc": {
            "$nearSphere": x['loc']['coordinates'],
            "$minDistance": math.radians( dpx * (sdpx-5) ),
            "$maxDistance": math.radians( dpx * (sdpx+5) )
          }
        }).count() > 0:
        score += 1
    if score == len(star_distances_pixels):
      print("Found it")
      print_star(x)


  # for star in db.stars.find( {
  #     "loc": {
  #       "$nearSphere": [ra, dec],
  #       "$minDistance": math.radians( dpx * (numPx-10) ),
  #       "$maxDistance": math.radians( dpx * (numPx+10) )
  #     }
  #   }):
  #   print(star['loc']['coordinates'], star['mag'], distStars(ra, dec, *star['loc']['coordinates']))

  # for starCoord in starCoords:
  #   ra, dec = str2coord(starCoord)

    # for star in findStar1(db.stars, ra, dec, r=0.001):
    #   print(ra, dec, "=>", star['loc']['coordinates'], star['mag'])

  # s1 = starCoords[0]
  # s2 = starCoords[3]
  # ra, dec = str2coord(s1)
  # d = distStars(ra, dec, *str2coord(s2))
  # stars = db.stars.find({
  #   "loc": {
  #     "$nearSphere": [ ra, dec ], "$maxDistance": math.radians(d)
  #   }
  # })
  # for star in stars:
  #   print(star['loc']['coordinates'], star['mag'], distStars(ra, dec, *star['loc']['coordinates']))
