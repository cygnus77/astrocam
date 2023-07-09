import math
import re
import pandas as pd
from pymongo import MongoClient
from astropy.coordinates import SkyCoord
from astropy import units as u
from astropy.coordinates import ICRS


class SkyMap:
  def __init__(self) -> None:
    self.client = MongoClient("localhost")
    self.db = self.client.stars
    self.cache = {}

  def __enter__(self):
    return self
  
  def __exit__(self, exc_type, exc_value, traceback):
    self.cache = None
    self.client.close()

  def findObjects(self, coord: SkyCoord, fov_deg:float=0.5, limit:int=None):

    # Conver fov to meters for mongo query
    fov_rad = math.radians(fov_deg)
    fov_meters = 6378.1 * 1000 * fov_rad

    ra, dec = coord.ra.degree-180, coord.dec.degree
    cache_key = (int(ra*100), int(dec*100))
    if cache_key in self.cache:
      return self.cache[cache_key]

    pipeline = [
      { '$geoNear': {
          'near': {
            'type': 'Point', 
            'coordinates': [ra, dec]
          }, 
          'maxDistance': fov_meters, 
          'key': 'icrs.location', 
          'spherical': True, 
          'distanceField': 'distance'
      }},
      { '$match': {
          '$or': [
            {'M': {'$exists': True}},
            {'NGC': {'$exists': True}},
            {'NAME': {'$exists': True}},
          ]
      }}
    ]

    if limit is not None:
      pipeline.append({'$limit': limit})

    cursor = self.db.stars.aggregate(pipeline)

    objects = []
    for star in cursor:
      if 'NAME' in star:
        objects.append(star['NAME'])
      if 'M' in star:
        objects.append('M ' + str(star['M']))
      if 'NGC' in star:
        objects.append('NGC ' + str(star['NGC']))
    searchresult = ", ".join(objects)
    self.cache[cache_key] = searchresult
    return searchresult
  
  def searchName(self, term):
    cursor = self.db.stars.find({'_id':{'$regex': re.compile(term, re.IGNORECASE)}}, limit=10)
    return [star for star in cursor]
  
  def coneSearch(self, coord: SkyCoord, fov_deg: float, limit:int=None):
    # Conver fov to meters for mongo query
    fov_rad = math.radians(fov_deg / 2.0) # radius from fov_deg which is diameter
    fov_meters = 6378.1 * 1000 * fov_rad

    ra, dec = coord.ra.degree-180, coord.dec.degree
    cache_key = (int(ra*100), int(dec*100))
    if cache_key in self.cache:
      return self.cache[cache_key]

    pipeline = [
      { '$geoNear': {
          'near': {
            'type': 'Point', 
            'coordinates': [ra, dec]
          }, 
          'maxDistance': fov_meters, 
          'key': 'icrs.location', 
          'spherical': True, 
          'distanceField': 'distance'
      }},
      { '$match': {
          '$and': [
            {'typ': re.compile('star|binary|supernova', re.IGNORECASE)},
            {'mag': {'$ne': None}}
          ]
      }},
      { '$sort': {
          'mag': 1
      }},
    ]

    if limit is not None:
      pipeline.append({'$limit': limit})

    cursor = self.db.stars.aggregate(pipeline)
    yield from cursor


def _test():
  m81 = SkyCoord.from_name("M81")
  m82 = SkyCoord.from_name("M82")

  sep = m81.separation(m82).degree

  with SkyMap() as sm:
    assert(len(sm.findObjects(m81, sep + 0.1).split(",")) > 1)
  with SkyMap() as sm:
    assert(len(sm.findObjects(m81, sep - 0.1).split(",")) == 1)

def _test_separation():
  # M101 RA: 14h04m00.0s
  c1 = SkyCoord(14.066564 * u.hour, 54.218594 * u.degree, frame=ICRS)
  with SkyMap() as sm:
    results = sm.searchName("andro")
    for result in results:
      print(result)
    print(sm.findObjects(c1, fov_deg=1))

  _test()

  c1 = SkyCoord("14h15m39.67207s +19d10m56.6730s", frame=ICRS)
  c2 = SkyCoord.from_name("Arcturus")
  print(c1.ra.degree, c1.dec.degree)
  print(c2.ra.degree, c2.dec.degree)
  print(c1.separation(c2).degree)

  with SkyMap() as sm:
    print(sm.findObjects(c1))
    print(sm.findObjects(c2))

if __name__ == "__main__":

  import matplotlib.pyplot as plt
  # M101 RA: 14h04m00.0s
  # c1 = SkyCoord(14.066564 * u.hour, 54.218594 * u.degree, frame=ICRS)
  c1 = SkyCoord.from_name("Mizar")
  with SkyMap() as sm:
    stars = []
    for star in sm.coneSearch(c1, .50):
      if 'NAME' in star:
        print(star['_id'])
        s_coord = SkyCoord(star['icrs']['deg']['ra'] * u.degree, star['icrs']['deg']['dec'] * u.degree, frame=ICRS)
        stars.append(s_coord)
    fig = plt.figure()
    plt.subplot(projection="aitoff")
    plt.scatter([x.ra.degree for x in stars], [x.dec.degree for x in stars])
    plt.grid(True)
    fig.show()
    while not fig.waitforbuttonpress(): pass
