  --------
- ManageHD -
  --------
  
A python v3.4 program written using the Wing IDE.

Wing IDE is professional level Python IDE written from the 
ground up specifically for Python. Is is available at:

	http://wingware.com

ManageHD allows you to select an entire directory of HD 
video files and lower their resolution from 1080 HD 
to 720 HD, in batch. It allows for setting a maximum number
of video files to convert. Only videos of the indicated type
will be converted, but more types can be added. If no maximum 
number of videos to convert is indicated then the software 
by default will convert all videos in the source directory. 
Archiving the original video to another location is also 
supported. If the archive location is omitted then the 
default is not to archiving the source files. 

ManageHD calls the HandBrake Command Line Interface (CLI) in 
order to re-encode each video. 

You *must* have the Handbrake CLI installed to use this software. 

The CLI for your platform can be downloaded at:

     http://handbrake.fr/downloads2.php

The average video file at 720 HD is generally one fourth to 
one sixth the size of its 1080 HD source file.

Submit bugs via email (with a subject of 'ManageHD Bug') to:

    InfanteLabz@gmail.com

	Please include information on how to recreate the bug
	and what platform you are running on (Mac, Windows, 
	Linux). Thanks!
	
Author: W. Infante

This sofware is released under GPL v3 licensing (read the 
included license file - gpl.txt). 

Files included in this release:
    ManageHD.py         ManageHD_GUI.py
    MangeHD_Icon.png    checked.jpg
    convert.png         copy.png
    ding.mp3            exit.png
    folder.png          new.png
    gpl.txt

Python Libraries Called:
    sys                os
    string             ctypes
    pygame             Thread
    datetime           sleep
    PySide.QtCore      PySide.QtGui

To get the source code from the GitHub repo:

	git clone git://github.com/DominicanKnight/ManageHD.git

	or, go to 
	
	https://github.com/DominicanKnight/ManageHD
	
	and click the 'Download Zip' button near the bottom right 
	of the page.

