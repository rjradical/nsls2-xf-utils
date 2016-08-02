#! /usr/bin/env /usr/bin/python2.7
#original gjw
#modified 2015/03/02 by ycchen, Wayne fixed the SSA blades PV names' assignment. Updated those PV names.

import signal
import sys
import os
import time
from epics import PV
import math
from optparse import OptionParser
import string
import decimal
import matplotlib.pyplot as plt
import numpy as np

#can we signal handle in python??
def sigint_handler(signal,frame):
    global simulate
    global fp
    if simulate != True:
        fp.close()
        print "!!!!!!!!!    stopped"
    else:
        print "Ctrl-C detected...exiting"
    sys.exit()
signal.signal(signal.SIGINT,sigint_handler)

simulate=False
dbd=0.0001

#target array:  (xpos, at_position)(ypos, at_position)
tar = []
tar.append([])
tar[0].append(0.)
tar[0].append(1)
tar.append([])
tar[1].append(0.)
tar[1].append(1)

global shut_open
shut_open = False
global current
current = False

def cbfx(pvname=None,value=None,char_value=None,type=None,enum_strs=None,**kw):
    if indeadband(float(tar[0][0]),float(value),dbd)==1:
        tar[0][1] = 0
    else:
        tar[0][1] = 1
def cbfy(pvname=None,value=None,char_value=None,type=None,enum_strs=None,**kw):
    if indeadband(float(tar[1][0]),float(value),dbd)==1:
        tar[1][1] = 0
    else:
        tar[1][1] = 1
def indeadband(com,act,dbd):
    if math.fabs(math.fabs(com)-math.fabs(act))<float(dbd):
        return 1
    else:
        return 0
def cbf_shut(pvname=None,value=None,char_value=None,type=None,enum_strs=None,**kw):
    global shut_open
    if value==1:
        shut_open=True
    else:
        shut_open=False
def cbf_curr(pvname=None,value=None,char_value=None,type=None,enum_strs=None,**kw):
    global current
    if value<1.:
        current=False
    else:
        current=True

def main(argv=None):
    global simulate
    global fp
    global shut_open
    global current

    #parse command line options
    usage = "usage: %prog [options]\nData files are written to /data/<year>/<month>/<day>/"
    parser = OptionParser(usage)
    parser.add_option("--detname", action="store", type="string", dest="detname", help="detector PV base")
    parser.add_option("--xstart", action="store", type="float", dest="xo", help="starting X position")
    parser.add_option("--xnumstep", action="store", type="int", dest="Nx", help="number of steps in X")
    parser.add_option("--xstepsize", action="store", type="float", dest="dx", help="step size in X")
    parser.add_option("--ystart", action="store", type="float", dest="yo", help="starting Y position")
    parser.add_option("--ynumstep", action="store", type="int", dest="Ny", help="number of steps in Y")
    parser.add_option("--ystepsize", action="store", type="float", dest="dy", help="step size in Y")
    parser.add_option("--wait", action="store", type="float", dest="stall", help="wait at each step [seconds]")
    parser.add_option("--simulate", action="store_true", dest="sim", default=False, help="simulate motor moves")
    parser.add_option("--checkbeam", action="store_true", dest="checkbeam", default=False, help="only acquire when beam is on")
    parser.add_option("--acqtime", action="store", type="float", dest="acqt", help="image integration time [sec]")

    (options,args) = parser.parse_args()

    #open log file
    D0=time.localtime()[0]
    D1=time.localtime()[1]
    D2=time.localtime()[2]
    D3=time.localtime()[3]
    D4=time.localtime()[4]
    cd=os.getcwd()
    
    filedir = '/nfs/xf05id1/data/' 
    
    if sys.argv[0][0]=='.':
        out_filename=filedir+repr(D0)+'/'+repr(D1)+'/'+repr(D2)+'/'+'log_'+repr(D3)+'_'+repr(D4)+'_'+\
         string.split(string.strip(sys.argv[0],'./'),'/')[0]+'.txt'
    else:
        out_filename=filedir+repr(D0)+'/'+repr(D1)+'/'+repr(D2)+'/'+'log_'+repr(D3)+'_'+repr(D4)+'_'+\
         string.split(string.strip(sys.argv[0],'./'),'/')[5]+'.txt'
    try:
        os.chdir(filedir+repr(D0))
    except OSError:
        try:    
            os.mkdir(filedir+repr(D0))
        except Exception:
            print 'cannot create directory: '+'/data/'+repr(D0)
            sys.exit()

    try:
        os.chdir(filedir+repr(D0)+'/'+repr(D1))
    except OSError:
        try:
            os.mkdir(filedir+repr(D0)+'/'+repr(D1))
        except Exception:
            print 'cannot create directory: '+'/data/'+repr(D0)+'/'+repr(D1)
            sys.exit()
    try:
        os.chdir(filedir+repr(D0)+'/'+repr(D1)+'/'+repr(D2))
    except OSError:
        try:
            os.mkdir(filedir+repr(D0)+'/'+repr(D1)+'/'+repr(D2))
        except Exception:
            print 'cannot create directory: '+filedir+repr(D0)+'/'+repr(D1)+'/'+repr(D2)
            sys.exit()
    try:
        fp=open(out_filename,'a')
    except Exception:
        print 'cannot open file: '+out_filename
        sys.exit()
    os.chdir(cd)
    fp.write('#'+', '.join(sys.argv))
    fp.write('\n')
    H5path='/epics/data/201507/300126'
    #initialize PVs and callbacks
    if options.detname == None:
#       detstr='XF:03IDA-BI{FS:1-CAM:1}'
        detstr=''
        print "must provide detector pv base, e.g., 'XF:28IDA-BI{URL:01}'"
        sys.exit()
    else:
        detstr=options.detname
    xmotname='XF:05IDD-ES:1{Stg:Smpl1-Ax:X}'
    ymotname='XF:05IDD-ES:1{Stg:Smpl1-Ax:Y}'
    xmot=PV(xmotname+'Mtr.VAL')
    xmot_cur=PV(xmotname+'Mtr.RBV')
    ymot=PV(ymotname+'Mtr.VAL')
    ymot_cur=PV(ymotname+'Mtr.RBV')
    shut_status=PV('SR:C05-EPS{PLC:1}Shutter:Sum-Sts')
    beam_current=PV('SR:C03-BI{DCCT:1}I:Total-I')
    #transmission
    #check command line options
    if options.yo == None:
        print "must provide a starting point in the vertical"
        sys.exit()
    else:   
        yo = options.yo
    if options.xo == None:
        print "must provide a starting point in the horizontal"
        sys.exit()
    else:   
        xo = options.xo
    if options.dx == None:
        dx = 0.00000001
    else:
        dx = options.dx
    if options.dy == None:
        dy = 0.00000001
    else:
        dy = options.dy
    if options.Nx == None:
        Nx = 0
    else:
        Nx = options.Nx
    if options.Ny == None:
        Ny = 0
    else:
        Ny = options.Ny
    if options.stall == None:
        twait = 0.
    else:
        twait = options.stall
    diode0=PV(detstr+'Cur:I0-I')
    diode1=PV(detstr+'Cur:I1-I')
    diode2=PV(detstr+'Cur:I2-I')
    diode3=PV(detstr+'Cur:I3-I')

    x3acq=PV('XSPRESS3-EXAMPLE:Acquire')
    x3erase=PV('XSPRESS3-EXAMPLE:ERASE')
    x3acqtime=PV('XSPRESS3-EXAMPLE:AcquireTime')
    x3acqnum=PV('XSPRESS3-EXAMPLE:NumImages')
    x3tmode=PV('XSPRESS3-EXAMPLE:TriggerMode')
    x3h5path=PV('XSPRESS3-EXAMPLE:HDF5:FilePath')
    x3h5fname=PV('XSPRESS3-EXAMPLE:HDF5:FileName')
    x3h5fnum=PV('XSPRESS3-EXAMPLE:HDF5:FileNumber')
    x3h5capture=PV('XSPRESS3-EXAMPLE:HDF5:Capture')
    #report ROIs for channels and counts at each point
    x3ch1roi0min=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI1_LLM')
    x3ch1roi0max=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI1_HLM')
    x3ch1roi0ct=PV('XSPRESS3-EXAMPLE:C1_ROI1:Value_RBV')
    x3ch1roi1min=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI2_LLM')
    x3ch1roi1max=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI2_HLM')
    x3ch1roi1ct=PV('XSPRESS3-EXAMPLE:C1_ROI2:Value_RBV')
    x3ch1roi2min=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI3_LLM')
    x3ch1roi2max=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI3_HLM')
    x3ch1roi2ct=PV('XSPRESS3-EXAMPLE:C1_ROI3:Value_RBV')
    x3ch2roi0min=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI1_LLM')
    x3ch2roi0max=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI1_HLM')
    x3ch2roi0ct=PV('XSPRESS3-EXAMPLE:C2_ROI1:Value_RBV')
    x3ch2roi1min=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI2_LLM')
    x3ch2roi1max=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI2_HLM')
    x3ch2roi1ct=PV('XSPRESS3-EXAMPLE:C2_ROI2:Value_RBV')
    x3ch2roi2min=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI3_LLM')
    x3ch2roi2max=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI3_HLM')
    x3ch2roi2ct=PV('XSPRESS3-EXAMPLE:C2_ROI3:Value_RBV')
    x3ch3roi0min=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI1_LLM')
    x3ch3roi0max=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI1_HLM')
    x3ch3roi0ct=PV('XSPRESS3-EXAMPLE:C3_ROI1:Value_RBV')
    x3ch3roi1min=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI2_LLM')
    x3ch3roi1max=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI2_HLM')
    x3ch3roi1ct=PV('XSPRESS3-EXAMPLE:C3_ROI2:Value_RBV')
    x3ch3roi2min=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI3_LLM')
    x3ch3roi2max=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI3_HLM')
    x3ch3roi2ct=PV('XSPRESS3-EXAMPLE:C3_ROI3:Value_RBV')


    #claim ROI 4 for our own use.  we will integrate over all 4096 channels.
    x3ch1roi3min=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI4_LLM')
    x3ch1roi3max=PV('XSPRESS3-EXAMPLE:C1_MCA_ROI4_HLM')
    x3ch1roi3ct=PV('XSPRESS3-EXAMPLE:C1_ROI4:Value_RBV')
    x3ch2roi3min=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI4_LLM')
    x3ch2roi3max=PV('XSPRESS3-EXAMPLE:C2_MCA_ROI4_HLM')
    x3ch2roi3ct=PV('XSPRESS3-EXAMPLE:C2_ROI4:Value_RBV')
    x3ch3roi3min=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI4_LLM')
    x3ch3roi3max=PV('XSPRESS3-EXAMPLE:C3_MCA_ROI4_HLM')
    x3ch3roi3ct=PV('XSPRESS3-EXAMPLE:C3_ROI4:Value_RBV')

    xmot_cur.get()
    ymot_cur.get()

    norm0=PV('XF:05IDD-BI:1{BPM:01}.S20')
    norm1=PV('XF:05IDD-BI:1{BPM:01}.S21')
    norm2=PV('XF:05IDD-BI:1{BPM:01}.S22')
    norm3=PV('XF:05IDD-BI:1{BPM:01}.S23')

    xmot_cur.add_callback(cbfx)
    ymot_cur.add_callback(cbfy)
    shut_status.add_callback(cbf_shut)
    beam_current.add_callback(cbf_curr)
    xmot_cur.run_callbacks()
    ymot_cur.run_callbacks()
    shut_status.run_callbacks()
    beam_current.run_callbacks()

    x3h5path.put(H5path)
    x3h5fname.put(repr(D3)+'_'+repr(D4)+'_')
    x3h5fnum.put(0)
    x3acqtime.put(options.acqt)
    x3acqnum.put(1)
    x3tmode.put(1)

    x3ch1roi3min.put(0)
    x3ch2roi3min.put(0)
    x3ch3roi3min.put(0)
    x3ch1roi3max.put(4096)
    x3ch2roi3max.put(4096)
    x3ch3roi3max.put(4096)
    str='#Start time is '+time.asctime()
    print str
    fp.write(str)
    fp.write('\n')
    str='#[point #]\tX pos\tY pos\tch 1\tch 2\tch 3\tch 4\tBPM1\troi0\troi1\troi2\troi3\ttime'
    print str
    fp.write(str)
    fp.write('\n')
    str='# x: %(hs)6.4f ; y: %(vs)6.4f ; ROI1 %(roi1i)d:%(roi1a)d ; ROI2 %(roi2i)d:%(roi2a)d ; ROI3 %(roi3i)d:%(roi3a)d'%\
     {"hs":xmot_cur.get(),"vs":ymot_cur.get(), 'roi1i':x3ch1roi1min.get(), 'roi1a':x3ch1roi1max.get(), 'roi2i':x3ch1roi2min.get(), 'roi2a':x3ch1roi2max.get(), 'roi3i':x3ch1roi3min.get(), 'roi3a':x3ch1roi3max.get(),}
    print str
    fp.write(str)
    fp.write('\n')
    roits=x3ch3roi3ct.timestamp
    if options.sim is True:
        str="      -----simulating motor moves and bursts-----"
        print str
        fp.write(str)
        fp.write('\n')
    time.sleep(2)

    #number of rows and columns completed by scan
    Ncol=Nrow=0
    LN=0

    #diode readback is now limiting factor for scan speed
    oldsig=0.
    #when the cryocooler kicks in, the beam is unusable for ~3200sec
    cryo=PV('XF:05IDA-OP:1{Mono:HDCM}T:LN2Out-I')
    ct=cryo.get()
    while( ct is None):
        time.sleep(0.05)
        ct=cryo.get()
    t0=time.time()
    cryocounter=0
    shut_toggle=False

    #nested loops for scanning z,x,y
    for y in np.linspace(yo,yo+((Ny)*dy),Ny+1):
        tar[1][0]=y
        tar[1][1]=1
        if options.sim is False:
            ymot.put(tar[1][0])
        if indeadband(float(tar[1][0]),float(ymot_cur.get()),dbd)==1:
            tar[1][1] = 0
        if Nrow%2==0:
            xs=0.+xo
            xe=((Nx+1)*dx)+xo-dx
            xi=dx
        else:
            xs=((Nx)*dx)+xo
            xe=0.+xo
            xi=-dx
        for x in np.linspace(xs,xe,Nx+1):
            tar[0][0]=x
            tar[0][1]=1
            if indeadband(float(tar[0][0]),float(xmot_cur.get()),dbd)==1:
                tar[0][1]=0
            if options.sim is False:
                xmot.put(tar[0][0])
                while ((tar[0][1] == 1) or (tar[1][1] == 1)):
                    time.sleep(0.01)
            signal0=signal1=signal2=signal3=0.
            nsig0=nsig1=nsig2=nsig3=0.
            sig0=sig1=sig2=sig3=0.
            time.sleep(twait)
            while ( options.checkbeam and (cryo.get() < (ct - 0.1)) ):
                    print "Stopped.  Detected possible cryocooler activation."
                    time.sleep(1)
                    cryocounter=cryocounter+1
            #if the above is true for five cycles, the cryocooler was on, wait another 10min
            if ( options.checkbeam and cryocounter > 300 ):
                print "Detected cryocooler activation, waiting 10min"
                time.sleep(600)
                cryocounter=0
            while ( options.checkbeam and (shut_open == False or beam_current == False)):
                print "Stopped.  Waiting for scan conditions to return to normal."
                if shut_open==False:
                    shut_toggle=True
                time.sleep(10.)
            if shut_toggle==True:
                print "Entering optics conditioning period.  Waiting 5min"
                time.sleep(300)
                shut_toggle=False
            if options.sim is False:
                x3h5capture.put(1)
                x3erase.put(1)
                x3acq.put(1)
                while signal0==0.:
                    signal0=diode0.get()            
                while signal1==0.:
                    signal1=float(diode1.get())
                    while(signal1 == oldsig):
                        time.sleep(0.05)
                        signal1=diode1.get()            
                    oldsig=signal1
                while signal2==0.:
                    signal2=diode2.get()            
                while signal3==0.:
                    signal3=diode3.get()            
                while nsig0==0.:
                    nsig0=float(norm0.get())
                while nsig1==0.:
                    nsig1=float(norm1.get())
                while nsig2==0.:
                    nsig2=float(norm2.get())
                while nsig3==0.:
                    nsig3=float(norm3.get())
                time.sleep(options.acqt)
                while ( x3ch3roi3ct.timestamp==roits):
                    time.sleep(0.1)
                roits=x3ch3roi3ct.timestamp
                while ( x3ch3roi3ct.timestamp==roits):
                    time.sleep(0.1)
                sig0=x3ch1roi0ct.get()+x3ch2roi0ct.get()+x3ch3roi0ct.get()
                sig1=x3ch1roi1ct.get()+x3ch2roi1ct.get()+x3ch3roi1ct.get()
                sig2=x3ch1roi2ct.get()+x3ch2roi2ct.get()+x3ch3roi2ct.get()
                sig3=x3ch1roi3ct.get()+x3ch2roi3ct.get()+x3ch3roi3ct.get()
                roits=x3ch3roi3ct.timestamp
            tn=time.time()-t0
            if options.sim is False:
                str='[%(X)06d] at ( %(XC)9.4f , %(YC)9.4f ): %(d1)10.7e %(d2)10.7e %(d3)10.7e %(d4)10.7e %(norm)10.7e %(s0)10.7e %(s1)10.7e %(s2)10.7e %(s3)10.7e %(time)9.2f'%{ 'X':Ncol, 'XC':xmot_cur.get(),"YC":ymot_cur.get(), "d1":float(signal0), "d2":float(signal1), "d3":float(signal2),"d4":float(signal3), 'norm':nsig0+nsig1+nsig2+nsig3, "s0":sig0,"s1":sig1,"s2":sig2,"s3":sig3, "time":tn}
                print str
                fp.write(str)
                fp.write('\n')
            else:
                str='[%(X)06d] at ( %(XC)8.4f , %(YC)8.4f ): %(d1)10.7e %(d2)10.7e %(d3)10.7e %(d4)10.7e'%{"X":int(Ncol),"XC":tar[0][0], "YC":tar[1][0], "d1":float(signal0), "d2":float(signal1), "d3":float(signal2),"d4":float(signal3)}     
                print str
                fp.write(str)
                fp.write('\n')
    
            Ncol=Ncol+1
        Nrow=Nrow+1

    str='End time is '+time.asctime()
    print str
    fp.write(str)
    fp.write('\n')
    fp.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())
