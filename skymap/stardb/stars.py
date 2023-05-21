import cv2
from PIL import Image
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import itertools
import imageio
import rawpy

if __name__ == "__main__":

  # imgFile = r"D:\Cherry Springs Pictures\starfield\milkyway_starfield.TIF"
  # imgFile = r"D:\Astro\CherrySprings-20210815\M57-ring\integration_DBE.tif"
  imgFile = r"D:\Astro\CherrySprings-20210815\M27-Dumbbell\integration_DBE.tif"
  # imgFile = r"D:\Astro\M13-02Aug2021\Image079.nef"
  
  if(Path(imgFile).suffix.lower() == '.nef'):
    with rawpy.imread(imgFile) as raw:
      img = raw.postprocess()
  else:
    img = imageio.imread(imgFile)
  print("Image shape:", img.shape, img.dtype, np.min(img), np.max(img))

  img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  if img.dtype == np.uint16:
    img = (img * 255.0 / 65536.0).astype(np.uint8)
  if img.dtype == np.float32:
    img = (img * 255).astype(np.uint8)
  print("Image shape:", img.shape, img.dtype, np.min(img), np.max(img))
  
  # plt.hist(img.flatten(), 100)
  # plt.show()
  ave = np.average(img)
  print("Average: ", ave)
  if ave < 10:
    thresh = 255 // 3
  elif ave < 100:
    thresh = 255 // 2
  else:
    thresh = 255 * 3 // 4
  ret, img = cv2.threshold(img, thresh, 255, cv2.THRESH_BINARY)
  print(f"Threshold: {ret}")

  numlabels, labels, stats, centroids = cv2.connectedComponentsWithStatsWithAlgorithm(img, 4, cv2.CV_16U, cv2.CCL_DEFAULT)
  print("Labels: ", numlabels)
  # print(labels)
  # print(stats)
  # print(centroids)

  rgbimg = np.zeros( list(img.shape) + [3], dtype=np.uint8)
  
  colors = list(itertools.permutations( [0, 128, 255], 3))
  for i in range(1,numlabels):
    rgbimg[labels == i] = colors[i % len(colors)]


  # areas = [x[cv2.CC_STAT_AREA] for x in stats[1:]]
  # plt.hist(areas)
  # plt.show()

  # diffs = [x[cv2.CC_STAT_WIDTH]/x[cv2.CC_STAT_HEIGHT] for x in stats[1:]]
  # plt.hist(diffs)
  # plt.show()

  # cv2.imshow(None, rgbimg)
  # cv2.waitKey()

  cv2.imwrite('test.png', rgbimg)