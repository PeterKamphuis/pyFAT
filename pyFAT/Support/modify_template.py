# -*- coding: future_fstrings -*-
# This module contains a set of functions and classes that are used to Modify the Tirific_Template


class InitializeError(Exception):
    pass
class CfluxError(Exception):
    pass
class FunctionCallError(Exception):
    pass
import copy
from pyFAT.Support.support_functions import set_rings,convertskyangle,sbr_limits,set_limits,print_log,set_limit_modifier,\
                              set_ring_size,calc_rings,finish_current_run,set_format,get_from_template,gaussian_function,fit_gaussian,\
                              get_ring_weights

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import savgol_filter
from scipy.interpolate import CubicSpline

def fix_sbr(Configuration,Tirific_Template,hdr, smooth = False, debug=False):
    if debug:
        print_log(f'''FIX_SBR: Starting a SBR check.
''',Configuration['OUTPUTLOG'],debug=True,screen=True)
    sbr = np.array(get_from_template(Tirific_Template,['SBR','SBR_2']),dtype=float)
    # Let's use a smoothed profile for the fittings
    sm_sbr = smooth_profile(Configuration,Tirific_Template,'SBR',hdr,
                            min_error= np.max([float(Tirific_Template['CFLUX']),
                            float(Tirific_Template['CFLUX_2'])]),fix_sbr_call = True ,debug=debug)

    if debug:
        print_log(f'''FIX_SBR: Before modify.
{sbr}
''',Configuration['OUTPUTLOG'],debug=False,screen=False)
    # get the cutoff limits
    vsys = float(Tirific_Template['VSYS'].split()[0])
    radii,cutoff_limits = sbr_limits(Configuration,hdr, systemic=vsys)


    #cutoff_limits = np.array([cutoff_limits,cutoff_limits],dtype=float)
    # We interpolate negative values as well as values below the limits inner part with a cubi
    for i in [0,1]:
        corr_val = np.where(sbr[i,2:] > cutoff_limits[2:])[0]+2
        if corr_val.size > 0:
            if debug:
                print_log(f'''FIX_SBR: From the list {corr_val} we select {corr_val[-1]} as the last reliable ring.
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
            Configuration['LAST_RELIABLE_RINGS'][i] = corr_val[-1]+1

        else:
            Configuration['LAST_RELIABLE_RINGS'][i] = Configuration['NO_RINGS']
        if corr_val.size > 3.:

            fit_sbr = sm_sbr[i,corr_val]
            if debug:
                print_log(f'''FIX_SBR: The values used for fitting are {fit_sbr}.
''',Configuration['OUTPUTLOG'],debug=True,screen=True)
            try:
                vals = fit_gaussian(radii[corr_val],fit_sbr)
                gaussian = gaussian_function(radii,*vals)
            except RuntimeError:
                # If we fail we try a CubicSpline interpolation
                try:
                    tmp = CubicSpline(radii[corr_val],fit_sbr,extrapolate = True,bc_type ='natural')
                    gaussian = tmp(radii)
                except:
                    # and if that fails we just let the values be what they are
                    gaussian= sm_sbr[i,:]


            missed =np.hstack(([0,1], np.where(sbr[i,2:] < cutoff_limits[2:])[0]+2))
            if missed[-1] != len(sbr[i,:])-1:
                missed = np.hstack((missed,[len(sbr[i,:])-1]))
            sbr[i,missed] = gaussian[missed]
            if np.where(np.max(gaussian) == gaussian)[0] < 2:
                sbr[[0,1],[0,1]] = np.mean(sm_sbr[[0,1],[0,1]])

    # Need to make sure there are no nans
    cutoff_limits = np.array([cutoff_limits,cutoff_limits],dtype=float)
    sbr[np.isnan(sbr)] = 2.*cutoff_limits[np.isnan(sbr)]
    # and where we are lower than the cutoff we replace with the 1.2 *cutoff
    sbr[np.where(sbr<cutoff_limits)] = 1.2*cutoff_limits[np.where(sbr<cutoff_limits)]

    if smooth:
        sbr = smooth_profile(Configuration,Tirific_Template,'SBR',hdr,
                        min_error= np.max([float(Tirific_Template['CFLUX']),
                        float(Tirific_Template['CFLUX_2'])]),profile = sbr, fix_sbr_call = True ,debug=debug)

    #rid the sawtooth

    #if sbr[0,1]/3. > np.mean([sbr[0,0],sbr[0,2]]):
    #    sbr[0,1] = np.mean([sbr[0,0],sbr[0,2]])
    #if sbr[1,1]/3. > np.mean([sbr[1,0],sbr[1,2]]):
    #    sbr[1,1] = np.mean([sbr[1,0],sbr[1,2]])
    #equalize the first two rings
    for i in[0,1]:
        sbr[:,i] = np.mean(sbr[:,i])
    # write back to template
    # the inner points are tricky lets do a spline interpolation on them

    if debug:
        print_log(f'''FIX_SBR: After modify.
{'':8s}{sbr}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
    Tirific_Template['SBR'] = f"{' '.join([f'{x:.2e}' for x in sbr[0]])}"
    Tirific_Template['SBR_2'] = f"{' '.join([f'{x:.2e}' for x in sbr[1]])}"
    print_log(f'''FIX_SBR: We checked the surface brightness profiles.
''',Configuration['OUTPUTLOG'])

def check_size(Configuration,Tirific_Template,hdr, fit_stage = 'Unitialized_Stage', stage = 'initial',
                Fits_Files= 'No Files' ,debug = False,fix_rc = False,current_run='Not Initialized'):
    if debug and not fix_rc:
        print_log(f'''CHECK_SIZE: Starting a new Check_size with the following parameters:
{'':8s}CHECK_SIZE: Rings = {Configuration['NO_RINGS']}
{'':8s}CHECK_SIZE: Size in Beams = {Configuration['SIZE_IN_BEAMS']}
{'':8s}CHECK_SIZE: Fix_RC = {fix_rc}
''',Configuration['OUTPUTLOG'],debug=True,screen=True)


    radii, sbr_ring_limits = sbr_limits(Configuration,hdr,systemic = float(Tirific_Template['VSYS'].split()[0]),debug=debug)
    if fix_rc:
        sbr_ring_limits = 2.5*np.array(sbr_ring_limits)
    #get the sbr profiles

    sbr = np.array(get_from_template(Tirific_Template, ['SBR','SBR_2'],debug=debug),dtype = float)
    if debug and not fix_rc:
        print_log(f'''CHECK_SIZE: This is the sizes
{'':8s}CHECK_SIZE: SBR = {len(sbr[0])}
{'':8s}CHECK_SIZE: limits = {len(sbr_ring_limits)}
{'':8s}CHECK_SIZE: No. Rings  = {Configuration['NO_RINGS']}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
    if len(sbr[0]) != len(sbr_ring_limits):
        #Check what the appropriate size should be
        if debug and not fix_rc:
            print_log(f'''CHECK_SIZE: Equalizing the sizes
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
        if len(sbr[0]) != Configuration['NO_RINGS']:
            if debug and not fix_rc:
                print_log(f'''CHECK_SIZE: Interpolating SBR
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
            old_radii = np.array(get_from_template(Tirific_Template, ['RADI'],debug=debug),dtype = float)
            for i in [0,1]:
                sbr[i] = np.interp(np.array(radii,dtype=float),np.array(old_radii[0],dtype=float),np.array(sbr[i],dtype=float))

    if debug and not fix_rc:
        print_log(f'''CHECK_SIZE: This after correcting.
{'':8s}CHECK_SIZE: SBR = {len(sbr[0])}
{'':8s}CHECK_SIZE: limits = {len(sbr_ring_limits)}
{'':8s}CHECK_SIZE: No. Rings  = {Configuration['NO_RINGS']}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
    #sbr_ring_limits = 1.25*np.array([sbr_ring_limits,sbr_ring_limits])
    sbr_ring_limits = np.array([sbr_ring_limits,sbr_ring_limits])
    #if debug:
    #    print_log(f'''CHECK_SIZE: We have {sbr_ring_limits.size} values in limits and  {sbr.size} in sbr.
#{'':8s}CHECK_SIZE: It should be {Configuration['NO_RINGS']}
#''',Configuration['OUTPUTLOG'], screen = True, debug = debug)

    new_rings = Configuration['NO_RINGS']
    difference_with_limit = np.array(sbr-sbr_ring_limits)
    # if all of the last points are  below the limit we start checking how far to cut
    if np.all(difference_with_limit[:,-1] < 0.):
        if debug and not fix_rc:
            print_log(f'''CHECK_SIZE: both last rings are below the limit
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
        for i in range(len(difference_with_limit[0,:])-1,int(new_rings/2.),-1):
            if debug and not fix_rc:
                print_log(f'''CHECK_SIZE: Checking ring {i}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
            if np.all(difference_with_limit[:,i] < 0.):
                #check that 1 any of the lesser rings are bright enough
                if np.any(sbr[:,i-1] > 1.5 *sbr_ring_limits[:,i-1]):
                    new_rings = i+1
                    if debug and not fix_rc:
                        print_log(f'''CHECK_SIZE: we find that the previous rings are bright enough, rings = {new_rings}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
                    break
                else:
                    if debug and not fix_rc:
                        print_log(f'''CHECK_SIZE: the previous rings are not bright enough so we reduce 1, old_rings = {new_rings}, new_rings = {i}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
                    new_rings = i
            else:
                #if not both values are below than this is the extend we want
                new_rings = i+1
                if debug and not fix_rc:
                        print_log(f'''CHECK_SIZE: Not both rings warrant cutting, rings = {new_rings}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
                break
    else:
        if debug and not fix_rc:
            print_log(f'''CHECK_SIZE: Not both last rings are below the limit
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
        # if they are not we first check wether both second to last rings are
        if ((difference_with_limit[0,-2] < 0.) and (sbr[0,-1] < 2*sbr_ring_limits[0,-1]) and (difference_with_limit[1,-1] < 0.)) or \
            ((difference_with_limit[1,-2] < 0.) and (sbr[1,-1] < 2*sbr_ring_limits[1,-1]) and (difference_with_limit[0,-1] < 0.)) or\
            ((difference_with_limit[0,-2] < 0.) and (difference_with_limit[1,-2] < 0.) and (sbr[0,-1] < 3*sbr_ring_limits[0,-1]) and (sbr[1,-1] < 3*sbr_ring_limits[1,-1])):
            new_rings -= 1
            if debug and not fix_rc:
                print_log(f'''CHECK_SIZE: A second ring is too faint, rings = {new_rings}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
        elif np.all(difference_with_limit[:,-2] < 0.) and np.all(sbr[:,-1] < 5*sbr_ring_limits[:,-1]):
            new_rings -= 1
            if debug and not fix_rc:
                print_log(f'''CHECK_SIZE: Both second rings are too faint, rings = {new_rings}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
        else:
            if debug and not fix_rc:
                print_log(f'''CHECK_SIZE: The second rings are too bright and do not allow for cutting.
''',Configuration['OUTPUTLOG'],debug=False,screen=True)
    if fix_rc:
        if new_rings == Configuration['NO_RINGS']:
            new_rings -= 1
        return new_rings-1

    #if we haven't subtracted we check if we should add
    if new_rings == Configuration['NO_RINGS']:
        if (np.any(sbr[:,-2] > sbr_ring_limits[:,-2]*7.) and np.any(sbr[:,-1] > sbr_ring_limits[:,-1]*3.)) or \
            np.any(sbr[:,-1] > sbr_ring_limits[:,-1]*5.):
            if debug and not fix_rc:
                print_log(f'''CHECK_SIZE: The last rings were found to be:
{'':8s}{sbr[:,-2:]}
{'':8s}and the limits:
{'':8s}{sbr_ring_limits[:,-2:]}
{'':8s}Thus we add a ring.
''', Configuration['OUTPUTLOG'],debug=False)
            new_rings += 1
        else:
            if debug and not fix_rc:
                print_log(f'''CHECK_SIZE: The last rings were found to be:
{'':8s}{sbr[:,-2:]}
{'':8s}and the limits:
{'':8s}{sbr_ring_limits[:,-2:]}
{'':8s}Thus we keep the ring size.
''', Configuration['OUTPUTLOG'],debug=False)
    else:
        if debug and not fix_rc:
            print_log(f'''CHECK_SIZE: The last rings were found to be:
{'':8s}{sbr[:,-2:]}
{'':8s}and the limits:
{'':8s}{sbr_ring_limits[:,-2:]}
{'':8s}Thus we have subtracted a set of rings.
''', Configuration['OUTPUTLOG'],debug=False)

    if new_rings <= Configuration['NO_RINGS']:
        size_in_beams = (radii[new_rings-1]-1./5.*Configuration['BMMAJ'])/Configuration['BMMAJ']
    else:
        size_in_beams = (radii[-1]-1./5.*Configuration['BMMAJ'])/Configuration['BMMAJ']+Configuration['RING_SIZE']
    size_in_beams = set_limits(size_in_beams, Configuration['MIN_SIZE_IN_BEAMS'], Configuration['MAX_SIZE_IN_BEAMS'])
    # limit between 3 and the maximum allowed from the sofia estimate
    size_in_beams,ring_size = set_ring_size(Configuration, size_in_beams=size_in_beams,debug=debug)
    print_log(f'''CHECK_SIZE: We find the following size in beams {size_in_beams} with size {ring_size}.
{'':8s}CHECK_SIZE: The previous iteration had {Configuration['SIZE_IN_BEAMS']} rings with size  {Configuration['RING_SIZE']} .
{'':8s}CHECK_SIZE: This results in {new_rings} rings in the model compared to {Configuration['NO_RINGS']} previously.
''', Configuration['OUTPUTLOG'],debug=False)
    if float(ring_size) != float(Configuration['RING_SIZE']):
        Configuration['NEW_RING_SIZE'] = True
    else:
        Configuration['NEW_RING_SIZE'] = False
    if debug:
        print_log(f'''CHECK_SIZE: The previous rings were {Configuration['OLD_RINGS']}
''',Configuration['OUTPUTLOG'],debug=False,screen=True)

    if f"{size_in_beams:.1f}" == Configuration['OLD_RINGS'][-1]:
        return True
    elif f"{size_in_beams:.1f}" in Configuration['OLD_RINGS']:
        print_log(f'''CHECK_SIZE: We have processed this size before.
''', Configuration['OUTPUTLOG'],debug=False)
        ind = Configuration['OLD_RINGS'].index(f"{size_in_beams:.1f}")
        if Configuration['OLD_RINGS'][ind+1] > Configuration['OLD_RINGS'][ind]:
            print_log(f'''CHECK_SIZE: After which we increased the size.
''', Configuration['OUTPUTLOG'],debug=False)
            if Configuration['OLD_RINGS'][ind+1] == Configuration['OLD_RINGS'][-1]:
                print_log(f'''CHECK_SIZE: Which is the current fit so that's ok.
''', Configuration['OUTPUTLOG'],debug=False)
                return True
            else:
                print_log(f'''CHECK_SIZE: Which is not the current fit so we refit this size.
''', Configuration['OUTPUTLOG'])
            Configuration['OLD_RINGS'].append(f"{size_in_beams:.1f}")
        else:
            print_log(f'''CHECK_SIZE: After which we decreased so we allow this addition. But no more.
''', Configuration['OUTPUTLOG'])
            Configuration['OLD_RINGS'].append(f"{size_in_beams:.1f}")
    else:
        if debug:
            print_log(f'''CHECK_SIZE: Adding the new ring size to OLD_RINGS.
''', Configuration['OUTPUTLOG'])
        Configuration['OLD_RINGS'].append(f"{size_in_beams:.1f}")

    Configuration['RING_SIZE'] = ring_size
    Configuration['SIZE_IN_BEAMS'] = size_in_beams
    Configuration['NO_RINGS'] = calc_rings(Configuration,debug=debug)
    print_log(f'''CHECK_SIZE: We Need to modify the number of rings in the model.
''', Configuration['OUTPUTLOG'])

    if Fits_Files == 'No Files':
        raise InitializeError('CHECK_SIZE: Trying to adapt the model size but the fits files were not provided.')
    else:
        # Do not move this from here else other routines such as sbr_limits are messed up
        set_new_size(Configuration,Tirific_Template,Fits_Files,fit_stage= fit_stage, stage = stage, hdr=hdr ,debug = debug,current_run = current_run)
    return False
check_size.__doc__ = '''
;+
; NAME:
;       check_size(Configuration,Tirific_Template)
;
; PURPOSE:
;       This routine compares the SBR profiles and decides what the new number of ring should be
;
; CATEGORY:
;       Support
;
; CALLING SEQUENCE:
;
;
;
; INPUTS:
;       SBR1in = The sbr profile of the approaching side
;       SBR2in = The sbr profile of the receding side
;       cutoffin = Array with the cutoff values
;
; OPTIONAL INPUTS:
;       -
;
; KEYWORD PARAMETERS:
;       /INDIVIDUAL - Set this keyword to get an independent ring for
;                     each sides.
;       /DEBUG      - Set this keyword to get printed output during
;                     the running
;
; OUTPUTS:
;       newrings = the new amount of rings. a 2D array when
;       /INDIVIDUAL is set
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       MAX(), FLOOR()

'''

def fix_profile(Configuration, key, profile, Tirific_Template, hdr, debug= False, singular = False,only_inner = False ):
    if debug:
        print_log(f'''FIX_PROFILE: Starting to fix {key} with the input values:
{'':8s}{profile}
''', Configuration['OUTPUTLOG'],debug=True)

    if key == 'SBR':
        print_log(f'''FIX_PROFILE: To fix sbr profiles use check SBR.
''', Configuration['OUTPUTLOG'],screen=True, debug=True)
        exit()
    if singular:
        indexes = [0]
        profile = [profile,profile]
    else:
        indexes = [0,1]
    profile = np.array(profile)



    if key in ['SDIS']:
        inner_mean = np.nanmean(profile[indexes,:3])
        profile[indexes,:3] = inner_mean
    elif key in ['VROT']:
        indexes = [0]
        inner_mean = 0.
    else:
        inner_mean = np.nanmean(profile[indexes,:Configuration['INNER_FIX']])
        profile[indexes,:Configuration['INNER_FIX']] = inner_mean
        if debug:
            print_log(f'''FIX_PROFILE: the  {Configuration['INNER_FIX']} inner rings are fixed for the profile:
''', Configuration['OUTPUTLOG'])


    for i in indexes:
        if Configuration['LAST_RELIABLE_RINGS'][i] < len(profile[i,:]) and not only_inner:
            if debug:
                print_log(f'''FIX_PROFILE: From ring {Configuration['LAST_RELIABLE_RINGS'][i]} on we do not trust these rings.
''', Configuration['OUTPUTLOG'])
            #profile[i,Configuration['LAST_RELIABLE_RINGS'][i]:] = profile[i,Configuration['LAST_RELIABLE_RINGS'][i]:]*0.25+profile[i,Configuration['LAST_RELIABLE_RINGS'][i]-1]*0.75
            profile[i,Configuration['LAST_RELIABLE_RINGS'][i]:] = profile[i,Configuration['LAST_RELIABLE_RINGS'][i]-1]

        if key == 'VROT':
            profile[i] =fix_outer_rotation(Configuration,profile[i], Tirific_Template, hdr,debug= debug)
        if key in ['PA','INCL','Z0']:
            xrange = set_limits((int(round(len(profile[0])-5.)/4.)),1,4)
        # need to make sure this connects smoothly
            for x in range(1,xrange):
                if Configuration['INNER_FIX']+x < len(profile[i,:]):
                    profile[i,Configuration['INNER_FIX']+x] = 1/(x+0.5)*inner_mean+ (1-1/(x+0.5))*profile[i,Configuration['INNER_FIX']+x]

        #profile[:,:Configuration['INNER_FIX']] = np.nanmean(profile[:,:Configuration['INNER_FIX']])
        if key in ['SDIS']:
            profile[i] =np.hstack([[profile[i,0]],[y if y <= x else x*0.95 for x,y in zip(profile[i,:],profile[i,1:])]])
    if key == 'VROT':
        tmp  = no_declining_vrot(Configuration,Tirific_Template,profile = profile[0],debug=debug)
        profile[0] = tmp
        profile[1] = tmp
    if singular:
        profile = profile[0]


    if debug:
        print_log(f'''FIX_PROFILE: The final profile for {key} is:
{'':8s}{profile}
''', Configuration['OUTPUTLOG'])
    return profile


def get_warp_slope(Configuration,Tirific_Template,hdr, debug = False):
    if debug:
        print_log(f'''GET_WARP_SLOPE: We have {Tirific_Template['NUR']} rings in the template. and this should be {Configuration['NO_RINGS']}
''', Configuration['OUTPUTLOG'],debug = debug, screen =True)
    radii, sbr_ring_limits = sbr_limits(Configuration,hdr,systemic = float(Tirific_Template['VSYS'].split()[0]),debug=debug)
    #get the sbr profiles
    sbr = np.array(get_from_template(Tirific_Template, ['SBR','SBR_2'],debug=debug),dtype = float)
    if debug:
        print_log(f'''GET_WARP_SLOPE: We have {len(sbr_ring_limits)} rings in our limits.
{'':8s}GET_WARP_SLOPE: And we have {len(sbr[0])} rings in our profiles.
''', Configuration['OUTPUTLOG'], debug = False, screen =True)
    warp_slope = [Tirific_Template['NUR'],Tirific_Template['NUR']]
    sbr_ring_limits = 1.5*np.array([sbr_ring_limits,sbr_ring_limits])
    difference_with_limit = np.array(sbr-sbr_ring_limits)
    for i in [0,1]:
        slope = difference_with_limit[i]
        final = slope[slope < 0.]
        if len(final) > 0.:
            not_found = True
            counter = len(slope)-1
            while not_found:
                if not slope[counter] < 0.:
                    not_found = False
                    final = counter+1
                else:
                    counter -= 1
        else:
            final = len(slope)
        if final > Configuration['LAST_RELIABLE_RINGS'][i]:
            final = Configuration['LAST_RELIABLE_RINGS'][i]
        warp_slope[i] = final
    if debug:
        print_log(f'''GET_WARP_SLOPE: We find a slope of {warp_slope}.
''', Configuration['OUTPUTLOG'], debug = False, screen =True)
    return warp_slope
get_warp_slope.__doc__ = '''
;+
; NAME:
;       get_warp_slope(Configuration,Tirific_Template,hdr, debug = False):
;
; PURPOSE:
;       This routine compares the SBR profiles and decides at what stage they are too low and the warp should be fitted with a slope
;
; CATEGORY:
;       Support
;
; CALLING SEQUENCE:
;
;
;
; INPUTS:
;       SBR1in = The sbr profile of the approaching side
;       SBR2in = The sbr profile of the receding side
;       cutoffin = Array with the cutoff values
;
; OPTIONAL INPUTS:
;       -
;
; KEYWORD PARAMETERS:
;       /INDIVIDUAL - Set this keyword to get an independent ring for
;                     each sides.
;       /DEBUG      - Set this keyword to get printed output during
;                     the running
;
; OUTPUTS:
;       newrings = the new amount of rings. a 2D array when
;       /INDIVIDUAL is set
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;       MAX(), FLOOR()

'''


def regularise_profile(Configuration,Tirific_Template, key ,hdr,min_error= [0.],debug = False, no_apply =False):
    # We start by getting an estimate for the errors
    min_error=np.array(min_error)
    profile = np.array(get_from_template(Tirific_Template, [key,f"{key}_2"]),dtype=float)
    weights = get_ring_weights(Configuration,hdr,Tirific_Template,debug=debug)


    #First if we have an RC we flatten the curve
    if debug:
        print_log(f'''REGULARISE_PROFILE: profile of {key} before regularistion
{'':8s}{profile[0]}
{'':8s}{profile[1]}
{'':8s}The minmal error is
{'':8s}{min_error}
''',Configuration['OUTPUTLOG'],screen=True,debug = True)
    # get a smoothed profiles
    sm_profile = smooth_profile(Configuration,Tirific_Template, key,hdr ,min_error=min_error,debug=debug,no_apply=True)

    error = get_error(Configuration,profile,sm_profile,min_error=min_error,weights = weights,debug=debug)

    #Check that we have two profiles
    diff = np.sum(profile[0]-profile[1])
    if key in ['SDIS','VROT']:
        diff = False
    if diff:
        if debug:
            print_log(f'''REGULARISE_PROFILE: Treating both sides independently.
''',Configuration['OUTPUTLOG'],debug = False)
        sides = [0,1]
    else:
        if debug:
            print_log(f'''REGULARISE_PROFILE: Found symmetric profiles.
''',Configuration['OUTPUTLOG'],debug = False)
        sides = [0]
    radii =set_rings(Configuration,debug=debug)
    for i in sides:

        if key == 'SDIS':
            try:
                fit_profile = fit_arc(Configuration,radii,profile[i],sm_profile[i],error[i],min_error=min_error,debug= debug)
            except:
                fit_profile = np.full(len(sm_profile[i]), np.mean(sm_profile[i]))
                #fit_err = get_error(Configuration,sm_profile[i],fit_profile,min_error=min_error,debug=debug,singular = True)

        else:
            fit_profile = fit_polynomial(Configuration,radii,profile[i],sm_profile[i],error[i],key, Tirific_Template, hdr,min_error=min_error,debug= debug)
        profile[i] = fit_profile

    if not diff:
        profile[1] = profile[0]

    original = np.array(get_from_template(Tirific_Template, [key,f"{key}_2"]),dtype=float)
    error = get_error(Configuration,original,profile,weights=weights,key=key,apply_max_error = True,min_error=min_error,debug=debug)
    if debug:
            print_log(f'''REGULARISE_PROFILE: This the fitted profile without corrections:
{'':8s}{profile}
''',Configuration['OUTPUTLOG'],debug = False)
#then we want to fit the profiles with a polynomial
    if key not in ['SBR','VROT']:
        #We should not fix the profile again as the fitted profile is fixed should be good
        #profile = fix_profile(Configuration, key, profile, Tirific_Template, hdr,only_inner = True, debug=debug)
        #original = np.array(get_from_template(Tirific_Template, [key,f"{key}_2"]),dtype=float)
        profile,error = modify_flat(Configuration, profile, original, error,key,debug=debug)
        #error = get_error(Configuration, original, profile,weightsmin_error=error,debug=debug)
        #for i in [0,1]:
        #    if Configuration['LAST_RELIABLE_RINGS'][i] < len(profile[i,:]):
        #        if debug:
        #            print_log(f'''REGULARISE_PROFILE: From ring {Configuration['LAST_RELIABLE_RINGS'][i]} on  the rings were reset so we use {max_error[key]} as the error.
#''', Configuration['OUTPUTLOG'])
#                for j in range(Configuration['LAST_RELIABLE_RINGS'][i], len(profile[i,:])):
#                    error[i,j] = np.nanmin([max_error[key],error[i,j]])

    format = set_format(key)

    if not no_apply:
        Tirific_Template[key]= f"{' '.join([f'{x:{format}}' for x in profile[0,:int(Configuration['NO_RINGS'])]])}"
        Tirific_Template[f"{key}_2"]= f"{' '.join([f'{x:{format}}' for x in profile[1,:int(Configuration['NO_RINGS'])]])}"
        Tirific_Template.insert(key,f"# {key}_ERR",f"{' '.join([f'{x:{format}}' for x in error[0,:int(Configuration['NO_RINGS'])]])}")
        Tirific_Template.insert(f"{key}_2",f"# {key}_2_ERR",f"{' '.join([f'{x:{format}}' for x in error[1,:int(Configuration['NO_RINGS'])]])}")

        if debug:
            print_log(f'''REGULARISE_PROFILE: And this has gone to the template.
{'':8s}{key} = {Tirific_Template[key]}
{'':8s}{key}_2 ={Tirific_Template[f"{key}_2"]}
{'':8s}# {key}_ERR ={Tirific_Template[f"# {key}_ERR"]}
{'':8s}# {key}_2_ERR ={Tirific_Template[f"# {key}_2_ERR"]}
''',Configuration['OUTPUTLOG'],screen=True,debug = True)
    return profile


def get_error(Configuration,profile,sm_profile,min_error = [0.],singular = False,weights= [1.],\
                apply_max_error = False, key = 'UNSET'  ,debug=False):

    try:
        size= len(min_error)
        min_error = np.array(min_error)
    except TypeError:
        min_error = np.array([min_error])

    if debug:
        print_log(f'''GET_ERROR: starting;
{'':8s}original profile = {profile}
{'':8s}new profile = {sm_profile}
{'':8s}weights = {weights}
{'':8s}singular = {singular}
{'':8s}min_error = {min_error}
{'':8s}max_error = {apply_max_error}
''',Configuration['OUTPUTLOG'],screen=True,debug = True)



    if singular:
        if len(weights) == 1:
            weights = np.full((len(profile)),weights[0])
        profile = [profile]
        sm_profile = [sm_profile]
        error =[[]]
        sides = [0]

    else:
        error = [[],[]]
        if len(weights) == 1:
            weights = np.full((len(profile[0]),len(profile[1])),1.)
        sides =[0,1]
    if debug:
        print_log(f'''GET_ERROR: using these weights =
{'':8s}{weights}
''',Configuration['OUTPUTLOG'],screen=True,debug = False)
    for i in sides:
        error[i] = abs(profile[i]-sm_profile[i])
        if len(min_error.shape) == 2:
            error[i] = [np.max([y,x]) for x,y in zip(error[i],min_error[i])]
        elif len(min_error) == len(error[i]):
            error[i] = [np.max([y,x]) for x,y in zip(error[i],min_error)]
        else:
            error[i] = [np.max([x,min_error[0]]) for x in error[i]]
        error[i]=error[i]/weights[i]
        if apply_max_error:
                error[i] = [np.nanmin([x,Configuration['MAX_ERROR'][key]]) for x in error[i]]

    if singular:
        error = np.array(error[0],dtype=float)
    else:
        error = np.array(error,dtype=float)
    if debug:
        print_log(f'''GET_ERROR: error =
{'':8s}{error}
''',Configuration['OUTPUTLOG'],screen=True,debug = False)
    return error

def fix_outer_rotation(Configuration,profile, Tirific_Template,hdr, debug = False):
    if debug:
        print_log(f'''FIX_OUTER_ROTATION: adjust last rings of VROT profile:
{'':8s}{profile}
''',Configuration['OUTPUTLOG'],screen=True,debug = True)
    profile = np.array(profile,dtype=float)
    inner_slope = check_size(Configuration,Tirific_Template,hdr, debug= debug, fix_rc = True)
    if debug:
        print_log(f'''FIX_OUTER_ROTATION: this is the inner slope {inner_slope}
''',Configuration['OUTPUTLOG'],debug = False)
    NUR = Configuration['NO_RINGS']
    #inner_slope = int(round(set_limits(NUR*(4.-Configuration['LIMIT_MODIFIER'][0])/4.,round(NUR/2.),NUR-2)))
    if inner_slope != NUR-1 and np.mean(profile[1:3]) > 180.:
        profile[inner_slope:] = profile[inner_slope-1]
    # For galaxies with more than 10 rings let's make sure the last quarter is not declinining steeply
    if Configuration['NO_RINGS'] > 10:
        for i in range(int(Configuration['NO_RINGS']*3./4),Configuration['NO_RINGS']-1):
            if profile[i+1] < profile[i]*0.8:
                profile[i+1] = profile[i]*0.8
    if debug:
        print_log(f'''FIX_OUTER_ROTATION: this is corrected profile:
{profile}
''',Configuration['OUTPUTLOG'],debug = False)

    return profile


def no_declining_vrot(Configuration, Tirific_Template, profile = None, debug = False):


    if debug:
        print_log(f'''NO_DECLINING_VROT: make RC flat from highest point on.
{'':8s}NO_DECLINING_VROT: But only for low value RCs
''',Configuration['OUTPUTLOG'],screen=True,debug = True)
    no_input = False
    if profile is None:
        no_input = True
        profile = np.array(get_from_template(Tirific_Template,['VROT'], debug = debug)[0],dtype = float)

    RCval = np.mean(profile[2:])
    RCmax = np.where(profile == np.max(profile))[0]
    if len(RCmax) > 1:
        RCmax = RCmax[0]
    if debug:
            print_log(f'''NO_DECLINING_VROT: We find the maximum at ring {RCmax}
{'':8s}NO_DECLINING_VROT: And a mean value of {RCval}.
''',Configuration['OUTPUTLOG'],debug = False)
    Configuration['OUTER_SLOPE_START'] = Configuration['NO_RINGS']-1
    if RCmax < len(profile)/2. or RCval > 180.:
        if debug:
            print_log(f'''NO_DECLINING_VROT: We shan't adapt the RC
''',Configuration['OUTPUTLOG'],debug = False)
    else:
        for i in range(len(profile)-1):
            if profile[i+1] < profile[i]:
                profile[i:] =profile[i]
                if debug:
                    print_log(f'''NO_DECLINING_VROT: Flattening from ring {i} on.)
    ''',Configuration['OUTPUTLOG'],debug = False)
                Configuration['OUTER_SLOPE_START'] = i+2
                break
    if Configuration['OUTER_SLOPE_START'] > Configuration['NO_RINGS']:
        Configuration['OUTER_SLOPE_START'] = Configuration['NO_RINGS']
    format = set_format('VROT')
    if no_input:
        Tirific_Template['VROT'] = f"{' '.join([f'{x:{format}}' for x in profile])}"
        Tirific_Template['VROT_2'] = f"{' '.join([f'{x:{format}}' for x in profile])}"
    else:
        return profile

def check_flat(Configuration,profile,error, debug = False):
    if debug:
        print_log(f'''CHECK_FLAT: checking flatness)
{'':8s}profile = {profile}
{'':8s}error = {error}
''',Configuration['OUTPUTLOG'],debug = True)
    flat = True
    for e,x,y in zip(error[1:],profile[1:],profile[0:]):
        if not x-e < y < x+e:
            flat = False
            break
    if debug:
        print_log(f'''CHECK_FLAT: profile is flat is {flat}.
''',Configuration['OUTPUTLOG'],debug = False)
    return flat
check_flat.__doc__ = '''
;+
; NAME:
;       check_flat(profile,error)
;
; PURPOSE:
;       Check whether within its errors a routine is varying compared to the prvious rings
;
; CATEGORY:
;       modify_template
;
; CALLING SEQUENCE:
;
; INPUTS:
;       profile = the profile to examine
;       error = The accompanying error
; OPTIONAL INPUTS:
;       -
;
; KEYWORD PARAMETERS:
;       /DEBUG      - Set this keyword to get printed output during
;                     the running
;
; OUTPUTS:
;       True if no variation is found false if variation is found
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;      zip()

'''
def arc_tan_function(axis,center,length,amplitude,mean):
    # to prevent instant turnover
    c = axis[-1]*0.1
    #and the turnover has to be beyon 20*of the inner part
    c2 = set_limits(axis[-1]*0.2,axis[2],axis[int(len(axis)/2.)])
    return -1*np.arctan((axis+(c2+abs(center)))/(c+abs(length)))/np.pi*amplitude + mean


def fit_arc(Configuration,radii,profile,sm_profile,error,min_error = 0. ,fixed = 0, debug = False ):
    est_center = radii[-1]/2.
    est_length = radii[-1]*0.2
    est_amp = abs(np.max(sm_profile)-np.min(sm_profile))
    est_mean = np.mean(sm_profile)
    arc_par,arc_cov  =  curve_fit(arc_tan_function, radii, sm_profile,p0=[est_center,est_length,est_amp,est_mean])
    new_profile = arc_tan_function(radii,*arc_par)
    new_profile[:3] = np.mean(new_profile[:3])
    #new_error = get_error(Configuration,profile,new_profile,min_error=min_error,debug=debug, singular = True)
    return new_profile#,new_error
fit_arc.__doc__ = '''
;+
; NAME:
;       fit_arc(Configuration,radii,profile,sm_profile,error, fixed = 0 ):
;
; PURPOSE:
;       Fit an arc tangent function between 3 and 8 order and determine the one with the optimal red chi square
;
; CATEGORY:
;       modify_template
;
; CALLING SEQUENCE:
;
; INPUTS:
;       profile = the unsmoothed profile to examine
;
;       error = The accompanying error
; OPTIONAL INPUTS:
;       -
;
; KEYWORD PARAMETERS:
;       /DEBUG      - Set this keyword to get printed output during
;                     the running
;
; OUTPUTS:
;       True if no variation is found false if variation is found
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;      zip()

'''

def fit_polynomial(Configuration,radii,profile,sm_profile,error, key, Tirific_Template, hdr,min_error =0., debug = False ):
    if debug:
        print_log(f'''FIT_POLYNOMIAL: starting to fit the polynomial with the following input:
{'':8s} key = {key}
{'':8s} radii = {radii}
{'':8s} profile = {profile}
{'':8s} sm_profile = {sm_profile}
{'':8s} error = {error}
''',Configuration['OUTPUTLOG'],screen =True, debug=debug)
    only_inner = False
    if key in ['PA','INCL','Z0']:
        fixed = Configuration['INNER_FIX']
        only_inner =True
        error[:fixed] = error[:fixed]/10.
    elif key in ['VROT']:
        fixed =len(radii)-Configuration['OUTER_SLOPE_START']
    else:
        fixed = 1
    if len(radii) > 15.:
        start_order = int(len(radii)/5)
    else:
        start_order = 0

    st_fit = int(0)
    if key in ['VROT']:
        st_fit = int(1)
        #This needs another -1 because the 0 and 1/5. ring are more or less 1 ring
        max_order = set_limits(len(radii)-fixed-2,3,8)
        #The rotation curve varies a lot so the lower limit should be as high as possible
        #But at least 3 less than max order and maximally 4
        if len(radii)-fixed-2 <= 6:
            lower_limit=set_limits(3,3,max_order-2)
        elif len(radii)-fixed-2 <= 10:
            lower_limit=set_limits(4,3,max_order-2)
        else:
            lower_limit=set_limits(5,3,max_order-2)
        start_order = set_limits(start_order,lower_limit,max_order)

    else:
        max_order = set_limits(len(radii)-fixed-1,3,7)

    if start_order >= max_order:
        max_order = max_order+1

    print_log(f'''FIT_POLYNOMIAL: For {key} we start at {start_order} because we have {len(radii)} rings of which {fixed} are fixed
{'':8s} this gves us a maximum order of {max_order}
''',Configuration['OUTPUTLOG'],screen =True, debug=False)

    reduced_chi = []
    order = range(start_order,max_order)
    if debug:
        print_log(f'''FIT_POLYNOMIAL: We will fit the following radii.
{'':8s}{radii[st_fit:]}
{'':8s} and the following profile:
{'':8s}{sm_profile[st_fit:]}''',Configuration['OUTPUTLOG'],screen =True, debug=False)
    for ord in order:
        fit_prof = np.poly1d(np.polyfit(radii[st_fit:],profile[st_fit:],ord,w=1./error[st_fit:]))
        if st_fit > 0.:
            fit_profile = np.concatenate(([sm_profile[0]],[e for e in fit_prof(radii[st_fit:])]))
        else:
            fit_profile = fit_prof(radii)
        #fit_profile = fit_prof(radii)
        fit_profile = fix_profile(Configuration, key, fit_profile, Tirific_Template, hdr, singular = True,only_inner =only_inner)
        red_chi = np.sum((profile[st_fit:]-fit_profile[st_fit:])**2/error[st_fit:])/(len(radii[st_fit:])-ord)
        reduced_chi.append(red_chi)
    reduced_chi = np.array(reduced_chi,dtype = float)
    final_order = order[np.where(np.min(reduced_chi ) == reduced_chi )[0][0]]
    if debug:
            print_log(f'''FIT_POLYNOMIAL: find {final_order} as the polynomial order to regularise {key}
''',Configuration['OUTPUTLOG'],screen =True, debug=False)
    fit_profile = np.poly1d(np.polyfit(radii[st_fit:],profile[st_fit:],final_order,w=1./error[st_fit:]))
    if st_fit > 0.:
        new_profile = np.concatenate(([sm_profile[0]],[e for e in fit_profile(radii[st_fit:])]))
    else:
        new_profile = fit_profile(radii)
    #if key in ['VROT'] and profile[1] < profile[2]:
    #    new_profile[1] = profile[1]
    new_profile = fix_profile(Configuration, key, new_profile, Tirific_Template, hdr,debug =debug, singular = True,only_inner =only_inner)
    #new_error = get_error(Configuration, profile, new_profile,min_error=min_error,singular = True,debug = debug)

    return new_profile#,new_error
fit_polynomial.__doc__ = '''
;+
; NAME:
;       fit_polynomial(Configuration,radii,profile,sm_profile,error, fixed = 0 ):
;
; PURPOSE:
;       Fit a polynomial between 3 and 8 order and determine the one with the optimal red chi square
;
; CATEGORY:
;       modify_template
;
; CALLING SEQUENCE:
;
; INPUTS:
;       profile = the unsmoothed profile to examine
;
;       error = The accompanying error
; OPTIONAL INPUTS:
;       -
;
; KEYWORD PARAMETERS:
;       /DEBUG      - Set this keyword to get printed output during
;                     the running
;
; OUTPUTS:
;       True if no variation is found false if variation is found
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;      zip()

'''
def flatten_the_curve(Configuration,Tirific_Template,debug = False):
    to_flatten = ['INCL','Z0','PA','SDIS']
    for key in to_flatten:
        profile = get_from_template(Tirific_Template, [key,f'{key}_2'] ,debug=debug)
        new_profile = [np.mean(profile) for x in profile[0]]
        Tirific_Template[key] =f" {' '.join([f'{x:.2f}' for x in new_profile])}"
        Tirific_Template[f'{key}_2'] =f" {' '.join([f'{x:.2f}' for x in new_profile])}"

def set_cflux(Configuration,Tirific_Template,debug = False):

    if any(np.isnan(Configuration['NO_POINTSOURCES'])):
        print_log(f'''SET_CFLUX: We detected an infinite number of model point sources.
{"":8s}SET_CFLUX: This must be an error. Exiting the fitting.
''',Configuration['OUTPUTLOG'])
        raise CfluxError('The model had infinite point sources')
    if Configuration['SIZE_IN_BEAMS'] < 15:
        factor = 1.
    else:
        factor=(Configuration['SIZE_IN_BEAMS']/15.)**1.5
    triggered = 0
    if not 0.5e6 < Configuration['NO_POINTSOURCES'][0] < 2.2e6:
        new_cflux = set_limits(float(Tirific_Template['CFLUX'])*Configuration['NO_POINTSOURCES'][0]/(factor*1e6),1e-7,5e-3)
        print_log(f'''SET_CFLUX: CFLUX is adapted from {Tirific_Template['CFLUX']} to {new_cflux:.2e}
''',Configuration['OUTPUTLOG'])
        Tirific_Template['CFLUX'] = f"{new_cflux:.2e}"
        triggered = 1
    if not 0.5e6 < Configuration['NO_POINTSOURCES'][1] < 2.2e6:
        new_cflux = set_limits(float(Tirific_Template['CFLUX_2'])*Configuration['NO_POINTSOURCES'][1]/(factor*1e6),1e-7,5e-3)
        print_log(f'''SET_CFLUX: CFLUX_2 is adapted from {Tirific_Template['CFLUX_2']} to {new_cflux:.2e}
''',Configuration['OUTPUTLOG'])
        Tirific_Template['CFLUX_2'] = f"{new_cflux:.2e}"
        triggered = 1
    if not triggered:
        print_log(f'''SET_CFLUX: CFLUXES are within the required limits.
''',Configuration['OUTPUTLOG'])
set_cflux.__doc__ = '''
;+
; NAME:
;       set_cflux(Configuration,Tirific_Template,debug = False)
;
; PURPOSE:
;       Check CFLUX values and make sure they are in the right order for the amount of point sources
;
; CATEGORY:
;       modify_template
;
; CALLING SEQUENCE:
;
; INPUTS:
;      Configuration =
;      Tirific_Template =
;
; OPTIONAL INPUTS:
;       -
;
; KEYWORD PARAMETERS:
;       /DEBUG      - Set this keyword to get printed output during
;                     the running
;
; OUTPUTS:
;       No outputs if CLUX has to be changes it is changes in the Template
;
; OPTIONAL OUTPUTS:
;       -
;
; PROCEDURES CALLED:
;

'''
def set_errors(Configuration,Tirific_Template,key,min_error = 0.,debug = False):
    error = np.full((2,int(Configuration['NO_RINGS'])),min_error)
    format=set_format(key)
    Tirific_Template.insert(key,f"# {key}_ERR",f"{' '.join([f'{x:{format}}' for x in error[0,:int(Configuration['NO_RINGS'])]])}")
    Tirific_Template.insert(f"{key}_2",f"# {key}_2_ERR",f"{' '.join([f'{x:{format}}' for x in error[1,:int(Configuration['NO_RINGS'])]])}")
    if debug:
        print_log(f'''SET_ERRORS: This has gone to the template.
{'':8s}# {key}_ERR ={Tirific_Template[f"# {key}_ERR"]}
{'':8s}# {key}_2_ERR ={Tirific_Template[f"# {key}_2_ERR"]}
''',Configuration['OUTPUTLOG'],debug = True)

def set_fitting_parameters(Configuration, Tirific_Template, \
                           parameters_to_adjust  = ['NO_ADJUSTMENT'], modifiers = ['EMPTY'], \
                           hdr = None,stage = 'initial', initial_estimates = ['EMPTY'],debug = False):
    if debug:
        print_log(f'''SET_FITTING_PARAMETERS: We are starting with these modifiers.
{'':8s} {modifiers}
''',Configuration['OUTPUTLOG'],debug=True,screen = True)
    try:
        if modifiers[0] == 'EMPTY':
            modifiers = {}
    except KeyError:
        pass
    try:
        if initial_estimates[0] == 'EMPTY':
            initial_estimates = {}
    except KeyError:
        pass
    fitting_settings = {}
    fitting_keys = ['VARY','VARINDX','MODERATE','DELEND','DELSTART','MINDELTA','PARMAX','PARMIN']

    if 'INCL' not in initial_estimates:
        profile = np.array([np.mean([x,y]) for x,y in zip(get_from_template(Tirific_Template, ['INCL']),get_from_template(Tirific_Template, [f"INCL_2"]) )])
        diff = abs(np.max(profile)-np.min(profile))/10.
        initial_estimates['INCL'] = [profile[0],set_limits(diff,1,5)]

    if parameters_to_adjust[0] == 'NO_ADJUSTMENT':
        if stage in ['initial','run_cc','after_cc']:
            if initial_estimates['INCL'][0] < 30.:
                parameters_to_adjust = ['VSYS','SBR','XPOS','YPOS','PA','SDIS','INCL','VROT']
            elif initial_estimates['INCL'][0] < 50.:
                parameters_to_adjust = ['VSYS','XPOS','YPOS','SBR','PA','SDIS','VROT','INCL']
            elif initial_estimates['INCL'][0] > 75.:
                parameters_to_adjust = ['VSYS','XPOS','YPOS','VROT','SBR','PA','INCL','SDIS','Z0']
            else:
                parameters_to_adjust = ['VSYS','XPOS','YPOS','SBR','VROT','PA','INCL','SDIS']
        elif stage in ['initialize_ec','run_ec','after_ec']:
            parameters_to_adjust = ['INCL','PA','VROT','SDIS','SBR','Z0','XPOS','YPOS','VSYS']
        elif stage in  ['initialize_os','run_os','after_os']:
            parameters_to_adjust = ['VSYS','XPOS','YPOS','INCL','PA','SBR','VROT','SDIS','Z0']
        else:
            if debug:
                print_log(f'''SET_FITTING_PARAMETERS: No default adjustment for unknown stage.
''',Configuration['OUTPUTLOG'],debug=False,screen = True)
            raise InitializeError('No default adjustment for unknown stage. ')
    if 'XPOS' in parameters_to_adjust or 'YPOS' in parameters_to_adjust or 'VSYS' in parameters_to_adjust:
        range = {}
        if hdr:
            range['XPOS'] = np.sort([hdr['CRVAL1']-(hdr['CRPIX1']*hdr['CDELT1']),hdr['CRVAL1']+((hdr['NAXIS1']-hdr['CRPIX1'])*hdr['CDELT1']) ])
            range['YPOS'] = np.sort([hdr['CRVAL2']-(hdr['CRPIX2']*hdr['CDELT2']),hdr['CRVAL2']+((hdr['NAXIS2']-hdr['CRPIX2'])*hdr['CDELT2']) ])
            range['VSYS'] = np.sort([hdr['CRVAL3']-(hdr['CRPIX3']*hdr['CDELT3']),hdr['CRVAL3']+((hdr['NAXIS3']-hdr['CRPIX3'])*hdr['CDELT3']) ])/1000.
        else:
            range['XPOS'] = [0.,360.]
            range['YPOS'] = [-90.,90.]
            range['VSYS'] = [-100,15000.]

    for key in parameters_to_adjust:
        if key not in initial_estimates:
            profile = np.array([np.mean([x,y]) for x,y in zip(get_from_template(Tirific_Template, [key])[0],get_from_template(Tirific_Template, [f"{key}_2"])[0] )])
            diff = abs(np.max(profile)-np.min(profile))/10.
            if key == 'PA':
                initial_estimates['PA'] = [profile[0],set_limits(diff,0.5,10)]
            elif key == 'VROT':
                initial_estimates['VROT'] = [np.nanmax(profile),set_limits(np.nanstd(profile[1:]),np.nanmax(profile)-np.nanmin(profile[1:]),np.nanmax(profile))]
            elif key == 'XPOS':
                initial_estimates['XPOS'] = [profile[0],abs(hdr['CDELT1'])]
            elif key == 'YPOS':
                initial_estimates['YPOS'] = [profile[0],abs(hdr['CDELT2'])]
            elif key == 'VSYS':
                initial_estimates['VSYS'] = [profile[0],abs(hdr['CDELT3']/2000.)]
            elif key == 'SDIS':
                initial_estimates['SDIS'] = [np.mean(profile),abs(hdr['CDELT3']/1000.)]
            elif key == 'Z0':
                initial_estimates['Z0'] = convertskyangle([0.2,0.05],Configuration['DISTANCE'], physical = True)
        if key not in modifiers:
            if debug:
                print_log(f'''SET_FITTING_PARAMETERS: Adding {key} to the modifiers
''',Configuration['OUTPUTLOG'],screen =True)
            if key == 'Z0': modifiers['Z0'] = [0.5,0.5,2.]
            elif key in ['XPOS','YPOS']: modifiers[key] = [1.,1.,1.]
            elif key == 'VSYS': modifiers[key] = [3.,1.,1.]
            elif stage in  ['initial','run_cc','after_cc','after_ec','after_os']:
                if key == 'INCL': modifiers['INCL'] = [1.,1.,1.]
                elif key == 'PA': modifiers['PA'] = [1.,1.,1.]
                elif key == 'SDIS': modifiers['SDIS'] =  [1.,1.,2.]
            else:
                if key == 'INCL': modifiers['INCL'] = [2.0,0.5,0.5]
                elif key == 'PA': modifiers['PA'] =[1.0,1.0,2.0]
                elif key == 'SDIS': modifiers['SDIS'] =  [1.,1.,0.5]
    if debug:
        for key in modifiers:
            print_log(f'''SET_FITTING_PARAMETERS: This {key} is in modifiers
''',Configuration['OUTPUTLOG'],screen=True)
    if debug:
        print_log(f'''SET_FITTING_PARAMETERS: These are the inclination modifiers
{'':8s} {modifiers['INCL']}
''',Configuration['OUTPUTLOG'])
    if initial_estimates['INCL'][0] < 30.:
        modifiers['Z0'][0:1] = np.array(modifiers['Z0'][0:1],dtype=float)*(0.2/0.5)
        modifiers['Z0'][2] = float(modifiers['Z0'][2])*1.5
        modifiers['INCL'][0:1] =np.array(modifiers['INCL'][0:1],dtype=float)*(0.1/1.0)
        modifiers['INCL'][2] = float(modifiers['INCL'][2])*2.
        modifiers['SDIS'][0:1] = np.array(modifiers['SDIS'][0:1],dtype=float)*1.5
        modifiers['SDIS'][2] = float(modifiers['SDIS'][2])*0.5
        if debug:
            print_log(f'''SET_FITTING_PARAMETERS: These are the inclination modifiers after correcting < 30.
{'':8s} {modifiers['INCL']}
''',Configuration['OUTPUTLOG'])
    elif initial_estimates['INCL'][0] < 50.:
        modifiers['Z0'][0:1] = np.array(modifiers['Z0'][0:1],dtype=float)*(0.4/0.5)
        modifiers['Z0'][2] = float(modifiers['Z0'][2])*1.2
        modifiers['INCL'][0:1] =np.array( modifiers['INCL'][0:1],dtype=float)*(0.75/1.0)
        modifiers['INCL'][2] = float(modifiers['INCL'][2])*0.8
        if debug:
            print_log(f'''SET_FITTING_PARAMETERS: These are the inclination modifiers after correcting < 50.
{'':8s} {modifiers['INCL']}
''',Configuration['OUTPUTLOG'])
    elif initial_estimates['INCL'][0] > 75.:
        modifiers['Z0'][0:1] = np.array(modifiers['Z0'][0:1],dtype=float)*(1.25)
        modifiers['Z0'][2] = float(modifiers['Z0'][2])*0.5
        modifiers['INCL'][0:1] = np.array(modifiers['INCL'][0:1],dtype=float)*(1.5/1.0)
        modifiers['INCL'][2] = float(modifiers['INCL'][2])*0.25
        modifiers['SDIS'][0:1] = np.array(modifiers['SDIS'][0:1],dtype=float)*0.5
        modifiers['SDIS'][2] = float(modifiers['SDIS'][2])*1.5
        if debug:
            print_log(f'''SET_FITTING_PARAMETERS: These are the inclination modifiers after correcting > 75.
{'':8s} {modifiers['INCL']}
''',Configuration['OUTPUTLOG'])

    else:
        pass

    for key in parameters_to_adjust:
        if key == 'VROT':
            fitting_settings['VROT'] = set_vrot_fitting(Configuration,Tirific_Template, hdr = hdr,stage = stage, rotation = initial_estimates['VROT'], debug = debug )
        elif key == 'SBR':
            fitting_settings['SBR'] = set_sbr_fitting(Configuration, hdr = hdr,stage = stage, systemic = initial_estimates['VSYS'][0], debug = debug)
        else:
            if key == 'INCL':
                brackets = [[60.,90.],[5.,50.]]
                fixed =  Configuration['FIX_INCLINATION'][0]
            elif key == 'PA':
                brackets = [[190.,370.],[-10,170]]
                fixed =  Configuration['FIX_PA'][0]
            elif key == 'Z0':
                fixed =  Configuration['FIX_Z0'][0]
                brackets = [convertskyangle([0.2,2.5],Configuration['DISTANCE'], physical = True), \
                            convertskyangle([0.05,0.2],Configuration['DISTANCE'], physical = True)]
            elif key in ['XPOS','YPOS','VSYS']:
                fixed = True
                brackets = [range[key],range[key]]
            elif key == 'SDIS':
                fixed = Configuration['FIX_SDIS'][0]
                if stage in ['initial','run_cc','after_cc','after_ec','after_os']:
                    limits = [[Configuration['CHANNEL_WIDTH'], 15],\
                              [Configuration['CHANNEL_WIDTH']/4., 15.], \
                              [Configuration['CHANNEL_WIDTH']/4., 15.]]
                else:
                    limits = [[Configuration['CHANNEL_WIDTH'], initial_estimates['SDIS'][1]], \
                             [Configuration['CHANNEL_WIDTH']/4., initial_estimates['SDIS'][1]],\
                             [Configuration['CHANNEL_WIDTH']/4., initial_estimates['SDIS'][1]]]
            if key in ['PA','INCL','Z0']:
                slope = Configuration['WARP_SLOPE']
                inner =  Configuration['INNER_FIX']
            else:
                inner = 3
                slope = [0.,0.]

            if key != 'SDIS':
                limits = set_boundary_limits(Configuration,Tirific_Template,key, tolerance = 0.1, values = initial_estimates[key],\
                                upper_bracket = brackets[0],lower_bracket = brackets[1],fixed = fixed)
                flat_slope = False
            else:
                flat_slope = True

            fitting_settings[key] =  set_generic_fitting(Configuration,key,stage = stage, values = initial_estimates[key], debug = debug,\
                                                        limits=limits,slope= slope, flat_slope = flat_slope, fixed =fixed, flat_inner = inner, step_modifier = modifiers[key])

    # Reset the fitting parameters
    for fit_key in fitting_keys:
        Tirific_Template[fit_key]= ''
    #write the new parameters
    for key in parameters_to_adjust:
        if key in fitting_settings:
            for fit_key in fitting_keys:
                if  fit_key in fitting_settings[key]:

                    if fit_key in ['DELSTART','DELEND','MINDELTA']:
                    #if fit_key in ['DELEND','MINDELTA']:
                        # These should never be 0.
                        format = set_format(key)
                        for i,x in enumerate(fitting_settings[key][fit_key]):
                            while float(f'{fitting_settings[key][fit_key][i]:{format}}') == 0.:
                                if float(fitting_settings[key][fit_key][i]) == 0.:
                                    fitting_settings[key][fit_key][i] += 0.01
                                else:
                                    fitting_settings[key][fit_key][i] *= 2.

                    if fit_key == 'VARY':
                        if len(Tirific_Template[fit_key]) == 0:
                            Tirific_Template[fit_key] = ', '.join([f'{x:<10s}' for x in fitting_settings[key][fit_key]])
                        else:
                            Tirific_Template[fit_key] = f"{Tirific_Template[fit_key]}, {', '.join([f'{x:<10s}' for x in fitting_settings[key][fit_key]])}"
                    else:
                        if fit_key == 'VARINDX':
                            format = '<10s'
                        else:
                            format = set_format(key)
                        Tirific_Template[fit_key] = f"{Tirific_Template[fit_key]} {' '.join([f'{x:{format}}' for x in fitting_settings[key][fit_key]])}"
set_fitting_parameters.__doc__ = '''

    ; NAME:
    ;      set_fitting_parameters(Configuration, Tirific_Template, \
                               parameters_to_adjust  = ['NO_ADJUSTMENT'],
                               hdr = None,stage = 'initial',systemic = [100.,2], \
                               inclination = [60.,2.], pa = [90,1], \
                               rotation = [100.,5.],ra = [180,1e-4], dec= [0,1e-4]):
    ;
    ; PURPOSE:
    ;      Set the parameters that control the fitting in the Tirific template
    ;
    ; CATEGORY:
    ;       modify_template
    ;
    ;
    ; INPUTS:
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
    ;      split, strip, open
    ;
    ; EXAMPLE:
    ;
    ;
'''

def set_boundary_limits(Configuration,Tirific_Template,key, tolerance = 0.01, values = [10,1],\
                        upper_bracket = [10.,100.], lower_bracket=[0., 50.], fixed = False,increase=10., debug = False):
    profile = np.array(get_from_template(Tirific_Template, [key,f"{key}_2"]),dtype = float)
    if f"{key}_CURRENT_BOUNDARY" in Configuration:
        current_boundaries = Configuration[f"{key}_CURRENT_BOUNDARY"]
    else:
        current_boundaries =[[set_limits(values[0]-values[1]*5.,*lower_bracket),\
                    set_limits(values[0]+values[1]*5.,*upper_bracket)] for x in range(3)]
    if fixed:
        range_to_check = [0]
    else:
        range_to_check = [0,1,2]
    for i in range_to_check:
        buffer = float(current_boundaries[i][1]-current_boundaries[i][0]) * tolerance
        if i == 0:
            profile_part = profile[0,:Configuration['INNER_FIX']]
        else:
            profile_part = profile[i-1,Configuration['INNER_FIX']:]
        #check the upper bounderies
        on_boundary = np.where(profile_part > float(current_boundaries[i][1])-buffer)[0]
        if len(on_boundary) > 0:
            if on_boundary[0] != len(profile[0])-1:
                current_boundaries[i][1] = set_limits(current_boundaries[i][1] + buffer*increase,*upper_bracket)
        #check the lower boundaries.
        on_boundary = np.where(profile_part < float(current_boundaries[i][0])+buffer)[0]
        if len(on_boundary) > 0:
            if on_boundary[0] != len(profile[0])-1:
                current_boundaries[i][0] = set_limits(current_boundaries[i][1] - buffer*increase,*lower_bracket)
    Configuration[f"{key}_CURRENT_BOUNDARY"] = current_boundaries
    return current_boundaries

def set_generic_fitting(Configuration, key , stage = 'initial', values = [60,5.], \
                        limits = [[0.,0.],[0.,0.],[0.,0.]],debug = False, slope = [0, 0], flat_slope = False , symmetric = False,\
                        upper_bracket = [10.,100.], lower_bracket=[0., 50.], fixed = True, moderate = 3, step_modifier = [1.,1.,1.],\
                        flat_inner = 3):
    if debug:
            print_log(f'''SET_GENERIC_FITTING: We are processing {key}.
''', Configuration['OUTPUTLOG'], screen = True ,debug = debug)
    NUR = Configuration['NO_RINGS']
    if all(x == 0. for x in np.array(slope)):
        slope = [NUR,NUR]
    if all(x == 0. for x in np.array(limits).reshape(6)):
        if debug:
            print_log(f'''SET_GENERIC_FITTING: Implementing limits
''', Configuration['OUTPUTLOG'], screen = True ,debug = False)

        limits = [[set_limits(values[0]-values[1]*5.,*lower_bracket),\
                    set_limits(values[0]+values[1]*5.,*upper_bracket)] for x in limits]

        if debug:
            print_log(f'''SET_GENERIC_FITTING: set these limits {limits}
''', Configuration['OUTPUTLOG'], screen = True ,debug = False)

    input= {}
    if debug:
            print_log(f'''SET_GENERIC_FITTING: flat is {fixed}
''', Configuration['OUTPUTLOG'], screen = True ,debug = False)
    if (stage in ['after_os','after_cc','after_ec','parameterized']) or fixed:
        if debug:
            print_log(f'''SET_GENERIC_FITTING: Fitting all as 1.
''', Configuration['OUTPUTLOG'], screen = True ,debug = False)
        input['VARY'] =  np.array([f"{key} 1:{NUR} {key}_2 1:{NUR}"])
        input['PARMAX'] = np.array([limits[0][1]])
        input['PARMIN'] = np.array([limits[0][0]])
        input['MODERATE'] = np.array([moderate]) #How many steps from del start to del end
        input['DELSTART'] = np.array([values[1]*step_modifier[0]]) # Starting step
        input['DELEND'] = np.array([0.1*values[1]*step_modifier[1]]) #Ending step
        input['MINDELTA'] = np.array([0.05*values[1]*step_modifier[2]]) #saturation criterum when /SIZE SIZE should be 10 troughout the code
    else:
        if not symmetric:
            if debug:
                print_log(f'''SET_GENERIC_FITTING: implementing a varying non-symmetric profile.
{'':8s} step_modifier = {step_modifier}
{'':8s} values = {values}
''', Configuration['OUTPUTLOG'], screen = True ,debug = False)
            if flat_inner+1 >= NUR:
                input['VARY'] =  np.concatenate((np.array([f"!{key} {NUR}"]),np.array([f"!{key}_2 {NUR}"]),np.array([f"{key} 1:{NUR-1} {key}_2 1:{NUR-1}"])))

            else:
                input['VARY'] =  np.concatenate((np.array([f"!{key} {NUR}:{flat_inner+1}"]),np.array([f"!{key}_2 {NUR}:{flat_inner+1}"]),np.array([f"{key} 1:{flat_inner} {key}_2 1:{flat_inner}"])))
            input['PARMAX'] = np.concatenate((np.array([limits[1][1]]),np.array([limits[2][1]]),np.array([limits[0][1]])))
            input['PARMIN'] = np.concatenate((np.array([limits[1][0]]),np.array([limits[2][0]]),np.array([limits[0][0]])))
            input['MODERATE'] =np.array([moderate,moderate,moderate]) #How many steps from del start to del end
            input['DELSTART'] =np.array([2.,2.,0.5],dtype=float)*step_modifier[0]*values[1]# Starting step
            input['DELEND'] = np.array([0.1,0.1,0.05],dtype=float)*step_modifier[1]*values[1] #Ending step
            input['MINDELTA'] = np.array([0.1,0.1,0.075],dtype=float)*step_modifier[2]*values[1] #saturation criterum when /SIZE SIZE should be 10 troughout the code
        else:
            if debug:
                print_log(f'''SET_GENERIC_FITTING: implementing a varying symmetric profile
''', Configuration['OUTPUTLOG'], screen = True ,debug = debug)
            if flat_inner+1 >= NUR:
                input['VARY'] =  np.concatenate((np.array([f"!{key} {NUR} {key}_2 {NUR}"]),np.array([f"{key} 1:{NUR-1} {key}_2 1:{NUR-1}"])))
            else:
                input['VARY'] =  np.concatenate((np.array([f"!{key} {NUR}:{flat_inner+1} {key}_2 {NUR}:{flat_inner+1}"]),np.array([f"{key} 1:{flat_inner} {key}_2 1:{flat_inner}"])))
            input['PARMAX'] = np.concatenate((np.array([limits[1][1]]),np.array([limits[0][1]])))
            input['PARMIN'] = np.concatenate((np.array([limits[1][0]]),np.array([limits[0][0]])))
            input['MODERATE'] =np.array([moderate,moderate]) #How many steps from del start to del end
            input['DELSTART'] =np.array([2.,0.5],dtype=float)*step_modifier[0]*values[1] # Starting step
            input['DELEND'] = np.array([0.1,0.05],dtype=float)*step_modifier[1]*values[1] #Ending step
            input['MINDELTA'] = np.array([0.1,0.075],dtype=float)*step_modifier[2]*values[1] #saturation criterum when /SIZE SIZE should be 10 troughout the code
        # then we need to set the warp slope

        forvarindex = ''
        implement_keys = [key, f"{key}_2"]
        for i,cur_key in enumerate(implement_keys):
            if slope[i] < NUR:
                if flat_slope:
                    if slope[i]+1 == NUR:
                        forvarindex = forvarindex+f"{cur_key} {NUR} "
                    else:
                        forvarindex = forvarindex+f"{cur_key} {NUR}:{slope[i]+1} "
                else:
                    if slope[i]+1 >= NUR-1:
                        forvarindex = forvarindex+f"{cur_key} {NUR-1} "
                    else:
                        forvarindex = forvarindex+f"{cur_key} {NUR-1}:{slope[i]+1} "

        input['VARINDX'] = np.array([forvarindex])


    return input
set_generic_fitting.__doc__ = '''

    ; NAME:
    ;      set_generic_fitting(Configuration, key ,hdr = None,systemic = 100., stage = 'initial', values = [60,5.], \
                            limits = [[0.,0.],[0.,0.],[0.,0.]],debug = False, slope = [0, 0], flat_slope = False , symmetric = False,\
                            upper_bracket = [10.,100.], lower_bracket=[0., 50.], Fixed = True, moderate = 5, step_modifier = [1.,1.,1.],\
                            flat_inner = 3):
    ;
    ; PURPOSE:
    ;      Generic routine for setting fitting parameters, SBR, VROT are separate
    ;
    ; CATEGORY:
    ;       modify_template
    ;
    ;
    ; INPUTS:
    ;
    ; OPTIONAL INPUTS:
    ;           step_modifier = array that modifies the fitting steps corresponding to [STARTDELTA, ENDDELTA, MINDELTA]
                                for flat disks the standard values are [error,0.1*error,0.05 error]
                                for varying disk [1.,0.1,1.] for the varying part and [error/2., 0.05*error, 0.1*error]  for the flat part
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
    ;      split, strip, open
    ;
    ; EXAMPLE:
    ;
    ;
'''

#Function
def set_model_parameters(Configuration, Tirific_Template,Model_Values, hdr = None, stage = 'initial',debug = False):
    parameters_to_set = ['RADI','VROT_profile','Z0','SBR_profile','INCL','PA','XPOS','YPOS','VSYS','SDIS']


    check_parameters = []
    if 'VSYS' in Model_Values:
        vsys =Model_Values['VSYS'][0]/1000.
    else:
        vsys=100.
    scramble = np.zeros(len(parameters_to_set))
    # If the inclination is low we want to throw the inclination and VROT out of Vobs hence we scramble with random values
    #if stage == 'initialize_def_file':
    #        if 'INCL' in parameters_to_set:
    #            if Model_Values['INCL'][0] < 40.:
    #                scramble[parameters_to_set.index('INCL')] = np.random.uniform(-5,5,1)[0]
                    #if 'VROT_profile' in parameters_to_set:
                    #    Model_Values['VROT_profile'] = [set_limits(x+np.random.uniform(-2.*Configuration['CHANNEL_WIDTH'],2.*Configuration['CHANNEL_WIDTH'],1)[0], 0,600.) for x in Model_Values['VROT_profile'] ]
                    #    scramble[parameters_to_set.index('VROT_profile')] = np.mean([x*np.sin(np.radians(Model_Values['INCL'][0]))/np.sin(np.radians(Model_Values['INCL'][0]))])

    for key in parameters_to_set:
        if key in Model_Values:
            if key in ['VROT_profile','SBR_profile']:
                key_to_set = key.split('_')[0]
            else:
                key_to_set = key
            # if 2 long we have a value and error
            format = set_format(key_to_set)
            if len(Model_Values[key]) == 2:
                Tirific_Template[key_to_set]= f"{Model_Values[key][0]+scramble[parameters_to_set.index(key)]:{format}}"
            else:
                Tirific_Template[key_to_set]= f"{' '.join([f'{x+scramble[parameters_to_set.index(key)]:{format}}' for x in Model_Values[key][:int(Configuration['NO_RINGS'])]])}"
            if key_to_set != 'RADI':
                key_write = f"{key_to_set}_2"
                if f"{key}_2" in Model_Values:
                    key = f"{key}_2"
                if len(Model_Values[key]) == 2:
                    Tirific_Template[key_write]= f"{Model_Values[key][0]+scramble[parameters_to_set.index(key)]:{format}}"
                else:
                    Tirific_Template[key_write]= f"{' '.join([f'{x+scramble[parameters_to_set.index(key)]:{format}}' for x in Model_Values[key][:int(Configuration['NO_RINGS'])]])}"

            check_parameters.append(key)
        else:
            if key == 'RADI':
                rad = set_rings(Configuration,debug=debug)
                if len(Configuration['OLD_RINGS']) == 0:
                    size_in_beams = (rad[-1]-1./5.*Configuration['BMMAJ'])/Configuration['BMMAJ']
                    Configuration['OLD_RINGS'].append(f"{size_in_beams:.1f}")
                Tirific_Template['RADI']= f"{' '.join([f'{x:.2f}' for x in rad])}"
                Tirific_Template['NUR']=str(len(rad))
                check_parameters.append('RADI')
            elif key == 'Z0':
                check_parameters.append('Z0')
                if hdr:
                    if Model_Values['INCL'][0] > 80:
                        Tirific_Template['Z0'] = f"{np.max([convertskyangle(0.2,distance=Configuration['DISTANCE'],physical= True),hdr['BMAJ']/4.*3600.]):.3f}"

                    else:
                        Tirific_Template['Z0'] = f"{convertskyangle(0.2,distance=Configuration['DISTANCE'],physical= True):.3f}"

                else:
                    Tirific_Template['Z0'] = f"{convertskyangle(0.2,distance=Configuration['DISTANCE'],physical= True):.3f}"

                Tirific_Template['Z0_2'] = Tirific_Template['Z0']

            elif key == 'SDIS':
                check_parameters.append('SDIS')
                Tirific_Template['SDIS'] = '8.'
                Tirific_Template['SDIS_2'] = '8.'
            elif key == 'XPOS':
                if 'RA' in Model_Values:
                    if len(Model_Values['RA']) == 2:
                        Tirific_Template[key]= f"{Model_Values['RA'][0]:.8e}"
                        Tirific_Template[f"{key}_2"]= f"{Model_Values['RA'][0]:.8e}"
                    else:
                        Tirific_Template[key]= f"{' '.join([f'{x:.8e}' for x in Model_Values['RA'][:int(Configuration['NO_RINGS'])]])}"
                        Tirific_Template[f"{key}_2"]= f"{' '.join([f'{x:.8e}' for x in Model_Values['RA'][:int(Configuration['NO_RINGS'])]])}"
                    check_parameters.append('XPOS')
            elif key == 'YPOS':
                if 'DEC' in Model_Values:
                    if len(Model_Values['DEC']) == 2:
                        Tirific_Template[key]= f"{Model_Values['DEC'][0]:.8e}"
                        Tirific_Template[f"{key}_2"]= f"{Model_Values['DEC'][0]:.8e}"
                    else:
                        Tirific_Template[key]= f"{' '.join([f'{x:.8e}' for x in Model_Values['DEC'][:int(Configuration['NO_RINGS'])]])}"
                        Tirific_Template[f"{key}_2"]=f"{' '.join([f'{x:.8e}' for x in Model_Values['DEC'][:int(Configuration['NO_RINGS'])]])}"
                    check_parameters.append('YPOS')



    #if we are in the initial stage check that all parameters are set
    if stage == 'initial':
        for key in parameters_to_set:
            if not key in check_parameters:
                raise InitializeError(f"The parameter {key} is not set in the initialization")

    #make sure that the first value in VROT = 0
    vrot = Tirific_Template['VROT'].split()
    if float(vrot[0]) != 0.:
        Tirific_Template['VROT']=f" 0. {' '.join([f'{x}' for x in vrot[:int(Configuration['NO_RINGS']-1)]])}"
        Tirific_Template['VROT_2']=f" 0. {' '.join([f'{x}' for x in vrot[:int(Configuration['NO_RINGS']-1)]])}"
    no_declining_vrot(Configuration, Tirific_Template, debug = debug)

set_model_parameters.__doc__ = '''

    ; NAME:
    ;      set_model_parameters(Configuration, Tirific_Template,Model_Values, hdr = None):
    ;
    ; PURPOSE:
    ;      Set the model values parameters in the tirific file that are singular values that apply to all of the fitting such as names and other issues
    ;
    ; CATEGORY:
    ;       modify_template
    ;
    ;
    ; INPUTS:
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
    ;      split, strip, open
    ;
    ; EXAMPLE:
    ;
    ;
'''

#function to check that all parameters in template have the proper length.
def set_new_size(Configuration,Tirific_Template, Fits_Files, fit_stage = 'Unitialized Stage', stage = 'initial',
                    hdr = 'Empty',current_run='Not Initialized', debug = False, Variables =
                    ['VROT','Z0', 'SBR', 'INCL','PA','XPOS','YPOS','VSYS','SDIS','VROT_2',  'Z0_2','SBR_2',
                     'INCL_2','PA_2','XPOS_2','YPOS_2','VSYS_2','SDIS_2', 'AZ1P', 'AZ1W' ,'AZ1P_2','AZ1W_2', 'RADI']):
    if debug:
        print_log(f'''SET_NEW_SIZE: Starting the adaptation of the size in the template
''',Configuration['OUTPUTLOG'],debug =True)
    for key in Variables:
        if not key in Tirific_Template:
            Variables.remove(key)
    parameters = get_from_template(Tirific_Template,Variables,debug = debug)
    # do a check on whether we need to modify all
    radii = set_rings(Configuration,debug=debug)
    if not Configuration['NEW_RING_SIZE']:
        print_log(f'''SET_NEW_SIZE: The rings size is stable and we are not interpolating
''',Configuration['OUTPUTLOG'],screen = True)
        interpolate = False
    else:
        print_log(f'''SET_NEW_SIZE: The rings size is updated and we are interpolating the old values.
''',Configuration['OUTPUTLOG'],screen = True)
        old_radii = parameters[Variables.index('RADI')]
        Configuration['NEW_RING_SIZE'] = False
        interpolate = True
    #if we add a ring we need to make sure that the radius gets extended
    if len(radii) > len(parameters[Variables.index('RADI')]):
        parameters[Variables.index('RADI')] = radii
        #and the last SBR values are far too high, set them to zero such that fix_sbr will correct them
        for i in [-3,-2,-1]:
            parameters[Variables.index('SBR')][i] = 0.
            parameters[Variables.index('SBR_2')][i] = 0.


    for i,key in enumerate(Variables):

        if debug:
            print_log(f'''SET_NEW_SIZE: We are processing {key}
''',Configuration['OUTPUTLOG'], debug=False)
            print_log(f'''SET_NEW_SIZE: We have a parameter of length {len(parameters[i])}.
{'':8s}SET_NEW_SIZE: Our current number of rings in the model is {Configuration['NO_RINGS']}.
{'':8s}SET_NEW_SIZE: {parameters[i]}
''',Configuration['OUTPUTLOG'], debug=False)
        if key == 'RADI':
            Tirific_Template[key] = f" {' '.join([f'{x:.2f}' for x in radii])}"
        else:
            if interpolate:
                if debug:
                    print_log(f'''SET_NEW_SIZE: We are interpolating par = {parameters[i]} old radii={old_radii} new radii={radii}
    ''',Configuration['OUTPUTLOG'], debug=False)
                if len(parameters[i]) > len(old_radii):
                    if debug:
                        print_log(f'''SET_NEW_SIZE: The parameters have more values than the radii. Cutting the end.
    ''',Configuration['OUTPUTLOG'], debug=False)
                        parameters[i] = parameters[i][:len(old_radii)-1]
                elif len(parameters[i]) < len(old_radii):
                    if debug:
                        print_log(f'''SET_NEW_SIZE: The parameters have less values than the radii. Adding the last value until match.
    ''',Configuration['OUTPUTLOG'], debug=False)
                        while len(parameters[i]) < len(old_radii):
                            parameters[i].append(parameters[i][-1])

                parameters[i] = list(np.interp(np.array(radii,dtype=float),np.array(old_radii,dtype=float),np.array(parameters[i],dtype=float)))

            format = set_format(key)

            if len(parameters[i]) > Configuration['NO_RINGS']-1:
                # if we are cutting a ring it is likely the outer ring have done weird stuff so we flatten the curve

                Tirific_Template[key] =f" {' '.join([f'{x:{format}}' for x in parameters[i][:int(Configuration['NO_RINGS'])]])}"
            elif len(parameters[i]) <= Configuration['NO_RINGS']-1:
                # We simply add the last value
                counter = len(parameters[i])
                while counter !=  Configuration['NO_RINGS']:
                    Tirific_Template[key] = Tirific_Template[key] + f" {parameters[i][-1]:{format}}"
                    counter += 1


        if debug:
            print_log(f'''SET_NEW_SIZE: We wrote the following line {Tirific_Template[key]}
''',Configuration['OUTPUTLOG'],screen = True)

    #Replace the old ring numbers in VARY and VARINDX
    old_rings = calc_rings(Configuration,size_in_beams = int(round(float(Configuration['OLD_RINGS'][-2]))), ring_size  = 0.,debug=debug)
    current_rings = calc_rings(Configuration,debug=debug)
    #This could lead to replacing a value smaller than the other side
    Tirific_Template['VARY'] = Tirific_Template['VARY'].replace(f"{old_rings}",f"{current_rings}")
    Tirific_Template['VARINDX'] = Tirific_Template['VARINDX'].replace(f"{old_rings-1}",f"{current_rings-1}")
    Tirific_Template['NUR'] = f"{current_rings}"
    # if we cut we want to flatten things
    if current_rings < old_rings:
        flatten_the_curve(Configuration,Tirific_Template,debug=debug)
    # Check whether the galaxy has become to small for variations
    if Configuration['SIZE_IN_BEAMS'] > Configuration['MINIMUM_WARP_SIZE']:
        Configuration['FIX_INCLINATION'][0] =Configuration['FIX_INCLINATION'][1]
        Configuration['FIX_SDIS'][0] = Configuration['FIX_SDIS'][1]
        Configuration['FIX_PA'][0] = Configuration['FIX_PA'][1]
        Configuration['FIX_Z0'][0] = Configuration['FIX_Z0'][1]
    else:
        Configuration['FIX_INCLINATION'][0] = True
        Configuration['FIX_SDIS'][0] = True
        Configuration['FIX_PA'][0] = True
        Configuration['FIX_Z0'][0] = True
        flatten_the_curve(Configuration,Tirific_Template,debug=debug)
    if debug:
        print_log(f'''Settings for the variations will be.
{'':8s} INCLINATION: Fixed = {Configuration['FIX_INCLINATION'][0]}
{'':8s} PA: Fixed = {Configuration['FIX_PA'][0]}
{'':8s} SDIS: Fixed = {Configuration['FIX_SDIS'][0]}
{'':8s} Z0: Fixed = {Configuration['FIX_Z0'][0]}
''',Configuration['OUTPUTLOG'],screen =False)

    #update the limit_modifier
    Inclination = np.array([(float(x)+float(y))/2. for x,y in zip(Tirific_Template['INCL'].split(),Tirific_Template['INCL_2'].split())],dtype=float)
    set_limit_modifier(Configuration,Inclination,debug=debug)
    # Maybe increase the amount of loops in smaller galaxies
    set_overall_parameters(Configuration, Fits_Files,Tirific_Template,loops = 10 ,fit_stage=fit_stage,hdr=hdr, debug=debug,stage=stage)
    # if we change the radii we need to restart tirific
    finish_current_run(Configuration,current_run,debug=debug)

def set_overall_parameters(Configuration, Fits_Files,Tirific_Template,stage = 'initial',fit_stage='Undefined_Stage', loops = 0,hdr= None, flux = None,debug = False):

            if Configuration['OPTIMIZED']:
                Tirific_Template['INSET'] = f"{Fits_Files['OPTIMIZED_CUBE']}"
            else:
                Tirific_Template['INSET'] = f"{Fits_Files['FITTING_CUBE']}"
            #if stage in ['run_ec','initialize_ec']:
            #    if Configuration['NO_RINGS'] < 5:
            #        Tirific_Template['INIMODE'] = '1'
            #    elif Configuration['NO_RINGS'] < 15:
            #        Tirific_Template['INIMODE'] = '2'
            #    else:
            #        Tirific_Template['INIMODE'] = '3'
            #else:
            if Configuration['NO_RINGS'] < 10:
                Tirific_Template['INIMODE'] = '1'
            elif Configuration['NO_RINGS'] < 25:
                Tirific_Template['INIMODE'] = '2'
            else:
                Tirific_Template['INIMODE'] = '3'

            if Configuration['NO_RINGS'] > 3.:

                Tirific_Template['INTY'] = 0
                #Tirific_Template['INDINTY'] = 0
            else:
                #This should not be used with 8 <  rings.
                Tirific_Template['INTY'] = 1
                #preferably we'd use the akima spline but there is an issue with that where the final ring does not get modified
                #Tirific_Template['INDINTY'] = 2
            Tirific_Template['NUR'] = f"{Configuration['NO_RINGS']}"

            Tirific_Template['RESTARTNAME'] = f"Logs/restart_{fit_stage}.txt"
            #this could be fancier
            '''
            if Configuration['NO_RINGS'] < 3:
                Tirific_Template['NCORES'] = '2'
            elif Configuration['NO_RINGS'] < 6:
                Tirific_Template['NCORES'] = '3'
            elif Configuration['NO_RINGS'] < 12:
                Tirific_Template['NCORES'] = '4'
            else:
                Tirific_Template['NCORES'] = '6'
            '''

            Tirific_Template['NCORES'] = Configuration['NCPU']

            Tirific_Template['LOOPS'] = f"{int(loops)}"
            Tirific_Template['DISTANCE'] = f"{Configuration['DISTANCE']}"
            out_keys = ['LOGNAME','OUTSET','TIRDEF']
            out_extensions = ['log','fits','def']
            for i,key in enumerate(out_keys):
                Tirific_Template[key] = f"{fit_stage}/{fit_stage}.{out_extensions[i]}"
            #some things we only set if a header is provided
            if hdr:
                Tirific_Template['BMAJ'] = f"{hdr['BMAJ']*3600:.2f}"
                Tirific_Template['BMIN'] = f"{hdr['BMIN']*3600:.2f}"
                Tirific_Template['RMS'] = f"{hdr['FATNOISE']:.2e}"
                try:
                    Tirific_Template['BPA'] = f"{hdr['BPA']:.2f}"
                except:
                    Tirific_Template['BPA'] = '0'
                if Configuration['HANNING']:
                    instrumental_vres = (hdr['CDELT3']/1000.*2)/(2.*np.sqrt(2.*np.log(2)))
                else:
                    instrumental_vres = (hdr['CDELT3']/1000.*1.2)/(2.*np.sqrt(2.*np.log(2)))
                Tirific_Template['CONDISP'] = f"{instrumental_vres:.2f}"
            if flux:
                Tirific_Template['CFLUX'] = f"{set_limits(flux/1.5e7,1e-6,1e-3):.2e}"
                Tirific_Template['CFLUX_2'] = f"{set_limits(flux/1.5e7,1e-6,1e-3):.2e}"
set_overall_parameters.__doc__ = '''

    ; NAME:
    ;      set_overall_parameters(Configuration, Fits_Files,Tirific_Template, loops = 0, outname = 'random_fit')
    ;
    ; PURPOSE:
    ;      Set the parameters in the tirific file that are singular values that apply to all of the fitting such as names and other issues
    ;
    ; CATEGORY:
    ;       modify_template
    ;
    ;
    ; INPUTS:
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
    ;      split, strip, open
    ;
    ; EXAMPLE:
    ;
    ;
'''

def set_sbr_fitting(Configuration,hdr = None,systemic = 100., stage = 'no_stage',debug = False):
    if debug:
        print_log(f'''SET_SBR_FITTING: We are setting the SBR limits.
{'':8s} No_Rings = {Configuration['NO_RINGS']}
''',Configuration['OUTPUTLOG'],debug = debug)
    sbr_input = {}
    inner_ring = 2
    if stage in ['initial','run_cc','initialize_ec','run_ec','initialize_os','run_os']:
        if hdr:
            radii,sbr_ring_limits = sbr_limits(Configuration,hdr,systemic = systemic, debug = debug)
            if stage in ['run_ec','run_os']:
                sbr_ring_limits[-4:]=[x/5 for x in sbr_ring_limits]
        else:
            sbr_ring_limits = np.zeros(Configuration['NO_RINGS'])
            radii = np.zeros(Configuration['NO_RINGS'])
        if debug:
            print_log(f'''SET_SBR_FITTING: Using these SBR limits.
{'':8s} limits = {sbr_ring_limits}
{'':8s} no of limits = {len(sbr_ring_limits)}
''',Configuration['OUTPUTLOG'],debug = False)
        if stage in ['initial','run_cc']:
            max_size = 4
        elif stage in ['initialize_ec','run_ec','initialize_os','run_os']:
            max_size = 2.

        if Configuration['SIZE_IN_BEAMS'] < max_size:
            sbr_input['VARY'] =  np.array([f"SBR {x+1} SBR_2 {x+1}" for x in range(len(radii)-1,inner_ring-1,-1)])
            sbr_input['PARMAX'] = np.array([1 for x in range(len(radii)-1,inner_ring-1,-1)])
            #if stage in ['initial','run_cc']:
            #    sbr_input['PARMIN'] = np.array([sbr_ring_limits[x]/2. if x <= (3./4.)*len(radii) else 0 for x in range(len(radii)-1,inner_ring-1,-1)])
            #elif stage in ['initialize_ec','run_ec']:
            sbr_input['PARMIN'] = np.array([sbr_ring_limits[x]/1.5 for x in range(len(radii)-1,inner_ring-1,-1)])
            sbr_input['MODERATE'] = np.array([5 for x in range(len(radii)-1,inner_ring-1,-1)]) #How many steps from del start to del end
            sbr_input['DELSTART'] = np.array([1e-4 for x in range(len(radii)-1,inner_ring-1,-1)]) # Starting step
            sbr_input['DELEND'] = np.array([2.5e-6 for x in range(len(radii)-1,inner_ring-1,-1)]) #Ending step
            sbr_input['MINDELTA'] = np.array([5e-6 for x in range(len(radii)-1,inner_ring-1,-1)]) #saturation criterum when /SIZE SIZE should be 10 troughout the code
        else:
            sbr_input['VARY'] =  np.array([[f"SBR {x+1}",f"SBR_2 {x+1}"] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2)
            sbr_input['PARMAX'] = np.array([[1,1] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2)
        #if stage in ['initial','run_cc']:
            #    sbr_input['PARMIN'] = np.array([[sbr_ring_limits[x]/2.,sbr_ring_limits[x]/2.] if x <= (3./4.)*len(radii) else [0.,0.] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2)
            #elif stage in ['initialize_ec','run_ec']:
            sbr_input['PARMIN'] = np.array([[sbr_ring_limits[x]/4.,sbr_ring_limits[x]/4.] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2)
            sbr_input['MODERATE'] = np.array([[5,5] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2) #How many steps from del start to del end
            sbr_input['DELSTART'] = np.array([[1e-4,1e-4] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2) # Starting step
            sbr_input['DELEND'] = np.array([[sbr_ring_limits[x]/20.,sbr_ring_limits[x]/20.] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2)
            sbr_input['MINDELTA'] = np.array([[sbr_ring_limits[x]/20.,sbr_ring_limits[x]/20.] for x in range(len(radii)-1,inner_ring-1,-1)]).reshape((len(radii)-inner_ring)*2)

        sbr_input['VARY'] = np.concatenate((sbr_input['VARY'],[f"SBR {' '.join([str(int(x)) for x in range(1,inner_ring+1)])} SBR_2 {' '.join([str(int(x)) for x in range(1,inner_ring+1)])}"]),axis=0)
        sbr_input['PARMAX'] = np.concatenate((sbr_input['PARMAX'],[2e-3]))
        sbr_input['PARMIN'] = np.concatenate((sbr_input['PARMIN'],[np.min(sbr_ring_limits)]))
        sbr_input['MODERATE'] = np.concatenate((sbr_input['MODERATE'],[5]))
        sbr_input['DELSTART'] = np.concatenate((sbr_input['DELSTART'],[1e-5]))
        sbr_input['DELEND'] = np.concatenate((sbr_input['DELEND'],[1e-6]))
        sbr_input['MINDELTA'] = np.concatenate((sbr_input['MINDELTA'],[2e-6]))
    elif stage in ['after_cc','after_ec','after_os']:
        #Used in Fit_Smoothed_Check
        sbr_input['VARY'] = [f"SBR 3:{Configuration['NO_RINGS']}, SBR_2 3:{Configuration['NO_RINGS']}"]
        sbr_input['PARMAX'] = np.concatenate(([2e-3],[2e-3]))
        sbr_input['PARMIN'] = np.concatenate(([0],[0]))
        sbr_input['MODERATE'] = np.concatenate(([5],[5]))
        sbr_input['DELSTART'] = np.concatenate(([1e-5],[1e-5]))
        sbr_input['DELEND'] = np.concatenate(([1e-6],[1e-6]))
        sbr_input['MINDELTA'] = np.concatenate(([2e-6],[2e-6]))

    return sbr_input
set_sbr_fitting.__doc__ = '''

    ; NAME:
    ;      set_sbr_fitting(Configuration,hdr = None,systemic = 100., stage = 'initial'):
    ;
    ; PURPOSE:
    ;      the fitting parameter for the sbr if required
    ;
    ; CATEGORY:
    ;       modify_template
    ;
    ;
    ; INPUTS:
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
    ;      split, strip, open
    ;
    ; EXAMPLE:
    ;
    ;
'''

def set_vrot_fitting(Configuration,Tirific_Template,hdr = None,systemic = 100., stage = 'initial', rotation = [100,5.], debug = False):
    NUR = Configuration['NO_RINGS']
    vrot_input = {}
    vrot_limits = [set_limits(rotation[0]-rotation[1]-10,hdr['CDELT3']/1000.,360.), \
                   set_limits(rotation[0]+rotation[1]+10,80.,600.)]
    if debug:
        print_log(f'''SET_VROT_FITTING: We are setting the VROT limits.
{'':8s} No_Rings = {Configuration['NO_RINGS']}
{'':8s} Limits = {vrot_limits}
''',Configuration['OUTPUTLOG'],debug = debug)
    if stage in  ['initial','run_cc','after_cc','initialize_ec','run_ec','initialize_os','run_os']:
        if stage in ['initial', 'run_cc','initialize_ec','run_ec','initialize_os','run_os']:
            vrot_input['VARY'] =  np.array([f"!VROT {NUR}:2 VROT_2 {NUR}:2"])
        elif stage in ['after_cc', 'after_ec','after_os']:
            vrot_input['VARY'] =  np.array([f"VROT {NUR}:2 VROT_2 {NUR}:2"])
        vrot_input['PARMAX'] = np.array([vrot_limits[1]])
        vrot_input['PARMIN'] = np.array([vrot_limits[0]])
        vrot_input['MODERATE'] = np.array([5]) #How many steps from del start to del end
        vrot_input['DELSTART'] = np.array([2.*hdr['CDELT3']/1000.*Configuration['LIMIT_MODIFIER'][0]]) # Starting step
        #These were lower in the original fat
        vrot_input['DELEND'] = np.array([0.1*hdr['CDELT3']/1000.*Configuration['LIMIT_MODIFIER'][0]]) #Ending step
        vrot_input['MINDELTA'] = np.array([0.1*hdr['CDELT3']/1000.*Configuration['LIMIT_MODIFIER'][0]]) #saturation criterum when /SIZE SIZE should be 10 troughout the code
        #if there is not values in the center we connect the inner ring to the next ring
        forvarindex = ''
        if Configuration['EXCLUDE_CENTRAL'] or rotation[0] > 150.:
            forvarindex = 'VROT 2 VROT_2 2 '
        if Configuration['OUTER_SLOPE_START'] == NUR:
            if Configuration['NO_RINGS'] > 5:
                inner_slope =  int(round(set_limits(check_size(Configuration,Tirific_Template,hdr, debug = debug,fix_rc = True),round(NUR/2.),NUR-1)))
            else:
                inner_slope = NUR
            if Configuration['NO_RINGS'] > 15 and inner_slope > int(Configuration['NO_RINGS']*4./5.) :
                inner_slope = int(Configuration['NO_RINGS']*4./5.)
            Configuration['OUTER_SLOPE_START'] = inner_slope
        else:
            inner_slope = Configuration['OUTER_SLOPE_START']
        if stage in ['initial','run_cc']:
                #inner_slope = int(round(set_limits(NUR*(4.-Configuration['LIMIT_MODIFIER'][0])/4.,round(NUR/2.),NUR-2)))
            if inner_slope >= NUR-1:
                forvarindex = forvarindex+f"VROT {NUR}:{NUR-1} VROT_2 {NUR}:{NUR-1} "
            else:
                forvarindex = forvarindex+f"VROT {NUR}:{inner_slope} VROT_2 {NUR}:{inner_slope} "
            vrot_input['VARINDX'] = np.array([forvarindex])
        elif stage in ['initialize_ec','run_ec']:
            if inner_slope >= NUR-1:
                forvarindex = forvarindex+f"VROT {NUR-1} VROT_2 {NUR-1} "
            else:
                forvarindex = forvarindex+f"VROT {NUR-1}:{inner_slope} VROT_2 {NUR-1}:{inner_slope} "
            vrot_input['VARINDX'] = np.array([forvarindex])


    return vrot_input
set_vrot_fitting.__doc__ = '''

    ; NAME:
    ;      set_vrot_fitting(Configuration,hdr = None,systemic = 100., stage = 'initial', rotation = [100,5.]):
    ;
    ; PURPOSE:
    ;      the fitting parameter for the incl if required
    ;
    ; CATEGORY:
    ;       modify_template
    ;
    ;
    ; INPUTS:
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
    ;      split, strip, open
    ;
    ; EXAMPLE:
    ;
    ;
'''

def smooth_profile(Configuration,Tirific_Template,key,hdr,min_error = 0.,debug=False ,profile = None, no_apply =False,fix_sbr_call = False):
    if debug:
        print_log(f'''SMOOTH_PROFILE: Starting to smooth the {key} profile.
''',Configuration['OUTPUTLOG'],debug = True)
    if key == 'SBR' and not fix_sbr_call:
        error_message = f'''SMOOTH_PROFILE: Do not use smooth_profile for the SBR, SBR is regularised in fix_sbr'''
        print_log(error_message,Configuration['OUTPUTLOG'],screen=True,debug = False)
        raise FunctionCallError(error_message)

    if profile is None:
        profile = np.array(get_from_template(Tirific_Template,[key,f"{key}_2"]),dtype = float)
    original_profile = copy.deepcopy(profile)
    #he sbr profile is already fixed before geting to the smoothing
    if not fix_sbr_call:
        profile =fix_profile(Configuration, key, profile, Tirific_Template, hdr,debug=debug)

    if key == 'VROT':
        if profile[0,1] > profile[0,2] or np.mean(profile[1:3]) > 120.:
            shortened =True
            profile = np.delete(profile, 0, axis = 1)
        else:
            shortened = False
    if debug:
        print_log(f'''SMOOTH_PROFILE: retrieved profile.
{'':8s}{profile}
''',Configuration['OUTPUTLOG'],debug = False)
    # savgol filters do not work for small array
    for i in [0,1]:
        if len(profile[i]) < 8:
            #In this case we are using a cubic spline so no smoothing required
            pass
        elif len(profile[i]) < 15:
            profile[i] = savgol_filter(profile[i], 3, 1)
        elif len(profile[i]) < 20:
            profile[i] = savgol_filter(profile[i], 5, 2)
        elif len(profile[i]) < 25:
            profile[i] = savgol_filter(profile[i], 7, 3)
        else:
            profile[i] = savgol_filter(profile[i], 9, 4)
    if fix_sbr_call:
        return profile
    # Fix the settings
    format = set_format(key)
    if key == 'VROT':
        if shortened:
            tmp = [[],[]]
            tmp[0] = np.hstack([[0.], profile[0]])
            tmp[1] = np.hstack([[0.], profile[1]])
            profile =  np.array(tmp,dtype=float)
        else:
            profile[:,0] = 0.

    profile =fix_profile(Configuration, key, profile, Tirific_Template, hdr,debug=debug)

    if debug:
        print_log(f'''SMOOTH_PROFILE: profile after smoothing.
{'':8s}{profile}
''',Configuration['OUTPUTLOG'],debug = False)
    if not no_apply:
        errors = get_error(Configuration,original_profile,profile,min_error=min_error,debug=debug)
        if key not in ['VROT']:
            # Check whether it should be flat
            profile,errors =modify_flat(Configuration,profile,original_profile,errors,key,debug=debug)
            #errors = get_error(Configuration,original_profile,profile,min_error=min_error,debug=debug)
        Tirific_Template[key]= f"{' '.join([f'{x:{format}}' for x in profile[0,:int(Configuration['NO_RINGS'])]])}"
        Tirific_Template[f"{key}_2"]= f"{' '.join([f'{x:{format}}' for x in profile[1,:int(Configuration['NO_RINGS'])]])}"
        Tirific_Template.insert(key,f"# {key}_ERR",f"{' '.join([f'{x:{format}}' for x in errors[0,:int(Configuration['NO_RINGS'])]])}")
        Tirific_Template.insert(f"{key}_2",f"# {key}_2_ERR",f"{' '.join([f'{x:{format}}' for x in errors[1,:int(Configuration['NO_RINGS'])]])}")

        if debug:
            print_log(f'''SMOOTH_PROFILE: This has gone to the template
{'':8s}{key} = {Tirific_Template[key]}
{'':8s}{key}_2 ={Tirific_Template[f"{key}_2"]}
{'':8s}# {key}_ERR ={Tirific_Template[f"# {key}_ERR"]}
{'':8s}# {key}_2_ERR ={Tirific_Template[f"# {key}_2_ERR"]}
''',Configuration['OUTPUTLOG'],screen=True,debug = False)

    return profile


def modify_flat(Configuration,profile,original_profile,errors,key,debug=False):

    if debug:
         print_log(f'''MODIFY_FLAT: These {key} profiles are checked to be flat.
{'':8s} profile = {profile}
{'':8s} original_profile = {original_profile}
{'':8s} errors = {errors}
''',Configuration['OUTPUTLOG'],debug = True)

    flatness = []
    for side in [0,1]:
         flatness.append(check_flat(Configuration,profile[side],errors[side],debug=debug))
    if all(flatness):
        profile[:] = np.nanmedian(original_profile[:,:round(len(original_profile)/2.)])
        errors = get_error(Configuration,original_profile,profile,apply_max_error = True,key=key,min_error =np.nanmin(errors) , debug=debug)
    else:
        if any(flatness):
            for side in [0,1]:
                if flatness[side]:
                    profile[side]  = np.median(original_profile[side,:round(len(original_profile)/2.)])
                    flat_val = profile[side,0]
                    errors[side] = get_error(Configuration,original_profile[side],profile[side],apply_max_error = True,key=key,min_error =np.nanmin(errors[side]),singular = True ,debug=debug)
            profile[:,0:3] = flat_val
            profile[:,4] = (flat_val+profile[:,4])/2.
    if debug:
        print_log(f'''MODIFY_FLAT: Returning:
{'':8s} profile = {profile}
{'':8s} errors = {errors}
''',Configuration['OUTPUTLOG'],debug = False)
    return profile,errors

def update_disk_angles(Tirific_Template,debug = False):
    extension = ['','_2']
    for ext in extension:
        PA = np.array(get_from_template(Tirific_Template,[f'PA{ext}'],debug=debug))[0]
        inc = np.array(get_from_template(Tirific_Template,[f'INCL{ext}'],debug=debug))[0]
        angle_adjust=np.array(np.tan((PA[0]-PA)*np.cos(inc*np.pi/180.)*np.pi/180.)*180./np.pi,dtype = float)
        if ext == '_2':
            angle_adjust[:] +=180.
        if debug:
            print_log(f'''UPDATE_DISK_ANGLES: adusting AZ1P{ext} with these angles
{'':8s}{angle_adjust}
''', None,screen = True)
        Tirific_Template.insert(f'AZ1W{ext}',f'AZ1P{ext}',f"{' '.join([f'{x:.2f}' for x in angle_adjust])}")

def write_new_to_template(Configuration, filename,Tirific_Template, Variables = ['VROT',
                 'Z0', 'SBR', 'INCL','PA','XPOS','YPOS','VSYS','SDIS','VROT_2',  'Z0_2','SBR_2',
                 'INCL_2','PA_2','XPOS_2','YPOS_2','VSYS_2','SDIS_2'], debug = False):
    with open(filename, 'r') as tmp:
        # Separate the keyword names
        for line in tmp.readlines():
            key = str(line.split('=')[0].strip().upper())
            if key in Variables:
                Tirific_Template[key] = str(line.split('=')[1].strip())
    # If we have written the INCL we need to update the limit modifier
    if 'INCL' in Variables or 'INCL_2' in Variables:
        Inclination = np.array([(float(x)+float(y))/2. for x,y in zip(Tirific_Template['INCL'].split(),Tirific_Template['INCL_2'].split())],dtype=float)
        set_limit_modifier(Configuration,Inclination,debug= debug)
