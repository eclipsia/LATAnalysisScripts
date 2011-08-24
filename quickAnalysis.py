#!/usr/bin/env python

"""Perform event selections and exposure calculations for Fermi LAT data.

This module prepares Fermi LAT data for a likelihood anlaysis.  The
user supplies a text file with a list of data runs (one per line) and
a spacecraft file.  These should be called <basename>.list and
<basename>_SC.fits respectively where <basename> is a user defined
prefix.  There are two ways to run this module: from within python or
from the command line.  The simplest way to run it is from the command
line.

First, generate a default config file:

> quickAnalysis -c

The, edit the config file to match your specific analysis by filling
out the various options.  Next, run the command again:

> quickAnalysis <basename>

where <basename> is the prefix you've chosen to use; usually the name
of your source of interest but not necissarily so.

If you want to run this from within python, you'll need to first
create a quickAnalysis object and then you can use the various
functions below.  See the documentation for the individual functions
for more details.

This module logs all of the steps to a file called
<basename>_quickAnalysis.log as well as to the screen.

"""

__author__ = 'Jeremy S. Perkins (FSSC)'
__version__ = '0.1'

import sys
import os
import math
from gt_apps import *
from quickUtils import *

class quickAnalysis:

    """This is the base class.  If you want to use this, you first
    need to create an object from this method:

    >>> qA = quickAnalysis('example_name', configFile = True)

    will create an object called qA with the <basename> of
    'example_name' and will read in all of the options from the config
    file.  You can create an example config frile via the writeConfig
    function or via the command line with the -c option.  You can also
    pass all of the variables via the intial object initialiation
    function (see below).  Once you've created this object, you can
    just execute the runAll function to execute all of the steps, or
    use the functions individually as needed.
    """

    def __init__(self,
                 base='MySource',
                 configFile = False,
                 analysisConfig = {"ra" : 0,
                                   "dec" : 0,
                                   "rad" : 10,
                                   "tmin" : "INDEF",
                                   "tmax" : "INDEF",
                                   "emin" : 100,
                                   "emax" : 300000,
                                   "zmax" : 100},
                 commonConfig = {"base" : 'MySource',
                                 "binned" : False,
                                 "eventclass" : 2,
                                 "irfs" : "P7SOURCE_V6",
                                 "verbosity" : 0}):

        commonConfig['base'] = base

        self.logger = initLogger(base, 'quickAnalysis')

        if(configFile):
            try:
                commonConfig,analysisConfig,likelihoodConfig = readConfig(self.logger,base)
            except(FileNotFound):
                self.logger.critical("One or more needed files do not exist")
                return

        self.commonConf = commonConfig
        self.analysisConf = analysisConfig

        logString = "Created quickAnalysis object: "
        for variable, value in commonConfig.iteritems():
            logString += variable+"="+str(value)+","
        for variable, value in analysisConfig.iteritems():
            logString += variable+"="+str(value)+","
        self.logger.info(logString)
            
    def writeConfig(self):

        """Writes all of the initialization variables to the config
        file called <basename>.cfg."""

        writeConfig(quickLogger=self.logger,
                    commonDictionary=self.commonConf,
                    analysisDictionary=self.analysisConf)

    def runCommand(self,AppCommand,run=True):

        """Runs a giving command if run is True.  If run is False,
        prints out what the function would run."""

        if(run):
            AppCommand.run()
            self.logger.info(AppCommand.command())
        else:
            print AppCommand.command()
            
    def runSelect(self,run = True,convtype=-1):

        """Runs gtselect on the data using the initialization
        parameters. User selected parameters include the conversion
        type and the eventclass."""

        filter['rad'] = self.analysisConf['rad']
        filter['evclass'] = self.commonConf['eventclass']
        filter['infile'] = "@"+self.commonConf['base']+".list"
        filter['outfile'] = self.commonConf['base']+"_filtered.fits"
        filter['ra'] = self.analysisConf['ra']
        filter['dec'] = self.analysisConf['dec']
        filter['tmin'] = self.analysisConf['tmin']
        filter['tmax'] = self.analysisConf['tmax']
        filter['emin'] = self.analysisConf['emin']
        filter['emax'] = self.analysisConf['emax']
        filter['zmax'] = self.analysisConf['zmax']
        filter['convtype'] = convtype

        self.runCommand(filter,run)
        
    def runGTI(self, run = True, filterString="DATA_QUAL==1 && LAT_CONFIG==1 && ABS(ROCK_ANGLE)<52",roi = 'yes'):

        """Executes gtmktime with the given filter"""

        maketime['scfile'] = self.commonConf['base']+'_SC.fits'
        maketime['filter'] = filterString
        maketime['roicut'] = roi
        maketime['evfile'] = self.commonConf['base']+'_filtered.fits'
        maketime['outfile'] = self.commonConf['base']+'_filtered_gti.fits'

        self.runCommand(maketime,run)

    def runLTCube(self, run=True, zmax=180):

        """Generates a livetime cube"""

        expCube['evfile'] = self.commonConf['base']+'_filtered_gti.fits'
        expCube['scfile'] = self.commonConf['base']+'_SC.fits'
        expCube['outfile'] = self.commonConf['base']+'_ltCube.fits'
        expCube['dcostheta'] = 0.025
        expCube['binsz'] = 1
        expCube['zmax'] = zmax

        self.runCommand(expCube,run)

    def runExpMap(self, run=True):

        """Generates an exposure map that is 10 degrees larger than
        the ROI and has 120 pixels in each direction."""

        expMap['evfile'] = self.commonConf['base']+'_filtered_gti.fits'
        expMap['scfile'] = self.commonConf['base']+'_SC.fits'
        expMap['expcube'] = self.commonConf['base']+'_ltcube.fits'
        expMap['outfile'] = self.commonConf['base']+'_expMap.fits'
        expMap['irfs'] = self.commonConf['irfs']
        expMap['srcrad'] = float(self.analysisConf['rad']) + 10.
        expMap['nlong'] = 120
        expMap['nlat'] = 120
        expMap['nenergies'] = 20

        self.runCommand(expMap,run)

    def runCCUBE(self, run=True,bin_size=0.1,nbins=30):

        """Generates a counts cube.  The dimensions of which are the
        largest square subtended by the ROI.  Note that if the ROI is
        exceptionally small or the bin size exceptionally large, the
        square might not be the largest posible since the npix
        calculation floors the calculated value.  The number of energy
        bins is logarithmic and is defined by the nbins variable."""

        npix = NumberOfPixels(float(self.analysisConf['rad']), bin_size)

        evtbin['evfile'] = self.commonConf['base']+'_filtered_gti.fits'
        evtbin['outfile'] = self.commonConf['base']+'_CCUBE.fits'
        evtbin['algorithm'] = 'CCUBE'
        evtbin['nxpix'] = npix
        evtbin['nypix'] = npix
        evtbin['binsz'] = bin_size
        evtbin['coordsys'] = 'CEL'
        evtbin['xref'] = self.analysisConf['ra']
        evtbin['yref'] = self.analysisConf['dec']
        evtbin['axisrot'] = 0
        evtbin['proj'] = 'AIT'
        evtbin['ebinalg'] = 'LOG'
        evtbin['emin'] = self.analysisConf['emin']
        evtbin['emax'] = self.analysisConf['emax']
        evtbin['enumbins'] = nbins

        self.runCommand(evtbin,run)

    def runCMAP(self, run=True,bin_size=0.1):
        
        """Generates a counts map.  The dimensions of which are the
        largest square subtended by the ROI.  Note that if the ROI is
        exceptionally small or the bin size exceptionally large, the
        square might not be the largest posible since the npix
        calculation floors the calculated value."""

        npix = NumberOfPixels(float(self.analysisConf['rad']), bin_size)

        evtbin['evfile'] = self.commonConf['base']+'_filtered_gti.fits'
        evtbin['outfile'] = self.commonConf['base']+'_CMAP.fits'
        evtbin['algorithm'] = 'CMAP'
        evtbin['nxpix'] = npix
        evtbin['nypix'] = npix
        evtbin['binsz'] = bin_size
        evtbin['coordsys'] = 'CEL'
        evtbin['xref'] = self.analysisConf['ra']
        evtbin['yref'] = self.analysisConf['dec']
        evtbin['axisrot'] = 0
        evtbin['proj'] = 'AIT'
    
        self.runCommand(evtbin,run)

    def runExpCube(self,run=True,bin_size=0.1,nbins=30):

        """Generates a binned exposure map that is 20 degrees larger
        than the ROI.  The binned exposure map needs to take into
        account the exposure on sources outside of the ROI.  20
        degrees is the size of the PSF at low energies plus an extra
        10 degrees for security.  The energy binning is logarithmic
        and the number of energy bins is defined by the nbins
        variable."""

        npix = NumberOfPixels(float(self.analysisConf['rad']), bin_size)

        cmd = "gtexpcube2 infile="+self.commonConf['base']+"_ltcube.fits"\
            +" cmap=none"\
            +" outfile="+self.commonConf['base']+"_BinnedExpMap.fits"\
            +" irfs="+self.commonConf['irfs']\
            +" xref="+str(self.analysisConf['ra'])\
            +" yref="+str(self.analysisConf['dec'])\
            +" nxpix="+str(npix)\
            +" nypix="+str(npix)\
            +" binsz="+str(bin_size)\
            +" coordsys=CEL"\
            +" axisrot=0"\
            +" proj=AIT"\
            +" ebinalg=LOG"\
            +" emin="+str(self.analysisConf['emin'])\
            +" emax="+str(self.analysisConf['emax'])\
            +" enumbins="+str(nbins)
            
        if(run):
            os.system(cmd)
            self.logger.info(cmd)
        else:
            print cmd

    def generateXMLmodel(self):
        
        """Calls the quickUtils function to make an XML model of your
        region based on the 2FGL. make2FGLXml.py needs to be in your
        python path.  This needs to have the galactic and isotropic
        diffuse models in your working directory as well as the 2FGL
        catalog in FITS format.  See the corresponding function in
        quickUtils for more details."""
        
        try:
            generateXMLmodel(self.logger, self.commonConf['base'])
        except(FileNotFound):
            self.logger.critical("One or more needed files do not exist")
            return

    def runSrcMaps(self, run=True):

        """Generates a source map for your region.  Checks to make
        sure that there's an XML model to be had and if not, creates
        one from the 2FGL."""

        self.generateXMLmodel()

        srcMaps['scfile'] = self.commonConf['base']+"_SC.fits"
        srcMaps['expcube'] = self.commonConf['base']+"_ltcube.fits"
        srcMaps['cmap'] = self.commonConf['base']+"_CCUBE.fits"
        srcMaps['srcmdl'] = self.commonConf['base']+"_model.xml"
        srcMaps['bexpmap'] = self.commonConf['base']+"_BinnedExpMap.fits"
        srcMaps['outfile'] = self.commonConf['base']+"_srcMaps.fits"
        srcMaps['irfs'] = self.commonConf['irfs']
        srcMaps['rfactor'] = 4
        srcMaps['emapbnds'] = "no"

        self.runCommand(srcMaps,run)

    def runModel(self,run=True):

        """Generates a model map."""
        
        model_map['srcmaps'] = self.commonConf['base']+"_srcMaps.fits"
        model_map['srcmdl'] = self.commonConf['base']+"_model.xml"
        model_map['outfile'] = self.commonConf['base']+"_modelMap.fits"
        model_map['expcube'] = self.commonConf['base']+"_ltcube.fits"
        model_map['irfs'] = self.commonConf['irfs']
        model_map['bexpmap'] = self.commonConf['base']+"_BinnedExpMap.fits"

        self.runCommand(model_map,run)

    def runAll(self, run=True):

        """Does a full event selection and exposure calculation.  This
        is the function called when this module is run from the
        command line.  You need to have two files to start with:
        <basename>.list and <basename>_SC.fits.  The first one is just
        a text file with a list of the raw data files (one per line)
        and the other is the spacecraft file.  <basename> is a user
        defined prefix (usually the source name but not necissarily).
        Returns an exception if any of the files are not found."""

        self.logger.info("***Checking for files***")
        try:
            checkForFiles(self.logger,[self.commonConf['base']+".list",self.commonConf['base']+"_SC.fits"])
        except(FileNotFound):
            self.logger.critical("One or more needed files do not exist")
            return
        self.logger.info("***Running gtselect***")
        self.runSelect(run)
        self.logger.info("***Running gtmktime***")
        self.runGTI(run)
        self.logger.info("***Running gtltcube***")
        self.runLTCube(run)

        if(self.commonConf['binned']):
            self.logger.info("***Running gtbin***")
            self.runCCUBE(run)
            self.logger.info("***Running gtexpcube2***")
            self.runExpCube(run)
            self.logger.info("***Running gtsrcMaps***")
            self.runSrcMaps(run)
        else:
            self.logger.info("***Running gtexpmap***")
            self.runExpMap(run)
   
# Command-line interface             
def cli():
    """Command-line interface.  Call this without any options for usage notes."""
    import getopt
    class BadUsage: pass
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'c')
        
        for opt, val in opts:
            if opt == '-c':
                print "Creating example configuration file called example.cfg"
                qA = quickAnalysis("example")
                qA.writeConfig()
                return

        if not args: raise BadUsage
        for arg in args:
            qA = quickAnalysis(arg, True)
            qA.runAll(False)

    except (getopt.error, BadUsage):
        cmd = os.path.basename(sys.argv[0])
        print """quickAnalysis - Perform event selections and exposure calculations for Fermi LAT data.

%s <basename> ...  Perform an analysis on <basename>.  <basename> is
    the prefix used for this analysis.  You must already have a
    configuration file if using the command line interface.
""" %(cmd)

if __name__ == '__main__': cli()
