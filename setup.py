from setuptools import setup
from Cython.Build import cythonize

setup(
    name='Astrocam',
    ext_modules=cythonize(["astrocam.py", "image_data.py", "snap_process.py", "settings.py", "ui/*.py", 
                           "Alpaca/*.py", "asi_native/asinative_camera.py", "simulated_devices/*.py",
                           "fwhm/*.py", "skymap/skymap.py", "skymap/platesolver.py", "skymap/stardb/render_view.py",
                           "xisf/*.py", "debayer/*.py"]),
)