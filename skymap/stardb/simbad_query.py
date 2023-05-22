import requests
from astropy import units as u
from astropy.coordinates import ICRS, Galactic
from astropy.coordinates import SkyCoord, Latitude, Longitude
import re

def query_coordinate(coord: SkyCoord):
    resp = requests.get('http://simbad.u-strasbg.fr/simbad/sim-coo', params={'output.format': 'ASCII', 'Coord': coord.to_string('hmsdms'), 'Radius': '1'})
    if resp.status_code == 200:
        lines = resp.text.split('\n')

        keys = None
        objs = []
        for line in lines:
            cells = line.split('|')
            if len(cells) > 2:
                if keys is None:
                    keys = [x.strip() for x in cells]
                else:
                    obj = {
                        k:cells[i].strip() for i,k in enumerate(keys)
                    }
                    try:
                        obj['Mag V'] = float(obj['Mag V'])
                        objs.append(obj)
                    except:
                        continue
        return sorted(objs, key=lambda x: -float(x['Mag V']))
    return None

def query_object(obj_id: str):
    resp = requests.get("https://simbad.cds.unistra.fr/simbad/sim-id", params={"Ident": obj_id, "output.format": "ASCII"})
    if resp.status_code == 200:
        if m := re.search(r"NAME\s(.*)\n", resp.text):
            return m.group(1)
    return None

def round_coord(coord: SkyCoord):
    return SkyCoord(coord.ra.round(2), coord.dec.round(2), frame=coord.frame)

def query_stellar_data():
    resp = requests.get("https://simbad.cds.unistra.fr/simbad/sim-fsam", params={"Query": "Vmag<5.9&maintype=\"GlC\"", "output.format": "ASCII"})

    """ This query was used to download all objects < 10th mag
    https://simbad.u-strasbg.fr/simbad/sim-sam?Criteria=Vmag%3c10%0d%0a&submit=submit%20query&OutputMode=LIST&CriteriaFile=&output.format=VOTABLE
    """
    if resp.status_code == 200:
        if m := re.search(r"NAME\s(.*)\n", resp.text):
            return m.group(1)
    return None

if __name__ == "__main__":
    # coord = SkyCoord("14h15m39.7s +19d10m56s", frame=Galactic)

    # objs = query_coordinate(coord)
    # if len(objs):
    #     obj = objs[0]
    #     print(obj['identifier'])
    #     print(query_object(obj['identifier']))

    # query_stellar_data()
