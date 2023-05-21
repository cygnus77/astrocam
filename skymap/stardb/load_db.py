from lxml import etree
from pymongo import MongoClient
from tqdm import tqdm


if __name__ == "__main__":

  mon = MongoClient("localhost")
  db = mon.stars

  with open(r"C:\Users\anand\Downloads\1631902895331O-result.1252.xml", 'rt') as f:
    et = etree.parse(f)

  doc = et.getroot()
  print(doc.nsmap)
  nsmap = {'x': doc.nsmap[None]}

  hdr = [field.get('ID') for field in doc.xpath('//x:FIELD', namespaces=nsmap)]

  def convRA(d):
    return d if d<=180 else (d-360)

  for row in tqdm(doc.xpath('//x:TR', namespaces=nsmap)):
    rowdata = [x.text for x in row.xpath("x:TD", namespaces=nsmap)]
    star = {
      "_id": rowdata[hdr.index('source_id')],
      "loc": {
        "type": "Point",
        "coordinates": [
          convRA(float(rowdata[hdr.index('ra')])),
          float(rowdata[hdr.index('dec')])
        ],
      },
      "mag": float(rowdata[hdr.index('phot_g_mean_mag')])
    }
    result=db.stars.insert_one(star)
