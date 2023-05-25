from pymongo import MongoClient
from tqdm import tqdm
from pathlib import Path
import re

# Columns: #, identifier, typ, coord1 (ICRS,J2000/2000), coord4 (Gal,J2000/2000), pm, Mag V, spec. type, ang. size, #Dist, distance Q unit, err-, err+, method, reference
simbad_row_re = re.compile(r"\s*\d+\s*\|\s*(?P<id>.*?)\|\s*(?P<typ>.*?)\|\s*(?P<icrs>.*?)\|\s*(?P<gal>.*?)\|\s*(?P<pm>.*?)\|\s*(?P<mag>.*?)\|\s*(?P<spec>.*?)\|\s*(?P<size>.*?)\|.*?\|\s*(?P<distance>.*?)\|.*$")

hmsdms_re = re.compile(r"(\d\d)\s(\d\d)\s(\d+\.?\d+)\s+([+|-]\d\d)\s(\d\d)\s(\d+\.?\d+)")
float_pair_re = re.compile(r"([+|-]?\d+\.?\d*)\s+([+|-]?\d+\.?\d*)")
ID_re = re.compile(r"([A-Z]+)\s(.*)")
distance_re = re.compile(r"(\d+\.?\d*)\s+(\w+)")

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
  elif k == 'gal':
    gal_ra, gal_dec = float_pair_re.match(v).groups()
    return {
      "ra": float(gal_ra),
      "dec": float(gal_dec)
    }
  elif k == 'mag':
    return float(v)
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


if __name__ == "__main__":

  objects_in_the_sky = {}
  for data_file in tqdm((Path(__file__).parent/"simbad_download").glob("*.txt")):
    with data_file.open() as f:
      while r := f.readline():
        if (rowmatch := simbad_row_re.match(r)) is not None:
          obj = {k:normalize(k,v) for k,v in rowmatch.groupdict().items() if k is not None and v is not None}
          obj["_id"] = obj["id"].replace(" ","")

          segs = obj["id"].split("  ")
          for seg in segs:
            if len(seg):
              if idm := ID_re.match(seg):
                if idm.group(1) in obj:
                  prev = obj[idm.group(1)]+", "
                else:
                  prev = ""
                obj[idm.group(1)] = prev + idm.group(2)
          objects_in_the_sky[obj['_id']] = obj

  with MongoClient("localhost") as mon:
    db = mon.stars
    db.stars.insert_many(objects_in_the_sky.values(), ordered=False)
    mon.close()
