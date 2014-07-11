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

import sys
import os
import string
import ctypes
import pygame
from threading import Thread
from datetime import datetime
from ManageHD import ProcessMovies, Progress, FileManip
from time import sleep
from PySide.QtCore import Qt, QDateTime, QTimer, SIGNAL, QEvent
from PySide.QtGui import QApplication, QDesktopWidget, QWidget, QLabel, QStatusBar, \
     QMainWindow, QProgressBar, QGridLayout, QIcon, QPushButton, QMessageBox, QLCDNumber, \
     QAction, QKeySequence, QTextEdit, QWidget, QLineEdit, QFont, QFileDialog

class QLineEditNoPeriodsOrCommas(QLineEdit):
    """ Subclassing PySide.QtGui.QLineEdit to add field validation ability """
    def __init__(self):
        super(QLineEditNoPeriodsOrCommas, self).__init__()

    def keyPressEvent(self, event): #Override
        keyLeft = 16777234
        keyRight = 16777236
        keyUp = 16777235
        keyDown = 16777237
        keyReturn = 16777220
        if event.key() == Qt.Key_Period:
            pass
        else:
            QLineEdit.keyPressEvent(self, event)

class QLineEditIntsOnly(QLineEdit):
    """ Subclassing PySide.QtGui.QLineEdit to add field validation ability """
    def __init__(self):
        super(QLineEditIntsOnly, self).__init__()

    def keyPressEvent(self, event): #Override
        keyLeft = 16777234
        keyRight = 16777236
        keyUp = 16777235
        keyDown = 16777237
        keyReturn = 16777220
        if event.key() == Qt.Key_0 or \
           event.key() == Qt.Key_1 or \
           event.key() == Qt.Key_2 or \
           event.key() == Qt.Key_3 or \
           event.key() == Qt.Key_4 or \
           event.key() == Qt.Key_5 or \
           event.key() == Qt.Key_6 or \
           event.key() == Qt.Key_7 or \
           event.key() == Qt.Key_8 or \
           event.key() == Qt.Key_9 or \
           event.key() == Qt.Key_Backspace or \
           event.key() == Qt.LeftArrow or \
           event.key() == Qt.RightArrow or \
           event.key() == Qt.UpArrow or \
           event.key() == Qt.DownArrow or \
           event.key() == Qt.ArrowCursor or \
           event.key() == keyLeft or \
           event.key() == keyRight or \
           event.key() == keyUp or \
           event.key() == keyDown or \
           event.key() == keyReturn or \
           event.key() == Qt.Key_Delete:
            QLineEdit.keyPressEvent(self, event)
        else:
            pass

class QLineEditDirectoriesOnly(QLineEdit):
    """ Subclassing PySide.QtGui.QLineEdit to add field validation ability """
    def __init__(self):
        super(QLineEditDirectoriesOnly, self).__init__()

    def focusOutEvent(self, event): #Override
        if self.text() == '':
            Progress.statuses['DirectoryChanged'] = True
            QLineEdit.focusOutEvent(self, event)
            return
        fm = FileManip()
        if fm.VerifyExists(self.text()) != True:
            QMessageBox.warning(self, 'Error',
                                "The path you specified cannot be located.\n\n Could not find: \"{}\"".format(self.text()),
                                QMessageBox.Ok)
            self.setFocus()
            return
        Progress.statuses['DirectoryChanged'] = True
        QLineEdit.focusOutEvent(self, event)

class MainWindow(QMainWindow):
    """ Starting point of the GUI based application """
    isMyProgressTimer = False
    def __init__(self):        
        """ MainWindow Constructor Function"""
        super(MainWindow, self).__init__()
        wdgt = QWidget()
        wdgt.setWindowTitle = "ManageHD"
        self.setCentralWidget(wdgt)
        self.InitUI()
        self.GetParameterFileInfo()        
    
    def InitUI(self):        
        """ Initialize user created UI elements """
        self.qlVidsDone         = QLabel('0', self)
        self.qlVidsInProgress   = QLabel('0', self)
        self.qlStartTime        = QLabel(datetime.now().strftime("%a, %d %b %Y %H:%M:%S"), self)
        self.qlEndTime          = QLabel('', self)
        self.qlTimeLeft         = QLabel('', self)
        self.qlDestinationSpace = QLabel('', self)
        self.qlArcSpace         = QLabel('', self)
        self.qlProcessingSpeed  = QLabel('', self)
        
        self.qleSourceDir       = QLineEditDirectoriesOnly()
        self.qleArchiveDir      = QLineEditDirectoriesOnly()
        self.qleDestinationDir  = QLineEditDirectoriesOnly()
        self.qleMaxVidsCap      = QLineEditIntsOnly()
        self.qleVideoTypes      = QLineEditNoPeriodsOrCommas()
        self.qleVideoTypes.installEventFilter(self)
        
        self.qpbSourceDir       = self.__CreateButton('folder.png',"", 50, self.SelectSingleFileForSourceDirectory)
        self.qpbArchiveDir      = self.__CreateButton('folder.png',"", 50, self.SelectSingleFileForArchiveDirectory)
        self.qpbTargetDir       = self.__CreateButton('folder.png',"", 50, self.SelectSingleFileForTargetDirectory)
        self.qpbRun             = self.__CreateButton(None,"Run", 75, self.Process)        
        
        self.setWindowTitle("Manage HD Video")
        self.videoExtensionFileFilter = "Video (*.mkv *.mp4 *.avi)"
        self.qleVideoTypes.setText("mkv mp4 avi")
        self.statusLabel = QLabel('Showing Progress')
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.__CreateActions()
        self.__CreateMenus()
        self.fileMenu.addAction(self.stdAction)
        self.fileMenu.addAction(self.altAction)
        if Progress.runPlatform == 'win':
            self.stdAction.setIcon(QIcon('checked.jpg'))
        self.stdAction.setChecked(True)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.exitAction)
        self.fileMenu.addSeparator()
        self.helpMenu.addAction(self.aboutAction)
        self.__SetIcon()
        self.__CenterWindow()
        self.__CreateGrid()       

    def eventFilter(self, source, event): #Override
        """ Override the QMainWindow eventFilter method to add File Mask Validation. """
        if (event.type() == QEvent.FocusOut and
            source is self.qleVideoTypes):
            self.ValidateFileMask()
        return QMainWindow.eventFilter(self, source, event)
    
    def DisableGuiElements(self):
        """ Change the setEnabled property of the main GUI elements to False. """
        self.qleArchiveDir.setEnabled(False)
        self.qleDestinationDir.setEnabled(False)
        self.qleMaxVidsCap.setEnabled(False)
        self.qleSourceDir.setEnabled(False)
        self.qleVideoTypes.setEnabled(False)

        self.qpbArchiveDir.setEnabled(False)
        self.qpbSourceDir.setEnabled(False)
        self.qpbTargetDir.setEnabled(False)
        self.qpbRun.setEnabled(False)

    def EnableGuiElements(self):
        """ Change the setEnabled property of the main GUI elements to True. """
        self.qleArchiveDir.setEnabled(True)
        self.qleDestinationDir.setEnabled(True)
        self.qleMaxVidsCap.setEnabled(True)
        self.qleSourceDir.setEnabled(True)
        self.qleVideoTypes.setEnabled(True)
        
        self.qpbArchiveDir.setEnabled(True)
        self.qpbSourceDir.setEnabled(True)
        self.qpbTargetDir.setEnabled(True)
        self.qpbRun.setEnabled(True)

    def __AddGridLabel(self, grid, lblText, custFont, row, column, justification):
        sd = QLabel(lblText, self)
        sd.setFont(custFont)
        grid.addWidget(sd, row, column, alignment = justification)        

    def SelectSingleFileForSourceDirectory(self):
        self.qleSourceDir.setText( self.InvokeSingleSelectionDirectoryDialog() )
        self.ValidateFileMask()

    def SelectSingleFileForArchiveDirectory(self):
        self.qleArchiveDir.setText( self.InvokeSingleSelectionDirectoryDialog() )
    
    def SelectSingleFileForTargetDirectory(self):
        self.qleDestinationDir.setText( self.InvokeSingleSelectionDirectoryDialog() )

    def InvokeSingleSelectionFileDialog(self):
        """ Prompts the user to select a single file from a file dialog window. """
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setFilter(self.videoExtensionFileFilter)        
        ret = dialog.exec_()
        FileNames = dialog.selectedFiles()
        if len(FileNames) == 0:
            FileNames.append(None)
        return FileNames[0]
    
    def InvokeSingleSelectionDirectoryDialog(self):
        """ Prompts the user to select a single directory from a directory dialog window. """
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.DirectoryOnly)        
        DirectoryName = dialog.getExistingDirectory()
        if len(DirectoryName) == 0:
            DirectoryName = None
        return DirectoryName

    def ValidateFileMask(self):
        """ Function to validate that the entered file mask is valid. """
        extensionList = ""
        if len(self.qleVideoTypes.text().split(" ")) > 0:
            for videoExtension in self.qleVideoTypes.text().split(" "):
                extensionList += ("*." + videoExtension + " ")
            extensionList = extensionList[:-1]
        self.videoExtensionFileFilter = "Video ({})".format(extensionList)        
        
    def __CreateGrid(self):
        g1 = QGridLayout()
        self.centralWidget().setLayout(g1)

        g1.setSpacing(5)

        bold = QFont()
        bold.setBold(True)
        self.__AddGridLabel(g1, 'Source Directory:', QFont(), 0, 0, -1)
        self.__AddGridLabel(g1, 'Archive Directory:', QFont(), 1, 0, -1)
        self.__AddGridLabel(g1, 'Target Directory:', QFont(), 2, 0, -1)
        self.__AddGridLabel(g1, 'Max Number of Videos:', QFont(), 3, 0, -1)
        self.__AddGridLabel(g1, 'Video File Types:', QFont(), 3, 2, -1)
        #self.__AddGridLabel(g1, 'Max Run Time in Hours:', QFont(), 4, 2, -1)

        g1.addWidget(self.qleSourceDir, 0, 1, 1, 3)
        g1.addWidget(self.qleArchiveDir, 1, 1, 1, 3)
        g1.addWidget(self.qleDestinationDir, 2, 1, 1, 3)
        g1.addWidget(self.qleMaxVidsCap, 3, 1)
        g1.addWidget(self.qleVideoTypes, 3, 3)
        #g1.addWidget(self.qleRunTimeMax, 4, 3)
        
        g1.addWidget(self.qpbRun, 10, 3, alignment = -1)
        
        g1.addWidget(QLabel('', self), 4, 0,) # Empty Column As Separator
        g1.addWidget(QLabel('', self), 5, 0,) # Empty Column As Separator
        
        self.__AddGridLabel(g1, 'Videos Completed:',   bold, 5, 0, -1)
        self.__AddGridLabel(g1, 'Start Time:',         bold, 5, 2, -1)
        self.__AddGridLabel(g1, 'Videos In Progress:', bold, 6, 0, -1)
        self.__AddGridLabel(g1, 'Time Remaining:',     bold, 7, 2, -1)
        self.__AddGridLabel(g1, 'Target Space Left:',  bold, 7, 0, -1)
        self.__AddGridLabel(g1, 'Archive Space Left:', bold, 8, 0, -1)
        self.__AddGridLabel(g1, 'End Time:',           bold, 6, 2, -1)
        self.__AddGridLabel(g1, 'Processing Speed:',   bold, 8, 2, -1)
        
        g1.addWidget(self.qlVidsDone,        5, 1,) 
        g1.addWidget(self.qlVidsInProgress,  6, 1)
        g1.addWidget(self.qlStartTime,       5, 3,) 
        g1.addWidget(self.qlEndTime,         6, 3,) 
        g1.addWidget(self.qlTimeLeft,        7, 3,) 
        g1.addWidget(self.qlDestinationSpace,     7, 1,) 
        g1.addWidget(self.qlArcSpace,        8, 1,)
        g1.addWidget(self.qlProcessingSpeed, 8, 3,)
        
        g1.addWidget(self.qpbSourceDir,      0, 4,)
        g1.addWidget(self.qpbArchiveDir,     1, 4,)
        g1.addWidget(self.qpbTargetDir,      2, 4,)        
        self.show
        
    def GetParameterFileInfo(self):
        Progress.DeterminePlatform()
        fm = FileManip()
        #params = Progress.cliParams.copy()
        params = fm.ReadSettingsFile()
        self.qlProcessingSpeed.setText(str(Progress.cliParams['ProcessingSpeedInGBperHour']))
        self.qleSourceDir.setText(params['sourceDir'])
        self.qleArchiveDir.setText(params['archiveDir'])
        self.qleDestinationDir.setText(params['destinationDir'])
        
    def GetDriveSpace(self, path):
        """ Call the GetDriveSpace() method using an instance of the FileManip class. """
        fm = FileManip() 
        return fm.GetDriveSpace(path)

    def ResetStats(self):
        """ Change statistical data displays back to their original initialized values. """
        Progress.ResetStatuses()
        self.qlVidsDone.setText( '0')
        self.qlVidsInProgress.setText('0')
        self.qlStartTime.setText(datetime.now().strftime("%a, %d %b %Y %H:%M:%S"))
        self.qlTimeLeft.setText("")
        if self.qleDestinationDir.text() != "":
            self.qlDestinationSpace.setText(str(self.GetDriveSpace(self.qleDestinationDir.text())))
        if self.qleArchiveDir.text() != "":
            self.qlArcSpace.setText(str(self.GetDriveSpace(self.qleArchiveDir.text())))
        self.qlEndTime.setText("")
        self.qlProcessingSpeed.setText("")
    
    def VerifyRequiredFieldsFilled(self):
        """ Cancels the RUN functionality and informs the user via Message Box if the required fields are not all completed. """
        if self.qleSourceDir.text() == "" or \
            self.qleVideoTypes.text() == "" or \
            self.qleDestinationDir.text() == "":
            QMessageBox.critical(self, "Required Field Error", 
                                 "You have not filled out the three required fields. "
                                 "'Source Directory', "
                                 "'Target Directory' and "
                                 "'Video File Types' "
                                 "are all required Fields.", QMessageBox.Ok)
            return 0
        return True        

    def Process(self):
        """ Batch processing of the source video files begins here. """
        result = self.VerifyRequiredFieldsFilled()
        if result != True:
            return
        self.ResetStats()
        
        Progress.statuses['ProcessingComplete'] = False
        self.DisableGuiElements()
        Params = Progress.cliParams.copy() 
        Params['sourceDir']      = self.qleSourceDir.text()
        Params['archiveDir']     = self.qleArchiveDir.text()
        Params['destinationDir'] = self.qleDestinationDir.text()

        maximumNumVids = ""
        for idx in range(0, len(self.qleMaxVidsCap.text())):
            if self.qleMaxVidsCap.text()[idx] != '.':
                maximumNumVids = maximumNumVids + self.qleMaxVidsCap.text()[idx]

        if maximumNumVids.isnumeric():
            Params['maxNumberOfVideosToProcess']  = '%1.f' % float(self.qleMaxVidsCap.text())

        if len(self.qleVideoTypes.text().split(" ")) > 0:
            extensionList = ""
            for videoExtension in self.qleVideoTypes.text().split(" "):
                extensionList += (videoExtension + ",")
        else:
            extensionList = None

        Params['videoTypes']     = extensionList
        
        #Create and instance of the processing class
        pm = ProcessMovies()

        #Disable applicable GUI elements
        self.DisableGuiElements

        #Spawn a thread to run this
        Thread(target=pm.StartWithGUI, args=(Params,)).start()

        sleep(1)
        self.qlTimeLeft.setText(Progress.CalculateTimeRemaining())
        Progress.statuses['StatusesHaveChanged'] = True
        return

    def __CreateButton(self, folderIcon, txt, pxSize, actionFunction):
        """ Function to add a button """
        if folderIcon != None:
            folderIcon = QIcon('folder.png')
            myButton = QPushButton(folderIcon, "")
        else:
            myButton = QPushButton(txt)
        myButton.setMaximumWidth(pxSize)
        myButton.clicked.connect(actionFunction)
        return myButton

    def aboutHelp(self):
        """ Displays the ABOUT box and sets its content. """
        QMessageBox.about(self, "About ManageHD",
                          "Program written in Python v3.4 \n\n"
                          "ManageHD allows you to select an entire "
                          "directory of HD video files and lower their "
                          "resolution from 1080 HD to 720 HD, in batch. "
                          "It calls the HandBrake Command Line Interface "
                          "(CLI) in order to re-encode each video. \n\nYou must "
                          "have the Handbrake CLI installed to use this "
                          "software. "
                          "The CLI (command line interface) can be downloaded at:\n\n "
                          "     http://handbrake.fr/downloads2.php \n\n"
                          "The average video file at 720 HD "
                          "is generally one fourth to one sixth the size "
                          "of its 1080 HD source file. \n\n"
                          "Coding was done by InfanteLabz. \n\n"
                          "This sofware is released under GPL v3 "
                          "licensing. ")

    def exitFile(self):
        """ Exits the Main Window, ending the program. """
        self.close()

    def __CreateActions(self):
        """ Function to create actions for menus """
        self.stdAction = QAction(QIcon('convert.png'), 
                                'Create MKV files',
                                self, shortcut = "Ctrl+K",
                                statusTip = "File format set to MKV container",
                                triggered = self.stdConversion,
                                checkable = True)

        self.altAction = QAction(QIcon('convert.png'), 
                                'Create MP4 files',
                                self, shortcut = "Ctrl+P",
                                statusTip = "File format set to MP4 file",
                                triggered = self.altConversion,
                                checkable = True)

        self.exitAction = QAction(QIcon('exit.png'),
                                  '&Quit',
                                  self, shortcut="Ctrl+Q",
                                  statusTip = "Exit the Application",
                                  triggered=self.exitFile)

        #self.copyAction = QAction(QIcon('copy.png'), 'C&opy',
                                  #self, shortcut="Ctrl+C",
                                  #statusTip="Copy",
                                  #triggered=self.CopyFunction)

        self.aboutAction = QAction(QIcon('about.png'), 'A&bout',
                                   self, statusTip="Displays info about ManageHD",
                                   triggered=self.aboutHelp)

    def __CreateMenus(self):
        """ Function to create actual menu bar """
        self.fileMenu = self.menuBar().addMenu("&File")
        self.helpMenu = self.menuBar().addMenu("&Help")
        
    def __CenterWindow(self):
        """ Function to center the window """
        qRect = self.frameGeometry()
        centerPoint = QDesktopWidget().availableGeometry().center()
        qRect.moveCenter(centerPoint)
        self.move(qRect.topLeft())
    
    def __SetAboutBox(self):
        """ Function to position and wire the ABOUT box """
        self.aboutButton = QPushButton("About", self)
        self.aboutButton.move(200, 100)
        self.aboutButton.clicked.connect(self.ShowAbout)
        
    def __SetIcon(self):
        """ Function to set Icon """
        appIcon = QIcon('ManageHD_Icon.png')
        self.setWindowIcon(appIcon)

    def DisplayAbnormalTerminationStatus(self, status): # Not Implemented
        pass

    def GetArchiveDirectory(self): # Not Implemented
        pass
    
    def stdConversion(self):
        """ Called by the STANDARD menu item under FILE. Sets ManageHD to perform the standard Handbrake conversion. """
        Progress.statuses['HandbrakeOptionsString'] = str(" -i {0} -o {1} -f mkv --width 1280 --crop 0:0:0:0 --decomb -s 1 -N eng -m --large-file --encoder x264 -q 19 -E ffac3")
        Progress.statuses['OutputExtension'] = 'mkv'
        self.altAction.setChecked(False)
        if Progress.runPlatform == "win":
            self.altAction.setIcon(QIcon('convert.png'))
            self.stdAction.setIcon(QIcon('checked.jpg'))
        self.stdAction.setChecked(True)
    
    def altConversion(self):
        """ Called by the ALTERNATE menu item under FILE. Sets ManageHD to perform Handbrake conversions using an alternate series of settings. """
        Progress.statuses['HandbrakeOptionsString'] = str(" -i {0} -o {1} -f mp4 --width 1280 --crop 0:0:0:0 --decomb -s 1 -N eng -m --large-file --encoder x264 -q 19 -E ffac3")
        Progress.statuses['OutputExtension'] = 'mp4'
        self.stdAction.setChecked(False)
        if Progress.runPlatform == "win":
            self.altAction.setIcon(QIcon('checked.jpg'))
            self.stdAction.setIcon(QIcon('convert.png'))
        self.altAction.setChecked(True)

    def CopyFunction(): # Not Implemented
        pass
        
    def ValidateAndRun(self): # Not Implemented
        pass
       

class ProgressUpdateTimer(QWidget):
    """ Class update progress """    
    def __init__(self, main):
        """ Constructor Function """
        QWidget.__init__(self)
        self.target = main
        timer = QTimer(self)
        self.connect(timer, SIGNAL("timeout()"), self.UpdateProgressStats)
        timer.start(100)
        pygame.init()

    def UpdateProgressStats(self):
        """ Function to update the progress statistics """
        self.__CheckForDirectoryChange()
        self.__CheckForExistenceOfVideoFiles()        
        self.__CheckForInvalidQuotingInFileName()
        self.__CheckForInsufficientSpaceOnArchive()
        self.__CheckForBatchCompletion()
        self.__CheckForChangeInStatistics()
        
    def __CheckForDirectoryChange(self):
        if Progress.statuses['DirectoryChanged']:
            Progress.cliParams['sourceDir'] = self.target.qleSourceDir.text()
            Progress.cliParams['archiveDir'] = self.target.qleArchiveDir.text()
            Progress.cliParams['destinationDir'] = self.target.qleDestinationDir.text()

    def __CheckForInsufficientSpaceOnArchive(self):
        if Progress.statuses['BatchStatus'] == 'Insufficient Drive Space': #other possible value is 'Completed'    
            boxChoice = QMessageBox.question(self, 'Message',
                    "There is insufficient room on your archive drive. Would you "
                    "like to make room and try again? Selecting 'No' will skip archiving. "
                    , QMessageBox.Yes | 
                    QMessageBox.No, QMessageBox.No)
            if boxChoice == QMessageBox.Yes:
                Progress.ArchiveSourceVideo(self.qleArchiveDir.text(), self.qleSourceDir.text(), self.qleTargetDir.text())
            
    def __CheckForExistenceOfVideoFiles(self):        
        if Progress.statuses['NoVideoFilesFound'] == True:
            Progress.statuses['NoVideoFilesFound'] = 0
            QMessageBox.warning(self, 'Warning',
                    "There were no video files ending with the video file type(s) of \"{}\" located "
                    "in the specified source directory. Please verify the file extensions of your "
                    "videos and try again.".format(self.target.qleVideoTypes.text())
                    , QMessageBox.Ok)
            self.target.ResetStats()
            self.target.EnableGuiElements()
            self.target.qlProcessingSpeed.setText("")

    def __CheckForInvalidQuotingInFileName(self):
        if Progress.statuses['InvalidQuotingInFileName'] != "":
            QMessageBox.critical(self, "Invalid Filename", \
                                 "Filename(s) containing a double"
                                 "quote (\") detected, skipping file.", QMessageBox.Ok)
            Progress.statuses['InvalidQuotingInFileName'] = ""     

    def __CheckForBatchCompletion(self):
        fm = FileManip()
        if Progress.statuses['VideosCurrent'] == 0 and \
           Progress.statuses['VideosCompleted'] != 0 and \
           Progress.statuses['TimeRemaining'] != 'Done':
            self.target.EnableGuiElements()
            if self.target.qlEndTime.text() == "" or self.target.qlEndTime.text() == None:
                self.target.qlEndTime.setText(datetime.now().strftime("%a, %d %b %Y %H:%M:%S"))                
                self.target.qlTimeLeft.setText('Done')
                self.target.qlDestinationSpace.setText(str(self.target.GetDriveSpace(self.target.qleDestinationDir.text())))
                if self.target.qleArchiveDir.text() != "":
                    self.target.qlArcSpace.setText(str(self.target.GetDriveSpace(self.target.qleArchiveDir.text())))
                Progress.statuses['TimeRemaining'] = 'Done'
                pygame.mixer.music.load("ding.mp3")
                pygame.mixer.music.set_volume(0.3)
                pygame.mixer.music.play()                        
                status = Progress.statuses['ProcessingCompleteStatus']
                if status != None:
                    self.target.DisplayAbnormalTerminationStatus(status)
                    Progress.statuses['ProcessingCompleteStatus'] = None
                    Progress.statuses['ProcessingComplete'] = False
                fm.WriteSettingsFile()
                


    def __CheckForChangeInStatistics(self):
        if Progress.statuses['StatusesHaveChanged'] == True:            
            self.target.qlVidsDone.setText(str(Progress.statuses['VideosCompleted']))
            self.target.qlVidsInProgress.setText(str(Progress.statuses['VideosCurrent']))
            self.target.qlStartTime.setText(str(Progress.statuses['StartTime'].strftime("%a, %d %b %Y %H:%M:%S")))
            if self.target.qlDestinationSpace.text() == "":
                self.target.qlProcessingSpeed.setText("0")
            if Progress.statuses['ProcessingSpeedInGBperHour'] == 0 and \
               self.target.qlDestinationSpace.text() != "":                  
                if Progress.cliParams['ProcessingSpeedInGBperHour'] != 0:
                    self.target.qlProcessingSpeed.setText(Progress.cliParams['ProcessingSpeedInGBperHour'])
                else:
                    self.target.qlProcessingSpeed.setText("Calc'd at end of 1st video ...")
            elif self.target.qlDestinationSpace.text() != "":
                self.target.qlProcessingSpeed.setText('%.1f' % Progress.statuses['ProcessingSpeedInGBperHour'] + " GB/hour")
            else:
                self.target.qlProcessingSpeed.setText("0")
            
            if Progress.statuses['TimeRemaining'] != 0:                
                if self.target.qlTimeLeft.text() != "Done":
                    self.target.qlTimeLeft.setText(str(Progress.statuses['TimeRemaining']))
            Progress.statuses['StatusesHaveChanged'] = False


if __name__ == '__main__':
    myApp = QApplication(sys.argv)
    
    mw = MainWindow()
    mw.ResetStats()
    mw.show()
    
    ProgressTimer = ProgressUpdateTimer(mw)
    myApp.exec_()
    sys.exit()
