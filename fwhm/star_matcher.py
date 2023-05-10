import importlib
import rawpy
import numpy as np
import cv2
import pandas as pd
import matplotlib.pyplot as plt
from itertools import combinations, product
import math

class StarMatcher:

    def matchStars(self, df_ref: pd.DataFrame, df_tgt: pd.DataFrame):
        tri_ref = self._getTriangles(df_ref)
        tri_tgt = self._getTriangles(df_tgt)

        # Collect triangle match counts
        TRIANGLETOLERANCE = 2e-4
        votes = np.zeros((len(df_ref)+1, len(df_tgt)+1), dtype=np.uint32)

        for tgt in tri_tgt.itertuples():
            ref_matches = tri_ref[(tri_ref.fX >= tgt.fX) & (tri_ref.fX <= tgt.fX + TRIANGLETOLERANCE)]
            ref_matches = ref_matches[(ref_matches.fX-tgt.fX)**2 + (ref_matches.fY-tgt.fY)**2 < TRIANGLETOLERANCE**2]
            for ref in ref_matches.itertuples():
                for a,b in product([ref.s1, ref.s2, ref.s3], [tgt.s1, tgt.s2, tgt.s3]):
                    votes[int(a), b] += 1

        # Produce sorted list of star pairs with highest votes
        vVotingPairs = np.column_stack(np.unravel_index(np.argsort(votes, axis=None), shape=votes.shape))[::-1]

        # Select only those votes that are higher than a treshold
        x,y = vVotingPairs[len(df_tgt)]
        cutoff = max(1, votes[x,y])
        # print(f"Vote cutoff threshold: {cutoff}")
        topVotePairs = list(filter(lambda r: votes[r[0],r[1]] > cutoff, vVotingPairs))

        matches = []
        for vp in topVotePairs:
            s1, s2 = vp
            if s1 == 0 or s2 == 0:
                continue
            if np.argmax(votes[:, s2]) != s1 or np.argmax(votes[s1, :]) != s2:
                continue
            matches.append((s1, s2))

        df_tgt['starno'] = None
        for m1, m2 in matches:
            df_tgt.loc[m2, 'starno'] = m1
        frames = pd.merge(left=df_ref,
                          right=df_tgt[df_tgt.starno.notna()],
                          left_index=True,
                          right_on='starno',
                          how='right',
                          suffixes=["_ref", "_tgt"])
        frames['fwhm_x_diff'] = frames.fwhm_x_ref - frames.fwhm_x_tgt
        frames['fwhm_y_diff'] = frames.fwhm_y_ref - frames.fwhm_y_tgt
        return frames

    def _getTriangles(self, df):
        # Cache distances between every pair of stars
        starDistances = {}
        for c in combinations(df.index, 2):
            assert(c[1] > c[0])
            key = (c[0], c[1])
            x1, y1 = df.loc[c[0],['cluster_cx', 'cluster_cy']]
            x2, y2 = df.loc[c[1],['cluster_cx', 'cluster_cy']]
            starDistances[key] = math.sqrt((x2-x1)**2 + (y2-y1)**2)

        vTriangles = []
        for i,j,k in combinations(df.index, 3):
            vDistances = sorted([starDistances[(i,j)], starDistances[(j,k)], starDistances[(i,k)]])

            if vDistances[2] > 0:
                fX = vDistances[1]/vDistances[2]
                fY = vDistances[0]/vDistances[2]

                # Filter
                if (fX < 0.9):
                    # Add to the triangle list
                    vTriangles.append({"s1":i, "s2":j, "s3":k, "fX":fX, "fY":fY})

        vTriangles = sorted(vTriangles, key=lambda x: x["fX"])
        return pd.DataFrame(vTriangles)

if __name__ == "__main__":
    from star_finder import StarFinder
    out_of_focus = r"C:\code\astrocam\outoffocus\Image741.nef"
    in_focus = r"C:\code\astrocam\light\Image752.nef"
    s = StarFinder()

    ref_data = s.getStarData(in_focus)
    tgt_data = s.getStarData(out_of_focus)
    ref_image, df_ref = ref_data["image"], ref_data["stars"]
    tgt_image, df_tgt = tgt_data["image"], tgt_data["stars"]

    matcher = StarMatcher()
    df_matched = matcher.matchStars(df_ref, df_tgt)
    print(df_matched.head())
