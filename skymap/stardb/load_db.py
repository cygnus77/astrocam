from lxml import etree as ET
from pymongo import MongoClient
from tqdm import tqdm
from pathlib import Path
import re
from astropy.coordinates import SkyCoord
import pandas as pd

# Columms:  #, identifier, typ, coord1 (ICRS,J2000/2000), coord4 (Gal,J2000/2000), pm, Mag V, spec. type, ang. size 
simbad_row_re = re.compile(r"(?P<no>\d+)\s*\|\s*(?P<id>.*)\|\s*(?P<typ>.*)\|\s*(?P<icrs>.*)\|\s*(?P<gal>.*)\|\s*(?P<pm>.*)\|\s*(?P<mag>.*)\|\s*(?P<spec>.*)\|\s*(?P<size>.*)$")

sexagecimal_re = re.compile(r"(\d\d)\s(\d\d)\s(\d+\.?\d+)\s+([+|-]\d\d)\s(\d\d)\s(\d+\.?\d+)")
float_pair_re = re.compile(r"([+|-]?\d+\.?\d*)\s+([+|-]?\d+\.?\d*)")

ID_re = re.compile(r"([A-Z]+)\s(.*)")

def normalize(k, v):
  v = v.strip()
  if v.startswith("~"):
    return None
  if k == 'icrs':
    rah,ram,ras,decd,decm,decs = sexagecimal_re.match(v).groups()
    return {
      "ra": f"{rah}h{ram}m{ras}s",
      "dec": f"{decd}d{decm}m{decs}s"
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

  return v


if __name__ == "__main__":

  mon = MongoClient("localhost")
  db = mon.stars

  objects_in_the_sky = []
  for data_file in tqdm((Path(__file__).parent/"simbad_download").glob("*.txt")):
    with data_file.open() as f:
      while r := f.readline():
        if (rowmatch := simbad_row_re.match(r)) is not None:
          obj = {k:normalize(k,v) for k,v in rowmatch.groupdict().items()}
          
          segs = obj["id"].split("  ")
          for seg in segs:
            if len(seg):
              if idm := ID_re.match(seg):
                obj[idm.group(1)] = idm.group(2)
          objects_in_the_sky.append(obj)
          db.stars.insert_one(obj)

  pd.DataFrame(objects_in_the_sky).to_csv("star_data.csv")

