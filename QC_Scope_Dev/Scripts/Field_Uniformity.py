# Import General Features
import os
import sys
import csv
from math import sqrt, floor

# Import ImageJ Features
from ij import IJ, ImagePlus, Prefs, WindowManager
from ij.process import ImageProcessor, FloatProcessor, ByteProcessor, ImageStatistics, ImageConverter
from ij.gui import Overlay, TextRoi
from ij.plugin import Duplicator, Zoom
from ij.measure import Measurements, ResultsTable
from ij.plugin.frame import RoiManager
from ij.plugin.filter import GaussianBlur

# Import Bioformat Features
from loci.plugins import BF
from loci.plugins.in import ImporterOptions
from loci.formats import MetadataTools, ImageReader

# Import Java Features
from java.io import File
from java.awt import Font, Color, GridLayout, GridBagLayout, GridBagConstraints, Insets, Frame, Panel, Button, Label
from javax.swing import JOptionPane, JFileChooser, JTextField, JLabel, JSeparator, JRadioButton, ButtonGroup, JSlider,JButton, JCheckBox, JPanel, JFrame, SwingUtilities, JDialog
from java.awt.event import ActionListener
from javax.swing.event import ChangeListener
import java.lang.System


# -*- coding: utf-8 -*-
reload(sys)
sys.setdefaultencoding('utf-8')


# Defining some constants
Plugin_Name = "QC Scope"
Function_Name = "Field Uniformity"
Unicode_Micron_Symbol = "u" #chr(0xB5)
Reset_Preferences = False # Usefull to reset Preferences with the template
User_Desktop_Path = os.path.join(os.path.expanduser("~"), "Desktop") # Used for Saving the Output DIrectory and as a default for selecting an input directory
Output_Dir = os.path.join(User_Desktop_Path, "Output") # Where all files are saved

# Tuple (List) of supported image file extensions. When an input folder is selected only images with these extensions are selected
Image_Valid_Extensions = (".tif", ".tiff", ".jpg", ".jpeg", ".png", ".czi", ".nd2", ".lif", ".lsm", ".ome.tif", ".ome.tiff")

# Provide possilble space units and an normalized correspondance
Space_Unit_Conversion_Dictionary = {
	"micron": Unicode_Micron_Symbol + "m",
	"microns":Unicode_Micron_Symbol + "m",
	Unicode_Micron_Symbol + "m": Unicode_Micron_Symbol + "m",
	"um": Unicode_Micron_Symbol + "m",
	"u": Unicode_Micron_Symbol + "m",
	"nm": "nm",
	"nanometer": "nm",
	"nanometers": "nm",
	"mm": "mm",
	"millimeter": "mm",
	"millimeters": "mm",
	"cm": "cm",
	"centimeter": "cm",
	"centimeters": "cm",
	"m": "m",
	"meter": "m",
	"meters": "m",
	"inch": "in",
	"inches": "in",
	"in": "in",
	"pixel": "pixels",
	"pixels": "pixels",
	"": "pixels",
	}

# Dictionnary of Settings
Settings_Templates_List={
"Field_Uniformity.Settings_Template": {
	"Field_Uniformity.Gaussian_Blur": True,
	"Field_Uniformity.Gaussian_Sigma": 10.0,
	"Field_Uniformity.Binning_Method": "Iso-Density",
	"Field_Uniformity.Batch_Mode": False,
	"Field_Uniformity.Save_Individual_Files": True,
	"Field_Uniformity.Prolix_Mode": True
	},

"Microscope_Settings_Template": {
	"Field_Uniformity.Microscope_Objective_Mag": "5x",
	"Field_Uniformity.Microscope_Objective_NA": 1.0,
	"Field_Uniformity.Microscope_Objective_Immersion": "Air",
	"Field_Uniformity.Microscope_Channel_Names": ["DAPI", "Alexa488", "Alexa555", "Alexa647", "Alexa730","Alexa731","Alexa732","Alexa733"],
	"Field_Uniformity.Microscope_Channel_WavelengthsEM": [425, 488, 555, 647, 730, 731, 732, 733]
	}
}


# Some Usefull functions
# Make Sure to get all measurements are selected in ImageJ
IJ.run("Set Measurements...", "area mean standard modal min centroid center perimeter bounding fit shape feret's integrated median skewness kurtosis area_fraction stack redirect=None decimal=3");

# Display a message in the log only in Prolix_Mode
def Prolix_Message(Message):
	Field_Uniformity_Settings_Stored=Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
	if Field_Uniformity_Settings_Stored["Field_Uniformity.Prolix_Mode"]:
		IJ.log(Message)

# Check if Setting in the Setting List are in the Preferences. If not, write them from the Templates. Also used to Reset Settings
def Initialize_Preferences(Settings_Templates_List, Reset_Preferences):
	for SettingsGroup in Settings_Templates_List.keys():
	 	for Setting, Value in Settings_Templates_List[SettingsGroup].items():
		 	if Prefs.get(Setting, None) is None:
				Save_Preferences(Settings_Templates_List[SettingsGroup])
 				break
		if Reset_Preferences:
			Save_Preferences(Settings_Templates_List[SettingsGroup])
	return None

# Read the Preferences an return a dictionnary with the settings
def Read_Preferences(Settings_Template):
	Preferences_Stored = {}
	for key, default_value in Settings_Template.items():
		value = Prefs.get(key, str(default_value))
		# Use the Type of data defined from the Settings Template to convert the settings from the Pref in the correct type
		if isinstance(default_value, bool):
			value = bool(int(value))
		elif isinstance(default_value, float):
			value = float(value)
		elif isinstance(default_value, int):
			value = int(value)
		elif isinstance(default_value, list):
			if isinstance(default_value[0], int):
	 			value = [int(round(float(item))) for item in value.split(",")]
			elif isinstance(default_value[0], float):
				value = [float(item) for item in value.split(",")]
			else:
				value = [str(item) for item in value.split(",")]
		else:
			value = str(value)
		Preferences_Stored[key] = value
	return Preferences_Stored # A dictionary of the Settings

# Save Settings in the Preference File
def Save_Preferences(Settings):
	for key, value in Settings.items():
		if isinstance(value, list):
			value = ",".join(map(str, value)) # If the value is a list join it with ","
		elif isinstance(value, bool):
			value = int(value) # If the value is boolean convert to integer because for some reasone writing False as string does not work
		else:
			value = value
		Prefs.set(key, str(value)) # Write the Preferences as strings
	Prefs.savePreferences()

# Get Images either from the opened ones or from a selected folder.
# Return Image_List a list of ImageTitle OR a List of File path
def Get_Images():
	Prolix_Message("Getting Images...")
	if WindowManager.getImageTitles(): # Get titles of all open images
		Image_List = WindowManager.getImageTitles()
		Image_List = [str(image) for image in Image_List]
		Prolix_Message("Opened images found: "+"\n".join(Image_List))
	else:
		Image_List=[]
		while not Image_List:
			Input_Dir_Path = Select_Folder(Default_Path = User_Desktop_Path)
			for Root, Dirs, Files in os.walk(Input_Dir_Path): # Get Files Recursively
			# Files = os.listdir(Input_Dir_Path): # Comment the line above and uncomment this line if you don"t want to get files recurcively
				for File in Files:
					if File.lower().endswith(tuple(Image_Valid_Extensions)): # Select only files ending with a Image_Valid_extensions
						Image_List.append(str(os.path.join(Root, File)))
			if not Image_List:
				Message = "No valid image files found in the selected folder."
				Advice = "Valid image file extensions are: " + ", ".join(Image_Valid_Extensions)
				IJ.log(Message+"\n"+Advice)
				JOptionPane.showMessageDialog(None, Message+"\n"+Advice, Plugin_Name+" "+Function_Name, JOptionPane.INFORMATION_MESSAGE)
		Prolix_Message("Images found:\n"+"\n".join(Image_List))
	return Image_List

# Return InputDir_Path as a string. Used in Get_Images
def Select_Folder(Default_Path):
	Prolix_Message("Selecting Folder...")
	Chooser = JFileChooser(Default_Path)
	Chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)
	Chooser.setDialogTitle("Choose a directory containing the images to process")
	Return_Value = Chooser.showOpenDialog(None)
	if Return_Value == JFileChooser.APPROVE_OPTION:
		InputDir_Path = Chooser.getSelectedFile().getAbsolutePath()
	else:
		Message="Folder selection was canceled by user."
		IJ.log(Message)
		JOptionPane.showMessageDialog(None, Message, Plugin_Name+" "+Function_Name, JOptionPane.INFORMATION_MESSAGE)
		sys.exit(Message)
	Prolix_Message("Selecting Folder: " + InputDir_Path + ". Done.")
	return InputDir_Path

# Open an image using Bioformat
def Open_Image_Bioformats(File_Path):
	Prolix_Message("Importing " + str(File_Path) + " with Bioformats...")
	Bioformat_Options = ImporterOptions()
	Bioformat_Options.setId(File_Path)
	try:
		imps = BF.openImagePlus(Bioformat_Options)
		if imps and len(imps) > 0:
			Prolix_Message("Importing " + str(File_Path) + " with Bioformats. Done.")
			return imps[0]
		else:
			IJ.log("Importing with Bioformats: No Images found in the file: " + File_Path + ".")
			return None
	except Exception,  Error:
		Prolix_Message("Importing with Bioformats: Error opening file" + str(Error) + ".")
		return None

# Generate a Unique filepath Directory\Basename_Suffix-001.Extension
def Generate_Unique_Filepath(Directory, Basename, Suffix, Extension):
	Prolix_Message("Generating Unique Filepath for: " + str(Basename) + "...")
	File_Counter = 1
	while True:
		Filename = "{}_{}-{:03d}{}".format(Basename, Suffix, File_Counter, Extension)
		Filepath = os.path.join(Directory, Filename)
		if not os.path.exists(Filepath):
			Prolix_Message("Generating Unique Filepath for: " + str(Basename) + ". Done.")
			return Filepath
		File_Counter += 1

# Match the Image Space Unit to a defined Standard Space Unit: m, cm, mm, micronSymbo+"m", nm
def Normalize_Space_Unit(Space_Unit):
	Prolix_Message("Standardizing space unit: " + str(Space_Unit) + "...")
	Space_Unit_Std = Space_Unit_Conversion_Dictionary.get(Space_Unit.lower(), "pixels")
	Prolix_Message("Standardizing space unit from " + str(Space_Unit) + " to " + str(Space_Unit_Std) + ".")
	return Space_Unit_Std


# Get Image Information. Works only on files written on the disk
# Return Image_Info a dictionnary including all image information
# This function also Normalize the Space Unit without writing it to the file
def Get_Image_Info(imp):
	Image_Name=imp.getTitle()
	Prolix_Message("Getting Image Info for: " + Image_Name + "...")
	File_Info = imp.getOriginalFileInfo()
	if File_Info is not None and File_Info.directory is not None:
		Filename = File_Info.fileName
		Input_Dir = File_Info.directory
		Input_File_Path = os.path.join(Input_Dir, Filename)
	else:
		Filename = "Unsaved Image"
		Input_Dir = "N/A"
		Input_File_Path = "N/A"
	Basename, Extension = os.path.splitext(Filename)
	Width = imp.getWidth()
	Height = imp.getHeight()
	Nb_Channels = imp.getNChannels()
	Nb_Slices = imp.getNSlices()
	Nb_Timepoints = imp.getNFrames()
	Bit_Depth = imp.getBitDepth()
	Current_Channel = imp.getChannel()
	Current_Slice = imp.getSlice()
	Current_Frame = imp.getFrame()
	Calibration = imp.getCalibration()
	Pixel_Width = Calibration.pixelWidth
	Pixel_Height = Calibration.pixelHeight
	Pixel_Depth = Calibration.pixelDepth
	Space_Unit = Calibration.getUnit()
	Time_Unit = Calibration.getTimeUnit()
	Frame_Interval = Calibration.frameInterval
	Calibration_Status = Calibration.scaled()
	Space_Unit_Std = Normalize_Space_Unit(Space_Unit)

	# Dictionnary storing all image information
	Image_Info = {
		"Input_File_Path": str(Input_File_Path),
		"Input_Dir": str(Input_Dir),
		"Filename": str(Filename),
		"Basename": str(Basename),
		"Extension": str(Extension),
		"Image_Name": str(Image_Name),
		"Width": int(Width),
		"Height": int(Height),
		"Nb_Channels": int(Nb_Channels),
		"Nb_Slices": int(Nb_Slices),
		"Nb_Timepoints": int(Nb_Timepoints),
		"Bit_Depth": int(Bit_Depth),
		"Current_Channel": int(Current_Channel),
		"Current_Slice": int(Current_Slice),
		"Current_Frame": int(Current_Frame),
		"Calibration": Calibration,
		"Pixel_Width": float(Pixel_Width),
		"Pixel_Height": float(Pixel_Height),
		"Pixel_Depth": float(Pixel_Depth),
		"Space_Unit": Space_Unit,
		"Space_Unit_Std": Space_Unit_Std,
		"Time_Unit": str(Time_Unit),
		"Frame_Interval": float(Frame_Interval),
		"Calibration_Status": bool(Calibration_Status),
		}
	Prolix_Message("Getting Image Info for: "+Image_Name+". Done.")
	return Image_Info

# Get Image Metadata
# Return Channel_Names_Metadata (list of channel Names as strings)
# Channel_WavelengthsEM_Metadata a list of Integer
#Objective_Mag_Metadata a string
# Objective_NA_Metadata a floating
# Objective_Immersion_Metadata a string
def Get_Metadata(imp):
	Image_Name = imp.getTitle()
	Prolix_Message("Getting Metadata for: " + Image_Name + "...")
	Image_Info = Get_Image_Info(imp)
	Bioformat_Options = ImporterOptions()
	Bioformat_Options.setId(Image_Info["Input_File_Path"])
	Metadata = MetadataTools.createOMEXMLMetadata()
	Reader = ImageReader()
	Reader.setMetadataStore(Metadata)
	Reader.setId(Image_Info["Input_File_Path"])
	try:
		if Image_Info["Nb_Channels"] > 0:
			Channel_Names_Metadata = [str(Metadata.getChannelName(0, i-1)) for i in range(1, Image_Info["Nb_Channels"]+1)]
			Channel_WavelengthsEM_Metadata = []
			for i in range(1, Image_Info["Nb_Channels"]+1 ):
				WavelengthEM = Metadata.getChannelEmissionWavelength(0, i-1)
				if WavelengthEM is not None:
					# Extract numeric value from the wavelength metadata
					value_str = str(WavelengthEM)
					start = value_str.find("value[") + 6
					end = value_str.find("]", start)
					if start != -1 and end != -1:
						value = value_str[start:end]
						Channel_WavelengthsEM_Metadata.append(int(round(float(value))))
					else:
						Channel_WavelengthsEM_Metadata.append(0)
				else:
					Channel_WavelengthsEM_Metadata.append(0)
			# Check if metadata contains objective and instrument information
			if Metadata.getInstrumentCount() > 0 and Metadata.getObjectiveCount(0) > 0:
				Objective_Magnification_Metadata = str(int(Metadata.getObjectiveNominalMagnification(0,0)))+"x"
				Objective_NA_Metadata = float(Metadata.getObjectiveLensNA(0, 0))
				Objective_Immersion_Metadata = str(Metadata.getObjectiveImmersion(0, 0))
				Prolix_Message("Getting Metadata for: " + Image_Name + ". Done.")
				return Channel_Names_Metadata, Channel_WavelengthsEM_Metadata, Objective_Magnification_Metadata, Objective_NA_Metadata, Objective_Immersion_Metadata
			else:
				IJ.log(Image_Name+" does not contain metadata. Proceeding with information from Preferences...")
				return None, None, None, None, None
	except Exception, Error:
		IJ.log("Error retrieving metadata: " + str(Error))
		return None, None, None, None, None


# Main Functions to process images.
# These function ares nested as follow
# Process_Image_List To Process a list of Images. This function calls to nested functions:
	# Process_Image
		# Display_Processing_Dialog
			# Measure_Uniformity_All_Ch
				# Measure_Uniformity_Single_Ch
					# Get the Image Statistics
					# Calculate the Std_Dev
					# Calculate the Uniformity Ratio
					# Calculate the Uniformity Standard
					# Caculate the Uniformity using the 5% 95% Percentile
					# Calculate the Coeeficient of Variation
					# Bin_Image
						# Bin the Image
						# Retrieve the X and Y Coordinates of the Reference ROI
			# Measure_Uniformity_Single_Ch
	# Process_Batch_Image
		# Measure_Uniformity_All_Ch
			# Measure_Uniformity_Single_Ch





# Main Function. Process a list of opened images or a list of filepath
# First image is always processed with a dialog Process_Image
# Batch processing is used when required
# Return Data_All_Files a List of Data 1 per file
# Retrurn Processed_Images_List a list of processed images

def Process_Image_List(Image_List):
	Prolix_Message("Processing Image List")
	Processed_Images_List = []
	Data_All_Files = []

	for Image, Image_File in enumerate(Image_List):
		# Checking Image_File is an opened image
		if isinstance(Image_File, str) and not ("/" in Image_File or "\\" in Image_File):
			imp = WindowManager.getImage(Image_File)
			Image_Window = WindowManager.getFrame(imp.getTitle())
			Image_Window.toFront()
			File_Source="Opened"
		else: # Else Image_File is a path, import it with Bioformat
			imp = Open_Image_Bioformats(Image_File)
			File_Source="Folder"
		Zoom.set(imp, 0.5);
		imp.show()
		Image_Info = Get_Image_Info(imp)
		Image_Name = Image_Info["Image_Name"]
		IJ.log("Opening " + Image_Name + ".")

		# Process the first image with Process_Image function showing a Dialog
		if Image == 0:
			Prolix_Message("Processing Initial Image.")
			Data_All_Files, Processed_Images_List = Process_Image(imp, Data_All_Files, Processed_Images_List, Batch_Message="")
			IJ.log("Success processing " + Image_Name + ".")
		# For subsequent images, check if batch mode is enabled
		else:
			Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
			if Field_Uniformity_Settings_Stored["Field_Uniformity.Batch_Mode"]:
				Prolix_Message("Processing in Batch")
				Data_All_Files, Processed_Images_List = Process_Image_Batch(imp, Data_All_Files, Processed_Images_List)
				IJ.log("Success batch processing " + Image_Name + ".")
			else:
			 	Data_All_Files, Processed_Images_List = Process_Image(imp, Data_All_Files, Processed_Images_List, Batch_Message="")
				IJ.log("Success processing " + Image_Name + ".")
		if File_Source=="Folder":
			imp.close()
	return Data_All_Files, Processed_Images_List


# Process and Image showing a Dialog
# Return Data_All_Files
# Return Processed_Images_List
# Reset Batch_Message to ""
def Process_Image(imp, Data_All_Files, Processed_Images_List, Batch_Message):
	Image_Info = Get_Image_Info(imp)
	Image_Name = Image_Info["Image_Name"]
	IJ.log("Processing: " + Image_Name + "...")
	Dialog_Counter = 0
	User_Click = None
	Test_Processing = False
	while True:
		Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
		Microscope_Settings_Stored = Read_Preferences(Settings_Templates_List["Microscope_Settings_Template"])
		# Display the main dialog with Metadata and results from predetection
		Field_Uniformity_User, Microscope_Settings_User, User_Click, Dialog_Counter, Test_Processing, Batch_Message = Display_Processing_Dialog(imp, Dialog_Counter, Test_Processing, Batch_Message)
		# Filtereing some Keys to be ignored
		Field_Uniformity_Settings_Stored_Filtered = {}
		for key, value in Field_Uniformity_Settings_Stored.items():
			if key not in [
			"Field_Uniformity.Batch_Mode",
			"Field_Uniformity.Save_Individual_Files",
			"Field_Uniformity.Prolix_Mode"
			]:
				Field_Uniformity_Settings_Stored_Filtered[key] = value

		Field_Uniformity_User_Filtered = {}
		for key, value in Field_Uniformity_User.items():
			if key not in [
			"Field_Uniformity.Batch_Mode",
			"Field_Uniformity.Save_Individual_Files",
			"Field_Uniformity.Prolix_Mode"
			]:
				Field_Uniformity_User_Filtered[key] = value



		# All conditions must be fulfilled to proceed
		if User_Click == "OK" and not Test_Processing and Field_Uniformity_Settings_Stored_Filtered == Field_Uniformity_User_Filtered: #and Microscope_Settings_User == Microscope_Settings_Stored:
			break
		elif User_Click == "Cancel":
			Message = "Processing Image:" + Image_Name + ". User canceled operation."
			IJ.log(Message)
			JOptionPane.showMessageDialog(None, Message, Plugin_Name+" "+Function_Name, JOptionPane.INFORMATION_MESSAGE)
			sys.exit(Message)
	Data_File = Measure_Uniformity_All_Ch(imp, Save_File = True)
	Data_All_Files.append(Data_File)
	Processed_Images_List.append(Image_Name)
	IJ.log("Processing: " + Image_Name + ". Done.")
	return Data_All_Files, Processed_Images_List



# Process Image without Dialog Check for metadata compatibility
# Return Data_All_Files, Processed_Images_List and a Batch_Message to be passed to the Dialog in case of Metadata and Settings Mismatch
def Process_Image_Batch(imp, Data_All_Files, Processed_Images_List):
	Image_Info = Get_Image_Info(imp)
	Image_Name = Image_Info["Image_Name"]
	Nb_Channels = Image_Info["Nb_Channels"]
	IJ.log("Processing in batch: " + Image_Name + "...")

	Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
	Microscope_Settings_Stored = Read_Preferences(Settings_Templates_List["Microscope_Settings_Template"])

	# Trying to get some metadata
	Channel_Names_Metadata, Channel_WavelengthsEM_Metadata, Objective_Mag_Metadata, Objective_NA_Metadata, Objective_Immersion_Metadata = Get_Metadata(imp)

	# Check for presence of metadata and compare it with stored preferences
	Batch_Message = ""
	if Channel_Names_Metadata or Channel_Names_Metadata or Objective_Mag_Metadata or Objective_NA_Metadata or Objective_Immersion_Metadata:
		if str(Objective_Mag_Metadata) != str(Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Mag"]):
			Batch_Message = Batch_Message + "Objective Magnification Metadata: " + str(Objective_Mag_Metadata) + ". Preferences: " + str(Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Mag"]) + "."

		if float(Objective_NA_Metadata) != float(Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_NA"]):
			Batch_Message = Batch_Message + "\n" + "Objective NA Metadata: " + str(Objective_NA_Metadata) + ". Preferences: " + str(Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_NA"]) + "."

		if str(Objective_Immersion_Metadata) != str(Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Immersion"]):
			Batch_Message = Batch_Message + "\n" + "Objective Immersion Metadata: " + str(Objective_Immersion_Metadata) + ". Preferences: " + str(Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Immersion"]) + "."

		if Nb_Channels > len(Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"]):
			Batch_Message = Batch_Message + "\n" + "Nb of Channels Image: " + str(Nb_Channels) + ". Preferences: " + str(len(Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"])) + "."
		else: # Nb of Channels is sufficient check Matching values
			if Channel_Names_Metadata != Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"][:Nb_Channels]:
				Batch_Message = Batch_Message + "\n" + "Channel Names Metadata: " + ", ".join(Channel_Names_Metadata)+". Preferences: " + ", ".join(Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"][:Nb_Channels]) + "."
			if Channel_WavelengthsEM_Metadata != Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_WavelengthsEM"][:Nb_Channels]:
				Batch_Message = Batch_Message + "\n" + "Channel Emission Wavelengths Metadata: " + ", ".join(map(str, Channel_WavelengthsEM_Metadata)) + ". Preferences: " + ", ".join(map(str,Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_WavelengthsEM"][:Nb_Channels])) + "."
		if Batch_Message !="":
			Batch_Message = "Metadata differ from preferences." + "\n" + Batch_Message
			IJ.log(Batch_Message)
			Batch_Processing = "Fail"
		else:
			Batch_Processing = "Pass"
	else: # No Metadata found try with stored data
		if Nb_Channels <= len(Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"]) and Nb_Channels <= len(Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_WavelengthsEM"]):
			Batch_Processing = "Pass"
		else:
			Batch_Processing = "Fail"
	if Batch_Processing == "Pass":
		Data_File = Measure_Uniformity_All_Ch(imp, Save_File = True)
		Data_All_Files.append(Data_File)
		Processed_Images_List.append(Image_Name)
		IJ.log("Success batch processing " + Image_Name + ".")
	else:
		IJ.log("Batch processing failed for " + Image_Name + "." + "\n" + Batch_Message)
		Data_All_Files, Processed_Images_List = Process_Image(imp, Data_All_Files, Processed_Images_List, Batch_Message)
	 	IJ.log("Success processing " + Image_Name + ".")
	return Data_All_Files, Processed_Images_List



# Display a Dialog when Processing an image excepted in Batch_Mode
# Return Field_Uniformity_User, Microscope_Settings_User, User_Click, Dialog_Counter, Test_Processing, Batch_Message
# The Dialog uses Javax Swing and takes some lines... Sorry...
def Display_Processing_Dialog(imp, Dialog_Counter, Test_Processing, Batch_Message):
	Image_Info = Get_Image_Info(imp)
	Image_Name = Image_Info["Image_Name"]
	Current_Channel = Image_Info["Current_Channel"]
	Prolix_Message("Displaying Processing Dialog for: " + Image_Name + "...")

	# Getting Metadata and Stored settings
	Channel_Names_Metadata, Channel_WavelengthsEM_Metadata, Objective_Mag_Metadata, Objective_NA_Metadata, Objective_Immersion_Metadata = Get_Metadata(imp)
	Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
	Microscope_Settings_Stored = Read_Preferences(Settings_Templates_List["Microscope_Settings_Template"])

	# Displaying Metadata in priority and Stored values as fall back
	Objective_Mag = Objective_Mag_Metadata if Objective_Mag_Metadata is not None and Dialog_Counter == 0 else Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Mag"]
	Objective_NA = Objective_NA_Metadata if Objective_NA_Metadata is not None and Dialog_Counter == 0 else Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_NA"]
	Objective_Immersion = Objective_Immersion_Metadata if Objective_Immersion_Metadata and Dialog_Counter == 0 else Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Immersion"]
	Channel_Names = Channel_Names_Metadata if Channel_Names_Metadata and Dialog_Counter == 0 else Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"]
	Channel_WavelengthsEM = Channel_WavelengthsEM_Metadata if Channel_WavelengthsEM_Metadata and Dialog_Counter == 0 else Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_WavelengthsEM"]
	Channel_Names_Stored = Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"]
	Channel_WavelengthsEM_Stored = Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_WavelengthsEM"]

	# Preprocessing the file before displaying the dialog
	Data_File = Measure_Uniformity_All_Ch(imp, Save_File = False)

	# PreProcessing the Current Channel for display purposes
	Data_Ch, Duplicated_Ch_imp = Measure_Uniformity_Single_Channel(imp, Current_Channel, Save_File = False, Display = True)

	# Create the Dialog. Sorry it is messy
	Processing_Dialog = JDialog(None, Plugin_Name + " " + Function_Name, False)  # 'True' makes it modal
	Processing_Panel = JPanel()
	Processing_Panel.setLayout(GridBagLayout())
	Constraints = GridBagConstraints()
	Pos_X = 0
	Pos_Y = 0

	# Add the name of the image
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(5, 0, 5, 0)
	J_Label = JLabel(Image_Name)
	J_Label.setFont(Font("Arial", Font.BOLD, 16))
	J_Label.setForeground(Color.BLACK)
	Processing_Panel.add(J_Label, Constraints)
	Pos_Y += 1

	if Batch_Message !="":
		Batch_Message_List = Batch_Message.split('\n')
		for Message in Batch_Message_List:
			Constraints.gridx = Pos_X
			Constraints.gridy = Pos_Y
			Constraints.gridwidth = GridBagConstraints.REMAINDER
			Constraints.gridheight = 1
			Constraints.anchor = GridBagConstraints.CENTER
			Constraints.insets = Insets(2, 2, 2, 2)
			Label = "{}".format(Message)
			J_Label = JLabel(Label)
			J_Label.setFont(Font("Arial", Font.PLAIN, 12))
			J_Label.setForeground(Color.BLACK)
			Processing_Panel.add(J_Label, Constraints)
			Pos_Y += 1



	# Add Microscope Settings Title
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(10, 0, 5, 0)
	J_Label = JLabel("======================= Microscope Settings ========================")
	J_Label.setFont(Font("Arial", Font.PLAIN, 14))
	J_Label.setForeground(Color.BLACK)
	Processing_Panel.add(J_Label, Constraints)
	Pos_Y += 1

		# Add Objective Field Title
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Mag"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Constraints.gridx = Pos_X + 2
	Label = "NA"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Constraints.gridx = Pos_X + 3
	Label = "Source"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1

	# Add the Objective
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Objective"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Objective Magnification
	Constraints.gridx = Pos_X + 1
	Text=str(Objective_Mag)
	Objective_Mag_User = JTextField(Text, 3)
	Objective_Mag_User.setFont(Font("Arial", Font.PLAIN, 12))
	Objective_Mag_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Objective_Mag_User, Constraints)

	# Objective NA
	Constraints.gridx = Pos_X + 2
	Text = str(Objective_NA)
	Objective_NA_User = JTextField(Text, 2)
	Objective_NA_User.setFont(Font("Arial", Font.PLAIN, 12))
	Objective_NA_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Objective_NA_User, Constraints)

	# Source
	Constraints.gridx = Pos_X + 3
	Label = "{}".format("Metadata" if Objective_Mag_Metadata and Dialog_Counter == 0 else "Pref")
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.PLAIN, 12))
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1

	# Immersion Media
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(10, 2, 2, 2)
	Label = "Immersion Media"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1
	# Immersion Media List
	Immersion_Radio_Group = ButtonGroup()
	Immersion_Media_List = ["Air", "Water", "Oil", "Glycerin", "Silicone"]
	X_Start = Pos_X
	Y_Start = Pos_Y
	for i, Media in enumerate(Immersion_Media_List):
		Constraints.gridx = X_Start + i
		Constraints.gridy = Y_Start
		Constraints.gridwidth = 1
		Constraints.gridheight = 1
		Constraints.anchor = GridBagConstraints.CENTER
		Constraints.insets = Insets(2, 2, 2, 2)
		Immersion_Radio_Button = JRadioButton(Media)
		Immersion_Radio_Button.setFont(Font("Arial", Font.PLAIN, 12))
		Processing_Panel.add(Immersion_Radio_Button, Constraints)
		Immersion_Radio_Group.add(Immersion_Radio_Button)
		if Media == Objective_Immersion_Metadata:
			Immersion_Radio_Button.setSelected(True)

	Pos_Y += 1


	# Add Image Settings title
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(20, 0, 5, 0)
	J_Label = JLabel("========================= Image Settings ===========================")
	J_Label.setFont(Font("Arial", Font.PLAIN, 14))
	J_Label.setForeground(Color.BLACK)
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1

	# Add Image Settings Fields
	# Pixel
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Pixel"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Width
	Constraints.gridx = Pos_X+1
	Label = "Width"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Height
	Constraints.gridx = Pos_X + 2
	Label = "Height"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Depth
	Constraints.gridx = Pos_X + 3
	Label = "Depth"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Unit
	Constraints.gridx = Pos_X + 4
	Label = "Unit"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Bit Deph
	#Constraints.gridx = Pos_X + 5
	#Label = "Bit Depth"
	#J_Label = JLabel(Label)
	#J_Label.setFont(Font("Arial", Font.BOLD, 12))
	#Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1
	# Image Settings Fields Source
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label ="{0}".format("Metadata" if Image_Info["Space_Unit_Std"] != "pixels" else "Uncalibrated")
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.PLAIN, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Width
	Constraints.gridx = Pos_X + 1
	Text_Field = str(Image_Info["Pixel_Width"])
	Pixel_Width_User = JTextField(Text_Field, 5)
	Pixel_Width_User.setFont(Font("Arial", Font.PLAIN, 12))
	Pixel_Width_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Pixel_Width_User, Constraints)

	# Pixel Height
	Constraints.gridx = Pos_X + 2
	Text_Field = str(Image_Info["Pixel_Height"])
	Pixel_Height_User = JTextField(Text_Field, 5)
	Pixel_Height_User.setFont(Font("Arial", Font.PLAIN, 12))
	Pixel_Height_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Pixel_Height_User, Constraints)

	# Pixel Voxel Depth
	Constraints.gridx = Pos_X + 3
	Text_Field = str(Image_Info["Pixel_Depth"])
	Pixel_Depth_User = JTextField(Text_Field, 5)
	Pixel_Depth_User.setFont(Font("Arial", Font.PLAIN, 12))
	Pixel_Depth_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Pixel_Depth_User, Constraints)

	# Pixel Unit
	Constraints.gridx = Pos_X + 4
	Text_Field = str(Image_Info["Space_Unit_Std"])
	Space_Unit_User = JTextField(Text_Field, 5)
	Space_Unit_User.setFont(Font("Arial", Font.PLAIN, 12))
	Space_Unit_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Space_Unit_User, Constraints)

	# Bit Depth
	#Constraints.gridx = Pos_X + 5
	#Text_Field = str(Image_Info["Bit_Depth"])
	#Bit_Depth_User = JTextField(Text_Field, 3)
	#Bit_Depth_User.setFont(Font("Arial", Font.PLAIN, 12))
	#Bit_Depth_User.setHorizontalAlignment(JTextField.CENTER)
	#Processing_Panel.add(Bit_Depth_User, Constraints)

	Pos_Y += 1

	# Channel Settings
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(20, 0, 5, 0)
	J_Label = JLabel("========================= Channel Settings =========================")
	J_Label.setFont(Font("Arial", Font.PLAIN, 14))
	J_Label.setForeground(Color.BLACK)
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1


	# Channel Field Names
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Channel"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Constraints.gridx = Pos_X + 1
	Label = "Name"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Constraints.gridx = Pos_X + 2
	Label = "Wavelength Em"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Constraints.gridx = Pos_X + 3
	Label = "Source"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1

	# Loop for all Channels
	Channel_Name_List_User = []
	Channel_WavelengthEm_List_User = []
	for Channel in range (1, Image_Info["Nb_Channels"]+1):
		if Channel_Names_Metadata and len(Channel_Names_Metadata) >= Channel and Dialog_Counter == 0:
			Channel_Name = Channel_Names[Channel-1]
			Channel_Names_Source = "Metadata"
		elif len(Channel_Names_Stored) >= Channel:
			Channel_Name = Channel_Names_Stored[Channel-1]
			Channel_Names_Source = "Pref"
		else:
			Channel_Name = "Channel_{}".format(Channel)
			Channel_Names_Source = "Default"

		if Channel_WavelengthsEM_Metadata and len(Channel_WavelengthsEM_Metadata) >= Channel and Dialog_Counter == 0:
			Channel_WavelengthEM = Channel_WavelengthsEM[Channel-1]
			Channel_WavelengthsEM_Source = "Metadata"
		elif len(Channel_WavelengthsEM_Stored) >= Channel:
			Channel_WavelengthEM = Channel_WavelengthsEM_Stored[Channel-1]
			Channel_WavelengthsEM_Source = "Pref"
		else:
			Channel_WavelengthEM = NaN
			Channel_WavelengthsEM_Source = "Default"

		# Channel Number
		Constraints.gridx = Pos_X
		Constraints.gridy = Pos_Y + Channel
		Constraints.gridwidth = 1
		Constraints.gridheight = 1
		Constraints.anchor = GridBagConstraints.CENTER
		Constraints.insets = Insets(2, 2, 2, 2)
		Label = "Channel " + str(Channel)
		J_Label = JLabel(Label)
		J_Label.setFont(Font("Arial", Font.PLAIN, 12))
		Processing_Panel.add(J_Label, Constraints)

		# Channel Names
		Constraints.gridx = Pos_X + 1
		Text_Field =  str(Channel_Name)
		Channel_Name_User = JTextField(Text_Field, 3)
		Channel_Name_User.setFont(Font("Arial", Font.PLAIN, 12))
		Channel_Name_User.setHorizontalAlignment(JTextField.CENTER)
		Processing_Panel.add(Channel_Name_User, Constraints)
		Channel_Name_List_User.append(Channel_Name_User)


		# Channel Wavelength
		Constraints.gridx = Pos_X + 2
		Text_Field =  str(Channel_WavelengthEM)
		Channel_WavelengthEm_User = JTextField(Text_Field, 3)
		Channel_WavelengthEm_User.setFont(Font("Arial", Font.PLAIN, 12))
		Channel_WavelengthEm_User.setHorizontalAlignment(JTextField.CENTER)
		Processing_Panel.add(Channel_WavelengthEm_User, Constraints)
		Channel_WavelengthEm_List_User.append(Channel_WavelengthEm_User)

		# Channel Source
		Constraints.gridx = Pos_X + 3
		Label =  str(Channel_Names_Source)
		J_Label = JLabel(Label)
		J_Label.setFont(Font("Arial", Font.PLAIN, 12))
		Processing_Panel.add(J_Label, Constraints)


	Pos_Y += Image_Info["Nb_Channels"]+1


	# Processing Settings
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(20, 0, 5, 0)
	J_Label = JLabel("======================== Processing Settings =======================")
	J_Label.setFont(Font("Arial", Font.PLAIN, 14))
	J_Label.setForeground(Color.BLACK)
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1

	# Binning Method
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Binning Method"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Binning Method Radio
	Binning_Group = ButtonGroup()
	Binning_Method_List = ["Iso-Density", "Iso-Intensity"]
	X_Start = Pos_X + 1
	Y_Start = Pos_Y
	for i, Method in enumerate(Binning_Method_List):
		Constraints.gridx = X_Start +  i
		Constraints.gridy = Y_Start
		Constraints.gridwidth = 1
		Constraints.gridheight = 1
		Constraints.anchor = GridBagConstraints.CENTER
		Constraints.insets = Insets(5, 5, 5, 5)
		Binning_Button = JRadioButton(Method)
		Binning_Button.setFont(Font("Arial", Font.PLAIN, 12))
		Processing_Panel.add(Binning_Button, Constraints)
		Binning_Group.add(Binning_Button)
		if Method == Field_Uniformity_Settings_Stored["Field_Uniformity.Binning_Method"]:
			Binning_Button.setSelected(True)

	# Batch Mode
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.WEST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Batch Mode"
	Batch_Mode_User = JCheckBox(Label)
	Batch_Mode_User.setFont(Font("Arial", Font.BOLD, 12))
	Batch_Mode_User.setSelected(Field_Uniformity_Settings_Stored["Field_Uniformity.Batch_Mode"])
	Processing_Panel.add(Batch_Mode_User, Constraints)

	Pos_Y += 1


	# Gaussian Blur
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label_Gaussian_Blur = JLabel("Gaussian Blur "+ str(Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Sigma"]))
	Label_Gaussian_Blur.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(Label_Gaussian_Blur, Constraints)

	# Gaussian Slider
	Gaussian_Slider = JSlider(0, 100, int(Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Sigma"]))  # Min value 0, max value 100, initial value 50
	Gaussian_Slider.setMajorTickSpacing(20)
	Gaussian_Slider.setMinorTickSpacing(10)
	Gaussian_Slider.setPaintTicks(True)
	Gaussian_Slider.setPaintLabels(True)

	# Add a listener to display the current slider value in the label
	class Gaussian_Slider_Listener(ChangeListener):
		def stateChanged(self, event):
			value = Gaussian_Slider.getValue()
			Label_Gaussian_Blur.setText("Gaussian Blur {}".format(value))

	Gaussian_Slider.addChangeListener(Gaussian_Slider_Listener())

	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	#Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridwidth = 3
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Processing_Panel.add(Gaussian_Slider, Constraints)

	# Save Individual Files
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.NORTHWEST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Save Individual Files"
	Save_Individual_Files_User = JCheckBox(Label)
	Save_Individual_Files_User.setFont(Font("Arial", Font.PLAIN, 12))
	Save_Individual_Files_User.setSelected(Field_Uniformity_Settings_Stored["Field_Uniformity.Save_Individual_Files"])
	Processing_Panel.add(Save_Individual_Files_User, Constraints)

	# Prolix Mode
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.SOUTHWEST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Prolix Mode"
	Prolix_Mode_User = JCheckBox(Label)
	Prolix_Mode_User.setFont(Font("Arial", Font.PLAIN, 12))
	Prolix_Mode_User.setSelected(Field_Uniformity_Settings_Stored["Field_Uniformity.Prolix_Mode"])
	Processing_Panel.add(Prolix_Mode_User, Constraints)

	Pos_Y += 1

	# Channel Text
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Channel_Label = JLabel("Channel " + str(Image_Info["Current_Channel"]))
	Channel_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(Channel_Label, Constraints)

	# Channel Slider
	Channel_Slider = JSlider(1, Image_Info["Nb_Channels"], Image_Info["Current_Channel"])
	Channel_Slider.setMajorTickSpacing(1)
	Channel_Slider.setPaintTicks(True)
	Channel_Slider.setPaintLabels(True)

	class SliderListener(ChangeListener):
		def stateChanged(self, event):
			value = Channel_Slider.getValue()
			Channel_Label.setText("Channel {}".format(value))

	Channel_Slider.addChangeListener(SliderListener())
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 3
	#Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Processing_Panel.add(Channel_Slider, Constraints)

	# Test Processing
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.NORTHWEST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Test Processing"
	Test_Processing_User = JCheckBox(Label)
	Test_Processing_User.setFont(Font("Arial", Font.BOLD, 12))
	Test_Processing_User.setSelected(Test_Processing)
	Processing_Panel.add(Test_Processing_User, Constraints)

	Pos_Y += 1

	# Pre Dectection Results Uniformity
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Uniformity (%)"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)


	Spacer_Str = " "
	Spacer = str(Spacer_Str * 15)
	Uniformity_Per_Ch_Str = [str(float(item["Uniformity_Std"])) for item in Data_File]
	Uniformity_Per_Ch_String = Spacer.join(Uniformity_Per_Ch_Str)
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 3
	#Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "{}".format(Uniformity_Per_Ch_String)
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	#User_Click = None
	# Cancel Button
	Cancel_Button = JButton("Cancel")
	def On_Cancel(event):
		Processing_Dialog.dispose()
		global User_Click
		User_Click = "Cancel"
		Message = "User clicked Cancel while processing "+ Image_Name +"."
		IJ.log(Message)
		JOptionPane.showMessageDialog(None, Message, Plugin_Name+" "+Function_Name, JOptionPane.INFORMATION_MESSAGE)
		sys.exit(Message)
		return

	Cancel_Button.addActionListener(On_Cancel)
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Processing_Panel.add(Cancel_Button,Constraints)



	Pos_Y += 1

	# Centering Results
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Centering Accuracy (%)"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	Centering_Accuracy_Per_Ch_Str = [str(float(item["Centering_Accuracy"])) for item in Data_File]
	Centering_Accuracy_Per_Ch_String = Spacer.join(Centering_Accuracy_Per_Ch_Str)
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.gridx = Pos_X+1
	Constraints.gridwidth = 3
	Label = "{}".format(Centering_Accuracy_Per_Ch_String)
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# OK Button
	OK_Button = JButton("OK")
	def On_OK(event):
		Processing_Dialog.dispose()
		global User_Click
		User_Click = "OK"
	OK_Button.addActionListener(On_OK)

	OK_Button.requestFocusInWindow()
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Processing_Panel.add(OK_Button, Constraints)
	Processing_Dialog.getRootPane().setDefaultButton(OK_Button)
	Processing_Dialog.add(Processing_Panel)
	Processing_Dialog.pack()
	Processing_Dialog.setLocationRelativeTo(None)
	Processing_Dialog.setVisible(True)

	while Processing_Dialog.isVisible():
		pass

	Duplicated_Ch_imp.changes = False
	Duplicated_Ch_imp.close()




	# Collect values from the Dialog
	# Objective Magnification
	Objective_Mag_Value = str(Objective_Mag_User.getText())

	# Objective NA
	Objective_NA_Value = float(Objective_NA_User.getText())

	# Immersion Media
	Objective_Immersion_Media_Value = None
	for button in Immersion_Radio_Group.getElements():
		if button.isSelected():
			Objective_Immersion_Media_Value = str(button.getText())
			break

	# Pixel Information
	Pixel_Width_Value = float(Pixel_Width_User.getText())
	Pixel_Height_Value = float(Pixel_Height_User.getText())
	Pixel_Depth_Value = float(Pixel_Depth_User.getText())
	Space_Unit_Value = str(Space_Unit_User.getText())
	#Bit_Depth_Value = int(Bit_Depth_User.getText())

	# Channel Information
	Channel_Names = [str(field.getText()) for field in Channel_Name_List_User]
	Channel_WavelengthsEM = [str(field.getText()) for field in Channel_WavelengthEm_List_User]

	# Binning Method
	Binning_Method_Value = None
	for button in Binning_Group.getElements():
		if button.isSelected():
			Binning_Method_Value = str(button.getText())
			break


	Gaussian_Blur_Value = int(Gaussian_Slider.getValue())
	Test_Channel_Value = int(Channel_Slider.getValue())

	# Checkboxes
	Batch_Mode_Value = Batch_Mode_User.isSelected()
	Save_Individual_Files_Value = Save_Individual_Files_User.isSelected()
	Prolix_Mode_Value = Prolix_Mode_User.isSelected()
	Test_Processing_Value = Test_Processing_User.isSelected()


	Microscope_Settings_User = {}
	Field_Uniformity_User = {}

	if User_Click == "Cancel":
		return
	elif User_Click == "OK":
		Microscope_Settings_User["Field_Uniformity.Microscope_Objective_Mag"] = Objective_Mag_Value
		Microscope_Settings_User["Field_Uniformity.Microscope_Objective_NA"] = Objective_NA_Value
		Microscope_Settings_User["Field_Uniformity.Microscope_Objective_Immersion"] = Objective_Immersion_Media_Value
		Pixel_Width_User = Pixel_Width_Value
		Pixel_Height_User = Pixel_Height_Value
		Pixel_Depth_User = Pixel_Depth_User
		Space_Unit_User = Space_Unit_Value
		# Bit_Depth_User = Bit_Depth_Value

		Channel_Names_User = Channel_Names
		Channel_WavelengthsEM_User = Channel_WavelengthsEM


		Microscope_Settings_User["Field_Uniformity.Microscope_Channel_Names"] = Channel_Names_User
		Microscope_Settings_User["Field_Uniformity.Microscope_Channel_WavelengthsEM"] = Channel_WavelengthsEM_User

		if Gaussian_Blur_Value == 0:
			Gaussian_Blur = False
		elif Gaussian_Blur_Value>0:
			Gaussian_Blur = True

		Field_Uniformity_User["Field_Uniformity.Gaussian_Blur"] = Gaussian_Blur
		Test_Processing = Test_Processing_Value
		Field_Uniformity_User["Field_Uniformity.Save_Individual_Files"] = Save_Individual_Files_Value
		Field_Uniformity_User["Field_Uniformity.Batch_Mode"] = Batch_Mode_Value
		Field_Uniformity_User["Field_Uniformity.Prolix_Mode"] = Prolix_Mode_Value
		Field_Uniformity_User["Field_Uniformity.Gaussian_Sigma"] = Gaussian_Blur_Value
		Field_Uniformity_User["Field_Uniformity.Binning_Method"] = Binning_Method_Value
		Selected_Channel = Test_Channel_Value
		if Selected_Channel != int(Current_Channel):
			imp.setC(Selected_Channel)
			imp.updateAndDraw()
			Test_Processing = True
		Save_Preferences(Microscope_Settings_User)
		Save_Preferences(Field_Uniformity_User)

#		Prolix_Message("Updating Image Calibration for: " + Image_Name + "...")
#		Image_Calibration = imp.getCalibration()
#		Image_Calibration.pixelWidth = Pixel_Width_User if isinstance(Pixel_Width_User, (float, int)) else float(1)
#		Image_Calibration.pixelHeight = Pixel_Height_User if isinstance(Pixel_Height_User, (float, int)) else float(1)
#		Image_Calibration.pixelDepth = Pixel_Depth_User if isinstance(Pixel_Depth_User, (float, int)) else float(1)
#		Space_Unit_User_Std = Normalize_Space_Unit(Space_Unit_User)
#		Image_Calibration.setUnit(Space_Unit_User_Std)
#		imp.setCalibration(Image_Calibration)
#		Prolix_Message("Updating Image Calibration: " + Image_Name + ". Done.")
		Batch_Message=""
		Dialog_Counter += 1
	return Field_Uniformity_User, Microscope_Settings_User, User_Click, Dialog_Counter, Test_Processing, Batch_Message



# Measure the Uniformity for all Channels
# Return a Data_File a dictionnary containing the data for all Channels for a given image
def Measure_Uniformity_All_Ch(imp, Save_File): # Run on all channels.
	Image_Info = Get_Image_Info(imp)
	Image_Name = Image_Info["Image_Name"]
	Prolix_Message("Running Uniformity on all channels for: " + Image_Name + "...")
	Current_Channel = Image_Info["Current_Channel"]
	Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
	#Microscope_Settings_Stored = Read_Preferences(Settings_Templates_List["Microscope_Settings_Template"])
	Data_File = [] # Store the dictionnaries containing the data for each Channel

	# Run Uniformity Single Channel and append the data
	for Channel in range(1, Image_Info["Nb_Channels"]+1):
		Data_Ch, _ = Measure_Uniformity_Single_Channel(imp, Channel, Save_File, Display = False)
		Data_File.append(Data_Ch)

	imp.setDisplayMode(IJ.COLOR)
	imp.setC(Current_Channel) # Channel starts from 1 to Image_Info[Nb_Channels]
	imp.updateAndDraw()

	#Define the Header and Ordered Keys has Global Variables
	global Data_File_Header
	global Data_File_Ordered_Keys

	Data_File_Ordered_Keys = [
	"Filename",
	"Channel_Nb",
	"Channel_Name",
	"Channel_Wavelength_EM",
	"Objective_Mag",
	"Objective_NA",
	"Objective_Immersion",
	"Gaussian_Blur",
	"Gaussian_Sigma",
	"Binning_Method",
	"Batch_Mode",
	"Save_Individual_Files",
	"Prolix_Mode",
	"Intensity_Min",
	"Intensity_Max",
	"Intensity_Mean",
	"Intensity_Std_Dev",
	"Intensity_Median",
	"Intensity_Mode",
	"Width_Pix",
	"Height_Pix",
	"Bit_Depth",
	"Pixel_Width",
	"Pixel_Height",
	"Pixel_Depth",
	"Space_Unit",
	"Space_Unit_Std",
	"Calibration_Status",
	"Std_Dev",
	"Uniformity_Std",
	"Uniformity_Percentile",
	"CV",
	"Uniformity_CV",
	"X_Center_Pix",
	"Y_Center_Pix",
	"X_Ref_Pix",
	"Y_Ref_Pix",
	"X_Ref",
	"Y_Ref",
	"Centering_Accuracy"
	]

	Data_File_Header = [
	"Filename",
	"Channel Nb",
	"Channel Name",
	"Channel Wavelength EM (nm)",
	"Objective Magnification",
	"Objective NA",
	"Objective Immersion Media",
	"Gaussian Blur Applied",
	"Gaussian Sigma",
	"Binning Method",
	"Batch Mode",
	"Save Individual Files",
	"Prolix Mode",
	"Image Min Intensity (GV)",
	"Image Max Intensity (GV)",
	"Image Mean Intensity (GV)",
	"Image Standard Deviation Intensity (GV)",
	"Image Median Intensity (GV)",
	"Image Mode Intensity (GV)",
	"Image Width (pixels)",
	"Image Height (pixels)",
	"Image Bit Depth",
	"Pixel Width (" + Image_Info["Space_Unit_Std"] + ")",
	"Pixel Height (" + Image_Info["Space_Unit_Std"] + ")",
	"Pixel Depth (" + Image_Info["Space_Unit_Std"] + ")",
	"Space Unit",
	"Space Unit Standard",
	"Calibration Status",",
	"Standard Deviation (GV)",
	"Uniformity Standard (%)",
	"Uniformity Percentile (%)",
	"Coefficient of Variation",
	"Uniformity CV based (%)",
	"X Center (pixels)",
	"Y Center (pixels)",
	"X Ref (pixels)",
	"Y Ref (pixels)",
	"X Ref (" + Image_Info["Space_Unit_Std"] + ")",
	"Y Ref (" + Image_Info["Space_Unit_Std"] + ")",
	"Centering Accuracy (%)"
	]

	Output_Data_CSV_Path = Generate_Unique_Filepath(Output_Dir, Image_Info["Basename"], "Uniformity-Data", ".csv")
	if Save_File and Field_Uniformity_Settings_Stored["Field_Uniformity.Save_Individual_Files"]:
		#with open(Output_Data_CSV_Path, "wb") as CSVFile:
		#with open(Output_Data_CSV_Path, "w") as CSV_File:
		CSV_File = open(Output_Data_CSV_Path, "w")
		CSV_Writer = csv.writer(CSV_File, delimiter = ",", lineterminator = "\n")
 		CSV_Writer.writerow(Data_File_Header)
		for Data_Ch in Data_File:
			Row = []
			for Key in Data_File_Ordered_Keys:
				Row.append(Data_Ch[Key])
			CSV_Writer.writerow(Row)
		CSV_File.close()
	Prolix_Message("Running Uniformity on all channel for: " + Image_Name + ". Done.")
	return Data_File


# Run Uniformityy on a single Channel
# Return Data_Ch a dictionnary with data for the selected Channel
def Measure_Uniformity_Single_Channel(imp, Channel, Save_File, Display):
 	Image_Info = Get_Image_Info(imp)
 	Image_Name = Image_Info["Image_Name"]
 	Prolix_Message("Running Uniformity for: "+str(Image_Name)+" Channel "+str(Channel)+".")

 	Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
 	Microscope_Settings_Stored = Read_Preferences(Settings_Templates_List["Microscope_Settings_Template"])

 	imp.setDisplayMode(IJ.COLOR)
	imp.setC(Channel) # Channel starts from 1 to Image_Info[Nb_Channels]
	imp.updateAndDraw()


	ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels = Get_Image_Statistics(imp)

	Uniformity_Std = round(Calculate_Uniformity_Std(imp), 1)
	Uniformity_Percentile = round(Calculate_Uniformity_Percentile(imp, Percentile=0.05), 1)
	CV = Calculate_CV(imp)
	if CV <= 1:
		Uniformity_CV = round(Calculate_Uniformity_CV(CV), 1)
	else:
		Uniformity_CV = "Too high"

	if Field_Uniformity_Settings_Stored["Field_Uniformity.Binning_Method"] == "Iso-Intensity":
		Duplicated_Ch_imp, X_Ref, Y_Ref, X_Ref_Pix, Y_Ref_Pix = Bin_Image_Iso_Intensity(imp, Channel, Display, Nb_Bins = 10, Final_Bin_Size = 25)
	else:
		Duplicated_Ch_imp, X_Ref, Y_Ref, X_Ref_Pix, Y_Ref_Pix = Bin_Image_Iso_Density(imp, Channel, Display, Nb_Bins = 10, Final_Bin_Size = 25)


	Centering_Accuracy = round(Calculate_Centering_Accuracy(imp, X_Ref_Pix, Y_Ref_Pix),1)

	Data_Ch={
	"Filename": Image_Info["Filename"],
	"Channel_Nb": Channel,
	"Objective_Mag": Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Mag"],
	"Objective_NA": "%.1f" % Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_NA"],
	"Objective_Immersion":	Microscope_Settings_Stored["Field_Uniformity.Microscope_Objective_Immersion"],
	"Gaussian_Blur": Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Blur"],
	"Gaussian_Sigma": Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Sigma"],
	"Binning_Method": Field_Uniformity_Settings_Stored["Field_Uniformity.Binning_Method"],
	"Batch_Mode": Field_Uniformity_Settings_Stored["Field_Uniformity.Batch_Mode"],
	"Save_Individual_Files": Field_Uniformity_Settings_Stored["Field_Uniformity.Save_Individual_Files"],
	"Prolix_Mode": Field_Uniformity_Settings_Stored["Field_Uniformity.Prolix_Mode"],
	"Intensity_Min": Min,
	"Intensity_Max": Max,
	"Intensity_Mean": "%.1f" % round(Mean,1),
	"Intensity_Std_Dev": "%.1f" % round(Std_Dev,1),
	"Intensity_Median": Median,
	"Intensity_Mode": Mode,
	"Width_Pix": Image_Info["Width"],
	"Height_Pix": Image_Info["Height"],
	"Bit_Depth": Image_Info["Bit_Depth"],
	"Pixel_Width": Image_Info["Pixel_Width"],
	"Pixel_Height": Image_Info["Pixel_Height"],
	"Pixel_Depth": Image_Info["Pixel_Depth"],
	"Space_Unit": Image_Info["Space_Unit"],
	"Space_Unit_Std": Image_Info["Space_Unit_Std"],
	"Calibration_Status": Image_Info["Calibration_Status"],
	"Std_Dev": "%.1f" % round(Std_Dev, 1),
	"Uniformity_Std": "%.1f" % Uniformity_Std,
	"Uniformity_Percentile": "%.1f" % Uniformity_Percentile,
	"CV": "%.1f" % round(CV,4),
	"Uniformity_CV": "%.1f" % Uniformity_CV,
	"X_Center_Pix": Image_Info["Width"]/2,
	"Y_Center_Pix": Image_Info["Height"]/2,
	"X_Ref_Pix": round(X_Ref_Pix,0),
	"Y_Ref_Pix": round(Y_Ref_Pix,0),
	"X_Ref": "%.3f" % round(X_Ref,3 ),
	"Y_Ref": "%.3f" % round(Y_Ref,3),
	"Centering_Accuracy": "%.1f" % Centering_Accuracy,
	}

	if Save_File:
		Data_Ch["Channel_Name"] = Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_Names"][Channel-1]
		Data_Ch["Channel_Wavelength_EM"] = Microscope_Settings_Stored["Field_Uniformity.Microscope_Channel_WavelengthsEM"][Channel-1]

	if Save_File and Field_Uniformity_Settings_Stored["Field_Uniformity.Save_Individual_Files"]:
		Output_Image_Path = Generate_Unique_Filepath(Output_Dir, Image_Info["Basename"] + "_Channel-0" + str(Channel), "Binned", ".tif")
		IJ.saveAs(Duplicated_Ch_imp, "Tiff", Output_Image_Path)
	if Display:
		Zoom.set(Duplicated_Ch_imp, 0.5);
		Duplicated_Ch_imp.show()
	if not Display:
		Duplicated_Ch_imp.changes = False
		Duplicated_Ch_imp.close()
	return Data_Ch, Duplicated_Ch_imp


# Get the statistics of the image
def Get_Image_Statistics(imp):
	Prolix_Message("Getting Image Statistics...")
	ip = imp.getProcessor()
	Stats = ip.getStatistics()
	Min = Stats.min
	Max = Stats.max
	Mean = Stats.mean
	Std_Dev = Stats.stdDev
	Median = Stats.median
	Hist = list(Stats.histogram())
	Mode = Stats.mode
	nPixels = Stats.pixelCount
	Prolix_Message("Getting Image Statistics. Done.")
	return ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels


# Calculate the Uniformity the same way than MetroloJ QC
def Calculate_Uniformity_Std(imp):
	Prolix_Message("Calculating Uniformity Standard...")
	ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels = Get_Image_Statistics(imp)
	Uniformity_Std = 100 * (Min / Max)
	Prolix_Message("Calculating Uniformity Standard. Done. Uniformity Standard = " + str(Uniformity_Std))
	return Uniformity_Std

# Calculate the Uniformity using the 5% 95% percentile
def Calculate_Uniformity_Percentile(imp, Percentile = 0.05):
	Prolix_Message("Calculating Uniformity 5% - 95% Percentile...")
	IJ.run(imp, "Select None", "");
	ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels = Get_Image_Statistics(imp)
	Pixels = ip.getPixels()
	Sorted_Pixels = sorted(Pixels)
	p5_Index = int(Percentile * nPixels)
	p95_Index = int((1-Percentile) * nPixels)
	Average_Pixel_Low = sum(Sorted_Pixels[:p5_Index]) / float(len(Sorted_Pixels[:p5_Index]))
	Average_Pixel_High = sum(Sorted_Pixels[p95_Index:]) / float(len(Sorted_Pixels[p95_Index:]))
	Uniformity_Percentile = (1 - (Average_Pixel_High - Average_Pixel_Low) / float(Average_Pixel_High + Average_Pixel_Low) ) * 100
	Prolix_Message("Calculating Uniformity " + str(Percentile * 100) + "% - " + str(100 - (Percentile * 100)) + "% Percentile. Done. Uniformity Percentile = " + str(Uniformity_Percentile))
	return Uniformity_Percentile

# Calculate the Coefficient of Variation
def Calculate_CV(imp):
	Prolix_Message("Calculating Coefficient of Variation...")
	ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels = Get_Image_Statistics(imp)
	if Mean != 0:
		CV = (Std_Dev / Mean)
	else:
		CV = 0
	Prolix_Message("Calculating Coefficient of Variation. Done. CV = " + str(CV))
	return CV

# Calculate the Uniformity from the CV
def Calculate_Uniformity_CV(CV):
	Uniformity_CV = (1 - CV) * 100 # CV range from 0 to infinity but in this context it is extremely unlikely to be above 1.
	return Uniformity_CV

# Calculate the Centering Accuracy Require the X and Y coordinate of the Reference ROI
def Calculate_Centering_Accuracy(imp, X_Ref_Pix, Y_Ref_Pix):
	Prolix_Message("Calculating Centering Accuracy...")
	ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels = Get_Image_Statistics(imp)
	Width = ip.getWidth()
	Height = ip.getHeight()
	Centering_Accuracy = 100 - 100 * (2 / sqrt(Width**2 + Height**2)) * sqrt ( (X_Ref_Pix - Width/2)**2 + (Y_Ref_Pix - Height/2)**2)
	Prolix_Message("Calculating Centering Accuracy. Done. Centering Accuracy = " + str(Centering_Accuracy))
	return Centering_Accuracy

# Duplicate a Channel
def Image_Ch_Duplicator(imp, Channel, Display):
	Image_Info = Get_Image_Info(imp)
	Original_Title = Image_Info["Basename"]
	Prolix_Message("Duplicating Channel " + str(Channel) + " for " + str(Original_Title) + "...")
	New_Title = Original_Title + "_Channel-0" + str(Channel)
	Duplicated_imp = Duplicator().run(imp, Channel, Channel, 1, 1, 1, 1);
	Duplicated_imp.setTitle(New_Title)
	if Display:
		Zoom.set(Duplicated_imp, 0.5);
		Duplicated_imp.show()
	Prolix_Message("Duplicating Channel " + str(Channel) +" for " + str(Original_Title) + ". Done.")
	return Duplicated_imp # Dupicated Channel with Original Name + ChNb

# Apply Gaussian Blur with Sigma from the preferences
def Apply_Gaussian_Blur(imp, Display):
	Image_Info = Get_Image_Info(imp)
	Prolix_Message("Applying Gaussian Blur on " + str(Image_Info["Filename"]) + "...")
	Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
	if Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Blur"]:
		Sigma = Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Sigma"]
		ip = imp.getProcessor()
		Blur = GaussianBlur()
		Blur.blurGaussian(ip, float(Sigma))
		Prolix_Message("Applying Gaussian Blur on " + str(Image_Info["Filename"]) + ". Done.")
		if Display:
			Zoom.set(imp, 0.5);
			imp.show()
			imp.updateAndDraw()
	return None



# This is one of the two core functions of the Uniformity_Single_Channel
def Bin_Image_Iso_Intensity(imp, Channel, Display, Nb_Bins=10, Final_Bin_Size=25):
	Image_Info = Get_Image_Info(imp) # Can only be used on an image written of disk
	Prolix_Message("Binning Image with Iso-Intensity" + str(Image_Info["Filename"]) + "...")
	Height = Image_Info["Height"]
	Width = Image_Info["Width"]
	imp.setRoi(None)
	imp.setDisplayMode(IJ.COLOR)
	imp.setC(Channel) # Channel starts from 1 to Image_Info[Nb_Channels]
	imp.updateAndDraw()

	Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
	imp.setRoi(None)
	Duplicated_Ch_imp = Image_Ch_Duplicator(imp, Channel, Display)

	if Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Blur"]:
		Duplicated_Ch_imp.setRoi(None)
		Apply_Gaussian_Blur(Duplicated_Ch_imp, Display)

	Duplicated_Ch_imp.setRoi(None)
	ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels = Get_Image_Statistics(Duplicated_Ch_imp)

	Intensity_Range = Max - Min

	# Caculate the Width of the Bins based on the range of intensities
	Bin_Width = Intensity_Range / float(Nb_Bins)
	# ImageJ Macro Equation
	Duplicated_Ch_imp.setRoi(None)
	IJ.run(Duplicated_Ch_imp, "32-bit", "")
	Equation = "[v = " + str(Final_Bin_Size) + " + floor(((v - " + str(Min) + ") / " + str(Bin_Width) + ")) * " + str(Final_Bin_Size)+"]"
	IJ.run(Duplicated_Ch_imp, "Macro...", "code=" + Equation)
	IJ.run(Duplicated_Ch_imp, "Macro...", "code=[if(v > 250) v = 250]");
	Prolix_Message("Iso Intensity Binnig Equation = "+ str(Equation))
	ImageConverter.setDoScaling(False)
	IJ.run(Duplicated_Ch_imp, "8-bit", "")
	IJ.run(Duplicated_Ch_imp, "Grays", "");
	if Display:
		Zoom.set(Duplicated_Ch_imp, 0.5);
		Duplicated_Ch_imp.show()

	# We have the original image imp, the Duplicated_Ch_imp (gaussian blur applied)
	# Add the overlay
	Threshold_Value_Lower = Final_Bin_Size * Nb_Bins
	Threshold_Value_Upper = 255

	# Duplicate the image processor to threshold on the last bin
	Duplicated_Ch_imp.setRoi(None)
	Thresholded_Ch_imp = Duplicated_Ch_imp.duplicate()
	IJ.setThreshold(Thresholded_Ch_imp, Threshold_Value_Lower, Threshold_Value_Upper)
	IJ.run(Thresholded_Ch_imp, "Convert to Mask", "")
	IJ.run(Thresholded_Ch_imp, "Analyze Particles...", "size=0-Infinity clear add")
	Result_Table = ResultsTable.getResultsTable()
	# Parse the result to get the largest particle
	Max_Area = 0
	Max_Area_Index = -1
	for i in range(Result_Table.getCounter()):
		Area = Result_Table.getValue("Area", i)
		if Area > Max_Area:
			Max_Area = Area
			Max_Area_Index = i

	if Max_Area_Index != -1:
		Roi_Manager = RoiManager.getInstance()
		if Roi_Manager is None:
			Roi_Manager = RoiManager()
		Roi_Last_Bin = Roi_Manager.getRoi(Max_Area_Index)
		imp.setRoi(Roi_Last_Bin)
		Roi_Statistics = imp.getStatistics(ImageStatistics.CENTROID)
		X_Ref = Roi_Statistics.xCentroid
		Y_Ref = Roi_Statistics.yCentroid
		imp.setRoi(None)
		Nb_Roi = Roi_Manager.getCount()
		if Nb_Roi > 0:
			Roi_Manager.close()
			#Roi_Manager.reset() # Cause errors
		Prolix_Message("Max_Area = " + str(Max_Area) + ".")
		Prolix_Message("Max_Area_Index = " + str(Max_Area_Index) + ".")
		Prolix_Message("X_Ref = " + str(X_Ref) + ".")
		Prolix_Message("Y_Ref = " + str(Y_Ref) + ".")
		Label_Text = "< Center here"
	else:
		X_Ref, Y_Ref = Width/2, Height/2
		Roi_Manager = RoiManager.getInstance()
		if Roi_Manager is None:
			Roi_Manager = RoiManager()
		imp.setRoi(None)
		Nb_Roi = Roi_Manager.getCount()
		if Nb_Roi > 0:
			Roi_Manager.close()
			#Roi_Manager.reset()
		Label_Text = "Center not found"

	if Image_Info["Space_Unit_Std"] != "pixels":
		X_Ref_Pix = X_Ref / Image_Info["Pixel_Width"]
		Y_Ref_Pix = Y_Ref / Image_Info["Pixel_Height"]
	else:
		X_Ref_Pix = X_Ref
		Y_Ref_Pix = Y_Ref
	Prolix_Message("X_Ref_Pix = " + str(X_Ref_Pix) + ".")
	Prolix_Message("Y_Ref_Pix = " + str(Y_Ref_Pix) + ".")

	Duplicated_Ch_imp_Overlay=Overlay()
	Font_Size = int(max(10, min(int(min(Width, Height) * 0.03), 50)))
	Font_Settings = Font("Arial", Font.BOLD, Font_Size)
	Prolix_Message("Font_Size = " + str(Font_Size))
	OffsetX = -1
	OffsetY = -int(Font_Size/2)
	Prolix_Message("OffsetX = " + str(OffsetX))
	Prolix_Message("OffsetY = " + str(OffsetY))
	Label = TextRoi(int(X_Ref_Pix+OffsetX), int(Y_Ref_Pix+OffsetY), Label_Text, Font_Settings)
	Label.setColor(Color.BLACK) # Set the font color to black
	Duplicated_Ch_imp_Overlay.add(Label)
	Thresholded_Ch_imp.changes = False
	Thresholded_Ch_imp.close()
	Duplicated_Ch_imp.setOverlay(Duplicated_Ch_imp_Overlay)
	if Display:
		Zoom.set(Duplicated_Ch_imp, 0.5);
		Duplicated_Ch_imp.show()
	Prolix_Message("Binning Image with Iso-Intensity" + str(Image_Info["Filename"]) + ". Done.")
	return Duplicated_Ch_imp, X_Ref, Y_Ref, X_Ref_Pix, Y_Ref_Pix


# This is the preferred method and core function of the Uniformity_Single_Channel
def Bin_Image_Iso_Density(imp, Channel, Display, Nb_Bins=10, Final_Bin_Size=25):
	Image_Info = Get_Image_Info(imp) # Can only be used on an image written of disk
	Prolix_Message("Binning Image with Iso-Density " + str(Image_Info["Filename"]) + "...")
	Height = Image_Info["Height"]
	Width = Image_Info["Width"]
	imp.setRoi(None)
	imp.setDisplayMode(IJ.COLOR)
	imp.setC(Channel) # Channel starts from 1 to Image_Info[Nb_Channels]
	imp.updateAndDraw()

	Field_Uniformity_Settings_Stored = Read_Preferences(Settings_Templates_List["Field_Uniformity.Settings_Template"])
	imp.setRoi(None)
	Duplicated_Ch_imp = Image_Ch_Duplicator(imp, Channel, Display)

	if Field_Uniformity_Settings_Stored["Field_Uniformity.Gaussian_Blur"]:
		Duplicated_Ch_imp.setRoi(None)
		Apply_Gaussian_Blur(Duplicated_Ch_imp, Display)

	ip, Min, Max, Mean, Std_Dev, Median, Hist, Mode, nPixels = Get_Image_Statistics(Duplicated_Ch_imp)
	Duplicated_Ch_IP = Duplicated_Ch_imp.getProcessor()
	# Get the pixel data and sort it
	Pixels = Duplicated_Ch_IP.getPixels()
	Sorted_Pixels = sorted(Pixels)
	Nb_Pixel_Per_Bin = int(nPixels / Nb_Bins)
	Prolix_Message("Nb_Pixel_Per_Bin" + str(Nb_Pixel_Per_Bin))

	Lower_Thresholds=[]
	Upper_Thresholds=[]
	for i in range(0, Nb_Bins):
		Pixel_Value_Low = Sorted_Pixels[int(i * Nb_Pixel_Per_Bin)]
		if i == Nb_Bins - 1:
			Pixel_Value_High = Max
		else:
			Pixel_Value_High = Sorted_Pixels[int((i+1) * Nb_Pixel_Per_Bin)]
		Lower_Thresholds.append(Pixel_Value_Low)
		Upper_Thresholds.append(Pixel_Value_High)
		Prolix_Message("Pixel_Value_Low" + str(Pixel_Value_Low))
		Prolix_Message("Pixel_Value_High" + str(Pixel_Value_High))
	Duplicated_Ch_imp.setRoi(None)
	Roi_Manager = RoiManager.getInstance()
	if Roi_Manager is None:
		Roi_Manager = RoiManager()
	Nb_Roi = Roi_Manager.getCount()
	if Nb_Roi > 0:
		Roi_Manager.close()
		#Roi_Manager.reset()

	# Loop through each bin
	for y in range(0, len(Lower_Thresholds)):
		Lower_Threshold_Value = Lower_Thresholds[y]
		Upper_Threshold_Value = Upper_Thresholds[y]
		Duplicated_Ch_IP.setThreshold(Lower_Threshold_Value, Upper_Threshold_Value)
		IJ.run(Duplicated_Ch_imp, "Create Selection", "")
		Roi_Manager.addRoi(Duplicated_Ch_imp.getRoi())
		Duplicated_Ch_imp.setRoi(None)
	Duplicated_Ch_imp.setRoi(None)
	ImageConverter.setDoScaling(False)
	IJ.run(Duplicated_Ch_imp, "8-bit", "")
	IJ.run(Duplicated_Ch_imp, "Grays", "");
	Duplicated_Ch_IP = Duplicated_Ch_imp.getProcessor()
	Roi_Manager = RoiManager.getInstance()
	if Roi_Manager is None:
		Roi_Manager = RoiManager()

	Nb_Roi = Roi_Manager.getCount()
	if Nb_Roi > 0:
		for Roi_Index in range(Roi_Manager.getCount()):
			Roi = Roi_Manager.getRoi(Roi_Index)
			New_Intensity = int ((Roi_Index + 1) * Final_Bin_Size)
			Duplicated_Ch_IP.setValue(New_Intensity)
			Duplicated_Ch_IP.fill(Roi);
			Duplicated_Ch_imp.setRoi(None)
			Prolix_Message("Roi_Index" + str(Roi_Index))
			Prolix_Message("New_Intensity" + str(New_Intensity))

	Nb_Roi = Roi_Manager.getCount()
	if Nb_Roi > 0:
		Roi_Manager.close()
		#Roi_Manager.reset()

	Duplicated_Ch_imp.setRoi(None)
	IJ.run(Duplicated_Ch_imp, "8-bit", "");
	IJ.run(Duplicated_Ch_imp, "Grays", "");
	Duplicated_Ch_imp.updateAndDraw()

	Threshold_Value_Lower = Final_Bin_Size * (Nb_Bins)
	Threshold_Value_Upper = 255
	Prolix_Message("Threshold_Value_Lower" + str(Threshold_Value_Lower))

	# Duplicate the image processor to threshold on the last bin
	Duplicated_Ch_imp.setRoi(None)
	Thresholded_Ch_imp = Duplicated_Ch_imp.duplicate()
	IJ.setThreshold(Thresholded_Ch_imp, Threshold_Value_Lower, Threshold_Value_Upper)
	IJ.run(Thresholded_Ch_imp, "Convert to Mask", "")
	IJ.run(Thresholded_Ch_imp, "Analyze Particles...", "size=0-Infinity clear add")
	Result_Table = ResultsTable.getResultsTable()
	# Parse the result to get the largest particle
	Max_Area = 0
	Max_Area_Index = -1
	for i in range(Result_Table.getCounter()):
		Area = Result_Table.getValue("Area", i)
		if Area > Max_Area:
			Max_Area = Area
			Max_Area_Index = i
	Prolix_Message("Max_Area" + str(Max_Area))
	Prolix_Message("Max_Area_Index" + str(Max_Area_Index))

	if Max_Area_Index != -1:
		Roi_Manager = RoiManager.getInstance()
		if Roi_Manager is None:
			Roi_Manager = RoiManager()
		Roi_Last_Bin = Roi_Manager.getRoi(Max_Area_Index)
		Duplicated_Ch_imp.setRoi(Roi_Last_Bin) #Or using the Original Image
		Roi_Statistics = Duplicated_Ch_imp.getStatistics(ImageStatistics.CENTROID)
		X_Ref = Roi_Statistics.xCentroid
		Y_Ref = Roi_Statistics.yCentroid
		Duplicated_Ch_imp.setRoi(None)
		Nb_Roi = Roi_Manager.getCount()
		if Nb_Roi > 0:
			Roi_Manager.close()
			#Roi_Manager.reset()
		Label_Text = "< Center here"
	else:
		X_Ref, Y_Ref = Width/2, Height/2
		Duplicated_Ch_imp.setRoi(None)
		Nb_Roi = Roi_Manager.getCount()
		if Nb_Roi > 0:
			Roi_Manager.close()
			#Roi_Manager.reset()
		Label_Text = "Center not found"
	Prolix_Message("Label_Text" + str(Label_Text))

	if Image_Info["Space_Unit_Std"] != "pixels":
		X_Ref_Pix = X_Ref / Image_Info["Pixel_Width"]
		Y_Ref_Pix = Y_Ref / Image_Info["Pixel_Height"]
	else:
		X_Ref_Pix = X_Ref
		Y_Ref_Pix = Y_Ref
	Prolix_Message("X_Ref_Pix" + str(X_Ref_Pix))
	Prolix_Message("Y_Ref_Pix" + str(Y_Ref_Pix))

	Duplicated_Ch_imp_Overlay=Overlay()
	Font_Size = max(10, min(int(min(Width, Height) * 0.03), 50))
	Font_Settings = Font("Arial", Font.BOLD, Font_Size)
	Prolix_Message("Font_Size = " + str(Font_Size))
	OffsetX = -1
	OffsetY = -int(Font_Size/2)
	Prolix_Message("OffsetX = " + str(OffsetX))
	Prolix_Message("OffsetY = " + str(OffsetY))
	Label = TextRoi(int(X_Ref_Pix+OffsetX), int(Y_Ref_Pix+OffsetY), Label_Text, Font_Settings)
	Label.setColor(Color.BLACK) # Set the font color to black
	Duplicated_Ch_imp_Overlay.add(Label)
	Thresholded_Ch_imp.changes = False
	Thresholded_Ch_imp.close()
	Duplicated_Ch_imp.setOverlay(Duplicated_Ch_imp_Overlay)
	if Display:
		Zoom.set(Duplicated_Ch_imp, 0.5);
		Duplicated_Ch_imp.show()
	Prolix_Message("Binning Image with Iso-Density " + str(Image_Info["Filename"]) + ". Done.")
	return Duplicated_Ch_imp, X_Ref, Y_Ref, X_Ref_Pix, Y_Ref_Pix


# We are done with functions... Getting to work now...

# Initializing or Resetting preferences
Initialize_Preferences(Settings_Templates_List, Reset_Preferences)

# Get some images Opened or Selected from a folder
Image_List = Get_Images()

# Checking and eventually Creating Output Directory
if not os.path.exists(Output_Dir): os.makedirs(Output_Dir)


# Process the List of Images
Data_All_Files, Processed_Images_List = Process_Image_List(Image_List)

# Saving all data
Output_Data_CSV_Path = Generate_Unique_Filepath(Output_Dir, Function_Name + "_All-Data", "Merged", ".csv")
#with open(Output_Data_CSV_Path, "w") as Merged_Output_File:
Merged_Output_File = open(Output_Data_CSV_Path, "w")
CSV_Writer = csv.writer(Merged_Output_File, delimiter = ",", lineterminator = "\n")
CSV_Writer.writerow(Data_File_Header) # Write the header
for Data_File in Data_All_Files:
	for Data_Ch in Data_File:
		Row = []
		for Key in Data_File_Ordered_Keys:
			Row.append(Data_Ch[Key])
		CSV_Writer.writerow(Row)
Merged_Output_File.close()

# Data_Ch is a dictionary
# Data_File is a list of dictionaries
# Data_All_Files is a list of a list of dictionnaries


# Saving Essential Data
Output_Simple_Data_CSV_Path = Generate_Unique_Filepath(Output_Dir, Function_Name + "_Essential-Data", "Merged", ".csv")
Input_File = open(Output_Data_CSV_Path, 'r')
Reader = csv.reader(Input_File, delimiter=',', lineterminator='\n')
Header = next(Reader)

# Adjust this index to the column containing the filenames
Filename_Column_Index = 0  # Example: 0 for the first column
Selected_Columns = [0, 1, 2, 4, 13, 14, 15, 28, 29, 30, 31, 32, 33, 34, 35, 36, 39]

# Select header for output
Selected_Header = [Header[i] for i in Selected_Columns]

# Prepare to handle dynamic variable columns
Max_Variable_Count = 0
Processed_Rows = []

# First pass: Process rows to determine maximum filename parts
for Row in Reader:
	Filename = Row[Filename_Column_Index]
	Filename_Parts = Filename.split("_")  # Split the filename
	if "." in Filename_Parts[-1]:
		Filename_Parts[-1] = os.path.splitext(Filename_Parts[-1])[0]  # Use os.path.splitext or split manually

	Max_Variable_Count = max(Max_Variable_Count, len(Filename_Parts))
	Selected_Row = [Row[i] for i in Selected_Columns]
	Processed_Rows.append((Selected_Row, Filename_Parts))

# Generate variable column headers
Variable_Columns = ["Filename-Variable-{0:03d}".format(i + 1) for i in range(Max_Variable_Count)]

# Update the header: Insert variable columns right after the filename column
Filename_Output_Index = Selected_Columns.index(Filename_Column_Index)
Updated_Header = (
	Selected_Header[:Filename_Output_Index + 1] +
	Variable_Columns +
	Selected_Header[Filename_Output_Index + 1:]
)

# Write the updated data
Output_File = open(Output_Simple_Data_CSV_Path, 'w')
CSV_Writer = csv.writer(Output_File, delimiter=',', lineterminator='\n')
CSV_Writer.writerow(Updated_Header)  # Write the header

# Second pass: Write rows with padding for variable columns
for Selected_Row, Filename_Parts in Processed_Rows:
	# Pad Filename_Parts with empty strings if fewer than Max_Variable_Count
	Padded_Filename_Parts = Filename_Parts + [""] * (Max_Variable_Count - len(Filename_Parts))
	# Insert the variables right after the filename
	Final_Row = (
		Selected_Row[:Filename_Output_Index + 1] +
		Padded_Filename_Parts +
		Selected_Row[Filename_Output_Index + 1:]
	)
	CSV_Writer.writerow(Final_Row)

Output_File.close()
Input_File.close()



#0.  Filename
#1.  Channel_Nb
#2.  Channel_Name
#3.  Channel_Wavelength_EM
#4.  Objective_Mag
#5.  Objective_NA
#6.  Objective_Immersion
#7.  Gaussian_Blur
#8.  Gaussian_Sigma
#9.  Binning_Method
#10. Batch_Mode
#11. Save_Individual_Files
#12. Prolix_Mode
#13. Intensity_Min
#14. Intensity_Max
#15. Intensity_Mean
#16. Intensity_Std_Dev
#17. Intensity_Median
#18. Intensity_Mode
#19. Width_Pix
#20. Height_Pix
#21. Bit_Depth
#22. Pixel_Width
#23. Pixel_Height
#24. Pixel_Depth
#25. Space_Unit
#26. Space_Unit_Std
#27. Calibration_Status
#28. Std_Dev
#29. Uniformity_Std
#30. Uniformity_Percentile
#31. CV
#32. Uniformity_CV
#33. X_Center_Pix
#34. Y_Center_Pix
#35. X_Ref_Pix
#36. Y_Ref_Pix
#37. X_Ref
#38. Y_Ref
#39. Centering_Accuracy

# Log the success message indicating the number of processed images
Message = Function_Name + " has been completed.\n" + str(len(Processed_Images_List)) + " images have been processed successfully."
Message = Message + "\n" + "Files are saved in " + str(Output_Dir)
IJ.log(Message)
JOptionPane.showMessageDialog(None, Message,Plugin_Name+" "+Function_Name, JOptionPane.INFORMATION_MESSAGE)

java.lang.System.gc() # Cleaning up my mess ;-)