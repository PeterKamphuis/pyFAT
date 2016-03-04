Pro overview_plot,distance,gdlidl,noise=noise

;+
; NAME:
;       overview_plot
;
; PURPOSE:
;       Create an overview plot to easily see how well the model fits the data.
;
; CATEGORY:
;       Support
; 
; CALLING SEQUENCE:
;       OVERVIEW_PLOT	
;
;
; INPUTS:
;         distance = Distance to the galaxy
;         gdlidl = an indicator whether we are running idl or gdl
; OPTIONAL INPUTS:
;         Noise = the noise in the cube.
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
;       AXIS,COLORMAPS,COLOUR_BAR,COLUMNDENSITY,CONTOUR,DEVICE,FILE_TEST(),LOADCT,MAX(),N_ELEMENTS(),OPLOT,OPLOTERR,PLOT,PLOTERR,READFITS(),SET_PLOT,SHOWPIXELSMAP,WRITENEWTOTEMPLATE,XYOUTS
;
; MODIFICATION HISTORY:
;       Written 20-02-2016 P.Kamphuis v1.0
;
; NOTE:
;     
;-
  arrays=1.
  IF gdlidl then SET_PLOT,'PS' else SET_PLOT, 'Z'
  plotpara=['RADI','SBR','SBR_2','VROT','VROT_ERR','PA','PA_ERR','PA_2','PA_2_ERR','INCL','INCL_ERR','INCL_2','INCL_2_ERR','SDIS','XPOS','YPOS','VSYS']
  plotstart=[[1,3,5,9],[2,3,7,11],[0,1,1,1]]
  Template=1.
  WriteNewToTemplate,Template,'Finalmodel/Finalmodel.def',ARRAYS=Arrays,VARIABLECHANGE=plotpara,/EXTRACT
  IF FILE_TEST('ModelInput.def') then begin
     Writenewtotemplate,Template,'ModelInput.def',ARRAYS=ModArrays,VARIABLECHANGE=plotpara,/EXTRACT
  ENDIF
  varunits=strarr(n_elements(plotpara))
  for i=0,n_elements(plotpara)-1 do begin
     tmp=str_sep(strtrim(strcompress(plotpara[i]),2),'_')
     case tmp[0] of
        'VROT':Varunits[i]='(km s!E-1!N)'
        'SDIS':Varunits[i]='(km s!E-1!N)'
        'PA' :Varunits[i]='(Degrees)'
        'INCL':Varunits[i]='(Degrees)'
        'SBR':Varunits[i]='(Jy km s!E-1!N arcsec!E-2!N)'
        'Z0':Varunits[i]='(Arcsec)'
        else:Varunits[i]=''
     endcase
  endfor
  maxvar=dblarr(4)
  minvar=dblarr(4)
  buffer=dblarr(4)
  minvar[*]=100000
  maxvar[*]=-10000
  for i=0,3 do begin
     tmpvals=[Arrays[*,plotstart[i,0]],Arrays[*,plotstart[i,1]]]
     tmplocs=WHERE(tmpvals NE 0.)
     tmpmax=MAX(tmpvals[tmplocs],MIN=tmpmin)
     IF tmpmax GT Maxvar[i] then Maxvar[i]=tmpmax
     IF tmpmin LT Minvar[i] then Minvar[i]=tmpmin
     buffer[i]=(ABS(Maxvar[i])+ABS(minvar[i]))/20.
  endfor
  RA=double(Arrays[0,n_elements(plotpara)-3])
  DEC=double(Arrays[0,n_elements(plotpara)-2])
  convertradec,RA,DEC
  vsys=strtrim(string(double(Arrays[0,n_elements(plotpara)-1]),format='(F10.1)'),2)
  disper=strtrim(string(double(Arrays[0,n_elements(plotpara)-4]),format='(F10.1)'),2)
  ysize=0.1
  !x.style=1.5
  !y.style=1.5
  !p.charsize=3.7
  !p.thick=6
  !P.FONT=1
  !p.background=0
  thick=2
  scrdim = [8.27*300.,11.69*300]
  A = FIndGen(16) * (!PI*2/16.) 
  UserSym, cos(A), sin(A), /fill
  ssize=1.3
  IF gdlidl then begin
     !p.charsize=0.4
     charthick=0.7
     ssize=0.3
                                ;Currently GDL does not recognize true
                                ;type fonts yet. This leads to errors
                                ;in using the degree symbol. It also
                                ;does not yet recognize superscript
                                ;commands in tickmarks.
     DEVICE,xsize=scrdim[0]/200.,ysize=scrdim[1]/200,FILENAME='Overview.ps',/color,/PORTRAIT,/ENCAPSULATED,SET_FONT='Times', /TT_FONT  
  endif else  $
     DEVICE,SET_FONT='Times',/TT_FONT,SET_RESOLUTION=[scrdim[0],scrdim[1]],DECOMPOSED=0,SET_PIXEL_DEPTH=24
  plotradii=Arrays[*,0]
  tmp=WHERE(Arrays[*,1] GT 1.1E-16)
  tmp2=WHERE(Arrays[*,2] GT 1.1E-16)
  
  maxradii=MAX([plotradii[tmp],plotradii[tmp2]])+(plotradii[n_elements(plotradii)-1]-plotradii[n_elements(plotradii)-2])/2.
  
  for i=0,3 do begin    
     IF i EQ 0 then begin
        
        plotvariable=Arrays[tmp,1]
        loadct,0,/silent
        plot,plotradii,plotVariable,position=[0.15,0.9-4*ysize,0.55,0.9-3*ysize],xtitle='Radius (arcmin)',$
             xrange=[0.,maxradii],yrange=[minvar[i]-buffer[i],maxvar[i]+buffer[i]],ytickname=[' ',' ',' ',' ',' ',' ',' ',' ',' ',' '],xtickname=[' ',' ',' ',' ',' ',' ',' ',' ',' ',' '],xticklayout=1,background=254,color=254
        oplot,plotradii,plotVariable,color=0,linestyle=0,symsize=ssize
        levelsrange=[minvar[i]-buffer[i],maxvar[i]+buffer[i]]*1000.
        oplot,plotradii,plotVariable,psym=8,color=0,linestyle=2,symsize=ssize
        columndensity,levelsrange,Arrays[0,14],[1.,1.],vwidth=1.,/arcsquare
        levelsranges=levelsrange/1e20
        reset=1e20
        levelsranges[0]=ceil(levelsranges[0])
        levelsranges[1]=floor(levelsranges[1])
        adst='x10!E20!N'
        if levelsranges[0] EQ levelsranges[1] then begin
           levelsranges=levelsrange/1e19
           levelsranges[0]=ceil(levelsranges[0])
           levelsranges[1]=floor(levelsranges[1])
           adst='x10!E19!N'
           reset=1e19
        endif
        midrange=levelsranges[0]+(levelsranges[1]-levelsranges[0])/2.
        IF fix(midrange) NE midrange then begin
           levelsranges[1]=levelsranges[1]-1 
           midrange=levelsranges[0]+(levelsranges[1]-levelsranges[0])/2.
        endif
        newlevels=[levelsranges[0],midrange,levelsranges[1]]
        jynewlevels=newlevels*reset
        columndensity,jynewlevels,double(vsys),[1.,1.],vwidth=1.,/NCOLUMN,/arcsquare
        AXIS,YAXIS=0,charthick=charthick,xthick=xthick,ythick=ythick,charsize=charsize,color=0
        AXIS,YAXIS=1,charthick=charthick,xthick=xthick,ythick=ythick,charsize=charsize,ytickv=jynewlevels/1000.,ytickname=[strtrim(strcompress(string(newlevels[0],format='(I3)')),2),strtrim(strcompress(string(fix(newlevels[1]),format='(I2)')),2),strtrim(strcompress(string(fix(newlevels[2]),format='(I2)')),2)],yticks=2,yminor=3,color=0
        XYOUTs,0.60,0.9-3.5*ysize,'N!IH',/NORMAL,alignment=0.5,ORIENTATION=90, CHARTHICK=charthick,charsize=!p.charsize*1.25,color=0
        XYOUTs,0.63,0.9-3.5*ysize,'('+adst+' cm!E-2!N)' ,/NORMAL,alignment=0.5,ORIENTATION=90, CHARTHICK=charthick,charsize=charsize,color=0
        AXIS,XAXIS=0,charthick=charthick,xthick=xthick,ythick=ythick,charsize=charsize,color=0 ,XTITLE='Radius (arcsec)'
        AXIS,XAXIS=1,charthick=charthick,xthick=xthick,ythick=ythick,charsize=charsize,XRANGE = convertskyanglefunction(!X.CRANGE,distance),xtickname=[' ',' ',' ',' ',' ',' ',' ',' ',' ',' '],color=0 
        loadct,40,/silent
        oplot,plotradii,Arrays[tmp2,2],thick=lthick,color=254,linestyle=2
        oplot,plotradii,Arrays[tmp2,2],psym=8,color=254,linestyle=2,symsize=ssize
        XYOUTs,0.05,0.9-3.5*ysize,plotpara[plotstart[i,0]],/NORMAL,alignment=0.5,ORIENTATION=90,charsize=!p.charsize*1.25,color=0,charthick=charthick
        XYOUTs,0.08,0.9-3.5*ysize,varunits[plotstart[i,0]],/NORMAL,alignment=0.5,ORIENTATION=90,color=0,charthick=charthick
        
        IF FILE_TEST('ModelInput.def') then begin
           oplot,ModArrays[*,0],ModArrays[*,1],thick=lthick,color=54
           oplot,ModArrays[*,0],ModArrays[*,1],psym=8,color=54,symsize=ssize
           oplot,ModArrays[*,0],ModArrays[*,2],thick=lthick,color=204,linestyle=2
           oplot,ModArrays[*,0],ModArrays[*,2],psym=8,color=204,linestyle=2,symsize=ssize
        ENDIF
     ENDIF ELSE begin
        plotvariable=Arrays[tmp,plotstart[i,0]]
        plotVariableErr=Arrays[tmp,plotstart[i,0]+plotstart[i,2]]
        loadct,0,/silent
        IF TOTAL(plotVariableErr) NE 0. then begin
           xerr=dblarr(n_elements(plotVariableErr))
           ploterror,plotradii,plotVariable,xerr,plotVariableErr,position=[0.15,0.9-(4-i)*ysize,0.55,0.9-(3-i)*ysize],$
                     xrange=[0.,maxradii],yrange=[minvar[i]-buffer[i],maxvar[i]+buffer[i]],xthick=xthick,ythick=ythick,xtickname=[' ',' ',' ',' ',' ',' ',' ',' ',' ',' '],xticklayout=1,charthick=charthick,thick=thick,charsize=charsize,linestyle=0,$
                     /noerase,color=0,ERRCOLOR = 0, ERRTHICK=!p.thick*0.4
        ENDIF ELSE BEGIN
           plot,plotradii,plotVariable,position=[0.15,0.9-(4-i)*ysize,0.55,0.9-(3-i)*ysize],$
                xrange=[0.,maxradii],yrange=[minvar[i]-buffer[i],maxvar[i]+buffer[i]],xthick=xthick,ythick=ythick,xtickname=[' ',' ',' ',' ',' ',' ',' ',' ',' ',' '],xticklayout=1,charthick=charthick,thick=thick,charsize=charsize,linestyle=0,$
                /noerase,color=0
        ENDELSE
        oplot,plotradii,plotVariable,psym=8,color=0,linestyle=2,symsize=ssize
        IF i EQ 3 then begin
           AXIS,XAXIS=1,charthick=charthick,xthick=xthick,ythick=ythick,charsize=charsize,XRANGE = convertskyanglefunction(!X.CRANGE,distance),XTITLE='Radius (kpc)',color=0 
        endif else begin
           AXIS,XAXIS=1,charthick=charthick,xthick=xthick,ythick=ythick,charsize=charsize,XRANGE = convertskyanglefunction(!X.CRANGE,distance),xtickname=[' ',' ',' ',' ',' ',' ',' ',' ',' ',' '],color=0 
        endelse
        XYOUTs,0.05,0.9-(3.5-i)*ysize,plotpara[plotstart[i,0]],/NORMAL,alignment=0.5,ORIENTATION=90,charsize=!p.charsize*1.25,color=0,charthick=charthick
        XYOUTs,0.08,0.9-(3.5-i)*ysize,varunits[plotstart[i,0]],/NORMAL,alignment=0.5,ORIENTATION=90,color=0,charthick=charthick
        loadct,40,/silent
        IF plotstart[i,0] NE plotstart[i,1] then begin
           plotvariable=Arrays[tmp2,plotstart[i,1]]
           plotVariableErr=Arrays[tmp2,plotstart[i,1]+plotstart[i,2]]          
           IF TOTAL(plotVariableErr) NE 0. then begin
              xerr=dblarr(n_elements(plotVariableErr))
              oploterror,plotradii,plotVariable,xerr,plotVariableErr,thick=lthick,color=254,linestyle=2,ERRCOLOR = 254, ERRTHICK=!p.thick*0.4
           ENDIF ELSE BEGIN
              oplot,plotradii,plotVariable,thick=lthick,color=254,linestyle=2
           ENDELSE
           oplot,plotradii,plotVariable,psym=8,color=254,linestyle=2,symsize=ssize
        ENDIF
        IF FILE_TEST('ModelInput.def') then begin
           oplot,ModArrays[*,0],ModArrays[*,plotstart[i,0]],thick=lthick,color=54
           oplot,ModArrays[*,0],ModArrays[*,plotstart[i,0]],psym=8,color=54,symsize=ssize
           IF plotstart[i,0] NE plotstart[i,1] then begin
              oplot,ModArrays[*,0],ModArrays[*,plotstart[i,1]],thick=lthick,color=204,linestyle=2
              oplot,ModArrays[*,0],ModArrays[*,plotstart[i,1]],psym=8,color=204,linestyle=2,symsize=ssize
           ENDIF
        ENDIF
     ENDELSE
  endfor
  IF FILE_TEST('ModelInput.def') then begin
     RAmod=double(ModArrays[0,n_elements(plotpara)-3])
     DECmod=double(ModArrays[0,n_elements(plotpara)-2])
     convertradec,RAmod,DECmod
     vsysmod=strtrim(string(double(ModArrays[0,n_elements(plotpara)-1]),format='(F10.1)'),2)
     dispermod=strtrim(string(double(ModArrays[0,n_elements(plotpara)-4]),format='(F10.1)'),2)
     XYOUTS,0.60,0.89,'Systemic Velocity= '+vsys+' ('+vsysmod+') km s!E-1',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.87,'R.A.= '+RA+' ('+RAmod+')',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.85,'DEC.= '+DEC+' ('+DECmod+')',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.83,'Dispersion= '+disper+' ('+dispermod+') km s!E-1',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.81,'Black lines: approaching side parameters.',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.79,'Red lines: receding side parameters.',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.77,'Blue lines: approaching side input model parameters.',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.75,'Yellow lines: receding side input model parameters.',/normal,alignment=0.,charthick=charthick
  ENDIF ELSE BEGIN
     XYOUTS,0.60,0.89,'Systemic Velocity= '+vsys+' km s!E-1',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.87,'R.A.= '+RA,/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.85,'DEC.= '+DEC,/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.83,'Dispersion= '+disper+' km s!E-1',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.81,'Black lines: approaching side parameters.',/normal,alignment=0.,charthick=charthick
     XYOUTS,0.60,0.79,'Red lines: receding side parameters.',/normal,alignment=0.,charthick=charthick
  ENDELSE
                                ;Currently GDL does not recognize true
                                ;type fonts yet. This leads to errors
                                ;in using the degree symbol. It also
                                ;does not yet recognize superscript
                                ;commands in tickmarks.
  spawn,'ls -1 Moments/*6.0_mom0*.fits',mom0name
  mom0=readfits(mom0name,mom0hed,/SILENT)
  mom0mod=readfits('Moments/FinalModel_mom0.fits',mom0hedmod,/SILENT)
  mapmax=MAX(mom0,min=mapmin)
  buildaxii,mom0hed,xaxis,yaxis
  colormaps,'heat'
  showpixelsmap,xaxis,yaxis,mom0,position=[0.15,0.1,0.35,0.1+0.2*scrdim[0]/scrdim[1]],/WCS, xtitle='RA (J2000)',ytitle='DEC (J2000)',BLANK_VALUE=0.,range=[0.,mapmax],/NOERASE,charthick=charthick,thick=thick
  levels=[1E20, 2E20, 4E20, 8E20,16E20,32E20]
  beam=[sxpar(mom0hed,'BMAJ')*3600.,sxpar(mom0hed,'BMIN')*3600.]
  columndensity,levels,double(vsys),beam,vwidth=1.,/NCOLUMN
  levels=levels/1000.
  loadct,0,/SILENT
  Contour,mom0,xaxis,yaxis,levels=levels,/overplot,c_colors=[0]
  Contour,mom0mod,xaxis,yaxis,levels=levels,/overplot,c_colors=[254]
  colormaps,'heat'
  colour_bar,[0.37,0.39],[0.12,0.1+0.2*scrdim[0]/scrdim[1]-0.02],strtrim(string(0,format='(F10.1)'),2),strtrim(string(mapmax,format='(F10.1)'),2),/OPPOSITE_LABEL,/BLACK,TITLE='(Jy bm!E-1!N x km s!E-1!N)',/VERTICAL,charthick=charthick
  loadct,0,/SILENT
  XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1],'Velocity Field, Moment0 and PV-Diagram along the major axis.',color=0,/normal,charthick=charthick
  XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1]-0.02,'Black Contours: Data, White Contours: Final Model',color=0,/normal,charthick=charthick
  XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1]-0.04,'Moment 0 Contours are at 1, 2, 4, 8, 16, 32 x 10!E20!N cm!E-2',color=0,/normal,charthick=charthick

;Velocity Field
  spawn,'ls -1 Moments/*6.0_mom1*.fits',mom0name
  mom0=readfits(mom0name,mom0hed,/SILENT)
  mom0mod=readfits('Moments/FinalModel_mom1.fits',mom0hedmod,/SILENT)
  tmp=WHERE(FINITE(mom0mod))
  mapmax=MAX(mom0mod[tmp],min=mapmin)
  buildaxii,mom0hed,xaxis,yaxis
  colormaps,'sauron_colormap'
  showpixelsmap,xaxis,yaxis,mom0,position=[0.15,0.1+0.2*scrdim[0]/scrdim[1],0.35,0.1+0.4*scrdim[0]/scrdim[1]],/WCS,ytitle='DEC (J2000)',BLANK_VALUE=0.,range=[mapmin,mapmax],/NOERASE,charthick=charthick,thick=thick,xtickname=[' ',' ',' ',' ',' ',' ',' ',' ',' ',' ']
  IF mapmax-mapmin LT 100 then levels=(findgen(20)+1)*10.+mapmin else levels=(findgen(30)+1)*25.+mapmin
  loadct,0,/SILENT
  Contour,mom0,xaxis,yaxis,levels=levels,/overplot,c_colors=[0]
  Contour,mom0mod,xaxis,yaxis,levels=levels,/overplot,c_colors=[254]
  colormaps,'sauron_colormap'
  colour_bar,[0.37,0.39],[0.1+0.2*scrdim[0]/scrdim[1]+0.02,0.1+0.4*scrdim[0]/scrdim[1]-0.02],strtrim(string(mapmin,format='(I10)'),2),strtrim(string(mapmax,format='(I10)'),2),/OPPOSITE_LABEL,/BLACK,TITLE='(km s!E-1!N)',/VERTICAL,charthick=charthick
  loadct,0,/SILENT
  IF mapmax-mapmin LT 100 then begin
     XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1]-0.06,'Velocity Field Contours start at '+strtrim(string(mapmin+10.,format='(I10)'),2)+' km s!E-1!N and increase with 10 km s!E-1!N.',color=0,/normal,charthick=charthick
  ENDIF ELSE BEGIN
     XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1]-0.06,'Velocity Field Contours start at '+strtrim(string(mapmin+25.,format='(I10)'),2)+' km s!E-1!N and increase with 25 km s!E-1!N.',color=0,/normal,charthick=charthick
  ENDELSE
  
;PV Diagram along major axis
  spawn,'ls -1 PV-Diagrams/*_[0-2]_xv.fits',mom0name
  mom0=readfits(mom0name[n_elements(mom0name)-1],mom0hed,/SILENT)
  mom0mod=readfits('PV-Diagrams/FinalModel_xv.fits',mom0hedmod,/SILENT)
  mapmax=MAX(mom0,min=mapmin)
  buildaxii,mom0hed,xaxis,yaxis
  colormaps,'heat'
  showpixelsmap,xaxis*3600.,yaxis,mom0,position=[0.65,0.1+0.2*scrdim[0]/scrdim[1],0.85,0.1+0.4*scrdim[0]/scrdim[1]], xtitle='Offset (arcsec)',ytitle='Velocity (km s!E-1!N)',BLANK_VALUE=0.,range=[mapmin,mapmax],/NOERASE,charthick=charthick,thick=thick
  if n_elements(noise) LT 1 then noise=STDDEV(mom0[0:10,0:10])
  levels=[1,2,4,8,16,32,64,128]*1.5*noise
  levelsneg=([-2,-1])*1.5*noise
  loadct,0,/SILENT
  Contour,mom0,xaxis*3600.,yaxis,levels=levels,/overplot,c_colors=[0]
  Contour,mom0,xaxis*3600,yaxis,levels=levelsneg,/overplot,c_colors=[100],c_linestyle=2
  Contour,mom0mod,xaxis*3600,yaxis,levels=levels,/overplot,c_colors=[254]
  colormaps,'heat'
  colour_bar,[0.87,0.89],[0.1+0.2*scrdim[0]/scrdim[1]+0.02,0.1+0.4*scrdim[0]/scrdim[1]-0.02],strtrim(string(mapmin,format='(F10.4)'),2),strtrim(string(mapmax,format='(F10.4)'),2),/OPPOSITE_LABEL,/BLACK,TITLE='(Jy bm!E-1!N)',/VERTICAL,charthick=charthick
  loadct,0,/SILENT
  XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1]-0.08,'PV-Diagram Contours start are at -3, -1.5, 1.5, 3, 6, 12, 24 x rms.',color=0,/normal,charthick=charthick
  XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1]-0.1,'rms = '+strtrim(string(noise,format='(F10.5)'),2)+' Jy bm!E-1!N.',color=0,/normal,charthick=charthick
  XYOUTS,0.45,0.01+0.2*scrdim[0]/scrdim[1]-0.12,'The distance used for conversions = '+strtrim(string(Distance,format='(F10.1)'),2)+' Mpc',color=0,/normal,charthick=charthick
  IF ~(gdlidl) then image = tvrd(true=1)
  DEVICE,/CLOSE  
  IF ~(gdlidl) then  write_png,'Overview.png',image
end
