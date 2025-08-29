TODO:
- Optimize plate solver
- Auto focus without bhatinov mask or slewing to bright star


- background subtract for FWHM ?

- UI controls to nudge mount
- Precompute triangles within 2deg FoV; and cache

- Video stream
- Convolutions for bilinear debayering

Log autofocus - done
Check AF  logic -> search width may be too big; out of focus stars are not detected; if no stars are picked up in a frame, code crashes
Histogram fitting fails on dark images
New gaussian2d fit errors out
Image zoom in/out does not adjust scrollbars


Task to turn off cooler
Try HFD instead of FWHM
Stop timer based polling events
Robust phd2 output parsing - continuous monitoring
Parameterize everything in yaml
