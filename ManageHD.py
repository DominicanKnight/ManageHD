#!/usr/bin/env python3.4

# #########################################################################
# This file is part of ManageHD.
#
# ManageHD is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ManageHD is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ManageHD.  If not, see <http://www.gnu.org/licenses/>.
# #########################################################################

import shutil
import os
import copy
import subprocess
import sys
import glob 
import ctypes
import threading
import xml.etree.ElementTree as ET
from os import stat
from time import sleep, mktime, ctime
from datetime import datetime
from enum import Enum
from queue import Queue
from datetime import datetime as dt
if sys.platform == "win32": import winreg

# ######################################################################################################################################
# COMMAND LINE CALLS:
#
#     Windows:
#         python ManageHD.py s=E:\Dropbox\Code\Python\TestEnv\video a= d=E:\Dropbox\Code\Python\TestEnv
#
#     Linux:
#         python3 ManageHD.py s=/home/knight/Dropbox/Code/Python/TestEnv/video a=/home/knight/Dropbox/Code/Python/TestEnv t=/home/knight/Dropbox/Code/Python/TestEnv/video/dest
#
# #####################################################################################################################################

class Handbrake():
    """Contains all Handbrake specific functionality"""
    def __init__(self):
        """ Handbrake class constructor. """
        if sys.platform[:5] == "linux":
            self.dirSep = "/"
        else:
            self.dirSep = "\\"
        pass

    def __BuildHandBrakeParameterString(self, movie, destinationDirectory):
        """Creates a string containing a well formed Handbrake CLI command"""
        if destinationDirectory[-1] != self.dirSep:
            destinationDirectory += self.dirSep

        #build movie string 
        fm = FileManip()
        MovieName = fm.GetFileNameOnlyFromPathWithFile(movie)
        
        MovieName = MovieName[:len(MovieName)-3] + Progress.statuses['OutputExtension']

        if sys.platform[:5] == "linux" or sys.platform[:3] == "osx":
            handbrakeOsSpecificPrefix = "/usr/bin/HandBrakeCLI"
        else:
            handbrakeOsSpecificPrefix = "HandBrakeCLI"

        #build defaults string and add movie string
        HandbrakeOptionsString = str(Progress.statuses['HandbrakeOptionsString'])
        CommandString = handbrakeOsSpecificPrefix + HandbrakeOptionsString.format('"' + movie + '"',  '"' + str(destinationDirectory + MovieName) + '"')
        return CommandString

    def CreateListOfCommandStrings(self, listOfVideos, destinationDirectory):
        """ Construct the command line strings needed to invoke Handbrake and process each video file. """
        if sys.platform[:5] == "win32":
            logDirectory = " > %UserProfile%\Desktop\ManageHD.log"
        else:
            logDirectory = os.path.dirname(os.path.abspath(__file__))

        fm = FileManip()
        listOfCommands = {}
        for video in listOfVideos:
            listOfCommands[(self.__BuildHandBrakeParameterString(video, destinationDirectory) + logDirectory)] = fm.GetFileSizeInMegabytes(video)            
        return listOfCommands

    def __BuildHandBrakeParameterList(self,  movie, destinationDirectory):
        """ Creates a list of parameter for Handbrake that will later be used to build the cli strings. """
        if destinationDirectory[-1] != self.dirSep:
            destinationDirectory += self.dirSep

        #build movie string 
        MovieName = self.GetFileNameOnlyFromPathWithFile(movie)
        #self.CurrentMovie.set_text(MovieName)

        #build defaults string and add movie string
        Parameters = '-f mkv --width 1280 --crop 0:0:0:0 --decomb -s 1 -N eng -m --large-file --encoder x264 -q 19 -E ffac3'.split(" ")
        Parameters.insert(0, str(destinationDirectory + MovieName))
        Parameters.insert(0, "-o")
        Parameters.insert(0, movie)
        Parameters.insert(0, "-i")
        if sys.platform[:5] == "linux":
            Parameters.insert(0,"/usr/bin/HandBrakeCLI")
        else:
            Parameters.insert(0,"HandBrakeCLI")
        return Parameters

class Progress():
    """ Keeps track of video conversion progress """
    #Need a static variable to track progress
    statuses = {'VideosTotal' : 0, \
                'VideosCurrent' : 0, \
                'VideosCompleted' : 0 ,\
                'VideoNames' : "", \
                'ListOfVidsAndSizesInMB' : {}, \
                'ProcessingSpeedInGBperHour' : 0, \
                'ProcessedSoFarInMB' : 0, \
                'AverageMinutesPerGigabyte' : 0, \
                'StartTime' : datetime.now(), \
                'EndTime' : "", \
                'TimeRemaining' : 0, \
                'VideosRemaining' : 0, \
                'StatusesHaveChanged' : True, \
                'ProcessingComplete' : False, \
                'ProcessingCompleteStatus' : None, \
                'BatchStatus' : "", \
                'InvalidQuotingInFileName' : "", \
                'NoVideoFilesFound' : 0, \
                'DirectoryChanged' : False, \
                'HandbrakeOptionsString' : str(" -i {0} -o {1} -f mkv --width 1280 --crop 0:0:0:0 --decomb -s 1 -N eng -m --large-file --encoder x264 -q 19 -E ffac3"), \
                'OutputExtension' : "mkv", 
               }
    
    cliParams ={'sourceDir' : None, \
                'archiveDir' : None, \
                'destinationDir' : None, \
                'maxNumberOfVideosToProcess' : 0, \
                'videoTypes' : "", \
                'ProcessingSpeedInGBperHour' : 0,
               }  
    
    runPlatform = ""
    listOfEachRunsGBperHourRate = []
    listOfSourceVideos = []

    def __init__(self):
        """ Constructor. """
        self.resetStatuses = copy.deepcopy(self.statuses)
    
    def GetStatuses(self):
        """ Returns the Statuses list."""
        return self.statuses
    
    @staticmethod
    def CalculateTimeRemaining():
        """ Estimate the projected time to completion for this batch based on the file sizes and processing speed estimate. """        
        totalDataSizeInMB = sum(Progress.statuses['ListOfVidsAndSizesInMB'].values())
        totalMinusDone = totalDataSizeInMB - Progress.statuses['ProcessedSoFarInMB']
        
        if Progress.statuses['ProcessingSpeedInGBperHour'] != 0.0:
            timeRemainingInMin = (totalMinusDone / ((Progress.statuses['ProcessingSpeedInGBperHour'] * 1024) / 60))
        elif Progress.cliParams['ProcessingSpeedInGBperHour'] != 0.0:
            timeRemainingInMin = (totalMinusDone / ((Progress.statuses['ProcessingSpeedInGBperHour'] * 1024) / 60))
        else:
            return "Calc'd at end of 1st video ..."

        fmt               = '%Y-%m-%d %H:%M:%S'
        dateTimeNowString = datetime.now().strftime(fmt)
        startTimeString   = Progress.statuses['StartTime'].strftime(fmt)
        dateTimeNow       = datetime.strptime(dateTimeNowString, fmt)
        startTime         = datetime.strptime(startTimeString, fmt)

        elapsedTimeInMinutes = (dateTimeNow - startTime).seconds / 60

        projectedRunTimeInMinutes = elapsedTimeInMinutes + timeRemainingInMin

        if timeRemainingInMin >= (60 * 24 * 2):
            return str( '%.1f' % (timeRemainingInMin / (60 * 24) )) + " Days"
        if timeRemainingInMin >= (60 * 24) and timeRemainingInMin < (60 * 24 * 2):
            return str( '%.1f' % (timeRemainingInMin / (60 * 24) )) + " Day"
        if timeRemainingInMin >= 120:
            return str( '%.1f' % (timeRemainingInMin / 60) ) + " Hours"
        if timeRemainingInMin >= 60 and timeRemainingInMin < 120:
            return str( '%.1f' % (timeRemainingInMin / 60) ) + " Hour"
        if timeRemainingInMin > 1 and timeRemainingInMin < 60:
            return str( '%.1f' % (timeRemainingInMin)) + " Minutes"
        return "less than 1 minute"

    @staticmethod
    def CalculateGBperHour(key, duration, threadCount):
        """ Calculate the speed at which video files are processed (varies by hardware implementation) in GB/Hour. """
        if duration == 0: return 1.5 #Most modern boxes can process 1.7 gb/hour this handles initial value population
        GBperSec = (Progress.statuses['ListOfVidsAndSizesInMB'][key] / 1024) / duration
        if threadCount > 1 and Progress.statuses['VideosCurrent'] > 0:
            if Progress.statuses['VideosCurrent'] < threadCount:
                threadMultiplier = (Progress.statuses['VideosCurrent'] + 1)
            else:
                threadMultiplier = threadCount
            GBperSec = GBperSec * threadMultiplier
        Progress.listOfEachRunsGBperHourRate.append(GBperSec * 60 * 60)
        return sum(Progress.listOfEachRunsGBperHourRate) / len(Progress.listOfEachRunsGBperHourRate)

    @staticmethod
    def ResetStatuses():  
        """ Store the initial values for the Statuses list. Used to re-initialize the list."""
        resetStatuses = {'VideosTotal' : 0, \
                    'VideosCurrent' : 0, \
                    'VideosCompleted' : 0 ,\
                    'VideoNames' : "", \
                    'ListOfVidsAndSizesInMB' : {}, \
                    'ProcessingSpeedInGBperHour' : 0, \
                    'ProcessedSoFarInMB' : 0, \
                    'AverageMinutesPerGigabyte' : 0, \
                    'StartTime' : datetime.now(), \
                    'EndTime' : "", \
                    'TimeRemaining' : 0, \
                    'VideosRemaining' : 0, \
                    'StatusesHaveChanged' : True, \
                    'ProcessingComplete' : False, \
                    'ProcessingCompleteStatus' : None, \
                    'BatchStatus' : "", \
                    'InvalidQuotingInFileName' : "", \
                    'NoVideoFilesFound' : 0, \
                    'DirectoryChanged' : False, \
                    'HandbrakeOptionsString' : Progress.statuses['HandbrakeOptionsString'], \
                    'OutputExtension' : Progress.statuses['OutputExtension'], 
                   }
        Progress.statuses = copy.deepcopy(resetStatuses)
        if Progress.cliParams['ProcessingSpeedInGBperHour'] != 0:
            Progress.statuses['ProcessingSpeedInGBperHour'] = Progress.cliParams['ProcessingSpeedInGBperHour']
        Progress.listOfEachRunsGBperHourRate = []
       
    def SetStatuses(self, newStatuses):
        """ Load information into the Statuses list. """
        self.statuses['VideosTotal']                = newStatuses['VideosTotal']
        self.statuses['VideosCurrent']              = newStatuses['VideosCurrent']
        self.statuses['VideoNames']                 = newStatuses['VideoNames']
        self.statuses['ListOfVidsAndSizesInMB']     = newStatuses['ListOfVidsAndSizesInMB']
        self.statuses['ProcessingSpeedInGBperHour'] = newStatuses['ProcessingSpeedInGBperHour'] 
        self.statuses['ProcessedSoFarInMB']         = newStatuses['ProcessedSoFarInMB']         
        self.statuses['AveragePerGigabyte']         = newStatuses['AveragePerGigabyte']
        self.statuses['StartTime']                  = newStatuses['StartTime']
        self.statuses['TimeRemaining']              = newStatuses['TimeRemaining']
        self.statuses['VideosRemaining']            = newStatuses['VideosRemaining']
        self.statuses['SpaceRemainingInMegs']       = newStatuses['SpaceRemainingInMegs']
        self.statuses['MaxHours']                   = newStatuses['MaxHours']
        self.statuses['BatchStatus']                = newStatuses['BatchStatus']
        self.statuses['InvalidQuotingInFileName']   = newStatuses['InvalidQuotingInFileName']
        self.statuses['NoVideoFilesFound']          = newStatuses['NoVideoFilesFound'] 
        self.statuses['DirectoryChanged']           = newStatuses['DirectoryChanged']
        self.statuses['HandbrakeOptionsString']     = newStatuses['HandbrakeOptionsString']
        self.statuses['OutputExtension']            = newStatuses['OutputExtension']

    def ArchiveSourceVideo(archiveDir, sourceDir, destinationDir, listOfSourceVideos=None):
        """ Move the source video files that were actually processed to the archive directory. """
        fm = FileManip()

        if archiveDir == '':
            return
        
        if listOfSourceVideos == None:
            listOfSourceVideos = Progress.listOfSourceVideos
        
        #Gather original video names and createdates from source directory into a list
        origNameAndSize = {}
        origNameAndDate = {}
        for item in listOfSourceVideos:
            #if sys.platform[:5] == "linux":
                #item = item.replace("\\ "," ")
            origNameAndSize[item] = fm.GetFileSizeInMegabytes(item)
            origNameAndDate[item] = ctime(os.path.getctime(item))
            
        #Gather converted video names and createdates from target directory into a list
        convertedAndSize = {}   
        convertedAndDate = {}
        for item in listOfSourceVideos:
            separator = ""
            if sys.platform[:5] == "linux":
                separator = "/"
            else:
                separator = "\\"
            fullyQualItem = destinationDir + separator + fm.GetFileNameOnlyFromPathWithFile(item)
            convertedAndSize[fullyQualItem] = fm.GetFileSizeInMegabytes(fullyQualItem)
            convertedAndDate[fullyQualItem] = ctime(os.path.getctime(fullyQualItem))
            
        #Iterate through the the orig vid list and look for the name in the converted list
        #  and make sure the converted date is more recent than the original create
        #  Add those meeting that criteria to a archive list with a fully qual'd path and add 
        #  its file size to the totalFileSize tally.
        
        filesToArchive       = []
        totalArchiveDataSize = 0.0
        fmt                  = '%a %b %d %H:%M:%S %Y'
        for origItem in origNameAndDate:
            for convItem in convertedAndDate:
                origName = fm.GetFileNameOnlyFromPathWithFile(origItem)
                convName = fm.GetFileNameOnlyFromPathWithFile(convItem)
                if origName == convName:
                    if datetime.strptime(origNameAndDate[origItem], fmt) <= datetime.strptime(convertedAndDate[convItem], fmt): #if orig date older
                        filesToArchive.append(origItem)
                        totalArchiveDataSize += origNameAndSize[origItem]
                    break

        #If the archive drive is different from the source drive then check to see if 
        #  the totalFileSize tally is less than the space available in the archive drive.
        areTheyDifferentDrives = False
        
        if sys.platform[:5] == "win32":
            # windows
            if archiveDir[0] != sourceDir[0]:
                #different drives
                areTheyDifferentDrives = True
        else:
            # *nix
            if os.stat(archiveDir).st_dev != os.stat(sourceDir).st_dev:
                #Different drive/mountpoint
                areTheyDifferentDrives = True

        if areTheyDifferentDrives == True:
            if fm.GetDriveSpace(archiveDir) < totalArchiveDataSize:
                #Not enough drive space
                Progress.statuses['BatchStatus'] = 'Insufficient Drive Space'
                return

        for item in filesToArchive:
            fm.MoveFile(sourceDir, fm.GetFileNameOnlyFromPathWithFile(item), archiveDir)
            Progress.listOfSourceVideos = listOfSourceVideos
            
        Progress.statuses['BatchStatus'] = 'Completed'
        Progress.listOfSourceVideos = []
        filesToArchive              = []
    def DeterminePlatform():
        """ Determine if the application is running on Linux, windows, or a Mac. """
        if sys.platform[:5] == "linux":
            Progress.runPlatform = "nix"
        else:
            Progress.runPlatform = "win"
            
class FileManip():
    def __init__(self):
        if sys.platform[:5] == "linux":
            self.dirSep = "/"
        else:
            self.dirSep = "\\"
        pass
    
    def GetEmptyXmlFileTemplate(self):
        """ Defines an empty XML layout for creating the application info file if it doesn't already exist. """
        return ('<?xml version="1.0"?>\n'
                                 '<data>\n'
                                 '    <directory name="source">\n'
                                 '        <win></win>\n'
                                 '        <nix></nix>\n'
                                 '        <mac></mac>\n'
                                 '    </directory>\n'
                                 '    <directory name="archive">\n'
                                 '        <win></win>\n'
                                 '        <nix></nix>\n'
                                 '        <mac></mac>\n'
                                 '    </directory>\n'
                                 '    <directory name="destination">\n'
                                 '        <win></win>\n'
                                 '        <nix></nix>\n'
                                 '        <mac></mac>\n'
                                 '    </directory>\n'
                                 '	<speed measure="GBpH">\n'
                                 '        <win></win>\n'
                                 '        <nix></nix>\n'
                                 '        <mac></mac>\n'
                                 '	</speed>\n'
                                 '</data>\n')
    
    def ReadSettingsFile(self):
        """ Retrieve information pertaining to last used settings from the application ini file in XML. """
        # if the file doesn't exist create it
        if not self.VerifyExists('cliattribs.xm'):
            with open("cliattribs.xm", "w") as text_file:
                print(self.GetEmptyXmlFileTemplate(), file=text_file)            
        tree = ET.parse('cliattribs.xm')
        root = tree.getroot()
        params = Progress.cliParams.copy()
        for directory in root.findall('directory'):
            if directory.get('name') == "source":
                if Progress.runPlatform  == "win":
                    params['sourceDir']  = directory.find('win').text
                else:
                    params['sourceDir']  = directory.find('nix').text
            if directory.get('name') == "archive":
                if Progress.runPlatform  == "win":
                    params['archiveDir'] = directory.find('win').text
                else:
                    params['archiveDir'] = directory.find('nix').text
            if directory.get('name') == "destination":
                if Progress.runPlatform  == "win":
                    params['destinationDir']  = directory.find('win').text
                else:
                    params['destinationDir']  = directory.find('nix').text
                    
        for speed in root.findall('speed'):
            processingTime = speed.find('win').text
            if processingTime == None:
                processingTime = 0
            processingTime = round(float(processingTime),1)
            if Progress.runPlatform  == "win":                
                Progress.statuses['ProcessingSpeedInGBperHour'] = processingTime
                Progress.cliParams['ProcessingSpeedInGBperHour'] = processingTime
            if Progress.runPlatform  == "nix":
                Progress.statuses['ProcessingSpeedInGBperHour'] = processingTime
                Progress.cliParams['ProcessingSpeedInGBperHour'] = processingTime
        return params
    
    def WriteSettingsFile(self): 
        # if the file doesn't exist create it
        if not self.VerifyExists('cliattribs.xm'):
            with open("cliattribs.xm", "w") as text_file:
                print(self.GetEmptyXmlFileTemplate(), file=text_file)            
        tree = ET.parse('cliattribs.xm')
        root = tree.getroot()
        params = Progress.cliParams.copy()
        
        for directory in root.findall('directory'):
            if Progress.runPlatform  == "win":
                for win in directory.findall('win'):
                    if directory.get('name') == "source":
                        win.text = params['sourceDir']
                    if directory.get('name') == "archive":
                        win.text = params['archiveDir']
                    if directory.get('name') == "destination":
                        win.text = params['destinationDir']
            else:
                for nix in directory.findall('nix'):
                    if directory.get('name') == "source":
                        nix.text = params['sourceDir']
                    if directory.get('name') == "archive":
                        nix.text = params['archiveDir']
                    if directory.get('name') == "destination":
                        nix.text = params['destinationDir']

        for speed in root.findall('speed'):
            for win in speed.findall('win'):
                if Progress.runPlatform  == "win":
                    win.text = str(round(Progress.statuses['ProcessingSpeedInGBperHour'], 1))
                if Progress.runPlatform  == "win":
                    win.text = str(round(Progress.statuses['ProcessingSpeedInGBperHour'], 1))
            for nix in speed.findall('nix'):
                if Progress.runPlatform  == "nix":
                    nix.text = str(round(Progress.statuses['ProcessingSpeedInGBperHour'], 1))
                if Progress.runPlatform  == "nix":
                    nix.text = str(round(Progress.statuses['ProcessingSpeedInGBperHour'], 1))

        tree.write('cliattribs.xm')
        self.ReadSettingsFile()
        return params

    def MoveFile(self, source_dir, file_name, target_dir):    
        """Relocate a given file from a given dir to another specific dir."""
        if source_dir[-1] != self.dirSep:
            source_dir += self.dirSep
        if target_dir[-1] != self.dirSep:
            target_dir += self.dirSep
        source_dir += file_name
        try:
            shutil.move(source_dir,  target_dir)
        except:
            #print("Move failed!!")
            pass

    def GetFileList(self, directoryPath, fileTypes, fileCount=0):
        """Retrieves name info for a specified number of files in the specified path."""
        MovieList = []
        items = []

        if directoryPath[-1] != self.dirSep:
            #print(self.dirSep)
            directoryPath += self.dirSep        
        
        for fileType in fileTypes:
            subItems = glob.glob(directoryPath + "*." + fileType)
            #print(subItems)
            for item in subItems:           
                items.append(item) #.replace(" ",self.dirSep)

        if fileCount == 0:
            fileCount = len(items)

        Progress.statuses['VideosTotal'] = fileCount
        
        try:
            for x in range(0,  fileCount):
                MovieList.append(items[x])
        except:
            return MovieList
        return MovieList


    def GetFileNameOnlyFromPathWithFile(self, PathWithFile):        
        """Retrieves the name of the file without the path portion."""
        FileNameStartIndex = PathWithFile.rfind(self.dirSep) + 1
        return PathWithFile[FileNameStartIndex:]

    def GetFileSizeInMegabytes(self, fileAndPath):
        """ Retrieves the size of a file from the os. """
        try:
            size = os.stat(fileAndPath).st_size / 1024 / 1024 # In Megabytes
        except:
            size = 0
        return size
    
    def GetDriveSpace(self, path):
        """ Returns the amount of free space, in gigabytes, on the drive containing the provided path. """
        if sys.platform[:5] == "linux":
            st = os.statvfs(path)
            return '%.1f' % ((st.f_bavail * st.f_frsize) / 1024/1024/1024) + " GB"
        elif sys.platform[:5] == "win32":
            drive = os.getenv(path)
            freeuser = ctypes.c_int64()
            total = ctypes.c_int64()
            free = ctypes.c_int64()
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(drive, 
                                            ctypes.byref(freeuser), 
                                            ctypes.byref(total), 
                                            ctypes.byref(free))
            return str('%.1f' % (free.value/1024/1024/1024)) + " GB"
        return 0
    def VerifyExists(self, pathOrFile):
        """ Verify that a path or fully qualified file exists. """
        if os.path.exists(pathOrFile):                        
            return True        
        return 0
    
class ShellCmd():
    def __init__(self): # Not Implemented
        pass
    
    def __IssueCmd(self, command):
        """ Private method, used to execute a command to the operating system. """
        #return os.system(command)
        status = subprocess.call(command,shell=True)
        return status
        
    def ExecuteCommand(self, command):
        """ Called to Execute a command against the operating system via a call to the private method __IssueCmd. """
        return self.__IssueCmd(command)
        
class Threads():
    # lock to serialize console output
    lock = threading.Lock()
    
    def CreateThreadPool(self, activeQueue, numThreads = 4):
        """ Create the queue and the thread pool. """
        self.NumberOfThreads = numThreads
        for threadCount in range(numThreads):
            thread = threading.Thread(target=self.Worker,args=(activeQueue,))
            thread.setDaemon(True)  # thread dies when main thread (only non-daemon thread) exits.
            thread.start()

    def Worker(self, activeQueue):
        """ Worker thread. """
        while True:
            item = activeQueue.get()
            activeQueue.task_done()

            with self.lock:
                Progress.statuses['VideosCurrent'] += 1
                Progress.statuses['StatusesHaveChanged'] = True
           
            # convert start time to unix timestamp
            startTime = mktime(datetime.now().timetuple())

            if sys.platform == 'win32':
                os.system(item)

            elif sys.platform == 'linux':
                os.system(item)

            # convert end time to unix timestamp
            endTime = mktime(datetime.now().timetuple())

            # in seconds
            duration = int(endTime - startTime)
            
            with self.lock:
                Progress.statuses['VideosCurrent'] -= 1
                Progress.statuses['VideosCompleted'] += 1
                
                #calculate rate of processing using the size of the just completed video
                Progress.statuses['ProcessedSoFarInMB'] = Progress.statuses['ProcessedSoFarInMB'] + \
                                                          Progress.statuses['ListOfVidsAndSizesInMB'][item]
                Progress.statuses['ProcessingSpeedInGBperHour'] = Progress.CalculateGBperHour(item, duration, self.NumberOfThreads)
                Progress.statuses['TimeRemaining'] = Progress.CalculateTimeRemaining()                
                Progress.statuses['StatusesHaveChanged'] = True

    def PopulateQueue(self, commandsAndSizes, activeQueue):
        """Populate the work queue with data"""
        self.CommandAndSizes = commandsAndSizes
        for command in commandsAndSizes:
            activeQueue.put(command)        
        activeQueue.join()

class ProcessMovies():
    archiveDirectory = ""
    targetFileFormat = ["mkv",] # The format (defined by extension) of the target files
    processAllVideos = 0        # zero is the flag for do all.
    listOfSourceVideos = ["",]
    listOfTargetVideos = ["",]

    def StartWithGUI(self, Params):
        """ Starting point for the processing portion of the application when invoked by the GUI. """
        cliParameters = {'sourceDir' : None, \
                         'archiveDir' : None, \
                         'destinationDir' : None, \
                         'maxNumberOfVideosToProcess' : 0, \
                         'videoTypes' : "",
                        }
        cliParameters['sourceDir']      = Params['sourceDir']
        cliParameters['archiveDir']     = Params['archiveDir']
        cliParameters['destinationDir'] = Params['destinationDir']

        if int(Params['maxNumberOfVideosToProcess']) > 0:
            cliParameters['maxNumberOfVideosToProcess']  = int(Params['maxNumberOfVideosToProcess'] )
        if Params['videoTypes'] != None:            
            cliParameters['videoTypes'] = Params['videoTypes']
        
        self.GetFilesAndFileStats(cliParameters)
        
        archivingResult = self.Start(useGUI = True, cliParameters=cliParameters)
        
        return archivingResult # normal completion = 0, insufficient space = -1


    def GetFilesAndFileStats(self, cliParameters):
        fm = FileManip()
        listOfSourceVideos = fm.GetFileList(cliParameters['sourceDir'], cliParameters['videoTypes'].split(','), cliParameters['maxNumberOfVideosToProcess'])
        self.listOfSourceVideos = listOfSourceVideos

        if len(listOfSourceVideos) == 0:
            Progress.statuses['NoVideoFilesFound'] = True
            return 0
        
        for idx in range(0, len(listOfSourceVideos)):
            if '\"' in listOfSourceVideos[idx]:
                Progress.statuses['InvalidQuotingInFileName'] = True
                del listOfSourceVideos[idx]
                if len(listOfSourceVideos) == 0:            
                    return 0

        hb = Handbrake()    
        commandsAndSizes = hb.CreateListOfCommandStrings(listOfSourceVideos, cliParameters['destinationDir'])
        listOfCommands = []
        
        for command in commandsAndSizes:
            listOfCommands.append(command)
            (Progress.statuses['ListOfVidsAndSizesInMB'])[command] = commandsAndSizes[command]
            
        if len(listOfCommands) == 0:
            cliParameters['ProcessingComplete'] = True
            cliParameters['ProcessingCompleteStatus'] = "No videos found at given source location."
            return
        return commandsAndSizes


    def Start(self, useGUI=False, cliParameters=None):
        """Starting point for the ManageHD.py application"""
        # Check to see if HandbrakeCLI.exe is installed
        self.__CheckForHandbrake()
        
        if useGUI == False:
            #Gathers command line arguments if ManageHD.py is called directly from the CLI                
            cliParameters = self.__ProcessParameters()
        
        fm = FileManip()
        listOfSourceVideos = fm.GetFileList(cliParameters['sourceDir'], cliParameters['videoTypes'].split(','), cliParameters['maxNumberOfVideosToProcess'])        
        commandsAndSizes = self.GetFilesAndFileStats(cliParameters)
        
        if commandsAndSizes == 0:
            return 1
        
        q = Queue()
        t = Threads()
        numThreads = 4
        if sys.platform == 'win32':
            numThreads = 1
        t.CreateThreadPool(q, numThreads)

        Progress.statuses['StartTime'] = datetime.now()

        t.PopulateQueue(commandsAndSizes, q)     

        cliParameters['ProcessingComplete'] = True
        
        #Do not continue unless processing is complete
        while True:
            sleep(1)
            if Progress.statuses['TimeRemaining'] == 'Done':
                break
            
        #Archive videos
        archiveResult = Progress.ArchiveSourceVideo(cliParameters['archiveDir'], cliParameters['sourceDir'], 
                                cliParameters['destinationDir'], listOfSourceVideos)
        
        return archiveResult # normal = 0, insufficient drive space = -1        
    
    def __ProcessParameters(self):
        """ Private method, gathers and adds defaults where necessary to the command line parameters"""
        if sys.argv[0][-3:] == ".py":
            arguments = sys.argv
            arguments.pop(0)
        else:
            arguments = sys.argv

        if len(arguments) == 0 or arguments[0] == "-h" or \
               arguments[0] == "h" or arguments[0] == "--h":
            __helpMessageCLI()
            sys.exit()
            
        cliParameters = {'sourceDir' : None, \
                         'archiveDir' : None, \
                         'destinationDir' : None, \
                         'maxNumberOfVideosToProcess' : 0, \
                         'videoTypes' : ""
                        }            
        try:
            while arguments[0] == "":
                del arguments[0]
        except:
            pass

        if len(arguments) > 0: 
            for argument in arguments:
                if argument[0]+argument[1] == "s=": cliParameters['sourceDir']      = argument[2:]
                if argument[0]+argument[1] == "a=": cliParameters['archiveDir']     = argument[2:]
                if argument[0]+argument[1] == "d=": cliParameters['destinationDir'] = argument[2:]
                if argument[0]+argument[1] == "m=": cliParameters['maxNumberOfVideosToProcess']  = int(argument[2:])
                if argument[0]+argument[1] == "v=": cliParameters['videoTypes']     = argument[2:]
                if argument[0]+argument[1] != "s=" and \
                   argument[0]+argument[1] != "a=" and \
                   argument[0]+argument[1] != "d=" and \
                   argument[0]+argument[1] != "m=" and \
                   argument[0]+argument[1] != "v=" and \
                   argument[0]+argument[1] != None and \
                   argument[0]+argument[1] != "":
                    print("")
                    print("Unrecognized parameter: " + argument)
                    print("")

        # If no video type is chosen then accept all 4
        if len(cliParameters['videoTypes']) == 0:
            cliParameters['videoTypes'] = "mkv,mp4,ogm,avi"

        if cliParameters['sourceDir']      == None or cliParameters['sourceDir']      == "" or\
           cliParameters['destinationDir'] == None or cliParameters['destinationDir'] == "":
            self.__missingParamMessageCLI()
            sys.exit()
        return cliParameters
    
    def __missingParamMessageCLI(self):
        """ Private method, prints the error relating to a missing but required command line parameter. """
        print("")
        print("ERROR: A mandatory parameter(s) is missing!")
        print("")
        print("You must specify a video source directory path using s=")
        print("                 a  destination directory path using d=")
        print("                 and an archive directory path using a=")
        print("  For example (on Linux):")
        print("    python ManageHD.py s=/vids/fam/2010  d=/vids/new  a=/vids/archive")
        print("")
        print("  or on Windows:")
        print("    python ManageHD.py s=d:\\vids\\fam\\2010  d=d:\\vids\\new  a=d:\\vids\\archive")
        print("")
        print("  For more info type: python ManageHD.py -h ")
        print("")
    
    def __helpMessageCLI(self):
        """ Private method, prints the help message for the application when used via the command line. """
        print("")
        print("Changes the resolution of 1080p (or i) video files to 720.")
        print("Requires the HandbrakeCLI to be installed (rev5474 or above).")
        print("")
        print("python ManageHD.py s=<video dir> a=<archive dir> t=<target dir> [c=...] [v=...]")
        print("")
        print("    s=   Source directory for videos.")
        print("    a=   Archive directory that original 1080p(i?) videos will be moved to.")
        print("    d=   Destination path that the converted videos will be placed in.")
        print("    c=   Optional. Maximum number of videos to convert. Default is all.")
        print("    v=   Optional. Format mkv, mp4...etc. Default is mkv,mp4,ogm,avi. No spaces.")
        print("")
        print("")
    
    def __CheckForHandbrake(self):
        if sys.platform[:5] == "win32":
            self.__CheckForHandbrakeOnWindows()
        elif sys.platform[:5] == "linux":
            #Not win32? Probably linix or *nix varient branch to here
            self.__CheckForHandbrakeOnLinux()
        elif sys.platform[:3] == "OSX":
            self.__CheckForHandbrakeOnMac()
        
    def __CheckForHandbrakeOnWindows(self):
        status = ShellCmd().ExecuteCommand("HandBrakeCLI --help > NUL")
        if status == 1:
            print("")
            print("ERROR: HandbrakeCLI module is either not in the 'path' or is not installed.")
            print("       HandbrakeCLI is required for this software to work.")
            sys.exit()
    
    def __CheckForHandbrakeOnLinux(self): # Not Implemented
        pass
    
    def __CheckForHandbrakeOnMac(self): # Not Implemented
        pass
         
# ########################### #
# Main Sentinel In Place Here #
if __name__ == "__main__":
    pm = ProcessMovies()
    pm.Start()
# ########################### #
