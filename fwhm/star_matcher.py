import importlib
import rawpy
import numpy as np
import cv2
import pandas as pd
import matplotlib.pyplot as plt
from itertools import combinations, product
import math

class StarMatcher:

    def matchStars(self, df_ref: pd.DataFrame, df_tgt: pd.DataFrame, 
                   vertex_sorted = True,
                   down_votes = True,
                   absolute_similar = True,
                   vote_with_conf = True,
                   limit_ref_triangle_fov=None):
        """ matchStars in a reference and target dataframes from either database or a photo
            Adds columns to target dataframe: starno (index in reference dataframe) and votes (int)
            Returns votes and voting pairs for informational purposes
            Code developed in refine_location.ipynb
        """

        if vertex_sorted:
            tri_ref = self._getVertexSortedTriangles(df_ref, fov_deg=limit_ref_triangle_fov)
            tri_tgt = self._getVertexSortedTriangles(df_tgt)
        else:
            tri_ref = self._getTriangles(df_ref)
            tri_tgt = self._getTriangles(df_tgt)

        TRIANGLETOLERANCE = 1e-3
        votes = np.zeros((len(df_ref)+1, len(df_tgt)+1), dtype=np.float32)

        for tgt in tri_tgt.itertuples():
            if absolute_similar:
                similar_triangles = tri_ref[
                    (tri_ref.fX >= tgt.fX - TRIANGLETOLERANCE/2) &
                    (tri_ref.fX <= tgt.fX + TRIANGLETOLERANCE/2) &
                    (tri_ref.fY >= tgt.fY - TRIANGLETOLERANCE/2) &
                    (tri_ref.fY <= tgt.fY + TRIANGLETOLERANCE/2)
                ]
            else:
                ref_matches = tri_ref[
                    (tri_ref.fX >= tgt.fX - TRIANGLETOLERANCE/2) &
                    (tri_ref.fX <= tgt.fX + TRIANGLETOLERANCE/2)]
                similar_triangles = ref_matches[(ref_matches.fX-tgt.fX)**2 + (ref_matches.fY-tgt.fY)**2 < TRIANGLETOLERANCE**2]

            for ref in similar_triangles.itertuples():
                if vote_with_conf:
                    err = ((ref.fX-tgt.fX)**2 + (ref.fY-tgt.fY)**2)
                    upvote = 1/(np.exp(err*100))
                    downvote = upvote / 4
                else:
                    upvote = 1
                    downvote = 1/4

                if vertex_sorted:
                    # expect matched ABC vertices
                    votes[ref.A, tgt.A] += upvote
                    votes[ref.B, tgt.B] += upvote
                    votes[ref.C, tgt.C] += upvote

                    if down_votes:
                        votes[ref.A, tgt.B] -= downvote
                        votes[ref.A, tgt.C] -= downvote

                        votes[ref.B, tgt.A] -= downvote
                        votes[ref.B, tgt.C] -= downvote
                        
                        votes[ref.C, tgt.A] -= downvote
                        votes[ref.C, tgt.B] -= downvote
                else:
                    # expect unordered star indices s1, s2, s3
                    for a,b in product([ref.s1, ref.s2, ref.s3], [tgt.s1, tgt.s2, tgt.s3]):
                        votes[int(a), b] += upvote

        # print(f"TRIANGLETOLERANCE: {TRIANGLETOLERANCE}")
        # print(f"Total triangle comparisons: {len(tri_ref) * len(tri_tgt)}")
        # print(f"Total votes: {np.sum(votes)}, hit-ratio: {np.sum(votes) / (len(tri_ref) * len(tri_tgt))}")

        # Produce sorted list of star pairs with highest votes
        vVotingPairs = np.column_stack(np.unravel_index(np.argsort(votes, axis=None), shape=votes.shape))[::-1]

        cutoff = votes.max() / 2
        # print(f"Vote cutoff threshold: {cutoff}")
        topVotePairs = list(filter(lambda r: votes[r[0],r[1]] > cutoff, vVotingPairs))

        matches = []
        for vp in topVotePairs:
            s1, s2 = vp
            # if s1 == 0 or s2 == 0: # WHY ?
            #     continue
            if np.argmax(votes[:, s2]) == s1 and np.argmax(votes[s1, :]) == s2:
                matches.append((s1, s2))

        df_tgt['starno'] = None
        df_tgt['votes'] = None
        for m1, m2 in matches:
            df_tgt.loc[m2, 'starno'] = m1
            df_tgt.loc[m2, 'votes'] = votes[m1, m2]

        return votes, vVotingPairs


    def _getTriangles(self, df):
        """ Return pair of side-ratios for each triangle formed by permutations of stars
        For each triangle ABC, with side lengths a,b,c in asc order (c is longest)
        return (a/c, b/c); sorted by a/c
        """
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

                # Add to the triangle list
                vTriangles.append({"s1":i, "s2":j, "s3":k, "fX":fX, "fY":fY})

        vTriangles = sorted(vTriangles, key=lambda x: x["fX"])
        return pd.DataFrame(vTriangles)

    def _getVertexSortedTriangles(self, df, fov_deg=None):
        # Cache distances between every pair of stars
        starDistances = {}
        for c in combinations(df.index, 2):
            assert(c[1] > c[0])
            key = (c[0], c[1])
            x1, y1 = df.loc[c[0],['cluster_cx', 'cluster_cy']]
            x2, y2 = df.loc[c[1],['cluster_cx', 'cluster_cy']]

            if fov_deg:
                ra1, dec1 = df.loc[c[0],['ra', 'dec']]
                ra2, dec2 = df.loc[c[1],['ra', 'dec']]
                sphere_dist = math.sqrt((ra2-ra1)**2 + (dec2-dec1)**2)
            else:
                sphere_dist = None

            cartesian_dist = math.sqrt((x2-x1)**2 + (y2-y1)**2)
            starDistances[key] = cartesian_dist, sphere_dist

        vTriangles = []
        for i,j,k in combinations(df.index, 3):

            ij, ijam = starDistances[(i, j)]
            jk, jkam = starDistances[(j, k)]
            ik, ikam = starDistances[(i, k)]

            if fov_deg and (ijam > fov_deg or
               jkam > fov_deg or
               ikam > fov_deg):
                continue

            s, m, l = sorted([
                (set([i, j]), ij),
                (set([j, k]), jk),
                (set([i, k]), ik)
            ], key=lambda x:x[1])

            A = s[0].intersection(l[0]).pop()
            C = m[0].intersection(l[0]).pop()
            B = s[0].intersection(m[0]).pop()

            fX = s[1]/l[1]
            fY = m[1]/l[1]

            # Add to the triangle list
            vTriangles.append({"A":A, "B":B, "C":C, "fX":fX, "fY":fY})

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
