#!/usr/local/bin/ python3
# This module contains a set of functions and classes that are used in several different Python scripts in the Database.
from astropy.io import fits
from astropy.wcs import WCS
from support_functions import linenumber,print_log,set_limits
from read_functions import obtain_border_pix
from scipy import ndimage
import numpy as np
import copy
import warnings

class BadHeaderError(Exception):
    pass
class BadCubeError(Exception):
    pass


# clean the header
def clean_header(hdr,log):
    if not 'EPOCH' in hdr:
        if 'EQUINOX' in hdr:
            log_statement = f'''CLEAN_HEADER: Your cube has no EPOCH keyword but we found EQUINOX.
{"":8s}We have set EPOCH to {hdr['EQUINOX']}
'''
            print_log(log_statement,log)
            hdr['EPOCH'] = hdr['EQUINOX']
            del hdr['EQUINOX']
        else:
            log_statement = f'''CLEAN_HEADER: Your cube has no EPOCH keyword
{"":8s}CLEAN_HEADER: We assumed J2000
'''
            print_log(log_statement,log)
            hdr['EPOCH'] = 2000.

    if hdr['CUNIT3'].upper() == 'HZ' or hdr['CTYPE3'].upper() == 'FREQ':
        print_log('CLEAN_HEADER: FREQUENCY IS NOT A SUPPORTED VELOCITY AXIS.',log)
        raise BadHeaderError('The Cube has frequency as a velocity axis this is not supported')

    if not 'CUNIT3' in hdr:
        if hdr['CDELT3'] > 500:
            hdr['CUNIT3'] = 'm/s'
        else:
            hdr['CUNIT3'] = 'km/s'
        log_statement = f'''CLEAN_HEADER: Your header did not have a unit for the third axis, that is bad policy.
{"":8s} We have set it to {hdr['CUNIT3']}. Please ensure that is correct.'
'''
        print_log(log_statement,log)
    vel_types = ['VELO-HEL','VELO-LSR','FELO-HEL','FELO-LSR','VELO', 'VELOCITY']
    if hdr['CTYPE3'].upper() not in vel_types:
        if hdr['CTYPE3'].split('-')[0].upper() in ['RA','DEC']:
            log_statement = f'''CLEAN_HEADER: Your zaxis is a spatial axis not a velocity axis.
{"":8s}CLEAN_HEADER: Please arrange your cube logically
'''
            print_log(log_statement,log)
            raise BadHeaderError("The Cube's third axis is not a velocity axis")
        hdr['CTYPE3'] = 'VELO'
        log_statement = f'''CLEAN_HEADER: Your velocity projection is not standard. The keyword is changed to VELO (relativistic definition). This might be dangerous.
'''
        print_log(log_statement,log)

    if hdr['CUNIT3'].lower() == 'km/s':
        log_statement = f'''CLEAN_HEADER: The channels in your input cube are in km/s. This sometimes leads to problems with wcs lib, hence we change it to m/s.'
'''
        print_log(log_statement,log)
        hdr['CUNIT3'] = 'm/s'
        hdr['CDELT3'] = hdr['CDELT3']*1000.
        hdr['CRVAL3'] = hdr['CRVAL3']*1000.
    # Check for the beam
    if not 'BMAJ' in hdr:
        if 'BMMAJ' in hdr:
            hdr['BMAJ']= hdr['BMMAJ']/3600.
        else:
            found = False
            for line in hdr['HISTORY']:
                tmp = [x.strip().upper() for x in line.split()]
                if 'BMAJ=' in tmp:
                    hdr['BMAJ'] = tmp[tmp.index('BMAJ=') + 1]
                    found = True
                if 'BMIN=' in tmp:
                    hdr['BMIN'] = tmp[tmp.index('BMIN=') + 1]
                if 'BPA=' in tmp:
                    hdr['BPA'] = tmp[tmp.index('BPA=') + 1]
                if found:
                    break
            if not found:
                log_statement = f'''CLEAN_HEADER: WE CANNOT FIND THE MAJOR AXIS FWHM IN THE HEADER
'''
                print_log(log_statement,log)
                raise BadHeaderError("The Cube has no major axis FWHM in the header.")
    if not 'CTYPE1' in hdr or not 'CTYPE2' in hdr:
        log_statement = f'''CLEAN_HEADER: Your spatial axes have no ctype. this can lead to errors.
'''
        print_log(log_statement,log)
        raise BadHeaderError("The Cube header has no ctypes.")

    if hdr['CTYPE1'].split('-')[0].upper() in ['DEC']:
        log_statement = f'''CLEAN_HEADER: !!!!!!!!!!Your declination is in the first axis, that's ignorant !!!!!!!!!!!!!!!!!
{"":8s}CLEAN_HEADER: !!!!!!!!!!         This will not work.          !!!!!!!!!!!!!!!!
'''
        print_log(log_statement,log)
        raise BadHeaderError("Your spatial axes are reversed")
    if hdr['CTYPE2'].split('-')[0].upper() in ['RA']:
        log_statement = f'''CLEAN_HEADER: !!!!!!!!!!Your right ascension is on the second axis, that's ignorant !!!!!!!!!!!!!!!!!
{"":8s}CLEAN_HEADER: !!!!!!!!!!         This will not work.          !!!!!!!!!!!!!!!!
'''
        print_log(log_statement,log)
        raise BadHeaderError("Your spatial axes are reversed")

    if not 'BMIN' in hdr:
        if 'BMMIN' in hdr:
            hdr['BMIN']= hdr['BMMIN']/3600.
        else:
            log_statement = f'''CLEAN_HEADER: We cannot find the minor axis FWHM. Assuming a circular beam.
'''
            print_log(log_statement,log)
            hdr['BMIN'] = hdr['BMAJ']

    if len(hdr['HISTORY']) > 10:
        del hdr['HISTORY']
        log_statement = f'''CLEAN_HEADER: Your cube has a significant history attached we are removing it for easier interpretation.
'''
        print_log(log_statement,log)

    if abs(hdr['BMAJ']/hdr['CDELT1']) < 2:
        log_statement = f'''CLEAN_HEADER: !!!!!!!!!!Your cube has less than two pixels per beam major axis.!!!!!!!!!!!!!!!!!
{"":8s}CLEAN_HEADER: !!!!!!!!!!           This will lead to bad results.              !!!!!!!!!!!!!!!!'
'''
        print_log(log_statement,log)

    if abs(hdr['BMAJ']/hdr['CDELT1']) > hdr['NAXIS1']:
        log_statement = f'''CLEAN_HEADER: !!!!!!!!!!Your cube is smaller than the beam major axis. !!!!!!!!!!!!!!!!!
{"":8s}CLEAN_HEADER: !!!!!!!!!!         This will not work.          !!!!!!!!!!!!!!!!
'''
        print_log(log_statement,log)
        raise BadHeaderError("Your cube is too small for your beam")

clean_header.__doc__ = '''
;+
; NAME:
;       CLEAN_HEADER
;
; PURPOSE:
;       Clean up the cube header and make sure it has all the right
;       variables that we require in the process of fitting
;
; CATEGORY:
;       Support
;
; CALLING SEQUENCE:
;       CLEAN_HEADER,header,log=log
;
;
; INPUTS:
;       hdr = the header of the cube
;      log = the logging file
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;       clean_header = a header that is ok.
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;
;
; EXAMPLE:

;
; NOTE:
;
;-
'''
# Create a cube suitable for FAT
def create_fat_cube(Configuration, Fits_Files):
    #First get the cubes
    Cube = fits.open(Configuration['FITTING_DIR']+Fits_Files['ORIGINAL_CUBE'],uint = False, do_not_scale_image_data=True,ignore_blank = True, output_verify= 'ignore')
    data = Cube[0].data
    hdr = Cube[0].header
    if hdr['NAXIS'] == 4:
        data = data[0,:,:,:]
        del hdr['NAXIS4']
        hdr['NAXIS'] = 3
    # clean the header
    clean_header(hdr,Configuration["OUTPUTLOG"])
    data = prep_cube(hdr,data,Configuration["OUTPUTLOG"])
    Configuration['NOISE'] = hdr['FATNOISE']
    # and write our new cube
    log_statement = f'''CREATE_FAT_CUBE: We are writing a FAT modfied cube to be used for the fitting. This cube is called {Configuration['FITTING_DIR']+Fits_Files['FITTING_CUBE']}
'''
    print_log(log_statement,Configuration["OUTPUTLOG"])
    fits.writeto(Configuration['FITTING_DIR']+Fits_Files['FITTING_CUBE'],data,hdr)
    # Release the arrays
    #We want to check if the cube has a decent number of pixels per beam.
    optimized_cube(hdr,data,Configuration, Fits_Files,log = Configuration["OUTPUTLOG"])

    Cube.close()
    data = []
    hdr = []


create_fat_cube.__doc__ = '''

;+
; NAME:
;       create_fat_cube
;
; PURPOSE:
;       As we do not want to work from the original cube this function copies that cube into a new cube that we can then happily modify and work with
;       To keep disk space overhead this cube might later on also be cut down to size
;
; CATEGORY:
;       Fits
;
;
; INPUTS:
;       dir =  directory where the fitting is done
;  cubename = name of the original cube
;
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;          beam = the beam recorded in the header. If no beam is
;          present it will return [NaN,Nan] and FAT will abort
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       astropy.io.fits
;
; EXAMPLE:
;
;
'''

def cut_cubes(Configuration, Fits_Files, galaxy_box,hdr):

    cube_edge= [5.,3.*round(hdr['BMAJ']/(np.mean([abs(hdr['CDELT1']),abs(hdr['CDELT2'])]))),3.*round(hdr['BMAJ']/(np.mean([abs(hdr['CDELT1']),abs(hdr['CDELT2'])])))]
    cube_size = [hdr['NAXIS3'],hdr['NAXIS2'],hdr['NAXIS1']]
    new_cube = np.array([[0,hdr['NAXIS3']],[0,hdr['NAXIS2']],[0,hdr['NAXIS1']]],dtype= int)
    cut  = False
    for i,limit in enumerate(galaxy_box):
        if limit[0] > cube_edge[i]:
            cut = True
            new_cube[i,0] = limit[0]-int(cube_edge[i])
        if limit[1] < cube_size[i] - cube_edge[i]:
            cut = True
            new_cube[i,1] = limit[1]+int(cube_edge[i])


    if cut and Configuration['START_POINT'] != 2:
        files_to_cut = [Fits_Files['FITTING_CUBE'],'Sofia_Output/'+Fits_Files['MASK'],\
                        'Sofia_Output/'+Fits_Files['MOMENT0'],\
                        'Sofia_Output/'+Fits_Files['MOMENT1'],\
                        'Sofia_Output/'+Fits_Files['MOMENT2'],\
                        'Sofia_Output/'+Fits_Files['CHANNEL_MAP'],\
                        ]
        if Configuration['OPTIMIZED']:
            files_to_cut.append(Fits_Files['OPTIMIZED_CUBE'])

            print_log(f'''CUT_CUBES: Your input cube is significantly larger than the detected source.
{"":8s}CUT_CUBES: we will cut to x-axis = [{new_cube[2,0]},{new_cube[2,1]}] y-axis = [{new_cube[1,0]},{new_cube[1,1]}]
{"":8s}CUT_CUBES: z-axis = [{new_cube[2,0]},{new_cube[2,1]}].
{"":8s}CUT_CUBES: We will cut the following files:
{"":8s}CUT_CUBES: {', '.join(files_to_cut)}
''', Configuration['OUTPUTLOG'])

        for file in files_to_cut:
            cutout_cube(Configuration['FITTING_DIR']+file,new_cube)
        return new_cube
cut_cubes.__doc__ = '''

;+
; NAME:
;       cut_cubes(Configuration, Fits_Files, galaxy_box,hdr):
;
; PURPOSE:
;       Cut all FAT related out back in size to a system that fits snugly around the sofia detection
;
; CATEGORY:
;       Fits
;
;
; INPUTS:
;       galaxy_box = array that contains the new size as [[z_min,z_max],[y_min,y_max], [x_min,x_max]] adhering to fits' idiotic way of rading fits files
;
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       np.array, cutout_cube
;
; NOTES:  The cut cubes will overwrite the _FAT products
;         down to size and overwrite the existing files,
;         hence do not apply this when SoFIA product are user suplied
;
;
'''

def cutout_cube(filename,sub_cube):
    Cube = fits.open(filename,uint = False, do_not_scale_image_data=True,ignore_blank = True, output_verify= 'ignore')
    hdr = Cube[0].header

    if hdr['NAXIS'] == 3:
        data = Cube[0].data[sub_cube[0,0]:sub_cube[0,1],sub_cube[1,0]:sub_cube[1,1],sub_cube[2,0]:sub_cube[2,1]]
        hdr['NAXIS1'] = sub_cube[2,1]-sub_cube[2,0]
        hdr['NAXIS2'] = sub_cube[1,1]-sub_cube[1,0]
        hdr['NAXIS3'] = sub_cube[0,1]-sub_cube[0,0]
        hdr['CRPIX1'] = hdr['CRPIX1'] -sub_cube[2,0]
        hdr['CRPIX2'] = hdr['CRPIX2'] -sub_cube[1,0]
        hdr['CRPIX3'] = hdr['CRPIX3'] -sub_cube[0,0]
    elif hdr['NAXIS'] == 2:
        data = Cube[0].data[sub_cube[1,0]:sub_cube[1,1],sub_cube[2,0]:sub_cube[2,1]]
        hdr['NAXIS1'] = sub_cube[2,1]-sub_cube[2,0]
        hdr['NAXIS2'] = sub_cube[1,1]-sub_cube[1,0]
        hdr['CRPIX1'] = hdr['CRPIX1'] -sub_cube[2,0]
        hdr['CRPIX2'] = hdr['CRPIX2'] -sub_cube[1,0]


    Cube.close()
    fits.writeto(filename,data,hdr,overwrite = True)

cut_cubes.__doc__ = '''

;+
; NAME:
;       cutout_cube(filename,sub_cube):
;
; PURPOSE:
;       Cut filename back to the size of subcube, update the header and write back to disk.
;
; CATEGORY:
;       Fits
;
;
; INPUTS:
;       filename = name of file to be cut.
;       sub_cube = array that contains the new size as [[z_min,z_max],[y_min,y_max], [x_min,x_max]] adhering to fits' idiotic way of rading fits files
;
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       astropy.io.fits
;
; NOTES:  The cut cubes will overwrite the _FAT products
;         down to size and overwrite the existing files,
;         hence do not apply this when SoFIA product are user suplied
;
;
'''

# Extract a PV-Diagrams
def extract_pv(cube_in,angle,center=[-1,-1,-1],finalsize=[-1,-1],convert=-1):
    cube = copy.deepcopy(cube_in)
    hdr = copy.deepcopy(cube[0].header)
    data = copy.deepcopy(cube[0].data)
    #Because astro py is even dumber than Python
    if hdr['CUNIT3'].lower() == 'km/s':
        hdr['CUNIT3'] = 'm/s'
        hdr['CDELT3'] = hdr['CDELT3']*1000.
        hdr['CRVAL3'] = hdr['CRVAL3']*1000.
    elif hdr['CUNIT3'].lower() == 'm/s':
        hdr['CUNIT3'] = 'm/s'
    if center[0] == -1:
        center = [hdr['CRVAL1'],hdr['CRVAL2'],hdr['CRVAL3']]
        xcenter,ycenter,zcenter = hdr['CRPIX1'],hdr['CRPIX2'],hdr['CRPIX3']
    else:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coordinate_frame = WCS(hdr)
        xcenter,ycenter,zcenter = coordinate_frame.wcs_world2pix(center[0], center[1], center[2], 0.)

    nz, ny, nx = data.shape
    if finalsize[0] != -1:
        if finalsize[1] >nz:
            finalsize[1] = nz
        if finalsize[0] > nx:
            finalsize[0] = nx
    # if the center is not set assume the crval values

    x1,x2,y1,y2 = obtain_border_pix(hdr,angle,[xcenter,ycenter])
    linex,liney,linez = np.linspace(x1,x2,nx), np.linspace(y1,y2,nx), np.linspace(0,nz-1,nz)
    new_coordinates = np.array([(z,y,x)
                        for z in linez
                        for y,x in zip(liney,linex)
                        ],dtype=float).transpose().reshape((-1,nz,nx))
    spatial_resolution = abs((abs(x2-x1)/nx)*np.sin(np.radians(angle)))+abs(abs(y2-y1)/ny*np.cos(np.radians(angle)))
    PV = ndimage.map_coordinates(data, new_coordinates,order=1)
    if hdr['CDELT1'] < 0:
        PV = PV[:,::-1]

    if finalsize[0] == -1:
        # then lets update the header
        # As python is stupid making a simple copy will mean that these changes are still applied to hudulist
        hdr['NAXIS2'] = nz
        hdr['NAXIS1'] = nx

        hdr['CRPIX2'] = hdr['CRPIX3']
        if convert !=-1:
            hdr['CRVAL2'] = hdr['CRVAL3']/convert
        else:
            hdr['CRVAL2'] = hdr['CRVAL3']
        hdr['CRPIX1'] = xcenter+1
    else:
        zstart = set_limits(int(zcenter-finalsize[1]/2.),0,int(nz))
        zend = set_limits(int(zcenter+finalsize[1]/2.),0,int(nz))
        xstart = set_limits(int(xcenter-finalsize[0]/2.),0,int(nx))
        xend = set_limits(int(xcenter+finalsize[0]/2.),0,int(nx))
        PV =  PV[zstart:zend, xstart:xend]
        hdr['NAXIS2'] = int(finalsize[0])
        hdr['NAXIS1'] = int(finalsize[1])
        hdr['CRPIX2'] = hdr['CRPIX3']-int(nz/2.-finalsize[0]/2.)
        if convert !=-1:
            hdr['CRVAL2'] = hdr['CRVAL3']/convert
        else:
            hdr['CRVAL2'] = hdr['CRVAL3']

        hdr['CRPIX1'] = int(finalsize[1]/2.)+1
    if convert !=-1:
        hdr['CDELT2'] = hdr['CDELT3']/convert
    else:
        hdr['CDELT2'] = hdr['CDELT3']
    hdr['CTYPE2'] = hdr['CTYPE3']
    try:
        if hdr['CUNIT3'].lower() == 'm/s' and convert == -1:
            hdr['CDELT2'] = hdr['CDELT3']/1000.
            hdr['CRVAL2'] = hdr['CRVAL3']/1000.
            hdr['CUNIT2'] = 'km/s'
            del (hdr['CUNIT3'])
        elif  convert != -1:
            del (hdr['CUNIT3'])
            del (hdr['CUNIT2'])
        else:
            hdr['CUNIT2'] = hdr['CUNIT3']
            del (hdr['CUNIT3'])
    except:
        print("No units")
    del (hdr['CRPIX3'])
    del (hdr['CRVAL3'])
    del (hdr['CDELT3'])
    del (hdr['CTYPE3'])

    del (hdr['NAXIS3'])
    hdr['CRVAL1'] = 0.
    hdr['CDELT1'] = abs(((abs(x2-x1)*abs(hdr['CDELT1']))/nx)*np.sin(np.radians(angle)))+abs((abs(y2-y1)*abs(hdr['CDELT2']))/ny*np.cos(np.radians(angle)))
    hdr['CTYPE1'] = 'OFFSET'
    hdr['CUNIT1'] = 'ARCSEC'
    # Then we change the cube and rteturn the PV construct
    cube[0].header = hdr
    cube[0].data = PV

    return cube

extract_pv.__doc__ = '''

;+
; NAME:
;       extract_pv(cube_in, angle, center, finalsize, ):
;
; PURPOSE:
;       extract a PV diagram from a cube object. Angle is the PA and center the central location. The profile is extracted over the full length of the cube and afterwards cut back to the finalsize.
;
; CATEGORY:
;       Fits
;
;
; INPUTS:
;        cube = is a fits cube object
;       angle = Pa of the slice
;      center = the central location of the slice in WCS map_coordinates [RA,DEC,VSYS]
;      finalsize = final size of the PV-diagram in pixels
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       ndimage.map_coordinates, WCS, numpy
;
;
;
'''


#Create an optimized cube if required
def optimized_cube(hdr,data,Configuration,Fits_Files, log =None):
    pix_per_beam = round(hdr['BMIN']/(np.mean([abs(hdr['CDELT1']),abs(hdr['CDELT2'])])))
    if abs(hdr['CDELT1']) != abs(hdr['CDELT2']):
        log_statement = f'''OPTIMIZED_CUBE: Your input cube does not have square pixels.
{"":8s}OPTIMIZED_CUBE: FAT cannot optimize your cube.
'''
        print_log(log_statement, log)
    elif pix_per_beam > Configuration['OPT_PIXELBEAM']:
        Configuration['OPTIMIZED'] = True
        required_cdelt = hdr['BMIN']/int(Configuration['OPT_PIXELBEAM'])
        ratio = required_cdelt/abs(hdr['CDELT2'])
        opt_data,opt_hdr = regrid_cube(data, hdr, ratio)

        fits.writeto(Configuration['FITTING_DIR']+Fits_Files['OPTIMIZED_CUBE'], opt_data,opt_hdr)

        Configuration['OPTIMIZED'] = True
        log_statement = f'''OPTIMIZED_CUBE: Your input cube has {pix_per_beam} pixels along the minor FWHM.
{"":8s}OPTIMIZED_CUBE: You requested { Configuration['OPT_PIXELBEAM']} therefore we regridded the cube into a new cube.
{"":8s}OPTIMIZED_CUBE: We are using the pixel size of {required_cdelt}.
'''
        print_log(log_statement, log)

    else:
        log_statement = f'''OPTIMIZED_CUBE: Your input cube has {pix_per_beam} pixels along the minor FWHM.
{"":8s}OPTIMIZED_CUBE: You requested { Configuration['OPT_PIXELBEAM']} but we cannot improve the resolution.
{"":8s}OPTIMIZED_CUBE: We are using the pixel size of the original cube.
'''
        print_log(log_statement, log)

optimized_cube.__doc__ = '''

;+
; NAME:
;       optimized_cube(hdr,data,Configuration,Fits_Files, log =None):
;
; PURPOSE:
;       Check the amount of pixels that are in the minor axis FWHM, if more than OPT_PIXELBEAM regrid the cube to less pixels
;       and write FAT_opt cube and set Configuration['OPTIMIZED'] = True
;
; CATEGORY:
;       Fits
;
;
; INPUTS:
;
;
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       astropy.io.fits,regrid_cube
;
; NOTES:
;
;
'''



#preprocess the cube

def prep_cube(hdr,data,log):

    if hdr['CDELT3'] < -1:
        log_statement = f'''PREPROCESSING: Your velocity axis is declining with increasing channels
{"":8s}PREPROCESSING: We reversed the velocity axis.
'''
        print_log(log_statement, log)
        hdr['CDELT3'] = abs(hdr['CDELT3'])
        hdr['CRPIX3'] = hdr['NAXIS3']-hdr['CRPIX3']+1
        data = data[::-1,:,:]
    #Check for zeros
    if np.where(data == 0.):
        log_statement = f'''PREPROCESSING: Your cube contains values exactly 0. If this is padding these should be blanks.
{"":8s}PREPROCESSING: We have changed them to blanks.
'''
        print_log(log_statement, log)
        data[np.where(data == 0.)] = float('NaN')

    # check for blank channels and noise statistics
    cube_ok = False
    prev_first_comparison = 0.
    prev_last_comparison = 0.
    times_cut_first_channel = 0
    times_cut_last_channel = 0
    while not cube_ok:
        while np.isnan(data[0,:,:]).all():
            data=data[1:,:,:]
            hdr['NAXIS3'] = hdr['NAXIS3']-1
            if hdr['NAXIS3'] < 5:
                log_statement = f'''PREPROCESSING: This cube has too many blanked channels.
'''
                print_log(log_statement, log)
                raise BadCubeError("The cube has too many blanked channels")
            log_statement = f'''PREPROCESSING: We are cutting the cube as the first channel is completely blank.
'''
            print_log(log_statement, log)
        while np.isnan(data[-1,:,:]).all():
            data=data[:-1,:,:]
            hdr['NAXIS3'] = hdr['NAXIS3']-1
            if hdr['NAXIS3'] < 5:
                log_statement = f'''PREPROCESSING: This cube has too many blanked channels.
'''
                print_log(log_statement, log)
                raise BadCubeError("The cube has too many blanked channels")
            log_statement = f'''PREPROCESSING: We are cutting the cube as the last channel is completely blank.
'''
            print_log(log_statement, log)
        #Then check the noise statistics
        noise_first_channel = np.nanstd(data[0,:,:])
        noise_last_channel = np.nanstd(data[-1,:,:])
        noise_bottom_right =  np.nanstd(data[:,:6,-6:])
        noise_top_right =  np.nanstd(data[:,-6:,-6:])
        noise_bottom_left =  np.nanstd(data[:,:6,:6])
        noise_top_left =  np.nanstd(data[:,-6:,:6])
        noise_corner = np.mean([noise_top_right,noise_bottom_right,noise_bottom_left,noise_top_left])
        channel_noise = np.mean([noise_first_channel,noise_last_channel])
        difference = abs((noise_first_channel-noise_last_channel)/noise_first_channel)
        if noise_corner/channel_noise >1.5 and difference < 0.2:
            noise_corner = copy.deepcopy(channel_noise)
        difference2 = abs(channel_noise-noise_corner)/channel_noise
        if difference < 0.2 and np.isfinite(difference) and difference2 < 0.25:
            cube_ok = True
        else:
            log_statement = f'''PREPROCESSING: We are cutting the cube as clearly the noise statistics are off.
{"":8s}PREPROCESSING: Noise in the first channel is {noise_first_channel}
{"":8s}PREPROCESSING: Noise in the last channel is {noise_last_channel}
{"":8s}PREPROCESSING: Noise in the corners is {noise_corner}
'''
            print_log(log_statement,log)
            first_comparison = abs(noise_first_channel-noise_corner)/noise_corner
            last_comparison = abs(noise_last_channel-noise_corner)/noise_corner
            if prev_first_comparison == 0:
                prev_first_comparison = first_comparison
            if prev_last_comparison == 0.:
                prev_last_comparison = last_comparison
            if (first_comparison > last_comparison and \
               abs((first_comparison-prev_first_comparison)/first_comparison) >= abs((last_comparison-prev_last_comparison)/last_comparison) and \
               times_cut_first_channel < 0.1*hdr['NAXIS3']) or \
               ~np.isfinite(noise_first_channel):
                prev_first_comparison = first_comparison
                times_cut_first_channel += 1
                data=data[1:,:,:]
                hdr['CRPIX3'] = hdr['CRPIX3'] - 1
                hdr['NAXIS3'] = hdr['NAXIS3'] - 1
            else:
                if times_cut_last_channel < 0.1*hdr['CRPIX3'] or \
                    ~np.finite(noise_last_channel):
                    prev_last_comparison = last_comparison
                    times_cut_last_channel += 1
                    data=data[:-1,:,:]
                    hdr['NAXIS3'] = hdr['NAXIS3'] - 1
                else:
                    cube_ok = True

            if times_cut_first_channel >= 8 and times_cut_last_channel >= 8:
                cube_ok = True
                log_statement = f'''  PREPROCESSING: This cube has non-uniform noise statistics.'
'''
                print_log(log_statement,log)
            if hdr['NAXIS3'] < 5:
                log_statement = f'''PREPROCESSING: This cube has noise statistics that cannot be dealt with.
'''
                print_log(log_statement,log)
                raise BadCubeError('The Cube has noise statistics that cannot be dealt with')

    hdr['FATNOISE'] = noise_corner
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        low_noise_indices = np.where(data < -10*noise_corner)
    if len(low_noise_indices) > 0:
        data[low_noise_indices] = float('NaN')
        log_statement=f'''PREPROCESSING: Your cube had values below -10*sigma. If you do not have a central absorption source there is something seriously wrong with the cube.
{"":8s}PREPROCESSING: We blanked these values.
'''
        print_log(log_statement,log)

    # Check whether any channels got fully blanked
    blanked_channels = []
    for z in range(hdr['NAXIS3']):
        if np.isnan(data[z,:,:]).all():
            blanked_channels.append(str(z))
    if len(blanked_channels) == 0.:
        blanked_channels = ['-1']
    hdr['BL_CHAN'] = ','.join(blanked_channels)
    #Previously SoFiA was not dealing with blanks properly and the statement went here

    return data

prep_cube.__doc__ = '''
;+
; NAME:
;       prep_cube
;
; PURPOSE:
;       Clean up the cube  and make sure it has all the right
;       characteristics and blanks
;
; CATEGORY:
;       Support
;
;
; INPUTS:
;         cube = the array containing the input cube.
;          log = the logging file.
;
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       np.where(), np.finite(), np.isnan()
;
; EXAMPLE:
'''



def regrid_cube(data,hdr,ratio):
    regrid_hdr = copy.deepcopy(hdr)
    # First get the shape of the data
    shape = np.array(data.shape, dtype=float)
    #The new shape has to be integers
    new_shape = [int(x/ratio) for x in shape]
    # Which means our real ratio is
    real_ratio = shape/new_shape

    #* np.ceil(shape / ratio).astype(int)
    new_shape[0] = shape[0]
    # Create the zero-padded array and assign it with the old density
    regrid_data = regridder(data,new_shape)
    regrid_hdr['CRPIX1'] =   (regrid_hdr['CRPIX1']-1)/real_ratio[2]+1
    regrid_hdr['CRPIX2'] =   (regrid_hdr['CRPIX2']-1)/real_ratio[1]+1
    wcs_found = False
    try:
        regrid_hdr['CDELT1'] =   regrid_hdr['CDELT1']*real_ratio[2]
        regrid_hdr['CDELT2'] =   regrid_hdr['CDELT2']*real_ratio[1]
        wcs_found = True
    except:
        print("No CDELT found")
    try:
        regrid_hdr['CD1_1'] =   regrid_hdr['CD1_1']*real_ratio[2]
        regrid_hdr['CD2_2'] =   regrid_hdr['CD2_2']*real_ratio[1]
        wcs_found = True
    except:
        if not wcs_found:
            print("No CD corr matrix found")
    try:
        regrid_hdr['CD1_2'] =   regrid_hdr['CD1_2']*real_ratio[2]
        regrid_hdr['CD2_1'] =   regrid_hdr['CD2_1']*real_ratio[1]
        wcs_found = True
    except:
        if not wcs_found:
            print("No CD cross-corr matrix found")

    regrid_hdr['NAXIS1'] =   new_shape[2]
    regrid_hdr['NAXIS2'] =   new_shape[1]
    return regrid_data,regrid_hdr
regrid_cube.__doc__= '''
;+
; NAME:
;       regrid_cube(data, hdr, ratio)
;
; PURPOSE:
;       Regrid a cube to an arbitrary smaller cube in the spatial plane
;
; CATEGORY:
;       fits
;
;
; INPUTS:
;         cube = the array containing the input cube.
;          hdr = the header data
;         ratio = the requested ratio of old/new
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       np.array(), regridder
;
; EXAMPLE:
'''

def regridder(oldarray, newshape):
    oldshape = np.array(oldarray.shape)
    newshape = np.array(newshape, dtype=float)
    ratios = oldshape/newshape
        # calculate new dims
    nslices = [ slice(0,j) for j in list(newshape) ]
    #make a list with new coord
    new_coordinates = np.mgrid[nslices]
    #scale the new coordinates
    for i in range(len(ratios)):
        new_coordinates[i] *= ratios[i]
    #create our regridded array
    newarray = ndimage.map_coordinates(oldarray, new_coordinates,order=1)

    return newarray
regridder.__doc__= '''
;+
; NAME:
;       regridder(oldarray, newshape)
;
; PURPOSE:
;       Regrid an array into a new shape through the ndimage module
;
; CATEGORY:
;       fits
;
;
; INPUTS:
;         oldarray = the larger array
;         newshape = the new shape that is requested
; OPTIONAL INPUTS:
;
;
; KEYWORD PARAMETERS:
;       -
;
; OUTPUTS:
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       scipy.ndimage.map_coordinates, np.array, np.mgrid
;
; EXAMPLE:
'''
