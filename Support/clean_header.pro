Pro clean_header,header,writecube,beam,log=log,catalogue=outputcatalogue,directory=dir

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
;       header = the header of the cube
;    writecube = trigger to determine whether the cube is modified and
;                we should write it back to disk. (0=no, 1=yes)
;          log = the logging file
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
; OPTIONAL OUTPUTS:
;       -
; 
; PROCEDURES CALLED:
;       SXPAR(),SXDELPAR(),SXADDPAR(),STRUPCASE()
;
; EXAMPLE:
;      
;
; MODIFICATION HISTORY:
;       Written 04-01-2016 P.Kamphuis v1.0
;
; NOTE:
;     
;-

  howmanyaxis=sxpar(header,'NAXIS')
  writecube=0
  IF howmanyaxis GT 3 then begin
     sxaddpar,header,'NAXIS',3
                                ;whenever we change something we want to rewrite the cube
     writecube=1
  ENDIF
  IF sxpar(header,'NAXIS4') then begin
     sxdelpar,header,'NAXIS4'
     writecube=1
  ENDIF
 
  channelwidth=ABS(sxpar(header,'CDELT3'))   
  veltype=strtrim(strcompress(sxpar(header,'CUNIT3')))
  IF STRUPCASE(veltype) EQ 'HZ' then begin
     IF size(log,/TYPE) EQ 7 then begin
        openu,66,log,/APPEND
        printf,66,linenumber()+'CLEAN_HEADER: FREQUENCY IS NOT A SUPPORTED VELOCITY AXIS.'          
        close,66
     ENDIF ELSE BEGIN
        print,linenumber()+'CLEAN_HEADER: FREQUENCY IS NOT A SUPPORTED VELOCITY AXIS.'    
     ENDELSE
     openu,1,outputcatalogue,/APPEND
     printf,1,format='(A60,A90)', Dir,'The Cube has frequency as a velocity axis this is not supported'
     close,1
     writecube=2  
  ENDIF
  IF isnumeric(veltype) then begin
     IF channelwidth GT 100. then begin
        veltype='M/S'
        sxaddpar,header,'CUNIT3','M/S',after='CDELT3'
        writecube=1
     endif else begin 
        veltype='KM/S'
        sxaddpar,header,'CUNIT3','KM/S',after='CDELT3'
        writecube=1
     endelse
     IF size(log,/TYPE) EQ 7 then begin
        openu,66,log,/APPEND
        printf,66,linenumber()+'CLEAN_HEADER: Your header did not have a unit for the third axis, that is bad policy.'          
        printf,66,linenumber()+'CLEAN_HEADER: We have set it to '+veltype+'. Please ensure that is correct.'          
        close,66
     ENDIF ELSE BEGIN
        print,linenumber()+'CLEAN_HEADER: Your header did not have a unit for the third axis, that is bad policy.'          
        print,linenumber()+'CLEAN_HEADER: We have set it to '+veltype+'. Please ensure that is correct.'     
     ENDELSE
  ENDIF
  velproj=sxpar(header,'CTYPE3')
  IF STRUPCASE(strtrim(velproj,2)) NE 'VELO-HEL' AND $
     STRUPCASE(strtrim(velproj,2)) NE 'VELO-LSR' AND $
     STRUPCASE(strtrim(velproj,2)) NE 'FELO-HEL' AND $
     STRUPCASE(strtrim(velproj,2)) NE 'FELO-LSR' AND $
     STRUPCASE(strtrim(velproj,2)) NE 'VELO' AND $
     STRUPCASE(strtrim(velproj,2)) NE 'FREQ' then begin
     sxaddpar,header,'CTYPE3','VELO',after='CUNIT3'
     writecube=1
     IF size(log,/TYPE) EQ 7 then begin
        openu,66,log,/APPEND
        printf,66,linenumber()+'CLEAN_HEADER: Your velocity projection is not standard. The keyword is changed to VELO (relativistic definition). This might be dangerous.'          
        close,66
     ENDIF ELSE BEGIN
        print,linenumber()+'CLEAN_HEADER: Your velocity projection is not standard. The keyword is changed to VELO (relativistic definition). This might be dangerous.'   
     ENDELSE
  ENDIF
  IF STRUPCASE(veltype) EQ 'KM/S' then begin
     IF size(log,/TYPE) EQ 7 then begin
        openu,66,log,/APPEND
        printf,66,linenumber()+'CLEAN_HEADER: The channels in your input cube are in km/s. This sometimes leads to problems with wcs lib, hence we change it to m/s.'          
        close,66
     ENDIF ELSE BEGIN
        printf,66,linenumber()+'CLEAN_HEADER: The channels in your input cube are in km/s. This sometimes leads to problems with wcs lib, hence we change it to m/s.'   
     ENDELSE
     sxaddpar,header,'CDELT3',sxpar(header,'CDELT3')*1000.
     sxaddpar,header,'CRVAL3',sxpar(header,'CRVAL3')*1000.
     sxaddpar,header,'CUNIT3','M/S'
  ENDIF
                                ;Let's check for presence of the beam in the header. IF present
                                ;supersede the input. !!!!Be careful with smoothed data. If not let's add
                                ;it from the file; This is important if you do it incorrectly the
                                ;pipeline will use a incorrect pixel size.
                                ;   writecube=0
  IF NOT sxpar(header,'BMAJ') then begin
     IF sxpar(header,'BMMAJ') then begin
        sxaddpar,header,'BMAJ',sxpar(header,'BMMAJ')/3600.
         writecube=1
     endif else begin
        IF size(log,/TYPE) EQ 7 then begin
           openu,66,log,/APPEND
           printf,66,linenumber()+'CLEAN_HEADER: WE CANNOT FIND THE MAJOR AXIS FWHM IN THE HEADER'          
           close,66
        ENDIF ELSE BEGIN
           print,linenumber()+'CLEAN_HEADER: WE CANNOT FIND THE MAJOR AXIS FWHM IN THE HEADER'   
        ENDELSE
        openu,1,outputcatalogue,/APPEND
        printf,1,format='(A60,A90)', Dir,'The Cube has no major axis FWHM in the header.'
        close,1
        writecube=2
        goto,finishup
     ENDELSE
    
  ENDIF 
  IF NOT sxpar(header,'BMIN') then begin
     IF sxpar(header,'BMMIN') then begin
        sxaddpar,header,'BMIN',sxpar(header,'BMMIN')/3600.
        writecube=1
     endif else begin
        IF sxpar(header,'BMAJ') then begin
           sxaddpar,header,'BMIN', sxpar(header,'BMAJ')
           writecube=1
           IF size(log,/TYPE) EQ 7 then begin
              openu,66,log,/APPEND
              printf,66,linenumber()+'CLEAN_HEADER: We cannot find the minor axis FWHM. Assuming a circular beam.'          
              close,66
           ENDIF ELSE BEGIN
              print,linenumber()+'CLEAN_HEADER: We cannot find the minor axis FWHM. Assuming a circular beam.'
           ENDELSE
        ENDIF ELSE BEGIN
           IF size(log,/TYPE) EQ 7 then begin
              openu,66,log,/APPEND
              printf,66,linenumber()+'CLEAN_HEADER: WE CANNOT FIND THE MINOR AXIS FWHM IN THE HEADER'          
              close,66
           ENDIF ELSE BEGIN
              print,linenumber()+'CLEAN_HEADER: WE CANNOT FIND THE MINOR AXIS FWHM IN THE HEADER'   
           ENDELSE
           
        ENDELSE
     ENDELSE
  ENDIF
  beam=[sxpar(header,'BMAJ')*3600,sxpar(header,'BMIN')*3600.]
  finishup:
end