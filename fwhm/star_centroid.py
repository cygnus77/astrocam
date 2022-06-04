import numpy as np
import math

"""
https://www.lost-infinity.com/night-sky-image-processing-part-4-calculate-the-star-centroid-with-sub-pixel-accuracy/
"""
def iwc_centroid(star: np.ndarray):
    bg = np.percentile(star, 5)
    star = np.clip(star - bg, 0, 255)
    cx = np.sum(np.full(star.shape, np.arange(star.shape[1])) * (star**2)) / (np.sum(star**2))
    cy = np.sum(np.full(star.shape, np.arange(star.shape[0]).reshape(star.shape[0],1)) * (star**2)) / (np.sum(star**2))
    cx = round(cx)
    cy = round(cy)
    inImg = star[cy-1:cy+2, cx-1:cx+2]
    b1 = inImg[0, 0]; a2 = inImg[0, 1]; b2 = inImg[0, 2]
    a1 = inImg[1, 0];  c = inImg[1, 1]; a3 = inImg[1, 2]
    b4 = inImg[2, 0]; a4 = inImg[2, 1]; b3 = inImg[2, 2]

    for i in range(10):
        c2 = 2 * c
        sp1 = (a1 + a2 + c2) / 4
        sp2 = (a2 + a3 + c2) / 4
        sp3 = (a3 + a4 + c2) / 4
        sp4 = (a4 + a1 + c2) / 4
        
        #New maximum is center
        newC = max(sp1, sp2, sp3, sp4)
        
        # Calc position of new center
        ad = math.pow(2.0, -(i + 1.0))

        if (newC == sp1):
            cx = cx - ad # to the left
            cy = cy - ad # to the top

            # Calculate new sub pixel values
            b1n = (a1 + a2 + 2 * b1) / 4
            b2n = (c + b2 + 2 * a2) / 4
            b3n = sp3
            b4n = (b4 + c + 2 * a1) / 4
            a1n = (b1n + c + 2 * a1) / 4
            a2n = (b1n + c + 2 * a2) / 4
            a3n = sp2
            a4n = sp4

        elif (newC == sp2):
            cx = cx + ad # to the right
            cy = cy - ad # to the top

            # Calculate new sub pixel values
            b1n = (2 * a2 + b1 + c) / 4
            b2n = (2 * b2 + a3 + a2) / 4
            b3n = (2 * a3 + b3 + c) / 4
            b4n = sp4
            a1n = sp1
            a2n = (b2n + c + 2 * a2) / 4
            a3n = (b2n + c + 2 * a3) / 4
            a4n = sp3
        elif (newC == sp3):
            cx = cx + ad # to the right
            cy = cy + ad # to the bottom

            # Calculate new sub pixel values
            b1n = sp1
            b2n = (b2 + 2 * a3 + c) / 4
            b3n = (2 * b3 + a3 + a4) / 4
            b4n = (2 * a4 + b4 + c) / 4
            a1n = sp4
            a2n = sp2
            a3n = (b3n + 2 * a3 + c) / 4
            a4n = (b3n + 2 * a4 + c) / 4
        else:
            cx = cx - ad # to the left
            cy = cy + ad # to the bottom   

            # Calculate new sub pixel values
            b1n = (2 * a1 + b1 + c) / 4
            b2n = sp2
            b3n = (c + b3 + 2 * a4) / 4
            b4n = (2 * b4 + a1 + a4) / 4
            a1n = (b4n + 2 * a1 + c) / 4
            a2n = sp1
            a3n = sp3
            a4n = (b4n + 2 * a4 + c) / 4

            c = newC # Oi = Oi+1

            a1 = a1n
            a2 = a2n
            a3 = a3n
            a4 = a4n

            b1 = b1n
            b2 = b2n
            b3 = b3n
            b4 = b4n
    return cx, cy
