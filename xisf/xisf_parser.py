import re
from struct import unpack
import numpy as np
import lxml.etree as ET
import matplotlib.pyplot as plt

ns = {'x':'http://www.pixinsight.com/xisf'}

def read_data_blocks_file(f):
  # Read datablock
  if (magic := f.read1(8)) != b'XISB0100':
    raise ValueError(f"Invalid data blocks header: {magic}")
  if f.read1(8) != b'\0'*8: # Reserved
    raise ValueError("Invalid data blocks file")

  num_blocks = 0
  next_blk_offset = f.tell()
  while next_blk_offset != 0:
    num_blocks += 1
    f.seek(next_blk_offset, 0)
    blk_len = unpack("<I", f.read(4)) [0]
    if f.read1(4) != b'\0'*4: # resvd
      raise ValueError("Invalid data block file")
    next_blk_offset = unpack("<I", f.read(4)) [0]

  print(f"Number of blocks: {num_blocks}")

def read_xisf(fname: str) -> np.ndarray:
  with open(fname, "rb") as f:
    if f.read(8) != b'XISF0100':
      raise ValueError("Invalid XISF file")
    
    hdr_len = unpack("<I", f.read(4)) [0]
    if f.read(4) != b'\0'*4: # resvd
      raise ValueError("Invalid XISF file")

    # Read header       
    hdr: ET.Element = ET.fromstring(f.read(hdr_len))
    # print(ET.tostring(hdr, pretty_print=True).decode('utf-8'))
    image = hdr.xpath('/x:xisf/x:Image', namespaces=ns)[0]

    # Fits Info
    fits_kws = image.xpath(".//x:FITSKeyword", namespaces=ns)
    fits_hdr = {kw.attrib['name'].strip(): kw.attrib['value'].strip("' ") for kw in fits_kws}

    # Image dimensions
    width, height, channels = map(int, image.attrib['geometry'].split(':'))
    m = re.match(r'attachment:(\d+):(\d+)', image.attrib['location'])
    if m is None:
      raise ValueError(f"Unexpected header parameter {image.attrib['location']}")

    # Image data pointer
    db_offset = int(m.group(1))
    db_len = int(m.group(2))
    f.seek(db_offset)

    img_data = f.read(db_len)
    img = np.frombuffer(img_data, dtype=np.float32).reshape((height, width, channels))
    # print(img.shape)
    return img, fits_hdr

if __name__ == "__main__":
  img, ph = read_xisf(r"D:\Astro\Objects\C30\subs\Light_00934_180.0sec_200gain_-0.3C_c_a.xisf")
  plt.imshow(img, cmap='gray')
  plt.waitforbuttonpress()
