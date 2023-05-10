import numpy as np
import scipy.optimize as opt

def twoD_GaussianScaledAmp(pos, xo, yo, sigma_x, sigma_y, amplitude, offset):
    """Function to fit, returns 2D gaussian function as 1D array"""
    x,y = pos
    xo = float(xo)
    yo = float(yo)
    g = offset + amplitude*np.exp( - (((x-xo)**2)/(2*sigma_x**2) + ((y-yo)**2)/(2*sigma_y**2)))
    return g.ravel()

def getFWHM_GaussianFitScaledAmp(img, ax=None):
    """Get FWHM(x,y) of a blob by 2D gaussian fitting
    Parameter:
        img - image as numpy array
    Returns: 
        FWHMs in pixels, along x and y axes.
    """
    assert(img.shape[0]< 100)
    assert(img.shape[1]< 100)
    x = np.linspace(0, img.shape[1], img.shape[1])
    y = np.linspace(0, img.shape[0], img.shape[0])
    x, y = np.meshgrid(x, y)
    #Parameters: xpos, ypos, sigmaX, sigmaY, amp, baseline
    initial_guess = (img.shape[1]/2,img.shape[0]/2,10,10,1,0)
    # subtract background and rescale image into [0,1], with floor clipping
    bg = np.percentile(img,5)
    img = np.clip((img - bg) / (img.max() - bg),0,1)

    popt, pcov = opt.curve_fit(twoD_GaussianScaledAmp, (x, y), 
                              img.ravel(), p0=None, #initial_guess,
                              bounds = (
                                  (0, 0, 1, 1, 0.5, -0.1), # Lower bound
                                  (img.shape[1], img.shape[0], img.shape[1], img.shape[0], 1.5, 0.5) # Upper bound
                                )
                            )
    xcenter, ycenter, sigmaX, sigmaY, amp, offset = popt[0], popt[1], popt[2], popt[3], popt[4], popt[5]

    if ax:
      z = offset + amp*np.exp( - (((x-xcenter)**2)/(2*sigmaX**2) + ((y-ycenter)**2)/(2*sigmaY**2)))
      ax.plot_surface(x,y,z)

    FWHM_x = np.abs(4*sigmaX*np.sqrt(-0.5*np.log(0.5)))
    FWHM_y = np.abs(4*sigmaY*np.sqrt(-0.5*np.log(0.5)))
    return (FWHM_x/img.shape[1], FWHM_y/img.shape[0], xcenter, ycenter)

def _parabola(x, a, b, c):
    return a * (x - b) ** 2 + c

def fwhm1d_old(star):
    x = np.arange(0, len(star))
    y = star
    half_max = np.max(y) / 2.
    # find when function crosses line half_max (when sign of diff flips)
    # take the 'derivative' of signum(half_max - y[])
    d = np.sign(half_max - np.array(y[0:-1])) - np.sign(half_max - np.array(y[1:]))
    # find the left and right most indexes
    left_idx = np.where(d > 0)[0][0]
    right_idx = np.where(d < 0)[0][0]
    # fit a parabola to the peak
    x_peak = (x[left_idx] + x[right_idx]) / 2.
    y_peak = y[left_idx:right_idx+1]
    p_init = [half_max, x_peak, 1.]
    coeff, _ = opt.curve_fit(_parabola, x[left_idx:right_idx+1], y[left_idx:right_idx+1], p_init)
    return abs(coeff[2] * 2.355)


def fwhm1d(arr):
    # Find maximum value of array
    max_val = np.max(arr)
    
    # Find index of maximum value
    max_index = np.argmax(arr)
    
    # Define Gaussian function
    def gaussian(x, amplitude, mean, stddev):
        return amplitude * np.exp(-((x - mean) / 4 / stddev)**2)
    
    # Define error function
    def errfunc(p, x, y):
        return gaussian(x, *p) - y
    
    # Define x and y values for curve_fit
    x = np.arange(len(arr))
    y = arr
    
    # Define initial guess for Gaussian parameters
    p0 = [max_val, max_index, 1]
    
    # Fit Gaussian to data using curve_fit
    p1, success = opt.leastsq(errfunc, p0[:], args=(x, y))
    
    # Calculate FWHM from Gaussian parameters
    fwhm = abs(8 * np.log(2) * p1[2])
    
    return fwhm

def _paraboloid(xy, a, x0, y0, sigma_x, sigma_y, c):
    x, y = xy
    return a * np.exp(-((x-x0)**2/(2*sigma_x**2) + (y-y0)**2/(2*sigma_y**2))) + c


def fwhm2d(star):
    x = np.arange(0, star.shape[1])
    y = np.arange(0, star.shape[0])
    x, y = np.meshgrid(x, y)
    z = star
    half_max = np.max(z) / 2.
    # find when function crosses line half_max (when sign of diff flips)
    # take the 'derivative' of signum(half_max - z[])
    d = np.sign(half_max - np.array(z[0:-1])) - np.sign(half_max - np.array(z[1:]))
    # find the left and right most indexes
    left_idx = np.where(d > 0)[0][0]
    right_idx = np.where(d < 0)[0][0]
    top_idx = np.where(d[:, left_idx] < 0)[0][0]
    bottom_idx = np.where(d[:, left_idx] > 0)[0][0]
    # fit a parabola to the peak
    x_peak = (x[left_idx] + x[right_idx]) / 2.
    y_peak = (y[top_idx] + y[bottom_idx]) / 2.
    z_peak = z[top_idx:bottom_idx+1, left_idx:right_idx+1]
    p_init = [half_max, x_peak, y_peak, 1., 1., 1.]
    coeff, _ = opt.curve_fit(_paraboloid, (x[left_idx:right_idx+1], y[top_idx:bottom_idx+1]), z_peak.ravel(), p_init)
    return abs(coeff[3] * 2.355), abs(coeff[4] * 2.355)


def gaussian2d(height, center_x, center_y, sigma_x, sigma_y, circular=False):
    """ Returns a gaussian function with the given parameters"""
    if circular:
        return lambda x,y: height*np.exp(-(((center_x-x)/sigma_x)**2+((center_y-y)/sigma_x)**2)/2)
    else:
        return lambda x,y: height*np.exp(-(((center_x-x)/sigma_x)**2+((center_y-y)/sigma_y)**2)/2)


def moments(data, circular=False, centered=False):
    """ Returns (height, x, y, width_x, width_y, circular) 
    the gaussian parameters of a 2D distribution by calculating its moments """
    total = data.sum()
    X, Y = np.indices(data.shape)
    if centered:
        x = float(data.shape[0]/2)
        y = float(data.shape[1]/2)
    else:
        x = (X*data).sum()/total
        y = (Y*data).sum()/total
    col = data[:, int(y)]
    sigma_x = np.sqrt(abs((np.arange(col.size)-y)**2*col).sum()/col.sum())
    row = data[int(x), :]
    sigma_y = np.sqrt(abs((np.arange(row.size)-y)**2*row).sum()/row.sum())
    height = data.max()
    if circular:
        sigma_y = sigma_x = (sigma_x + sigma_y)/2
    return height, x, y, sigma_x, sigma_y


def fitgaussian2d(data, circular=False, centered=False):
    """ Returns (height, x, y, width_x, width_y)
    the gaussian parameters of a 2D distribution found by a fit"""
    params = moments(data, circular=circular, centered=centered)     
    errorfunction = lambda p: np.ravel(gaussian2d(*p, circular=circular)(*np.indices(data.shape)) - data)
    p, success = opt.leastsq(errorfunction, params)
    if circular: # make sure that we have something sensible to sigma_y
        p[4] = p[3]
    return p[0], p[1], p[2], p[3], p[4]

def fwhm(sigma):
    """ Calculates the full width half maximum for a given width
    only makes sense for circular gaussians """
    fwhm = 2 * np.sqrt(2 * np.log(2)) * sigma # standard fcn, see web
    return fwhm

def test_fitgaussian2d():
    """ Test gaussian fit """
    import matplotlib.pyplot as plt
    # Create the gaussian data
    Xin, Yin = np.mgrid[0:201, 0:201]
    data = gaussian2d(1, 100, 100, 20, 20, circular=True)(Xin, Yin) + (0.25 * np.random.random(Xin.shape))
    # Fit the gaussian data
    params = fitgaussian2d(data, circular=True)
    fit = gaussian2d(*params, circular=True)(Xin, Yin)
    print(params)
    print(fwhm(params[3]), fwhm(params[4]))
    # Plot the gaussian data and the fit
    
    plt.matshow(data)
    plt.matshow(fit)
    plt.show()

def test_fwhm():
    """ Test fwhm """
    # Create the gaussian data
    Xin, Yin = np.mgrid[0:201, 0:201]
    data = gaussian2d(3, 100, 100, 20, 40, circular=True)(Xin, Yin) + np.random.random(Xin.shape)
    # Fit the gaussian data
    params = fitgaussian2d(data, circular=True)
    print(params)
    print(fwhm(params[3]), fwhm(params[4]))
    # Plot the gaussian data and the fit
    import matplotlib.pyplot as plt
    plt.matshow(data)
    plt.show()

if __name__ == '__main__':
    test_fitgaussian2d()
    # test_fwhm()
