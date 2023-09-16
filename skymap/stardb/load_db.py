from pymongo import MongoClient, ASCENDING, GEOSPHERE, TEXT
from tqdm import tqdm
from pathlib import Path
import re

# Columns: #, identifier, typ, coord1 (ICRS,J2000/2000), coord4 (Gal,J2000/2000), pm, Mag V, spec. type, ang. size, #Dist, distance Q unit, err-, err+, method, reference
#simbad_row_re = re.compile(r"\s*\d+\s*\|\s*(?P<id>.*?)\|\s*(?P<typ>.*?)\|\s*(?P<icrs>.*?)\|\s*(?P<gal>.*?)\|\s*(?P<pm>.*?)\|\s*(?P<mag>.*?)\|\s*(?P<spec>.*?)\|\s*(?P<size>.*?)\|.*?\|\s*(?P<distance>.*?)\|.*$")
hmsdms_re = re.compile(r"(\d\d)\s(\d\d)\s(\d+\.?\d+)\s+([+|-]\d\d)\s(\d\d)\s(\d+\.?\d+)")
float_pair_re = re.compile(r"([+|-]?\d+\.?\d*)\s+([+|-]?\d+\.?\d*)")
ID_re = re.compile(r"([A-Z]+)\s(.*)")
distance_re = re.compile(r"(\d+\.?\d*)\s+(\w+)")

# Columns: # | identifier | typ | all types | coord1 (ICRS,J2000/2000) | coord2 (ICRS,J2000/2000) | plx | Mag U | Mag B | Mag V | Mag R | Mag I | spec. type 
simbad_row_re = re.compile(r"\s*\d+\s*\|\s*(?P<id>.*?)\|\s*(?P<typ>.*?)\|\s*(?P<alltyp>.*?)\|\s*(?P<icrs>.*?)\|\s*(?P<icrs2>.*?)\|\s*(?P<plx>.*?)\|\s*(?P<magU>.*?)\|\s*(?P<magB>.*?)\|\s*(?P<magV>.*?)\|\s*(?P<magR>.*?)\|\s*(?P<magI>.*?)\|\s*(?P<spec>.*?)")

def normalize(k, v):
  v = v.strip()
  if v.startswith("~"):
    return None
  if k == 'icrs':
    rah,ram,ras,decd,decm,decs = hmsdms_re.match(v).groups()
    ra_deg = 15*(float(rah) + float(ram)/60 + float(ras)/3600)
    dec_deg = float(decd) + float(decm)/60 + float(decs)/3600
    return {
      "hmsdms": {
        "ra": f"{rah}h{ram}m{ras}s",
        "dec": f"{decd}d{decm}m{decs}s",
      },
      "deg": {
        "ra": ra_deg,
        "dec": dec_deg
      },
      "location": {
        "type": "Point",
        "coordinates": [ra_deg - 180, dec_deg], # convert to RA:(-180 to +180) and DEC:(-90 to +90)
      }
    }
  elif k == 'icrs2':
    gal_ra, gal_dec = float_pair_re.match(v).groups()
    return {
      "ra": float(gal_ra),
      "dec": float(gal_dec)
    }
  elif k.startswith('mag'):
    return float(v) if v != '~' else None
  elif k == 'plx':
    return float(v) if v != '~' else None
  elif k == 'pm':
    return [float(x) for x in float_pair_re.match(v).groups()]
  elif k == 'size':
    return [float(x) for x in float_pair_re.match(v).groups()]
  elif k == 'distance':
    if m := distance_re.match(v):
      dist, units = m.groups()
      dist = float(dist)
      if units == "pc":
        pass
      elif units == "kpc":
        dist = float(dist) * 1e3
      elif units == "Mpc":
        dist = float(dist) * 1e6
      else:
        raise ValueError(f"Unknown distance units: {units}")
      return dist
    return None
  return v

star_terms = [
  "star",
  "supergiant",
  "binary",
  "dwarf",
  "variable",
  "classical nova",
  "wolf-rayet",
  "supernova"
]

def is_star(typ):
  tl = typ.lower()
  for x in star_terms:
    if x in tl:
      return True
  return False

def load_data():

  multi_space_re = re.compile(r"\s+")
  objects_in_the_sky = {}
  counter = 0
  file_list = list((Path(__file__).parent/"s3").glob("*.txt"))
  file_list.extend(list((Path(__file__).parent/"s4").glob("*.txt")))
  for data_file in tqdm(file_list):
    with data_file.open() as f:
      while r := f.readline():
        if (rowmatch := simbad_row_re.match(r)) is not None:
          obj = {k:normalize(k,v) for k,v in rowmatch.groupdict().items() if k is not None and v is not None}
          obj["_id"] = counter
          counter += 1
          obj["star"] = is_star(obj["typ"])

          tm = 0
          tw = 0
          for m, w in zip(['magU', 'magB', 'magV', 'magR', 'magI'], [0.1, 0.3, 0.5, 0.3, 0.1]):
            if obj[m] is None:
              continue
            tm += obj[m]*w
            tw += w
          if tw == 0:
            obj["mag"] = None
          else:
            obj["mag"] = tm/tw

          segs = obj["id"].split("  ")
          for seg in segs:
            if len(seg):
              if idm := ID_re.match(seg):
                if idm.group(1) in obj:
                  prev = obj[idm.group(1)]+", "
                else:
                  prev = ""
                obj[idm.group(1)] = prev + idm.group(2)

          obj["id"] = multi_space_re.sub(" ", obj["id"])
          unique_id = obj["id"].replace(" ", "")
          objects_in_the_sky[unique_id] = obj

  return objects_in_the_sky


if __name__ == "__main__":
  objects_in_the_sky = load_data()
  with MongoClient("localhost") as mon:
    db = mon.stars
    db.stars.insert_many(objects_in_the_sky.values(), ordered=False)
    db.stars.create_index([("id", TEXT)])
    db.stars.create_index([("mag", ASCENDING)])
    db.stars.create_index([("star", ASCENDING)])
    db.stars.create_index([("icrs.location", GEOSPHERE)])
    mon.close()
