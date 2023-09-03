from astropy.io import fits
import numpy as np
import cv2
import rawpy
from fwhm.star_finder import StarFinder
from fwhm.star_matcher import StarMatcher

class ImageData:
    def __init__(self, raw, fname, header):
        self._raw = raw
        self._fname = fname
        self._header = header
        self._rgb24 = None
        self._deb16 = None
        self._gray16 = None
        self._gray8 = None
        self._stars = None
        self._star_img = None

    def close(self):
        self._raw = None
        self._fname = None
        self._header = None
        self._rgb24 = None
        self._deb16 = None
        self._gray16 = None
        self._gray8 = None
        self._stars = None
        self._star_img = None

    @property
    def fname(self):
        return self._fname

    @property
    def header(self):
        return self._header

    @property
    def raw(self):
        """ RAW image data (before debayer)
        """
        if self._raw is None:
            ext = self.fname[-3:].lower()
            if ext == 'nef':
                raw = rawpy.imread(self.fname)
                print(f"Postprocessing {self.fname}")
                params = rawpy.Params(demosaic_algorithm = rawpy.DemosaicAlgorithm.AHD,
                    half_size = False,
                    four_color_rgb = False,
                    fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
                    use_camera_wb=True,
                    use_auto_wb=False,
                    #output_color=rawpy.ColorSpace.raw, 
                    #output_bps = 8,
                    user_flip = 0,
                    no_auto_scale = False,
                    no_auto_bright=True
                    #highlight_mode= rawpy.HighlightMode.Clip
                    )

                self._raw = raw.raw_image.copy()
                self._rgb24 = raw.postprocess(params=params)
                raw.close()

            elif ext == 'fit':
                with fits.open(self.fname) as f:
                    ph = f[0]
                    img = ph.data

                    if ph.header['BAYERPAT'] == 'RGGB':
                        self._raw = img
                        deb = cv2.cvtColor(img, cv2.COLOR_BAYER_BG2BGR)
                        if self._raw.dtype == np.uint16:
                            self._deb16 = deb
                        img = deb.astype(np.float32) / np.iinfo(deb.dtype).max
                        img = (img * 255).astype(np.uint8)
                        self._rgb24 = img
                    else:
                        raise NotImplementedError(f"Unsupported bayer pattern: {ph.header['BAYERPAT']}")

        return self._raw

    @property
    def rgb24(self):
        if self._rgb24 is None:
            deb = cv2.cvtColor(self.raw, cv2.COLOR_BAYER_BG2BGR)
            if self.raw.dtype == np.uint16:
                self._deb16 = deb

            img = deb.astype(np.float32) / np.iinfo(deb.dtype).max
            img = (img * 255).astype(np.uint8)
            self._rgb24 = img
        return self._rgb24
    
    @property
    def deb16(self):
        if self._deb16 is None:
            if self.raw.dtype != np.uint16:
                if self.raw.dtype == np.uint8:
                    raw = self.raw.astype(np.uint16)
                    raw *= 256
                else:
                    raise NotImplemented(f"Unsupported raw format")
            else:
                raw = self.raw

            self._deb16 = cv2.cvtColor(raw, cv2.COLOR_BAYER_BG2BGR)
            assert(self._deb16.dtype == np.uint16)
            assert(len(self._deb16.shape) == 3)
            assert(self._deb16.shape[2] == 3)
        return self._deb16

    @property
    def gray16(self):
        if self._gray16 is None:
            self._gray16 = cv2.cvtColor(self.deb16, cv2.COLOR_BGR2GRAY)
        return self._gray16

    @property
    def gray8(self):
        if self._gray8 is None:
            self._gray8 = ((self.gray16 / np.iinfo(np.uint16).max) *np.iinfo(np.uint8).max).astype(np.uint8)
        return self._gray8

    def computeStars(self):
        self.starFinder = StarFinder()
        self.starMatcher = StarMatcher()
        numStars = 20
        self._star_img, self._stars = self.starFinder.find_stars(img8=np.squeeze(self.gray8), img16=np.squeeze(self.gray16), topk=numStars)

    @property
    def stars(self):
        return self._stars
