# Written by Nicolas Stifani nstifani@gmail.com for info

# Import General Features
import os
import sys
import csv
from math import sqrt, floor, asin, cos, fabs
from ij import IJ, ImagePlus, Prefs, WindowManager
from ij.process import ImageProcessor, FloatProcessor, ByteProcessor, ImageStatistics, ImageConverter
from ij.gui import Overlay, TextRoi
from ij.plugin import Duplicator, Zoom
from ij.measure import Measurements, ResultsTable
from ij.plugin.frame import RoiManager
from ij.plugin.filter import GaussianBlur
from loci.plugins import BF
from loci.plugins.in import ImporterOptions
from loci.formats import MetadataTools, ImageReader
from java.io import File
from java.awt import Font, Color, GridLayout, GridBagLayout, GridBagConstraints, Insets, Frame, Panel, Button, Label, Toolkit
from javax.swing import JOptionPane, JFileChooser, JTextField, JLabel, JSeparator, JRadioButton, ButtonGroup, JSlider,JButton, JCheckBox, JPanel, JFrame, SwingUtilities, JDialog
from java.awt.event import ActionListener
from javax.swing.event import ChangeListener, DocumentListener
import java.lang.System
from fiji.plugin.trackmate import Model, Settings, TrackMate, SelectionModel, Logger
from fiji.plugin.trackmate.detection import DogDetectorFactory, LogDetectorFactory
from fiji.plugin.trackmate.tracking.jaqaman import SparseLAPTrackerFactory
from fiji.plugin.trackmate.features import FeatureFilter
from fiji.plugin.trackmate.features.track import TrackIndexAnalyzer
from fiji.plugin.trackmate.gui.displaysettings import DisplaySettingsIO
from fiji.plugin.trackmate.visualization.table import TrackTableView, AllSpotsTableView
from fiji.plugin.trackmate.visualization.hyperstack import HyperStackDisplayer

Plugin_Name = "QC Scope"
Function_Name = "Channel Alignment"
Unicode_Micron_Symbol = "u" #chr(0xB5)
Reset_Preferences = False 
User_Desktop_Path = os.path.join(os.path.expanduser("~"), "Desktop") 
Output_Dir = os.path.join(User_Desktop_Path, "Output")

Image_Valid_Extensions = (".tif", ".tiff", ".jpg", ".jpeg", ".png", ".czi", ".nd2", ".lif", ".lsm", ".ome.tif", ".ome.tiff")
Space_Unit_Conversion_Dictionary = {
    "micron": Unicode_Micron_Symbol + "m", "microns": Unicode_Micron_Symbol + "m", Unicode_Micron_Symbol + "m": Unicode_Micron_Symbol + "m",
    "um": Unicode_Micron_Symbol + "m", "u": Unicode_Micron_Symbol + "m", u"\u00B5m": Unicode_Micron_Symbol + "m", "nm": "nm", "nanometer": "nm", 
    "nanometers": "nm", "mm": "mm", "millimeter": "mm", "millimeters": "mm", "cm": "cm", "centimeter": "cm", "centimeters": "cm", "m": "m",
    "meter": "m", "meters": "m", "inch": "in", "inches": "in", "in": "in", "pixel": "pixels", "pixels": "pixels", "": "pixels", " ": "pixels"
}

Settings_Template= {
	Function_Name+".Trackmate.Detection_Method": "Dog Detector",
	Function_Name+".Trackmate.DogDetector.Threshold_Value": 20.0,
	Function_Name+".Trackmate.DogDetector.Median_Filtering": False,
	Function_Name+".Trackmate.DogDetector.Spot_Diameter": 4.0,
	Function_Name+".Trackmate.DogDetector.Subpixel_Localization": True,
	Function_Name+".Trackmate.LogDetector.Threshold_Value": 100.0,
	Function_Name+".Trackmate.LogDetector.Median_Filtering": False,
	Function_Name+".Trackmate.LogDetector.Spot_Diameter": 4.0,
	Function_Name+".Trackmate.LogDetector.Subpixel_Localization": True,
	Function_Name+".Batch_Mode": True,
	Function_Name+".Save_Individual_Files": False,
	Function_Name+".Prolix_Mode": False,
	Function_Name+".Objective_Mag": "5x",
	Function_Name+".Objective_NA": 1.0,
	Function_Name+".Objective_Immersion": "Air",
	Function_Name+".Channel_Names": ["DAPI","Alexa488","Alexa555","Alexa647","Alexa730","Alexa731","Alexa732","Alexa733"],
	Function_Name+".Channel_WavelengthsEM": [425,488,555,647,730,731,732,733],
	}

IJ.run("Set Measurements...", "area mean standard modal min centroid center perimeter bounding fit shape feret's integrated median skewness kurtosis area_fraction stack redirect=None decimal=3");
IJ.setTool("rectangle");
IJ.run("Colors...", "foreground=white background=black selection=yellow")

def Prolix_Message(Message):
	Settings_Stored = Read_Preferences(Settings_Template)
	if Settings_Stored[Function_Name + ".Prolix_Mode"]:
		IJ.log(Message)
	return

def Initialize_Preferences(Settings, Reset_Preferences):
 	if Reset_Preferences:
		Save_Preferences(Settings)
	else:
		for Setting, Value in Settings.items():
		 	if Prefs.get(Setting, None) is None:
				Save_Preferences(Settings)
 				break
	return

def Read_Preferences(Settings):
	Preferences_Stored = {}
	for Key, Default_Value in Settings.items():
		Value = Prefs.get(Key, str(Default_Value))
		if isinstance(Default_Value, bool):
			Value = bool(int(Value)) # Interestingly Boolean are saved as a float in the Pref so we need to convert to int and then to boolean
		elif isinstance(Default_Value, float):
			Value = float(Value)
		elif isinstance(Default_Value, int):
			Value = int(Value)
		elif isinstance(Default_Value, list):
			if isinstance(Default_Value[0], int):
	 			Value = [int(Item.strip()) for Item in Value.split(",")]
			elif isinstance(Default_Value[0], float):
				Value = [float(Item.strip()) for Item in Value.split(",")]
			else:
				Value = [str(Item.strip()) for Item in Value.split(",")]
		else:
			Value = str(Value)
		Preferences_Stored[Key] = Value
	return Preferences_Stored

def Save_Preferences(Settings):
	for Key, Value in Settings.items():
		if isinstance(Value, list):
			Value = ",".join(map(str, Value))
		elif isinstance(Value, bool):
			Value = int(Value)
		else:
			Value = str(Value)
		Prefs.set(Key, str(Value))
	Prefs.savePreferences()
	return

def Get_Images():
	Prolix_Message("Getting Images...")
	if WindowManager.getImageTitles():
		Image_List = WindowManager.getImageTitles()
		Image_List = [str(image) for image in Image_List]
		Prolix_Message("Success opened images found: :{}".format("\n".join(Image_List)))
	else:
		Image_List = []
		Prolix_Message("No opened image. Selecting Folder...")
		while not Image_List:
			Input_Dir_Path = Select_Folder(Default_Path = User_Desktop_Path)
			Prolix_Message("Selected Folder {}.".format(Input_Dir_Path))
			for Root, Dirs, Files in os.walk(Input_Dir_Path): # Get Files Recursively
			# Files = os.listdir(Input_Dir_Path): # Comment the line above and uncomment this line if you don"t want to get files recurcively
				for File in Files:
					if File.lower().endswith(tuple(Image_Valid_Extensions)): # Select only files ending with a Image_Valid_extensions
						Image_List.append(str(os.path.join(Root, File)))
						Prolix_Message("Success adding {}.".format(os.path.join(Root, File)))
			Image_List.sort()
			if not Image_List:
				Message = "Failed No valid image files found in the selected folder."
				Advice = "Valid image file extensions are: " + ", ".join(Image_Valid_Extensions)
				IJ.log("{}\n{}".format(Message, Advice))
				JOptionPane.showMessageDialog(None, "{}\n{}".format(Message, Advice), "{} {}".format(Plugin_Name, Function_Name), JOptionPane.INFORMATION_MESSAGE)
		Prolix_Message("Success List of Images:\n{}".format("\n".join(Image_List)))
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
		Prolix_Message("Success Selecting Folder: {}.".format(InputDir_Path))
	else:
		Message="Folder selection was canceled by user."
		IJ.log(Message)
		JOptionPane.showMessageDialog(None, Message, "{} {}".format(Plugin_Name, Function_Name), JOptionPane.INFORMATION_MESSAGE)
		sys.exit(Message)
	return InputDir_Path

# Open an image using Bioformat
def Open_Image_Bioformats(File_Path):
	Prolix_Message("Importing {} with Bioformats...".format(File_Path))
	Bioformat_Options = ImporterOptions()
	Bioformat_Options.setId(File_Path)
	try:
		imps = BF.openImagePlus(Bioformat_Options)
		if imps and len(imps) > 0:
			Prolix_Message("Success Importing {} with Bioformats.".format(File_Path))
			return imps[0]
		else:
			IJ.log("Failed importation with Bioformats: No Images found in {}".format(File_Path))
			return
	except Exception, Error:
		IJ.log("Failed Importation with Bioformats: Error opening {}".format(Error))
		return

# Generate a Unique filepath Directory\Basename_Suffix-001.Extension
def Generate_Unique_Filepath(Directory, Basename, Suffix, Extension):
	Prolix_Message("Generating Unique Filepath {}...".format(Basename))
	Filename = "{}_{}{}".format(Basename, Suffix, Extension)
	Filepath = os.path.join(Directory, Filename)
	if not os.path.exists(Filepath):
		Prolix_Message("Success Generating Unique Filepath {}.".format(Basename))
		return Filepath
	File_Counter = 2
	while True:
		Filename = "{}_{}-{:03d}{}".format(Basename, Suffix, File_Counter, Extension)
		Filepath = os.path.join(Directory, Filename)
		if not os.path.exists(Filepath):
			Prolix_Message("Success Generating Unique Filepath {}.".format(Basename))
			return Filepath
		File_Counter += 1
	return

# Match the Image Space Unit to a defined Standard Space Unit: m, cm, mm, micronSymbo+"m", nm
def Normalize_Space_Unit(Space_Unit):
	Prolix_Message("Standardizing space unit: {}...".format(Space_Unit))
	Space_Unit_Std = Space_Unit_Conversion_Dictionary.get(Space_Unit.lower(), "pixels")
	Prolix_Message("Success Standardizing space unit from {} to {}".format(Space_Unit, Space_Unit_Std))
	return Space_Unit_Std

# Get Image Information. Works only on files written on the disk
# Return Image_Info a dictionnary including all image information
# This function also Normalize the Space Unit without writing it to the file
def Get_Image_Info(imp):
	Image_Name = imp.getTitle()
	Prolix_Message("Getting Image Info for {}...".format(Image_Name))
	File_Info = imp.getOriginalFileInfo()
	if not File_Info :
		Filename = Image_Name + "_Unsaved"
		Input_Dir = "N/A"
		Input_File_Path = "N/A"
		IJ.log("{} not written on the disk. Proceeding with Filename: {}, Input Dir: {}, Path: {}".format(Image_Name, Filename, Input_Dir, Input_File_Path))
	else : # File Info is not None
		Filename = File_Info.fileName
		Input_Dir = File_Info.directory
		if not Input_Dir :
			Input_Dir = "N/A"
			Input_File_Path = "N/A"
			IJ.log("{} has no directory. Proceeding with Filename: {}, Input Dir: {}, Path: {}".format(Image_Name, Filename, Input_Dir, Input_File_Path))
		else:
			Input_File_Path = os.path.join(Input_Dir, Filename)
			Prolix_Message("Filename: {}, Input Dir: {}, Path: {}".format(Filename, Input_Dir, Input_File_Path))
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
	Image_Type = imp.getType()
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
		"Image_Type":int(Image_Type)
		}
	Prolix_Message("Success getting Image Info for {}.".format(Image_Name))
	return Image_Info

# Get Image Metadata
def Get_Image_Metadata(imp):
	Image_Name = imp.getTitle()
	Prolix_Message("Getting Metadata for {}...".format(Image_Name))
	Image_Metadata = {}
	Image_Info = Get_Image_Info(imp)
	if Image_Info["Input_File_Path"] == "N/A":
		IJ.log("{} {} can only get metadata from images written on the disk. {} is virtual. Proceeding with information from Preferences...". format(Plugin_Name, Function_Name, Image_Name))
		return None
	Bioformat_Options = ImporterOptions()
	Bioformat_Options.setId(Image_Info["Input_File_Path"])
	Metadata = MetadataTools.createOMEXMLMetadata()
	Reader = ImageReader()
	Reader.setMetadataStore(Metadata)
	Reader.setId(Image_Info["Input_File_Path"])
	if Metadata.getImageCount() == 0:
		IJ.log("{} does not contain metadata. Proceeding with information from Preferences...".format(Image_Name))
		return None
	else:
		Channel_Names_Metadata = []
		for i in range(Metadata.getChannelCount(0)):
			Channel_Name = Metadata.getChannelName(0, i) # Channel_Name are Unicode
			if Channel_Name is not None:
				Channel_Name = str(Channel_Name) # Convert Unicode to regular string
			Channel_Names_Metadata.append(Channel_Name)
		if any(Channel_Name is None for Channel_Name in Channel_Names_Metadata):
			Channel_Names_Metadata = None
		Channel_WavelengthsEM_Metadata = []
		for i in range(Metadata.getChannelCount(0)):
			WavelengthEM = Metadata.getChannelEmissionWavelength(0, i)
			if WavelengthEM is not None:
				# Extract numeric value from the wavelength metadata
				Value_Str = str(WavelengthEM)
				Start = Value_Str.find("value[") + 6
				End = Value_Str.find("]", Start)
				if Start != -1 and End != -1:
					Value = Value_Str[Start:End]
					Channel_WavelengthsEM_Metadata.append(int(round(float(Value))))
				else:
					Channel_WavelengthsEM_Metadata.append(0)
			else:
				Channel_WavelengthsEM_Metadata.append(0)
		if any(Channel_WavelengthEM == 0 for Channel_WavelengthEM in Channel_WavelengthsEM_Metadata):
			Channel_WavelengthsEM_Metadata = None

		# Check if metadata contains objective and instrument information
		if Metadata.getInstrumentCount() > 0 and Metadata.getObjectiveCount(0) > 0:
			Objective_Mag_Metadata = str(int(Metadata.getObjectiveNominalMagnification(0,0)))+"x"
			Objective_NA_Metadata = float(Metadata.getObjectiveLensNA(0, 0))
			Objective_Immersion_Metadata = str(Metadata.getObjectiveImmersion(0, 0))
		else:
			Objective_Mag_Metadata = None
			Objective_NA_Metadata = None
			Objective_Immersion_Metadata = None
		Prolix_Message("Objective_Mag_Metadata = {}.".format(Objective_Mag_Metadata))
		Prolix_Message("Objective_NA_Metadata = {}.".format(Objective_NA_Metadata))
		Prolix_Message("Objective_Immersion_Metadata = {}.".format(Objective_Immersion_Metadata))
		Prolix_Message("Channel Names Metadata = {}.".format(str(Channel_Names_Metadata)))
		Prolix_Message("Channel Wavelengths EM Metadata = {}.".format(Channel_WavelengthsEM_Metadata))
		Prolix_Message("Success getting Metadata for {}.".format(Image_Name))
		Image_Metadata["Objective_Mag_Metadata"] = Objective_Mag_Metadata
		Image_Metadata["Objective_NA_Metadata"] = Objective_NA_Metadata
		Image_Metadata["Objective_Immersion_Metadata"] = Objective_Immersion_Metadata
		Image_Metadata["Channel_Names_Metadata"] = Channel_Names_Metadata
		Image_Metadata["Channel_WavelengthsEM_Metadata"] = Channel_WavelengthsEM_Metadata
	return Image_Metadata

def Get_Refractive_Index(Objective_Immersion): # Get the refractive Index (float) from the Immersion media (String). Return Refracive_Index
	Prolix_Message("Getting refractive index for {} objective...".format(Objective_Immersion))
	Refractive_Indices = {
		"Air": 1.0003,
		"Water": 1.333,
		"Oil": 1.515,
		"Glycerin": 1.47,
		"Silicone": 1.40,
	}
	Refractive_Index = float(Refractive_Indices.get(Objective_Immersion, 1.0))
	Prolix_Message("Success getting refractive index for {} objective. Refractive Index = {}.".format(Objective_Immersion, Refractive_Index))
	return Refractive_Index

def Process_Image_List(Image_List):
	Prolix_Message("Processing Image List {}.".format(Image_List))
	Processed_Image_List = []
	Data_All_Files = []
	Data_Processed_All_Files = []
	global Image

	for Image, Image_File in enumerate(Image_List):
		# Checking Image_File is an Opened Image
		if isinstance(Image_File, str) and not ("/" in Image_File or "\\" in Image_File):
			imp = WindowManager.getImage(Image_File)
			Image_Window = WindowManager.getFrame(imp.getTitle())
			Image_Window.toFront()
			File_Source = "Opened"
		else: # Image_File is a path, import it with Bioformat
			imp = Open_Image_Bioformats(Image_File)
			File_Source = "Folder"
		#Zoom.set(imp, 0.5);
		imp.show()
		Image_Name = imp.getTitle()
		Prolix_Message("Success opening {} from {}.".format(Image_Name, File_Source))
		# Process the first image with Process_Image function showing a Dialog
		if Image == 0:
			Prolix_Message("Processing initial Image {}.".format(Image_Name))
			Data_All_Files, Data_Processed_All_Files, Processed_Image_List = Process_Image(imp, Data_All_Files, Data_Processed_All_Files, Processed_Image_List, Batch_Message = "")
		# For subsequent images, check if batch mode is enabled
		else:
			Settings_Stored = Read_Preferences(Settings_Template)
			if Settings_Stored[Function_Name+".Batch_Mode"]:
				Prolix_Message("Processing in batch {}.".format(Image_Name))
				Data_All_Files, Data_Processed_All_Files, Processed_Image_List = Process_Image_Batch(imp, Data_All_Files, Data_Processed_All_Files, Processed_Image_List)
			else:
			 	IJ.log("Failed Batch processing {}. Falling back to dialog processing.".format(Image_Name))
			 	Data_All_Files, Data_Processed_All_Files, Processed_Image_List = Process_Image(imp, Data_All_Files,Data_Processed_All_Files, Processed_Image_List, Batch_Message = "")
		if File_Source == "Folder":
			Prolix_Message("Closing {}".format(Image_Name))
			imp.close()
	return Data_All_Files, Data_Processed_All_Files, Processed_Image_List

def Process_Image(imp, Data_All_Files, Data_Processed_All_Files, Processed_Image_List, Batch_Message):
	Image_Name = imp.getTitle()
	Prolix_Message("Processing {}...".format(Image_Name))
	Dialog_Counter = 0
	User_Click = None
	Test_Processing = False
	while True:
		Settings_Stored = Read_Preferences(Settings_Template)


		# Display the main dialog with Metadata and results from predetection
		Settings_User, User_Click, Dialog_Counter, Test_Processing, Nb_Detected_Spot_File, Batch_Message = Display_Processing_Dialog(imp, Dialog_Counter, Test_Processing, Batch_Message)

		global DetectionMethod
		DetectionMethod = (Settings_Stored[Function_Name+".Trackmate.Detection_Method"]).replace(" ", "")

		Settings_Stored_Filtered = {}
		for Key, Value in Settings_Stored.items():
			if Key in [
			Function_Name+".Trackmate.Detection_Method",
			Function_Name+".Trackmate." + DetectionMethod + ".Threshold_Value",
			Function_Name+".Trackmate." + DetectionMethod + ".Subpixel_Localization",
			Function_Name+".Trackmate." + DetectionMethod + ".Median_Filtering",
			Function_Name+".Trackmate." + DetectionMethod + ".Spot_Diameter"
			]:
				Settings_Stored_Filtered[Key] = Value

		Settings_User_Filtered = {}
		for Key, Value in Settings_User.items():
			if Key in [
			Function_Name+".Trackmate.Detection_Method",
			Function_Name+".Trackmate." + DetectionMethod + ".Threshold_Value",
			Function_Name+".Trackmate." + DetectionMethod + ".Subpixel_Localization",
			Function_Name+".Trackmate." + DetectionMethod + ".Median_Filtering",
			Function_Name+".Trackmate." + DetectionMethod + ".Spot_Diameter"
			]:
				Settings_User_Filtered[Key] = Value

		# All conditions must be fulfilled to proceed
		if User_Click == "OK" and not Test_Processing and all(Nb_Spot == 1 for Nb_Spot in Nb_Detected_Spot_File) and Settings_Stored_Filtered == Settings_User_Filtered:
			break # Break the while loop
		elif User_Click == "Cancel":
			Message = "Processing {}, User Canceled operation".format(Image_Name)
			IJ.log(Message)
			JOptionPane.showMessageDialog(None, Message, "{} {}".format(Plugin_Name, Function_Name), JOptionPane.INFORMATION_MESSAGE)
			sys.exit(Message)
	# Once we break the loop
	Data_File, _, _ = Run_Trackmate_All_Channel(imp, Save_File = True)
	Data_All_Files.append(Data_File)
	Data_Processed_File = Channel_Alignment_Data_Processing(imp, Data_File)
	Data_Processed_All_Files.append(Data_Processed_File)
	Processed_Image_List.append(Image_Name)
	IJ.log("Success processing {}.".format(Image_Name))
	return Data_All_Files, Data_Processed_All_Files, Processed_Image_List

def Process_Image_Batch(imp, Data_All_Files, Data_Processed_All_Files, Processed_Image_List):
	Image_Name = imp.getTitle()
	Nb_Channels = imp.getNChannels()
	Prolix_Message("Processing {} in batch...". format(Image_Name))

	Settings_Stored = Read_Preferences(Settings_Template)
	Channel_Names_Stored = Settings_Stored[Function_Name+".Channel_Names"]
	Channel_WavelengthsEM_Stored = Settings_Stored[Function_Name+".Channel_WavelengthsEM"]
	Objective_Mag_Stored = Settings_Stored[Function_Name+".Objective_Mag"]
	Objective_NA_Stored = Settings_Stored[Function_Name+".Objective_NA"]
	Objective_Immersion_Stored = Settings_Stored[Function_Name+".Objective_Immersion"]

	# Trying to get some metadata
	Image_Metadata = Get_Image_Metadata(imp)

	# Check for presence of metadata and compare it with stored preferences
	Batch_Message = ""
	if Image_Metadata is not None:
		Channel_Names_Metadata = Image_Metadata["Channel_Names_Metadata"]
		Channel_WavelengthsEM_Metadata = Image_Metadata["Channel_WavelengthsEM_Metadata"]
		Objective_Mag_Metadata = Image_Metadata["Objective_Mag_Metadata"]
		Objective_NA_Metadata = Image_Metadata["Objective_NA_Metadata"]
		Objective_Immersion_Metadata = Image_Metadata["Objective_Immersion_Metadata"]

		if Objective_Mag_Metadata != Objective_Mag_Stored:
			Batch_Message = Batch_Message + "Objective Magnification Metadata: {}. Preferences: {}.".format(Objective_Mag_Metadata, Objective_Mag_Stored)
		if Objective_NA_Metadata != Objective_NA_Stored:
			Batch_Message = Batch_Message + "\n" + "Objective NA Metadata: {}. Preferences: {}.".format(Objective_NA_Metadata, Objective_NA_Stored)
		if Objective_Immersion_Metadata != Objective_Immersion_Stored:
			Batch_Message = Batch_Message + "\n" + "Objective Immersion Metadata: {}. Preferences: {}.".format(Objective_Immersion_Metadata, Objective_Immersion_Stored)
		if Nb_Channels > len(Channel_Names_Stored):
			Batch_Message = Batch_Message + "\n" + "Nb of Channels Image: {}. Preferences: {}.".format(Nb_Channels, len(Channel_Names_Stored))
		else: # Nb of Channels is sufficient check Matching values
			if Channel_Names_Metadata != Channel_Names_Stored[:Nb_Channels]:
				Batch_Message = Batch_Message + "\n" + "Channel Names Metadata: {}. Preferences: {}.".format(Channel_Names_Metadata, Channel_Names_Stored[:Nb_Channels])
			if Channel_WavelengthsEM_Metadata != Channel_WavelengthsEM_Stored[:Nb_Channels]:
				Batch_Message = Batch_Message + "\n" + "Channel Emission Wavelengths Metadata: {}. Preferences: {}.".format(Channel_WavelengthsEM_Metadata, Channel_WavelengthsEM_Stored[:Nb_Channels])
		if Batch_Message != "":
			Batch_Message = "Metadata differ from preferences. {}".format(Batch_Message)
			Prolix_Message(Batch_Message)
			Batch_Processing = "Fail"
		else:
			Batch_Processing = "Pass"
	else: # No Metadata found try with stored data
		if Nb_Channels <= len(Channel_WavelengthsEM_Stored) and Nb_Channels <= len(Channel_WavelengthsEM_Stored):
			Batch_Processing = "Pass"
		else:
			Batch_Processing = "Fail"
	if Batch_Processing == "Pass":
		Data_File, Nb_Detected_Spot_File, Max_Quality_File = Run_Trackmate_All_Channel(imp, Save_File = True) # Might need to Save File here to avoid running it twice ICIT
		if all(Nb_Detected_Spot == 1 for Nb_Detected_Spot in Nb_Detected_Spot_File):
			#Data_File, _, _ = Run_Trackmate_All_Channel(imp, Save_File = True)
			Data_All_Files.append(Data_File)
			Data_Processed_File = Channel_Alignment_Data_Processing(imp, Data_File)
			Data_Processed_All_Files.append(Data_Processed_File)
			Processed_Image_List.append(Image_Name)
			IJ.log("Success batch processing {}.".format(Image_Name))
		else:
			IJ.log("Batch processing failed for {}.{}".format(Image_Name, Batch_Message))
			Data_All_Files, Data_Processed_All_Files, Processed_Image_List = Process_Image(imp, Data_All_Files, Data_Processed_All_Files,Processed_Image_List, Batch_Message)
	else:
		IJ.log("Batch processing failed for {}.{}".format(Image_Name, Batch_Message))
		Data_All_Files, Data_Processed_All_Files, Processed_Image_List = Process_Image(imp, Data_All_Files,Data_Processed_All_Files, Processed_Image_List, Batch_Message)
	return Data_All_Files, Data_Processed_All_Files, Processed_Image_List

def Display_Processing_Dialog(imp, Dialog_Counter, Test_Processing, Batch_Message):
	Image_Name = imp.getTitle()
	Image_Info = Get_Image_Info(imp)
	Nb_Channels = imp.getNChannels()
	Current_Channel = imp.getChannel()
	Prolix_Message("Displaying Processing Dialog for {}...".format(Image_Name))

	Image_Metadata = Get_Image_Metadata(imp)

	# Check for presence of metadata and compare it with stored preferences
	if Image_Metadata is not None:
		Channel_Names_Metadata = Image_Metadata["Channel_Names_Metadata"]
		Channel_WavelengthsEM_Metadata = Image_Metadata["Channel_WavelengthsEM_Metadata"]
		Objective_Mag_Metadata = Image_Metadata["Objective_Mag_Metadata"]
		Objective_NA_Metadata = Image_Metadata["Objective_NA_Metadata"]
		Objective_Immersion_Metadata = Image_Metadata["Objective_Immersion_Metadata"]

	Settings_Stored = Read_Preferences(Settings_Template)
	Channel_Names_Stored = Settings_Stored[Function_Name+".Channel_Names"]
	Channel_WavelengthsEM_Stored = Settings_Stored[Function_Name+".Channel_WavelengthsEM"]
	Objective_Mag_Stored = Settings_Stored[Function_Name+".Objective_Mag"]
	Objective_NA_Stored = Settings_Stored[Function_Name+".Objective_NA"]
	Objective_Immersion_Stored = Settings_Stored[Function_Name+".Objective_Immersion"]

	def Set_Data(Data_Metadata, Data_Stored, Dialog_Counter):
		if Data_Metadata is not None and Dialog_Counter == 0:
			return Data_Metadata, "Metadata"
		else:
			return Data_Stored, "Prefs"

	Objective_Mag, Objective_Mag_Source = Set_Data(Objective_Mag_Metadata, Objective_Mag_Stored, Dialog_Counter)
	Objective_NA, Objective_NA_Source = Set_Data(Objective_NA_Metadata, Objective_NA_Stored, Dialog_Counter)
	Objective_Immersion, Objective_Immersion_Source = Set_Data(Objective_Immersion_Metadata, Objective_Immersion_Stored, Dialog_Counter)
	Channel_Names, Channel_Names_Source = Set_Data(Channel_Names_Metadata, Channel_Names_Stored, Dialog_Counter)
	Channel_WavelengthsEM, Channel_WavelengthsEM_Source = Set_Data(Channel_WavelengthsEM_Metadata, Channel_WavelengthsEM_Stored, Dialog_Counter)

		# Adding Channel Names and wavelengths from templates
	if len(Channel_Names) < Nb_Channels:
		Missing_Channel_Names = Settings_Template[Function_Name + ".Channel_Names"][len(Channel_Names):Nb_Channels]
		Channel_Names.extend(Missing_Channel_Names)
	if len(Channel_WavelengthsEM) < Nb_Channels:
		Missing_Channel_WavelengthsEM = Settings_Template[Function_Name + ".Channel_WavelengthsEM"][len(Channel_WavelengthsEM):Nb_Channels]
		Channel_WavelengthsEM.extend(Missing_Channel_WavelengthsEM)

	# Preprocessing the file before displaying the dialog
	_, Nb_Detected_Spot_File, Max_Quality_File = Run_Trackmate_All_Channel(imp, Save_File = False)

	# PreProcessing the Current Channel for display purposes
	_, _, _ = Run_Trackmate_Single_Channel(imp, Current_Channel, Save_File = False, Display = True)

	# Create the Dialog. Sorry it is long and messy but looks good huh?
	Processing_Dialog = JDialog(None, "{} {}".format(Plugin_Name, Function_Name), False) # 'True' makes it modal
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

	if Batch_Message != "":
		Batch_Message_List = Batch_Message.split("\n")
		for Message in Batch_Message_List:
			Constraints.gridx = Pos_X
			Constraints.gridy = Pos_Y
			Constraints.gridwidth = GridBagConstraints.REMAINDER
			Constraints.gridheight = 1
			Constraints.anchor = GridBagConstraints.CENTER
			Constraints.insets = Insets(2, 2, 2, 2)
			Label = "{}".format(Message)
			J_Label = JLabel(Label)
			J_Label.setFont(Font("Arial", Font.BOLD, 12))
			J_Label.setForeground(Color.BLUE)
			Processing_Panel.add(J_Label, Constraints)
			Pos_Y += 1
	elif not all(Spot == 1 for Spot in Nb_Detected_Spot_File):
		Message = "Nb Detected Spots {} = {} vs {}".format("+".join(map(str,Nb_Detected_Spot_File)), sum(Nb_Detected_Spot_File), Image_Info["Nb_Channels"])
		IJ.log(Message)
		Message = "Nb of Detected Spots per channel must be exactly 1. "
		if (sum(Nb_Detected_Spot_File) > Image_Info["Nb_Channels"]):
			Message = Message + "Increase the detection threshold."
		elif (sum(Nb_Detected_Spot_File) < Image_Info["Nb_Channels"]):
			Message = Message + "Decrease the detection threshold."
		IJ.log(Message)
		Constraints.gridx = Pos_X
		Constraints.gridy = Pos_Y
		Constraints.gridwidth = GridBagConstraints.REMAINDER
		Constraints.gridheight = 1
		Constraints.anchor = GridBagConstraints.CENTER
		Constraints.insets = Insets(2, 2, 2, 2)
		Label = Message
		J_Label = JLabel(Label)
		J_Label.setFont(Font("Arial", Font.BOLD, 12))
		J_Label.setForeground(Color.BLUE)
		Processing_Panel.add(J_Label, Constraints)
		Pos_Y += 1
	elif all(Spot == 1 for Spot in Nb_Detected_Spot_File):
		Message = "Detection successful. 1 Spot per Channel."
		Constraints.gridx = Pos_X
		Constraints.gridy = Pos_Y
		Constraints.gridwidth = GridBagConstraints.REMAINDER
		Constraints.gridheight = 1
		Constraints.anchor = GridBagConstraints.CENTER
		Constraints.insets = Insets(2, 2, 2, 2)
		Label = Message
		J_Label = JLabel(Label)
		J_Label.setFont(Font("Arial", Font.BOLD, 12))
		Dark_Green = Color(20, 200, 20)
		J_Label.setForeground(Dark_Green)
		Processing_Panel.add(J_Label, Constraints)
		Pos_Y += 1

	# Error label
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.NORTH
	Constraints.insets = Insets(2, 2, 2, 2)
	Error_Label = JLabel("")
	Error_Label.setFont(Font("Arial", Font.BOLD, 12))
	Error_Label.setForeground(Color.RED)
	Processing_Panel.add(Error_Label, Constraints)

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

	# Add Objective Labels
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

	# Add the Objective Label
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

	# Objective Magnification Field
	Constraints.gridx = Pos_X + 1
	Text = "{}".format(Objective_Mag)
	Objective_Mag_User = JTextField(Text, 6)
	Objective_Mag_User.setFont(Font("Arial", Font.PLAIN, 12))
	Objective_Mag_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Objective_Mag_User, Constraints)

	def Numeric_Validator(Text):
		try:
			return float(Text.strip()) > 0
		except ValueError:
			return False

	class Numeric_Validator_Listener(DocumentListener):
		def __init__(self, Text_Fields, Error_Label, OK_Button):
			self.Text_Fields = Text_Fields
			self.Error_Label = Error_Label
			self.OK_Button = OK_Button

		def Validate(self):
			All_Valid = True
			for Field in self.Text_Fields:
				Text = Field.getText()
				if not Numeric_Validator(Text):
					All_Valid = False
					break
			if All_Valid:
				self.Error_Label.setText("") # Clear error message
				self.OK_Button.setEnabled(True)
			else:
				self.Error_Label.setText("Positive number required")
				self.OK_Button.setEnabled(False)
		def insertUpdate(self, event):
			self.Validate()
		def removeUpdate(self, event):
			self.Validate()
		def changedUpdate(self, event):
			self.Validate()

	# Objective NA Field
	Constraints.gridx = Pos_X + 2
	Text = "{}".format(Objective_NA)
	Objective_NA_User = JTextField(Text, 6)
	Objective_NA_User.setFont(Font("Arial", Font.PLAIN, 12))
	Objective_NA_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Objective_NA_User, Constraints)

	# Objective info Source
	Constraints.gridx = Pos_X + 3
	Label = "{}".format(Objective_Mag_Source)
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.PLAIN, 12))
	Processing_Panel.add(J_Label, Constraints)

	Pos_Y += 1

	# Immersion Media Title
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = GridBagConstraints.REMAINDER
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(10, 2, 2, 2)
	Label = "Immersion Media ({})".format(Objective_Immersion_Source)
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
		if Media == Objective_Immersion:
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
	# Pixel Label
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

	# Pixel Width Label
	Constraints.gridx = Pos_X+1
	Label = "Width"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Height Label
	Constraints.gridx = Pos_X + 2
	Label = "Height"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Depth Label
	Constraints.gridx = Pos_X + 3
	Label = "Depth"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Unit Label
	Constraints.gridx = Pos_X + 4
	Label = "Unit"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Bit Deph It"s there but it does not look balanced
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
	Label = "{}".format("Metadata" if Image_Info["Space_Unit_Std"] != "pixels" else "Uncalibrated")
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.PLAIN, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Pixel Width Field
	Constraints.gridx = Pos_X + 1
	Text_Field = "{}".format(Image_Info["Pixel_Width"])
	Pixel_Width_User = JTextField(Text_Field, 6)
	Pixel_Width_User.setFont(Font("Arial", Font.PLAIN, 12))
	Pixel_Width_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Pixel_Width_User, Constraints)

	# Pixel Height Field
	Constraints.gridx = Pos_X + 2
	Text_Field = "{}".format(Image_Info["Pixel_Height"])
	Pixel_Height_User = JTextField(Text_Field, 6)
	Pixel_Height_User.setFont(Font("Arial", Font.PLAIN, 12))
	Pixel_Height_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Pixel_Height_User, Constraints)

	# Pixel Voxel Depth Field
	Constraints.gridx = Pos_X + 3
	Text_Field = "{}".format(Image_Info["Pixel_Depth"])
	Pixel_Depth_User = JTextField(Text_Field, 6)
	Pixel_Depth_User.setFont(Font("Arial", Font.PLAIN, 12))
	Pixel_Depth_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Pixel_Depth_User, Constraints)

	# Pixel Unit Field
	Constraints.gridx = Pos_X + 4
	Text_Field = "{}".format(Image_Info["Space_Unit_Std"])
	Space_Unit_User = JTextField(Text_Field, 6)
	Space_Unit_User.setFont(Font("Arial", Font.PLAIN, 12))
	Space_Unit_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Space_Unit_User, Constraints)

	# Bit Depth Field
	#Constraints.gridx = Pos_X + 5
	#Text_Field = str(Image_Info["Bit_Depth"])
	#Bit_Depth_User = JTextField(Text_Field, 6)
	#Bit_Depth_User.setFont(Font("Arial", Font.PLAIN, 12))
	#Bit_Depth_User.setHorizontalAlignment(JTextField.CENTER)
	#Processing_Panel.add(Bit_Depth_User, Constraints)

	Pos_Y += 1

	# Channel Settings Title
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

	# Channel Labels
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

	# Loop for all Channels adding the name and Wavelength Fields
	Channel_Name_List_User = [] # Sotring the Dialog Identifier in a list for retrieval
	Channel_WavelengthsEm_List_User = [] # Sotring the Dialog Identifier in a list for retrieval
	for Channel in range (1, Image_Info["Nb_Channels"]+1):
		# Adding Channel Number Label
		Constraints.gridx = Pos_X
		Constraints.gridy = Pos_Y + Channel
		Constraints.gridwidth = 1
		Constraints.gridheight = 1
		Constraints.anchor = GridBagConstraints.CENTER
		Constraints.insets = Insets(2, 2, 2, 2)
		Label = "Channel {}".format(Channel)
		J_Label = JLabel(Label)
		J_Label.setFont(Font("Arial", Font.PLAIN, 12))
		Processing_Panel.add(J_Label, Constraints)

		# Adding Channel Names Fields
		Constraints.gridx = Pos_X + 1
		Text_Field = "{}".format(Channel_Names[Channel-1])
		Channel_Name_User = JTextField(Text_Field, 6)
		Channel_Name_User.setFont(Font("Arial", Font.PLAIN, 12))
		Channel_Name_User.setHorizontalAlignment(JTextField.CENTER)
		Processing_Panel.add(Channel_Name_User, Constraints)
		Channel_Name_List_User.append(Channel_Name_User)

		# Adding Channel Wavelength Fields
		Constraints.gridx = Pos_X + 2
		Text_Field = "{}".format(Channel_WavelengthsEM[Channel-1])
		Channel_Wavelength_EM_User = JTextField(Text_Field, 6)
		Channel_Wavelength_EM_User.setFont(Font("Arial", Font.PLAIN, 12))
		Channel_Wavelength_EM_User.setHorizontalAlignment(JTextField.CENTER)
		Processing_Panel.add(Channel_Wavelength_EM_User, Constraints)
		Channel_WavelengthsEm_List_User.append(Channel_Wavelength_EM_User)

		# Adding Channel Source Label
		Constraints.gridx = Pos_X + 3
		Label = "{}".format(Channel_Names_Source)
		J_Label = JLabel(Label)
		J_Label.setFont(Font("Arial", Font.PLAIN, 12))
		Processing_Panel.add(J_Label, Constraints)

	Pos_Y += Image_Info["Nb_Channels"]+1

	# Processing Settings title
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

	# Detection Method Label
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Detection Method"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Detection Method Radio
	Detection_Group = ButtonGroup()
	Detection_Method_List = ["Log Detector", "Dog Detector"]
	X_Start = Pos_X + 1
	Y_Start = Pos_Y
	for i, Method in enumerate(Detection_Method_List):
		Constraints.gridx = X_Start + i
		Constraints.gridy = Y_Start
		Constraints.gridwidth = 1
		Constraints.gridheight = 1
		Constraints.anchor = GridBagConstraints.CENTER
		Constraints.insets = Insets(5, 5, 5, 5)
		Detection_Button = JRadioButton(Method)
		Detection_Button.setFont(Font("Arial", Font.PLAIN, 12))
		Processing_Panel.add(Detection_Button, Constraints)
		Detection_Group.add(Detection_Button)
		if Method == Settings_Stored[Function_Name+".Trackmate.Detection_Method"]:
			Detection_Button.setSelected(True)
			global DetectionMethod
			DetectionMethod = (Settings_Stored[Function_Name+".Trackmate.Detection_Method"]).replace(" ", "")

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
	Batch_Mode_User.setSelected(Settings_Stored[Function_Name+".Batch_Mode"])
	Processing_Panel.add(Batch_Mode_User, Constraints)

	Pos_Y += 1

	global DetectionMethod

	# Threshold Value
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label_Threshold_Value = JLabel("Threshold {}".format(Settings_Stored[Function_Name+".Trackmate.{}.Threshold_Value".format(DetectionMethod)]))
	Label_Threshold_Value.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(Label_Threshold_Value, Constraints)

	# Threshold Slider
	Quality_Limit = int(min(Max_Quality_File))
	Quality_Scale = len(str(Quality_Limit))
	Major_Tick = int(10**(Quality_Scale-1))
	Threshold_Slider_Stored_Value = int(Settings_Stored[Function_Name+".Trackmate.{}.Threshold_Value".format(DetectionMethod)])
	Threshold_Slider_Default_Value = int(min(Threshold_Slider_Stored_Value, Quality_Limit))
	Threshold_Slider = JSlider(0, Quality_Limit, Threshold_Slider_Default_Value)
	Threshold_Slider.setMajorTickSpacing(Major_Tick)
	if int(Major_Tick/10) > 1:
		Minor_Tick = int(Major_Tick/10)
	else:
		Minor_Tick = 1
	Threshold_Slider.setMinorTickSpacing(Minor_Tick)
	Threshold_Slider.setPaintTicks(True)
	Threshold_Slider.setPaintLabels(True)

	# Add a listener to display the current slider value in the label
	class Threshold_Slider_Listener(ChangeListener):
		def stateChanged(self, event):
			Value = Threshold_Slider.getValue()
			Label_Threshold_Value.setText("Threshold {}".format(Value))

	Threshold_Slider.addChangeListener(Threshold_Slider_Listener())

	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 3
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Processing_Panel.add(Threshold_Slider, Constraints)

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
	Save_Individual_Files_User.setSelected(Settings_Stored[Function_Name+".Save_Individual_Files"])
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
	Prolix_Mode_User.setSelected(Settings_Stored[Function_Name+".Prolix_Mode"])
	Processing_Panel.add(Prolix_Mode_User, Constraints)

	Pos_Y += 1

	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Detection Parameters"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Spot Diameter Label
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Diameter ({})".format(Image_Info["Space_Unit_Std"])
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.PLAIN, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Spot Diameter Field
	Constraints.gridx = Pos_X + 2
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Text_Field = "{}".format(Settings_Stored[Function_Name+".Trackmate.{}.Spot_Diameter".format(DetectionMethod)])
	Spot_Diameter_User = JTextField(Text_Field, 6)
	Spot_Diameter_User.setFont(Font("Arial", Font.PLAIN, 12))
	Spot_Diameter_User.setHorizontalAlignment(JTextField.CENTER)
	Processing_Panel.add(Spot_Diameter_User, Constraints)

	# Subpixel Localization
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y + 1
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.NORTHWEST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Subpixel Precision"
	Subpixel_Localization_User = JCheckBox(Label)
	Subpixel_Localization_User.setFont(Font("Arial", Font.BOLD, 12))
	Subpixel_Localization_User.setSelected(Settings_Stored[Function_Name+".Trackmate.{}.Subpixel_Localization".format(DetectionMethod)])
	Processing_Panel.add(Subpixel_Localization_User, Constraints)

	# Median Filtering
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.WEST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Median Filtering"
	Median_Filtering_User = JCheckBox(Label)
	Median_Filtering_User.setFont(Font("Arial", Font.PLAIN, 12))
	Median_Filtering_User.setSelected(Settings_Stored[Function_Name+".Trackmate.{}.Median_Filtering".format(DetectionMethod)])
	Processing_Panel.add(Median_Filtering_User, Constraints)

	Pos_Y += 1

	# Channel Test
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Channel_Label = JLabel("Channel {}".format(Current_Channel))
	Channel_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(Channel_Label, Constraints)

	# Channel Slider
	Channel_Slider = JSlider(1, Nb_Channels, Current_Channel)
	Channel_Slider.setMajorTickSpacing(1)
	Channel_Slider.setPaintTicks(True)
	Channel_Slider.setPaintLabels(True)

	class Channel_Slider_Listener(ChangeListener):
		def stateChanged(self, event):
			Value = Channel_Slider.getValue()
			Channel_Label.setText("Channel {}".format(Value))

	Channel_Slider.addChangeListener(Channel_Slider_Listener())
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 3
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Processing_Panel.add(Channel_Slider, Constraints)

	# Test Processing
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.SOUTHWEST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Test Processing"
	Test_Processing_User = JCheckBox(Label)
	Test_Processing_User.setFont(Font("Arial", Font.BOLD, 12))
	Test_Processing_User.setSelected(Test_Processing)
	Processing_Panel.add(Test_Processing_User, Constraints)

	Pos_Y += 1

	# Pre Dectection Results Label
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Nb Detected Spots"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)


	Spacer_Str = " "
	Spacer = str(Spacer_Str * 13) # The Spacer_Str is repeated 13 times so the values fit under each Channel. Might need improvement because nChannels... HERE
	Nb_Detected_Spot_File_String = Spacer.join(map(str, Nb_Detected_Spot_File))
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 3
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "{}".format(Nb_Detected_Spot_File_String)
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# Cancel Button
	Cancel_Button = JButton("Cancel")
	def On_Cancel(Event):
		global User_Click
		User_Click = "Cancel"
		Processing_Dialog.dispose()
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

	# Spot Quality Results
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.EAST
	Constraints.insets = Insets(2, 2, 2, 2)
	Label = "Max Quality"
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)
	Spacer = str(Spacer_Str * 8) #Might need improvement HERE because of nChannels
	Max_Quality_File_String = Spacer.join(map(str, Max_Quality_File))
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.gridx = Pos_X + 1
	Constraints.gridwidth = 3
	Label = "{}".format(Max_Quality_File_String)
	J_Label = JLabel(Label)
	J_Label.setFont(Font("Arial", Font.BOLD, 12))
	Processing_Panel.add(J_Label, Constraints)

	# OK Button
	OK_Button = JButton("OK")
	def On_OK(Event):
		global User_Click
		User_Click = "OK"
		Processing_Dialog.dispose()

	OK_Button.addActionListener(On_OK)
	OK_Button.requestFocusInWindow()
	Constraints.gridx = Pos_X + 4
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.insets = Insets(2, 2, 2, 2)
	Processing_Panel.add(OK_Button, Constraints)
	Processing_Dialog.getRootPane().setDefaultButton(OK_Button) # Preselect OK button

	# Add one DocumentListener for all text fields
	Text_Fields = [Objective_NA_User, Pixel_Width_User, Pixel_Height_User, Pixel_Depth_User, Spot_Diameter_User]
	Text_Fields.extend(Channel_WavelengthsEm_List_User)
	Numeric_Listener = Numeric_Validator_Listener(Text_Fields, Error_Label, OK_Button)
	for Field in Text_Fields:
		Field.getDocument().addDocumentListener(Numeric_Listener)

	Processing_Dialog.add(Processing_Panel)

	Processing_Dialog.pack()
	Screen_Size = Toolkit.getDefaultToolkit().getScreenSize()
	Screen_Width = Screen_Size.width
	Screen_Height = Screen_Size.height
	Processing_Dialog.setLocation(Screen_Width/2, 0)
	Processing_Dialog.setVisible(True)
	while Processing_Dialog.isVisible():
		pass

	# Collect values from the Dialog
	Objective_Mag_User = str(Objective_Mag_User.getText())
	Objective_NA_User = float(Objective_NA_User.getText())
	Objective_Immersion_User = None
	for Button in Immersion_Radio_Group.getElements():
		if Button.isSelected():
			Objective_Immersion_User = str(Button.getText())
			break

	Pixel_Width_User = float(Pixel_Width_User.getText())
	Pixel_Height_User = float(Pixel_Height_User.getText())
	Pixel_Depth_User = float(Pixel_Depth_User.getText())
	Space_Unit_User = str(Space_Unit_User.getText())
	#Bit_Depth_User = int(Bit_Depth_User.getText())

	Channel_Names_User = [str(Field.getText()) for Field in Channel_Name_List_User]
	Channel_WavelengthsEM_User = []
	for Field in Channel_WavelengthsEm_List_User:
		Channel_WavelengthsEM_User.append(int(Field.getText()))

	# Detection Method
	Detection_Method_User = None
	for Button in Detection_Group.getElements():
		if Button.isSelected():
			Detection_Method_User = str(Button.getText())
			global DetectionMethod
			DetectionMethod = Detection_Method_User.replace(" ", "")
			break
	Threshold_User = int(Threshold_Slider.getValue())
	Spot_Diameter_User = float(Spot_Diameter_User.getText())
	Test_Channel_User = int(Channel_Slider.getValue())
	Batch_Mode_User = Batch_Mode_User.isSelected()
	Save_Individual_Files_User = Save_Individual_Files_User.isSelected()
	Prolix_Mode_User = Prolix_Mode_User.isSelected()
	Subpixel_Localization_User = Subpixel_Localization_User.isSelected()
	Median_Filtering_User = Median_Filtering_User.isSelected()
	Test_Processing_User = Test_Processing_User.isSelected()

	Settings_User = {}
	if User_Click == "Cancel":
		Message = "User clicked Cancel while processing {}.".format(Image_Name)
		IJ.log(Message)
		JOptionPane.showMessageDialog(None, Message, "{} {}".format(Plugin_Name, Function_Name), JOptionPane.INFORMATION_MESSAGE)
		sys.exit(Message)
		return
	elif User_Click == "OK":
		Settings_User[Function_Name+".Objective_Mag"] = Objective_Mag_User
		Settings_User[Function_Name+".Objective_NA"] = Objective_NA_User
		Settings_User[Function_Name+".Objective_Immersion"] = Objective_Immersion_User
		Settings_User[Function_Name+".Channel_Names"] = Channel_Names_User
		Settings_User[Function_Name+".Channel_WavelengthsEM"] = Channel_WavelengthsEM_User
		Settings_User[Function_Name+".Trackmate.Detection_Method"] = Detection_Method_User
		Settings_User[Function_Name+".Trackmate.{}.Threshold_Value".format(DetectionMethod)] = Threshold_User
		Settings_User[Function_Name+".Trackmate.{}.Spot_Diameter".format(DetectionMethod)] = Spot_Diameter_User
		Settings_User[Function_Name+".Trackmate.{}.Subpixel_Localization".format(DetectionMethod)] = Subpixel_Localization_User
		Settings_User[Function_Name+".Trackmate.{}.Median_Filtering".format(DetectionMethod)] = Median_Filtering_User
		Settings_User[Function_Name+".Batch_Mode"] = Batch_Mode_User
		Settings_User[Function_Name+".Save_Individual_Files"] = Save_Individual_Files_User
		Settings_User[Function_Name+".Prolix_Mode"] = Prolix_Mode_User
		Test_Processing = Test_Processing_User
		Selected_Channel = Test_Channel_User

		if Selected_Channel != int(Current_Channel):
			imp.setC(Selected_Channel)
			imp.updateAndDraw()
			Test_Processing = True
		Save_Preferences(Settings_User)
		Batch_Message = "" # Reset Batch Message
		Dialog_Counter += 1 # Counter to ignore Metadata and use the Prefs
	return Settings_User, User_Click, Dialog_Counter, Test_Processing, Nb_Detected_Spot_File, Batch_Message

# Return a Data_File a dictionnary containing the data for all Channels for a given image
def Run_Trackmate_All_Channel(imp, Save_File): # Run on all channels.
	Image_Info = Get_Image_Info(imp)
	Image_Name = imp.getTitle()
	Prolix_Message("Processing all channels for {}...".format(Image_Name))
	Nb_Channels = imp.getNChannels()
	Current_Channel = imp.getChannel()
	Settings_Stored = Read_Preferences(Settings_Template)
	Data_File = [] # Store the dictionnaries containing the data for each Channel
	Nb_Detected_Spot_File = [] # Store the Nb Detected Spot for each Channel
	Max_Quality_File = [] # Store the Max Quality for all detected spots per Channel
	for Channel in range(1, Image_Info["Nb_Channels"] + 1):
		Data_Ch, Nb_Detected_Spot_Ch, Max_Quality_Ch = Run_Trackmate_Single_Channel(imp, Channel, Save_File, Display = False)
		Data_File.append(Data_Ch)
		Nb_Detected_Spot_File.append(Nb_Detected_Spot_Ch)
		Max_Quality_File.append(Max_Quality_Ch)
	Prolix_Message("Nb detected Spots for {} = {}".format(Image_Name, Nb_Detected_Spot_File))
	imp.setDisplayMode(IJ.COLOR)
	imp.setC(Current_Channel) # Going back to the initial Channel
	imp.updateAndDraw()
	Prolix_Message("Processing all channels for {}. Done.".format(Image_Name))
	return Data_File, Nb_Detected_Spot_File, Max_Quality_File

# Return Data_Ch a dictionnary with data for the selected Channel
def Run_Trackmate_Single_Channel(imp, Channel, Save_File, Display):
 	Image_Info = Get_Image_Info(imp)
	Image_Name = imp.getTitle()
 	Settings_Stored = Read_Preferences(Settings_Template)
 	imp.setDisplayMode(IJ.COLOR)
	imp.setC(Channel)
	imp.updateAndDraw()

	Trackmate_Model = Model()
	Trackmate_Model.setPhysicalUnits(Image_Info["Space_Unit_Std"], Image_Info["Time_Unit"])
	Trackmate_Settings = Settings(imp)

	Detector_Method = Settings_Stored[Function_Name+".Trackmate.Detection_Method"]
	Prolix_Message("Detector_Method: {}".format(Detector_Method))

	global DetectionMethod # This a Variable used in to define Detector specific keys in the settings
	DetectionMethod = Detector_Method.replace(" ", "")

	Threshold = Settings_Stored[Function_Name+".Trackmate.{}.Threshold_Value".format(DetectionMethod)]
	Median_Filtering = Settings_Stored[Function_Name+".Trackmate.{}.Median_Filtering".format(DetectionMethod)]
	Radius = Settings_Stored[Function_Name+".Trackmate.{}.Spot_Diameter".format(DetectionMethod)] / 2
	Subpixel_Localization = Settings_Stored[Function_Name+".Trackmate.{}.Subpixel_Localization".format(DetectionMethod)]


	if Detector_Method == "Dog Detector":
		Trackmate_Settings.detectorFactory = DogDetectorFactory()
	elif Detector_Method == "Log Detector":
		Trackmate_Settings.detectorFactory = LogDetectorFactory()

	Trackmate_Settings.detectorSettings = {
		"TARGET_CHANNEL": Channel,
		"THRESHOLD": Threshold,
		"DO_MEDIAN_FILTERING": Median_Filtering,
		"RADIUS": Radius,
		"DO_SUBPIXEL_LOCALIZATION": Subpixel_Localization,
		}
	Trackmate_Settings.trackerFactory = SparseLAPTrackerFactory()
	Trackmate_Settings.trackerSettings = Trackmate_Settings.trackerFactory.getDefaultSettings()
	Trackmate_Settings.addAllAnalyzers()

	Trackmate_Workflow = TrackMate(Trackmate_Model, Trackmate_Settings)
	Trackmate_Input = Trackmate_Workflow.checkInput()
	Trackmate_Result = Trackmate_Workflow.process()

	if not Trackmate_Input:
		Message = "Trackmate invalid input for {} Channel = {}".format(Image_Name, Channel)
		IJ.log(Message)
		Message = "Detector {}.".format(Detector_Method)
		IJ.log(Message)
		IJ.log("Trackmate detector Settings {}.".format(Trackmate_Settings.detectorSettings))
		Data_Ch = None
		Nb_Detected_Spot_Ch = 0
		Max_Quality_Ch = 10
	else:
		Trackmate_Result = Trackmate_Workflow.process()
		if not Trackmate_Result:
			Message = "Trackmate detection failed for {} at Channel = {}.".format(Image_Name, Channel)
			IJ.log(Message)
			Data_Ch = None
			Nb_Detected_Spot_Ch = 0
			Max_Quality_Ch = 10
		else:
			Prolix_Message("Detection successful for {}. Rendering detection...".format(Image_Name))
			Selection_Model = SelectionModel(Trackmate_Model)
			Display_Settings = DisplaySettingsIO.readUserDefault()
			Display_Settings.setSpotDisplayRadius(0.9)
			Display_Settings.setSpotDisplayedAsRoi(True)
			Display_Settings.setSpotShowName(True)
			Display_Settings.setSpotTransparencyAlpha(0.7)
			Display_Settings.setSpotFilled(True)
			Displayer = HyperStackDisplayer(Trackmate_Model, Selection_Model, imp, Display_Settings)
			if Display:
				Displayer.render()
				Displayer.refresh()
			Nb_Detected_Spot_Ch = int(Trackmate_Model.getSpots().getNSpots(False)) # False to get all spots
			Prolix_Message("Nb of Detected Spot {} for {} at Channel {}".format(Nb_Detected_Spot_Ch, Image_Name, Channel))
			Max_Quality_Ch_All_Spots = []
			for Spot in Trackmate_Model.getSpots().iterable(False):
				Max_Quality_Ch_All_Spots.append(int(Spot.getFeature("QUALITY")))
			Max_Quality_Ch = max(Max_Quality_Ch_All_Spots)
			Prolix_Message("Spot Quality: {} for {} at Channel {}".format(Max_Quality_Ch_All_Spots, Image_Name, Channel))

			Data_Ch = {
    "Filename": [], "Channel_Nb": [], "Objective_Mag": [], "Objective_NA": [], "Objective_Immersion": [],
    "Refractive_Index": [], "Detection_Method": [], "Spot_Diameter": [], "Threshold_Value": [],
    "Subpixel_Localization": [], "Median_Filtering": [], "Batch_Mode": [], "Save_Individual_Files": [],
    "Prolix_Mode": [], "Width_Pix": [], "Height_Pix": [], "Bit_Depth": [], "Pixel_Width": [], "Pixel_Height": [],
    "Pixel_Depth": [], "Space_Unit": [], "Space_Unit_Std": [], "Time_Unit": [], "Calibration_Status": [],
    "Nb_Detected_Spots": [], "Spot_ID": [], "Spot_Quality": [], "Spot_Pos_X": [], "Spot_Pos_Y": [],
    "Spot_Pos_Z": [], "Spot_Pos_T": [], "Spot_Frame": [], "Spot_Radius": [], "Spot_Visibility": [],
    "Channel_Name": [], "Channel_Wavelength_EM": []
}
			if Nb_Detected_Spot_Ch > 0:
			# Initialize an empty dictionary with keys that will hold lists as values
				for Spot in Trackmate_Model.getSpots().iterable(False):
					Prolix_Message("Tracking successful for " + str(Image_Name) + ". Storing results...")
					# Append the values to the respective lists
					Data_Ch["Filename"].append(Image_Info["Filename"])
					Data_Ch["Channel_Nb"].append(Channel)
					Data_Ch["Objective_Mag"].append(Settings_Stored[Function_Name + ".Objective_Mag"])
					Data_Ch["Objective_NA"].append("%.1f" % Settings_Stored[Function_Name + ".Objective_NA"])
					Data_Ch["Objective_Immersion"].append(Settings_Stored[Function_Name + ".Objective_Immersion"])
					Data_Ch["Refractive_Index"].append(Get_Refractive_Index(Settings_Stored[Function_Name + ".Objective_Immersion"]))
					Data_Ch["Detection_Method"].append(Settings_Stored[Function_Name + ".Trackmate.Detection_Method"])
					Data_Ch["Spot_Diameter"].append(Settings_Stored[Function_Name + ".Trackmate." + str(DetectionMethod) + ".Spot_Diameter"])
					Data_Ch["Threshold_Value"].append(Settings_Stored[Function_Name + ".Trackmate." + str(DetectionMethod) + ".Threshold_Value"])
					Data_Ch["Subpixel_Localization"].append(Settings_Stored[Function_Name + ".Trackmate." + str(DetectionMethod) + ".Subpixel_Localization"])
					Data_Ch["Median_Filtering"].append(Settings_Stored[Function_Name + ".Trackmate." + str(DetectionMethod) + ".Median_Filtering"])
					Data_Ch["Batch_Mode"].append(Settings_Stored[Function_Name + ".Batch_Mode"])
					Data_Ch["Save_Individual_Files"].append(Settings_Stored[Function_Name + ".Save_Individual_Files"])
					Data_Ch["Prolix_Mode"].append(Settings_Stored[Function_Name + ".Prolix_Mode"])
					Data_Ch["Width_Pix"].append(Image_Info["Width"])
					Data_Ch["Height_Pix"].append(Image_Info["Height"])
					Data_Ch["Bit_Depth"].append(Image_Info["Bit_Depth"])
					Data_Ch["Pixel_Width"].append(Image_Info["Pixel_Width"])
					Data_Ch["Pixel_Height"].append(Image_Info["Pixel_Height"])
					Data_Ch["Pixel_Depth"].append(Image_Info["Pixel_Depth"])
					Data_Ch["Space_Unit"].append(Image_Info["Space_Unit"])
					Data_Ch["Space_Unit_Std"].append(Image_Info["Space_Unit_Std"])
					Data_Ch["Time_Unit"].append(Image_Info["Time_Unit"])
					Data_Ch["Calibration_Status"].append(Image_Info["Calibration_Status"])
					Data_Ch["Nb_Detected_Spots"].append(int(Nb_Detected_Spot_Ch))
					Data_Ch["Spot_ID"].append(str(Spot.ID()))
					Data_Ch["Spot_Quality"].append(int(Spot.getFeature("QUALITY")))
					Data_Ch["Spot_Pos_X"].append(Spot.getFeature("POSITION_X"))
					Data_Ch["Spot_Pos_Y"].append(Spot.getFeature("POSITION_Y"))
					Data_Ch["Spot_Pos_Z"].append(Spot.getFeature("POSITION_Z"))
					Data_Ch["Spot_Pos_T"].append(Spot.getFeature("POSITION_T"))
					Data_Ch["Spot_Frame"].append(Spot.getFeature("FRAME"))
					Data_Ch["Spot_Radius"].append(Spot.getFeature("RADIUS"))
					Data_Ch["Spot_Visibility"].append(Spot.getFeature("VISIBILITY"))
					if Save_File:
						Data_Ch["Channel_Name"].append(Settings_Stored[Function_Name+".Channel_Names"][Channel-1])
						Data_Ch["Channel_Wavelength_EM"].append(Settings_Stored[Function_Name+".Channel_WavelengthsEM"][Channel-1])
				if Save_File and Settings_Stored[Function_Name+".Save_Individual_Files"] and Settings_Stored[Function_Name+".Prolix_Mode"]:
					Spot_Table = AllSpotsTableView(Trackmate_Model, Selection_Model, Display_Settings, Image_Info["Filename"])
					Output_Trackmate_Spot_Data_Path = Generate_Unique_Filepath(Output_Dir, Image_Info["Basename"], "Trackmate_Spot-Data_Ch-0" + str(Channel), ".csv")
					Spot_Table.exportToCsv(Output_Trackmate_Spot_Data_Path)
			else:
				Data_Ch = None
				IJ.log("Trackmate detection failed for {} at Channel = {}. No spot detected.".format(Image_Name, Channel))
	return Data_Ch, Nb_Detected_Spot_Ch, Max_Quality_Ch


# Calculate the Nyquist Pixel Size and Nyquist Ratios
def Nyquist_Calculator(EMWavelength_Unit, Objective_NA, Refractive_Index, Pixel_Width, Pixel_Height, Pixel_Depth):
	Prolix_Message("Computing Nyquist values. EMWavelength_Unit: {}, Objective_NA: {}, Refractive_Index: {}, Pixel_Width: {}, Pixel_Height: {}, Pixel_Depth: {}".format(EMWavelength_Unit, Objective_NA, Refractive_Index, Pixel_Width, Pixel_Height, Pixel_Depth))
	Nyquist_Pixel_Size_Lateral = EMWavelength_Unit / (4 * Objective_NA)
	Theta = asin(Objective_NA / float(Refractive_Index))
	Nyquist_Pixel_Size_Axial = EMWavelength_Unit / (2 * Refractive_Index * (1-cos(Theta)))
	Nyquist_Ratio_Lateral = Pixel_Width / Nyquist_Pixel_Size_Lateral # Or Take the average of PixelWidth and Pixel Height for non square pixels
	Nyquist_Ratio_Axial = Pixel_Depth / Nyquist_Pixel_Size_Axial
	Prolix_Message("Computing Nyquist values Done. Nyquist_Pixel_Size_Lateral: {}, Nyquist_Pixel_Size_Axial: {}, Nyquist_Ratio_Lateral: {}, Nyquist_Ratio_Axial: {}".format(Nyquist_Pixel_Size_Lateral, Nyquist_Pixel_Size_Axial, Nyquist_Ratio_Lateral, Nyquist_Ratio_Axial))
	return Nyquist_Pixel_Size_Lateral, Nyquist_Pixel_Size_Axial, Nyquist_Ratio_Lateral, Nyquist_Ratio_Axial

def Euclidean_Distance(x1, y1, z1, x2, y2, z2):
	Prolix_Message("Computing Euclidedan Distances x1: {}, y1: {}, z1: {}, x2: {}, y2: {}, z2: {}".format(x1, y1, z1, x2, y2, z2))
	dxy = sqrt((x2 - x1)**2 + (y2 - y1)**2)
	dz = z2 - z1 # Oriented Distance
	d3D = sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
	Prolix_Message("Computing Euclidedan Distances dxy: {}, dz: {}, d3D: {}".format(dxy, dz, d3D))
	return dxy, dz, d3D

# Calculate the Resolution Theortical and Practical (weighted by the Nyquist Ratio if it is > 1
def Resolution_Calculator(EMWavelength_Unit, Objective_NA, Refractive_Index, Nyquist_Ratio_Lateral, Nyquist_Ratio_Axial):
	Prolix_Message("Calculating Resolution with EMWavelength_Unit: {}, Objective_NA: {}, Refractive_Index: {}, Nyquist_Ratio_Lateral: {}, Nyquist_Ratio_Axial: {}".format(EMWavelength_Unit, Objective_NA, Refractive_Index, Nyquist_Ratio_Lateral, Nyquist_Ratio_Axial))
	Resolution_Lateral_Theoretical = (0.51 * EMWavelength_Unit) / (Objective_NA) # Compute resolution based on wavelengths and NA
	# Resolution_Axial = (Refractive_Index * EMWavelengthUnit) / (Objective_NA ** 2)
	Resolution_Axial_Theoretical = (1.77 * Refractive_Index * EMWavelength_Unit) / (Objective_NA ** 2)
	# Get the Effective resolution based on the Nyquist Ratio
	if Nyquist_Ratio_Lateral > 1:
		Resolution_Lateral_Practical = Nyquist_Ratio_Lateral * Resolution_Lateral_Theoretical
	else:
		Resolution_Lateral_Practical = Resolution_Lateral_Theoretical

	if Nyquist_Ratio_Axial > 1:
		Resolution_Axial_Practical = Nyquist_Ratio_Axial * Resolution_Axial_Theoretical
	else:
		Resolution_Axial_Practical = Resolution_Axial_Theoretical
	Prolix_Message("Calculating Resolution with Resolution_Lateral_Theoretical: {}, Resolution_Axial_Theoretical: {}, Resolution_Lateral_Practical: {}, Resolution_Axial_Practical: {}".format(Resolution_Lateral_Theoretical, Resolution_Axial_Theoretical, Resolution_Lateral_Practical, Resolution_Axial_Practical))
	return Resolution_Lateral_Theoretical, Resolution_Axial_Theoretical, Resolution_Lateral_Practical, Resolution_Axial_Practical

# Calculate the xyz coordinates of a point in the Spot1 Spot2 Line depedning on t
def Line(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, t):
	x = X_Ch1 + t * (X_Ch2 - X_Ch1)
	y = Y_Ch1 + t * (Y_Ch2 - Y_Ch1)
	z = Z_Ch1 + t * (Z_Ch2 - Z_Ch1)
	return x, y, z
def Compute_Ellipse_Ratio(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, t):
	# Get the coordinates of a point on the Spot1 Spot2 line for parameter t
	x, y, z = Line(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, t)
	# Compute the Ellipse Ratio value from this new point
	Ellipse_Ratio = ((x - X_Ch1)**2 / Semi_Minor_Axis**2 +
		 (y - Y_Ch1)**2 / Semi_Minor_Axis**2 +
		 (z - Z_Ch1)**2 / Semi_Major_Axis**2)
	return Ellipse_Ratio
def Project_on_Ellipse(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, Max_Iterations, Initial_Step, Tolerance):
	t = 0 # Starting from point X1 Y1 Z1
	Step = Initial_Step # Start with an initial Step size
	for Iteration in range(Max_Iterations):
		Ellipse_Ratio = Compute_Ellipse_Ratio(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, t)
		if fabs(Ellipse_Ratio - 1.0) < Tolerance: # Close enough to 1
			# print "Found t =", t, "where Ellipse Ratio is ",Ellipse_Ratio," after ",iteration," iterations"
			Prolix_Message("Found t = {} where Ellipse Ratio = {} after {} iterations".format(t, Ellipse_Ratio, Iteration))
			X_Ref, Y_Ref, Z_Ref = Line(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, t) # Retrieve the Coordinates
			return X_Ref, Y_Ref, Z_Ref
		# Adjust Step size# The smaller the difference, the smaller the Step
		if Ellipse_Ratio > 1.0:
			Step = Step * 0.5 # Reduce Step
			t -= Step # Move backwards if Ellipse_Ratio > 1
		else:
			Step = Step * 1.5 # Increase Step
			t += Step # Move forward if Ellipse_Ratio < 1
	return None
def Channel_Alignment_Data_Processing(imp, Data_File): # Compute the Channel alignment for all pair of channels
	# Return Data_File_Processed a list
	Image_Info = Get_Image_Info(imp)
	Image_Name = imp.getTitle()
	Prolix_Message("Computing Ch Alignemnt Metrics for {}".format(Image_Name))
	Nb_Channels = imp.getNChannels()
	# Collect Microscope Settings
	Settings_Stored = Read_Preferences(Settings_Template)
	Data_Processed_File = {
			"Filename": [],
			"Objective_Mag": [], "Objective_NA": [], "Objective_Immersion": [], "Refractive_Index": [],
			"Detection_Method": [], "Spot_Diameter": [], "Threshold_Value": [], "Subpixel_Localization": [], "Median_Filtering": [],
			"Batch_Mode": [], "Save_Individual_Files": [], "Prolix_Mode": [],
			"Width_Pix": [], "Height_Pix": [], "Bit_Depth": [],	"Pixel_Width": [], "Pixel_Height": [], "Pixel_Depth": [],
			"Space_Unit": [], "Space_Unit_Std": [], "Time_Unit": [], "Calibration_Status": [],
			"Channel_Ch1": [], "Channel_Name_Ch1": [], "EMWavelength_Ch1": [],
			"Nb_Detected_Spots_Ch1": [], "Spot_ID_Ch1": [], "Spot_Quality_Ch1": [],
			"Pos_X_Ch1": [], "Pos_Y_Ch1": [], "Pos_Z_Ch1": [], "Pos_T_Ch1": [],
			"Frame_Ch1": [], "Radius_Ch1": [], "Visibility_Ch1": [],
			"Channel_Ch2": [], "Channel_Name_Ch2": [], "EMWavelength_Ch2": [],
			"Nb_Detected_Spots_Ch2": [], "Spot_ID_Ch2": [], "Spot_Quality_Ch2": [],
			"Pos_X_Ch2": [], "Pos_Y_Ch2": [], "Pos_Z_Ch2": [], "Pos_T_Ch2": [],
			"Frame_Ch2": [], "Radius_Ch2": [], "Visibility_Ch2": [],
			"Channel_Pair": [],
			"Diff_X": [], "Diff_Y": [], "Diff_Z": [],
			"Diff_X_Pix": [], "Diff_Y_Pix": [], "Diff_Z_Pix": [],
			"Distance_Lateral": [],	"Distance_Axial": [], "Distance_3D": [],
			"Conversion_Factor": [], "EMWavelength_Unit_Ch1": [], "EMWavelength_Unit_Ch2": [],
			"Nyquist_Pixel_Size_Lateral_Ch1": [], "Nyquist_Pixel_Size_Axial_Ch1": [], "Nyquist_Ratio_Lateral_Ch1": [], "Nyquist_Ratio_Axial_Ch1": [],
			"Nyquist_Pixel_Size_Lateral_Ch2": [], "Nyquist_Pixel_Size_Axial_Ch2": [], "Nyquist_Ratio_Lateral_Ch2": [], "Nyquist_Ratio_Axial_Ch2": [],
			"Resolution_Lateral_Theoretical_Ch1": [], "Resolution_Axial_Theoretical_Ch1": [], "Resolution_Lateral_Practical_Ch1": [], "Resolution_Axial_Practical_Ch1": [],
			"Resolution_Lateral_Theoretical_Ch2": [], "Resolution_Axial_Theoretical_Ch2": [], "Resolution_Lateral_Practical_Ch2": [], "Resolution_Axial_Practical_Ch2": [],
			"X_Proj": [], "Y_Proj": [], "Z_Proj": [],
			"Diff_X_Ref": [], "Diff_Y_Ref": [], "Diff_Z_Ref": [],
			"Semi_Minor_Axis": [], "Semi_Major_Axis": [],
			"Distance_Lateral_Ref": [], "Distance_Axial_Ref": [], "Distance_3D_Ref": [],
			"Colocalization_Ratio": [],
			}
	# Loop through all pair of Channels for calculating Ch Shifts
	for Ch1 in range(1, Nb_Channels+1):
		for Ch2 in range(1, Nb_Channels+1):
			Data_Ch1 = next((Data_Ch for Data_Ch in Data_File if Data_Ch["Channel_Nb"] == [Ch1]), None)
			Data_Ch2 = next((Data_Ch for Data_Ch in Data_File if Data_Ch["Channel_Nb"] == [Ch2]), None)
			if Data_Ch1 is not None and Data_Ch2 is not None and len(Data_Ch1["Channel_Nb"]) == 1 and len(Data_Ch2["Channel_Nb"]) == 1:
				# Get All parameters from Ch1 since they are the same than Channel 2
				Filename = str(Data_Ch1["Filename"][0])
				Objective_Mag = str(Data_Ch1["Objective_Mag"][0])
				Objective_NA = float(Data_Ch1["Objective_NA"][0])
				Objective_Immersion = str(Data_Ch1["Objective_Immersion"][0])
				Refractive_Index = float(Data_Ch1["Refractive_Index"][0])
				Detection_Method = str(Data_Ch1["Detection_Method"][0])
				Spot_Diameter = float(Data_Ch1["Spot_Diameter"][0])
				Threshold_Value = float(Data_Ch1["Threshold_Value"][0])
				Subpixel_Localization = bool(Data_Ch1["Subpixel_Localization"][0])
				Median_Filtering = bool(Data_Ch1["Median_Filtering"][0])
				Batch_Mode = bool(Data_Ch1["Batch_Mode"][0])
				Save_Individual_Files = bool(Data_Ch1["Save_Individual_Files"][0])
				Prolix_Mode = bool(Data_Ch1["Prolix_Mode"][0])
				Width_Pix = int(Data_Ch1["Width_Pix"][0])
				Height_Pix = int(Data_Ch1["Height_Pix"][0])
				Bit_Depth = int(Data_Ch1["Bit_Depth"][0])
				Pixel_Width = float(Data_Ch1["Pixel_Width"][0])
				Pixel_Height = float(Data_Ch1["Pixel_Height"][0])
				Pixel_Depth = float(Data_Ch1["Pixel_Depth"][0])
				Space_Unit = str(Data_Ch1["Space_Unit"][0])
				Space_Unit_Std = str(Data_Ch1["Space_Unit_Std"][0])
				Time_Unit = str(Data_Ch1["Time_Unit"][0])
				Calibration_Status = bool(Data_Ch1["Calibration_Status"][0])
				# Get Channel Specific values
				Channel_Ch1 = int(Data_Ch1["Channel_Nb"][0])
				Channel_Name_Ch1 = str(Data_Ch1["Channel_Name"][0])
				EMWavelength_Ch1 = float(Data_Ch1["Channel_Wavelength_EM"][0])
				Nb_Detected_Spots_Ch1 = int(Data_Ch1["Nb_Detected_Spots"][0])
				Spot_ID_Ch1 = int(Data_Ch1["Spot_ID"][0])
				Spot_Quality_Ch1 = float(Data_Ch1["Spot_Quality"][0])
				X_Ch1 = float(Data_Ch1["Spot_Pos_X"][0])
				Y_Ch1 = float(Data_Ch1["Spot_Pos_Y"][0])
				Z_Ch1 = float(Data_Ch1["Spot_Pos_Z"][0])
				T_Ch1 = float(Data_Ch1["Spot_Pos_T"][0])
				Frame_Ch1 = int(Data_Ch1["Spot_Frame"][0])
				Radius_Ch1 = float(Data_Ch1["Spot_Radius"][0])
				Visibility_Ch1 = bool(Data_Ch1["Spot_Visibility"][0])
				Channel_Ch2 = int(Data_Ch2["Channel_Nb"][0])
				Channel_Name_Ch2 = str(Data_Ch2["Channel_Name"][0])
				EMWavelength_Ch2 = float(Data_Ch2["Channel_Wavelength_EM"][0])
				Nb_Detected_Spots_Ch2 = int(Data_Ch2["Nb_Detected_Spots"][0])
				Spot_ID_Ch2 = int(Data_Ch2["Spot_ID"][0])
				Spot_Quality_Ch2 = float(Data_Ch2["Spot_Quality"][0])
				X_Ch2 = float(Data_Ch2["Spot_Pos_X"][0])
				Y_Ch2 = float(Data_Ch2["Spot_Pos_Y"][0])
				Z_Ch2 = float(Data_Ch2["Spot_Pos_Z"][0])
				T_Ch2 = float(Data_Ch2["Spot_Pos_T"][0])
				Frame_Ch2 = int(Data_Ch2["Spot_Frame"][0])
				Radius_Ch2 = float(Data_Ch2["Spot_Radius"][0])
				Visibility_Ch2 = bool(Data_Ch2["Spot_Visibility"][0])
				Channel_Pair = "{} x {}".format(Channel_Name_Ch1, Channel_Name_Ch2)
				# Compute differences
				Diff_X = float(X_Ch2 - X_Ch1)
				Diff_Y = float(Y_Ch2 - Y_Ch1)
				Diff_Z = float(Z_Ch2 - Z_Ch1)
				Diff_X_Pix = float(Diff_X / Pixel_Width)
				Diff_Y_Pix = float(Diff_Y / Pixel_Height)
				Diff_Z_Pix = float(Diff_Z / Pixel_Depth)
				# Compute distances
				Distance_Lateral, Distance_Axial, Distance_3D = Euclidean_Distance(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2)
				Conversion_Factors = { # Space Unit Std: Conversion factors
				"{}m".format(Unicode_Micron_Symbol): 1000,	# 1 nm = 0.001 m
				"nm": 1,		# 1 nm = 1 nm
				"mm": 1000000,	 # 1 nm = 0.000001 mm
				"cm": 10000000,	 # 1 nm = 0.0000001 cm
				"m": 1000000000,	 # 1 nm = 0.0000000001 m
				"in": 2540000, # 1 nm = 0.0000000393701 in (approx.)
				"pixels": 1,	# Assuming pixels is the default unit and conversion factor for pixels is 1 (since no physical measurement)
				}
				Conversion_Factor = float(Conversion_Factors[Space_Unit_Std])
				EMWavelength_Unit_Ch1 = EMWavelength_Ch1 / Conversion_Factor
				EMWavelength_Unit_Ch2 = EMWavelength_Ch2 / Conversion_Factor
				Nyquist_Pixel_Size_Lateral_Ch1, Nyquist_Pixel_Size_Axial_Ch1, Nyquist_Ratio_Lateral_Ch1, Nyquist_Ratio_Axial_Ch1 = Nyquist_Calculator(EMWavelength_Unit_Ch1, Objective_NA, Refractive_Index, Pixel_Width, Pixel_Height, Pixel_Depth)
				Nyquist_Pixel_Size_Lateral_Ch2, Nyquist_Pixel_Size_Axial_Ch2, Nyquist_Ratio_Lateral_Ch2, Nyquist_Ratio_Axial_Ch2 = Nyquist_Calculator(EMWavelength_Unit_Ch2, Objective_NA, Refractive_Index, Pixel_Width, Pixel_Height, Pixel_Depth)
				Resolution_Lateral_Theoretical_Ch1, Resolution_Axial_Theoretical_Ch1, Resolution_Lateral_Practical_Ch1, Resolution_Axial_Practical_Ch1 = Resolution_Calculator(EMWavelength_Unit_Ch1, Objective_NA, Refractive_Index, Nyquist_Ratio_Lateral_Ch1, Nyquist_Ratio_Axial_Ch1)
				Resolution_Lateral_Theoretical_Ch2, Resolution_Axial_Theoretical_Ch2, Resolution_Lateral_Practical_Ch2, Resolution_Axial_Practical_Ch2 = Resolution_Calculator(EMWavelength_Unit_Ch2, Objective_NA, Refractive_Index, Nyquist_Ratio_Lateral_Ch2, Nyquist_Ratio_Axial_Ch2)
				# Resolution is in nm must convert it to match the distance values
				Semi_Minor_Axis = (max(Resolution_Lateral_Practical_Ch1, Resolution_Lateral_Practical_Ch2))/2 # Using the largest number to calculate the Ratios
				Semi_Major_Axis = (max(Resolution_Axial_Practical_Ch1, Resolution_Axial_Practical_Ch2))/2 # Using the largest number to calculate the Ratios
				# If spots are not already colocalized project the Spot1->Spot2 vector to the Ellipse
				if X_Ch1 != X_Ch2 and Y_Ch1 != Y_Ch2 and Z_Ch1 != Z_Ch2:
					X_Proj, Y_Proj, Z_Proj = Project_on_Ellipse(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, Max_Iterations = 1000, Initial_Step = 10, Tolerance = 1e-12)
				else:
					X_Proj = X_Ch1
					Y_Proj = Y_Ch1
					Z_Proj = Z_Ch1
				Diff_X_Ref = X_Proj - X_Ch1
				Diff_Y_Ref = Y_Proj - Y_Ch1
				Diff_Z_Ref = Z_Proj - Z_Ch1
				Distance_Lateral_Ref, Distance_Axial_Ref, Distance_3D_Ref = Euclidean_Distance(X_Ch1, Y_Ch1, Z_Ch1, X_Proj, Y_Proj, Z_Proj)
				if Distance_3D_Ref == 0:
					Colocalization_Ratio = 0
				else:
					Colocalization_Ratio = Distance_3D / Distance_3D_Ref
				Data_Processed_File["Filename"].append(Filename)
				Data_Processed_File["Objective_Mag"].append(Objective_Mag)
				Data_Processed_File["Objective_NA"].append(Objective_NA)
				Data_Processed_File["Objective_Immersion"].append(Objective_Immersion)
				Data_Processed_File["Refractive_Index"].append(Refractive_Index)
				Data_Processed_File["Detection_Method"].append(Detection_Method)
				Data_Processed_File["Spot_Diameter"].append(Spot_Diameter)
				Data_Processed_File["Threshold_Value"].append(Threshold_Value)
				Data_Processed_File["Subpixel_Localization"].append(Subpixel_Localization)
				Data_Processed_File["Median_Filtering"].append(Median_Filtering)
				Data_Processed_File["Batch_Mode"].append(Batch_Mode)
				Data_Processed_File["Save_Individual_Files"].append(Save_Individual_Files)
				Data_Processed_File["Prolix_Mode"].append(Prolix_Mode)
				Data_Processed_File["Width_Pix"].append(Width_Pix)
				Data_Processed_File["Height_Pix"].append(Height_Pix)
				Data_Processed_File["Bit_Depth"].append(Bit_Depth)
				Data_Processed_File["Pixel_Width"].append(Pixel_Width)
				Data_Processed_File["Pixel_Height"].append(Pixel_Height)
				Data_Processed_File["Pixel_Depth"].append(Pixel_Depth)
				Data_Processed_File["Space_Unit"].append(Space_Unit)
				Data_Processed_File["Space_Unit_Std"].append(Space_Unit_Std)
				Data_Processed_File["Time_Unit"].append(Time_Unit)
				Data_Processed_File["Calibration_Status"].append(Calibration_Status)
				Data_Processed_File["Channel_Ch1"].append(Channel_Ch1)
				Data_Processed_File["Channel_Name_Ch1"].append(Channel_Name_Ch1)
				Data_Processed_File["EMWavelength_Ch1"].append(EMWavelength_Ch1)
				Data_Processed_File["Nb_Detected_Spots_Ch1"].append(Nb_Detected_Spots_Ch1)
				Data_Processed_File["Spot_ID_Ch1"].append(Spot_ID_Ch1)
				Data_Processed_File["Spot_Quality_Ch1"].append(Spot_Quality_Ch1)
				Data_Processed_File["Pos_X_Ch1"].append(float("%.3f" % X_Ch1))
				Data_Processed_File["Pos_Y_Ch1"].append(float("%.3f" % Y_Ch1))
				Data_Processed_File["Pos_Z_Ch1"].append(float("%.3f" % Z_Ch1))
				Data_Processed_File["Pos_T_Ch1"].append(float("%.3f" % T_Ch1))
				Data_Processed_File["Frame_Ch1"].append(Frame_Ch1)
				Data_Processed_File["Radius_Ch1"].append(Radius_Ch1)
				Data_Processed_File["Visibility_Ch1"].append(Visibility_Ch1)
				Data_Processed_File["Channel_Ch2"].append(Channel_Ch2)
				Data_Processed_File["Channel_Name_Ch2"].append(Channel_Name_Ch2)
				Data_Processed_File["EMWavelength_Ch2"].append(EMWavelength_Ch2)
				Data_Processed_File["Nb_Detected_Spots_Ch2"].append(Nb_Detected_Spots_Ch2)
				Data_Processed_File["Spot_ID_Ch2"].append(Spot_ID_Ch2)
				Data_Processed_File["Spot_Quality_Ch2"].append(Spot_Quality_Ch2)
				Data_Processed_File["Pos_X_Ch2"].append(float("%.3f" % X_Ch2))
				Data_Processed_File["Pos_Y_Ch2"].append(float("%.3f" % Y_Ch2))
				Data_Processed_File["Pos_Z_Ch2"].append(float("%.3f" % Z_Ch2))
				Data_Processed_File["Pos_T_Ch2"].append(float("%.3f" % T_Ch2))
				Data_Processed_File["Frame_Ch2"].append(Frame_Ch2)
				Data_Processed_File["Radius_Ch2"].append(Radius_Ch2)
				Data_Processed_File["Visibility_Ch2"].append(Visibility_Ch2)
				Data_Processed_File["Channel_Pair"].append(Channel_Pair)
				Data_Processed_File["Diff_X"].append(float("%.3f" % Diff_X))
				Data_Processed_File["Diff_Y"].append(float("%.3f" % Diff_Y))
				Data_Processed_File["Diff_Z"].append(float("%.3f" % Diff_Z))
				Data_Processed_File["Diff_X_Pix"].append(float("%.1f" % Diff_X_Pix))
				Data_Processed_File["Diff_Y_Pix"].append(float("%.1f" % Diff_Y_Pix))
				Data_Processed_File["Diff_Z_Pix"].append(float("%.1f" % Diff_Z_Pix))
				Data_Processed_File["Distance_Lateral"].append(float("%.3f" % Distance_Lateral))
				Data_Processed_File["Distance_Axial"].append(float("%.3f" % Distance_Axial))
				Data_Processed_File["Distance_3D"].append(float("%.3f" % Distance_3D))
				Data_Processed_File["Conversion_Factor"].append(Conversion_Factor)
				Data_Processed_File["EMWavelength_Unit_Ch1"].append(EMWavelength_Unit_Ch1)
				Data_Processed_File["EMWavelength_Unit_Ch2"].append(EMWavelength_Unit_Ch2)
				Data_Processed_File["Nyquist_Pixel_Size_Lateral_Ch1"].append(float("%.3f" % Nyquist_Pixel_Size_Lateral_Ch1))
				Data_Processed_File["Nyquist_Pixel_Size_Axial_Ch1"].append(float("%.3f" % Nyquist_Pixel_Size_Axial_Ch1))
				Data_Processed_File["Nyquist_Ratio_Lateral_Ch1"].append(float("%.1f" % Nyquist_Ratio_Lateral_Ch1))
				Data_Processed_File["Nyquist_Ratio_Axial_Ch1"].append(float("%.1f" % Nyquist_Ratio_Axial_Ch1))
				Data_Processed_File["Nyquist_Pixel_Size_Lateral_Ch2"].append(float("%.3f" % Nyquist_Pixel_Size_Lateral_Ch2))
				Data_Processed_File["Nyquist_Pixel_Size_Axial_Ch2"].append(float("%.3f" % Nyquist_Pixel_Size_Axial_Ch2))
				Data_Processed_File["Nyquist_Ratio_Lateral_Ch2"].append(float("%.1f" % Nyquist_Ratio_Lateral_Ch2))
				Data_Processed_File["Nyquist_Ratio_Axial_Ch2"].append(float("%.1f" % Nyquist_Ratio_Axial_Ch2))
				Data_Processed_File["Resolution_Lateral_Theoretical_Ch1"].append(float("%.3f" % Resolution_Lateral_Theoretical_Ch1))
				Data_Processed_File["Resolution_Axial_Theoretical_Ch1"].append(float("%.3f" % Resolution_Axial_Theoretical_Ch1))
				Data_Processed_File["Resolution_Lateral_Practical_Ch1"].append(float("%.3f" % Resolution_Lateral_Practical_Ch1))
				Data_Processed_File["Resolution_Axial_Practical_Ch1"].append(float("%.3f" % Resolution_Axial_Practical_Ch1))
				Data_Processed_File["Resolution_Lateral_Theoretical_Ch2"].append(float("%.3f" % Resolution_Lateral_Theoretical_Ch2))
				Data_Processed_File["Resolution_Axial_Theoretical_Ch2"].append(float("%.3f" % Resolution_Axial_Theoretical_Ch2))
				Data_Processed_File["Resolution_Lateral_Practical_Ch2"].append(float("%.3f" % Resolution_Lateral_Practical_Ch2))
				Data_Processed_File["Resolution_Axial_Practical_Ch2"].append(float("%.3f" % Resolution_Axial_Practical_Ch2))
				Data_Processed_File["X_Proj"].append(float("%.3f" % X_Proj))
				Data_Processed_File["Y_Proj"].append(float("%.3f" % Y_Proj))
				Data_Processed_File["Z_Proj"].append(float("%.3f" % Z_Proj))
				Data_Processed_File["Diff_X_Ref"].append(float("%.3f" % Diff_X_Ref))
				Data_Processed_File["Diff_Y_Ref"].append(float("%.3f" % Diff_Y_Ref))
				Data_Processed_File["Diff_Z_Ref"].append(float("%.3f" % Diff_Z_Ref))
				Data_Processed_File["Semi_Minor_Axis"].append(float("%.3f" % Semi_Minor_Axis))
				Data_Processed_File["Semi_Major_Axis"].append(float("%.3f" % Semi_Major_Axis))
				Data_Processed_File["Distance_Lateral_Ref"].append(float("%.3f" % Distance_Lateral_Ref))
				Data_Processed_File["Distance_Axial_Ref"].append(float("%.3f" % Distance_Axial_Ref))
				Data_Processed_File["Distance_3D_Ref"].append(float("%.3f" % Distance_3D_Ref))
				Data_Processed_File["Colocalization_Ratio"].append(float("%.1f" % Colocalization_Ratio))
		global Data_Processed_File_Ordered_Keys
		global Data_Processed_File_Header
		Data_Processed_File_Ordered_Keys = [
			"Filename",
			"Objective_Mag", "Objective_NA", "Objective_Immersion", "Refractive_Index",
			"Detection_Method", "Spot_Diameter", "Threshold_Value", "Subpixel_Localization", "Median_Filtering",
			"Batch_Mode", "Save_Individual_Files", "Prolix_Mode",
			"Width_Pix", "Height_Pix", "Bit_Depth",	"Pixel_Width", "Pixel_Height", "Pixel_Depth",
			"Space_Unit", "Space_Unit_Std", "Time_Unit", "Calibration_Status",
			"Channel_Ch1", "Channel_Name_Ch1", "EMWavelength_Ch1",
			"Nb_Detected_Spots_Ch1", "Spot_ID_Ch1", "Spot_Quality_Ch1",
			"Pos_X_Ch1", "Pos_Y_Ch1", "Pos_Z_Ch1", "Pos_T_Ch1",
			"Frame_Ch1", "Radius_Ch1", "Visibility_Ch1",
			"Channel_Ch2", "Channel_Name_Ch2", "EMWavelength_Ch2",
			"Nb_Detected_Spots_Ch2", "Spot_ID_Ch2", "Spot_Quality_Ch2",
			"Pos_X_Ch2", "Pos_Y_Ch2", "Pos_Z_Ch2", "Pos_T_Ch2",
			"Frame_Ch2", "Radius_Ch2", "Visibility_Ch2",
			"Channel_Pair",
			"Diff_X", "Diff_Y", "Diff_Z",
			"Diff_X_Pix", "Diff_Y_Pix", "Diff_Z_Pix",
			"Distance_Lateral",	"Distance_Axial", "Distance_3D",
			"Conversion_Factor", "EMWavelength_Unit_Ch1", "EMWavelength_Unit_Ch2",
			"Nyquist_Pixel_Size_Lateral_Ch1", "Nyquist_Pixel_Size_Axial_Ch1", "Nyquist_Ratio_Lateral_Ch1", "Nyquist_Ratio_Axial_Ch1",
			"Nyquist_Pixel_Size_Lateral_Ch2", "Nyquist_Pixel_Size_Axial_Ch2", "Nyquist_Ratio_Lateral_Ch2", "Nyquist_Ratio_Axial_Ch2",
			"Resolution_Lateral_Theoretical_Ch1", "Resolution_Axial_Theoretical_Ch1", "Resolution_Lateral_Practical_Ch1", "Resolution_Axial_Practical_Ch1",
			"Resolution_Lateral_Theoretical_Ch2", "Resolution_Axial_Theoretical_Ch2", "Resolution_Lateral_Practical_Ch2", "Resolution_Axial_Practical_Ch2",
			"X_Proj", "Y_Proj", "Z_Proj",
			"Diff_X_Ref", "Diff_Y_Ref", "Diff_Z_Ref",
			"Semi_Minor_Axis", "Semi_Major_Axis",
			"Distance_Lateral_Ref", "Distance_Axial_Ref", "Distance_3D_Ref",
			"Colocalization_Ratio",
			]
		Data_Processed_File_Header = [
		"Filename",
		"Objective Magnification", 		"Objective NA", "Objective Immersion Media", "Immersion Media Refractive Index",
		"Detection Method", "Spot Diameter ({})".format(Space_Unit_Std), "Threshold Value", "Subpixel Localization", "Median Filtering",
		"Batch Mode", "Save Individual Files", "Prolix Mode",
		"Image Width (pixels)", "Image Height (pixels)", "Image Bit Depth", "Pixel Width ({}/px)".format(Space_Unit_Std), "Pixel Height ({}/px)".format(Space_Unit_Std), "Pixel Depth ({}/px)".format(Space_Unit_Std),
		"Space Unit", "Space Unit Standard", " Time Unit", "Calibration Status",
		"Channel 1", "Name Channel 1", "EM Wavelength Channel 1 (nm)",
		"Nb Detected Spots Ch1", "Spot ID Ch1", "Spot Quality Ch1",
		"X Ch1 ({})".format(Space_Unit_Std), "Y Ch1 ({})".format(Space_Unit_Std),"Z Ch1 ({})".format(Space_Unit_Std), "T Ch1 ({})".format(Time_Unit),
		"Frame Ch1", "Radius Ch1 ({})".format(Space_Unit_Std), "Visibility Ch1",
		"Channel 2", "Name Channel 2", "EM Wavelength Channel 2 (nm)",
		"Nb Detected Spots Ch2", "Spot ID Ch2", "Spot Quality Ch2",
		"X Ch2 ({})".format(Space_Unit_Std), "Y Ch2 ({})".format(Space_Unit_Std), "Z Ch2 ({})".format(Space_Unit_Std), "T Ch2 ({})".format(Time_Unit),
		"Frame Ch2", "Radius Ch2", "Visibility Ch2",
		"Channel Pair",
		"X Shift ({})".format(Space_Unit_Std), "Y Shift ({})".format(Space_Unit_Std), "Z Shift ({})".format(Space_Unit_Std),
		"X Shift (pixels)", "Y Shift (pixels)", "Z Shift (pixels)",
		"Distance Lateral ({})".format(Space_Unit_Std), "Distance Axial ({})".format(Space_Unit_Std), "Distance 3D ({})".format(Space_Unit_Std),
		"Conversion Factor", "EMWavelength Unit Ch1 ({})".format(Space_Unit_Std), "EMWavelength Unit Ch2 ({})".format(Space_Unit_Std),
		"Nyquist Pixel Size Lateral Ch1 ({})".format(Space_Unit_Std), "Nyquist Pixel Size Axial Ch1 ({})".format(Space_Unit_Std), "Nyquist Ratio Lateral Ch1", "Nyquist Ratio Axial Ch1",
		"Nyquist Pixel Size Lateral Ch2 ({})".format(Space_Unit_Std), "Nyquist Pixel Size Axial Ch2 ({})".format(Space_Unit_Std), "Nyquist Ratio Lateral Ch2", "Nyquist Ratio Axial Ch2",
		"Resolution Lateral Theoretical Ch1 ({})".format(Space_Unit_Std), "Resolution Axial Theoretical Ch1 ({})".format(Space_Unit_Std), "Resolution Lateral Practical Ch1 ({})".format(Space_Unit_Std), "Resolution Axial Practical Ch1 ({})".format(Space_Unit_Std),
		"Resolution Lateral Theoretical Ch2 ({})".format(Space_Unit_Std), "Resolution Axial Theoretical Ch2 ({})".format(Space_Unit_Std), "Resolution Lateral Practical Ch2 ({})".format(Space_Unit_Std), "Resolution Axial Practical Ch2 ({})".format(Space_Unit_Std),
		"X Ref ({})".format(Space_Unit_Std), "Y Ref ({})".format(Space_Unit_Std), "Z Ref ({})".format(Space_Unit_Std),
		"X Ref Shift ({})".format(Space_Unit_Std), "Y Ref Shift ({})".format(Space_Unit_Std), "Z Ref Shift ({})".format(Space_Unit_Std),
		"Semi Minor Axis ({})".format(Space_Unit_Std), "Semi Major Axis ({})".format(Space_Unit_Std),
		"Distance Lateral Ref ({})".format(Space_Unit_Std), "Distance Axial Ref ({})".format(Space_Unit_Std), "Distance 3D Ref ({})".format(Space_Unit_Std),
		"Colocalization Ratio",
		]
		Settings_Stored = Read_Preferences(Settings_Template)
	if Settings_Stored[Function_Name+".Save_Individual_Files"]:
		Data_Processed_Ouput_Path = Generate_Unique_Filepath(Output_Dir, Image_Info["Basename"], "Channel-Alignment_All-Data", ".csv")
		CSV_File = open(Data_Processed_Ouput_Path, "w")
		CSV_Writer = csv.writer(CSV_File, delimiter = ",", lineterminator = "\n")
		CSV_Writer.writerow(Data_Processed_File_Header)
		for i in range(len(Data_Processed_File["Filename"])):
			Row = []
			for Key in Data_Processed_File_Ordered_Keys:
				Value = Data_Processed_File[Key][i]
				Row.append(Value)
			CSV_Writer.writerow(Row)
		CSV_File.close()
	return Data_Processed_File
# We are done with functions... Getting to work now...
Initialize_Preferences(Settings_Template, Reset_Preferences)
Image_List = Get_Images()
if not os.path.exists(Output_Dir): os.makedirs(Output_Dir)
Data_All_Files, Data_Processed_All_Files, Processed_Image_List = Process_Image_List(Image_List)
Output_Data_Processed_CSV_Path = Generate_Unique_Filepath(Output_Dir, "{}_All-Data".format(Function_Name), "Merged", ".csv")
Output_Data_Processed_File = open(Output_Data_Processed_CSV_Path, "w")
CSV_Writer = csv.writer(Output_Data_Processed_File, delimiter = ",", lineterminator = "\n")
CSV_Writer.writerow(Data_Processed_File_Header)
for Data_Processed_File in Data_Processed_All_Files:
	for i in range(len(Data_Processed_File["Filename"])):
		Row = []
		for Key in Data_Processed_File_Ordered_Keys:
					Value = Data_Processed_File[Key][i]
					Row.append(Value)
		CSV_Writer.writerow(Row)
Output_Data_Processed_File.close()
Output_Essential_Data_Processed_CSV_Path = Generate_Unique_Filepath(Output_Dir, "{}_Essential-Data".format(Function_Name), "Merged", ".csv")
Output_Data_Processed_File = open(Output_Data_Processed_CSV_Path, "r")
Reader = csv.reader(Output_Data_Processed_File, delimiter = ",", lineterminator = "\n")
Header = next(Reader)
Filename_Column_Index = 0
Selected_Columns = [0, 1, 23, 24, 36, 37, 53, 54, 55, 89] # Add Index to have more columns saved in the Essential Data
Selected_Header = [Header[i] for i in Selected_Columns]
Max_Filename_Variables = 0
Processed_Rows = []
for Row in Reader:
	Filename = Row[Filename_Column_Index]
	Filename_Variables = Filename.split("_")
	if "." in Filename_Variables[-1]:
		Filename_Variables[-1] = os.path.splitext(Filename_Variables[-1])[0]
	Max_Filename_Variables = max(Max_Filename_Variables, len(Filename_Variables))
	Selected_Row = [Row[i] for i in Selected_Columns]
	Processed_Rows.append((Selected_Row, Filename_Variables))
Filename_Variable_Columns = ["Filename-Variable-{0:03d}".format(i + 1) for i in range(Max_Filename_Variables)]
Filename_Output_Index = Selected_Columns.index(Filename_Column_Index)
Updated_Header = (
	Selected_Header[:Filename_Output_Index + 1] +
	Filename_Variable_Columns +
	Selected_Header[Filename_Output_Index + 1:]
)
Output_Essential_Data_Processed_File = open(Output_Essential_Data_Processed_CSV_Path, "w")
CSV_Writer = csv.writer(Output_Essential_Data_Processed_File, delimiter = ",", lineterminator = "\n")
CSV_Writer.writerow(Updated_Header)
for Selected_Row, Filename_Variables in Processed_Rows:
	Filename_Variables_Padded = Filename_Variables + [""] * (Max_Filename_Variables - len(Filename_Variables))
	Final_Row = (
		Selected_Row[:Filename_Output_Index + 1] +
		Filename_Variables_Padded +
		Selected_Row[Filename_Output_Index + 1:]
	)
	CSV_Writer.writerow(Final_Row)
Output_Essential_Data_Processed_File.close()
Output_Data_Processed_File.close()
Message = "{} {} successful.\n{} images have been processed.\n Files are saved in {}".format(Plugin_Name, Function_Name, len(Processed_Image_List), Output_Dir)
IJ.log(Message)
JOptionPane.showMessageDialog(None, Message, "{} {}".format(Plugin_Name, Function_Name), JOptionPane.INFORMATION_MESSAGE)
java.lang.System.gc() # Cleaning up my mess ;-)