import os
import sys
import csv
import glob
import math
from math import sqrt
from ij import IJ, WindowManager, Prefs
from ij.gui import GenericDialog, NonBlockingGenericDialog
from ij.IJ import micronSymbol
from java.io import File
from javax.swing import JOptionPane, JFileChooser
from fiji.util.gui import GenericDialogPlus
from fiji.plugin.trackmate import Model, Settings, TrackMate, SelectionModel, Logger
from fiji.plugin.trackmate.detection import DogDetectorFactory, LogDetectorFactory
from fiji.plugin.trackmate.tracking.jaqaman import SparseLAPTrackerFactory
from fiji.plugin.trackmate.features import FeatureFilter
from fiji.plugin.trackmate.features.track import TrackIndexAnalyzer
from fiji.plugin.trackmate.gui.displaysettings import DisplaySettingsIO
from fiji.plugin.trackmate.visualization.table import TrackTableView, AllSpotsTableView
from fiji.plugin.trackmate.visualization.hyperstack import HyperStackDisplayer
from loci.plugins import BF
from loci.plugins.in import ImporterOptions
from loci.formats import MetadataTools, ImageReader





# Constants
ResetPreferences=True
UserDesktopPath = os.path.join(os.path.expanduser("~"), "Desktop") # Used for Saving the Output DIrectory and as a default for selecting an input directory
Output_Dir=os.path.join(UserDesktopPath, "Output") # Where all files are saved

Image_Valid_Extension = ('.tif', '.tiff', '.jpg', '.jpeg', '.png', '.czi', '.nd2', '.lif', '.lsm', '.ome.tif', '.ome.tiff') # Supported image file extensions. When a folder is selected only images with this extension are selected

Acceptable_SpaceUnits = {
	# Provide possilble space units and an Standard correspondance required for later converting Resolution in nm into the same unit than the measured distance
	"micron": ""+micronSymbol +"m", ""+micronSymbol +"m": ""+micronSymbol +"m", "microns": ""+micronSymbol +"m", "um": ""+micronSymbol +"m", "u": ""+micronSymbol +"m",
	"nm": "nm", "nanometer": "nm", "nanometers": "nm",
	"mm": "mm","millimeter": "mm", "millimeters": "mm",
	"cm": "cm","centimeter": "cm", "centimeters": "cm",
	"m": "m","meter": "m", "meters": "m",
	"inch": "in", "inches": "in", "in": "in",
	"pixel": "pixels", "pixels": "pixels", "": "pixels",
	}


TrackmateSettings_Template = {
	'ChRegistration.Trackmate.Subpixel_Localization': True,
	'ChRegistration.Trackmate.Spot_Diameter': 4.0,
	'ChRegistration.Trackmate.Threshold_Value': 20.904,
	'ChRegistration.Trackmate.Median_Filtering': False,
	'ChRegistration.Trackmate.BatchMode': False,
	'ChRegistration.Trackmate.Save_Individual_CSVs': False,
	'ChRegistration.Trackmate.Debug': False
	}

MicroscopeSettings_Template = {
	'ChRegistration.Microscope.Objective_NA': 1.0,
	'ChRegistration.Microscope.Objective_Immersion': "Air",
	'ChRegistration.Microscope.Channel_Names': ["DAPI", "Alexa488", "Alexa555", "Alexa647", "Alexa730","Alexa731","Alexa732","Alexa733"],
	'ChRegistration.Microscope.Channel_WavelengthsEM': [425, 488, 555, 647, 730, 731, 732, 733]
	}



# A bunch of usefull functions
def Log_Message(message): # Display a message in the log only in Debug Mode is active Debug mode is known as Prolix mode
	TrackmateSettings_Stored=Read_Preferences(TrackmateSettings_Template)
	if TrackmateSettings_Stored['ChRegistration.Trackmate.Debug']:
		IJ.log(message)



def Read_Preferences(Settings_Template): # Return Preferences_Stored a dictionnary including keys found in the Templates above Can't receive Log_Message Since it depends on Read_Preferences
	Preferences_Stored = {}
	for key, default_value in Settings_Template.items():
		value = Prefs.get(key, str(default_value))
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
	return Preferences_Stored



def Save_Preferences(settings): # Save Preferences as Strings
	Log_Message("Saving Preferences...")
	for key, value in settings.items():
		if isinstance(value, list):
			value = ",".join(map(str, value))
		elif isinstance(value, bool):
			value = int(value)
		else:
			value = value
		Prefs.set(key, str(value))
		Log_Message("Saving Preferences. Done.")
	Prefs.savePreferences()


if ResetPreferences: # Reseting the Preferences for debuging
	Save_Preferences(MicroscopeSettings_Template)
	Save_Preferences(TrackmateSettings_Template)



def Get_Images(): # Get Images. Return Image_List a list of ImageTitle OR a List of File path and the Flag OpenedvsFolder telling if it open images or from a folder
	Log_Message("Getting Images...")
	if WindowManager.getImageTitles(): # Get titles of all open images
		Image_List = WindowManager.getImageTitles()
		OpenedvsFolder="Opened"
		Log_Message("Opened images found: "+"\n".join(Image_List))
	else:
		Image_List=[]
		while not Image_List:
			InputDir_Path = Select_Folder(Default_Path = UserDesktopPath) # Select a folder

			for Root, Dirs, Files in os.walk(InputDir_Path): # Get Files Recursively
			#Files = os.listdir(InputDir_Path): # Comment the line above and uncomment this line if you don't want to get files recurcively
				for File in Files:
					if File.lower().endswith(tuple(Image_Valid_Extension)): # Select only files ending with a Image_Valid_extension
						Image_List.append(str(os.path.join(Root, File)))
			if not Image_List:
				IJ.log("No valid image files found in the selected folder.")
				IJ.log("Valid image file extensions are :"+ ", ".join(Image_Valid_Extension))
				JOptionPane.showMessageDialog(None, "No valid image files found in the selected folder.", "Channel Registration with Batch Trackmate", JOptionPane.INFORMATION_MESSAGE)
		OpenedvsFolder="Folder"
		Log_Message("Images found:\n"+"\n".join(Image_List))
	return Image_List, OpenedvsFolder



def Select_Folder(Default_Path): # Return InputDir_Path as a string which should contain images
	Log_Message("Selecting Folder...")
	Chooser = JFileChooser(Default_Path)
	Chooser.setFileSelectionMode(JFileChooser.DIRECTORIES_ONLY)
	Chooser.setDialogTitle("Choose a directory containing the images to process")
	Return_Value = Chooser.showOpenDialog(None)
	if Return_Value == JFileChooser.APPROVE_OPTION:
		InputDir_Path = Chooser.getSelectedFile().getAbsolutePath()
	Log_Message("Selecting Folder: " + InputDir_Path + ". Done.")
	return InputDir_Path



def Open_Image_Bioformats(Filepath): # Open an image using Bioformat
	Log_Message("Importing " + str(Filepath) + " with Bioformats...")
	options = ImporterOptions()
	options.setId(Filepath)
	try:
		imps = BF.openImagePlus(options)
		if imps and len(imps) > 0:
			Log_Message("Importing " + str(Filepath) + " with Bioformats. Done.")
			return imps[0]
		else:
			IJ.log("Importing with Bioformats: No Images found in the file: " + Filepath + ".")
			return None
	except Exception as e:
		Log_Message("Importing with Bioformats: Error opening file" + str(e) + ".")
		return None



def Generate_Unique_Filepath(Directory, Basename, Suffix, Extension): # Return Filepath a Unique filepath Directory\Basename_Suffix-001.Extension Return the unique file path
	Log_Message("Generating Unique Filepath for: " + str(Basename) + "...")
	File_Counter = 1
	while True:
		Filename = "{}_{}-{:03d}{}".format(Basename, Suffix, File_Counter, Extension)
		Filepath = os.path.join(Directory, Filename)
		if not os.path.exists(Filepath):
			Log_Message("Generating Unique Filepath for: " + str(Basename) + ". Done.")
			return Filepath
		File_Counter += 1



def Clean_Filename(Filename): # Accessory function to clean filename. Return Filename_Cleaned a string
	Log_Message("Cleaning Filename " + str(Filename) + " ...")
	Filename_Cleaned = Filename.replace(" - ", "_")
	Filename_Cleaned = Filename_Cleaned.replace(".czi", "")
	Filename_Cleaned = Filename_Cleaned.replace("_spots", "")
	Filename_Cleaned = Filename_Cleaned.replace(".csv", "")
	Log_Message("Cleaning Filename " + str(Filename_Cleaned) + ": Done")
	return Filename_Cleaned



def Get_Refractive_Index(Objective_Immersion): # Get the refractive Index (float) from the Immersion media (String). Return Refracive_Index
	Log_Message("Getting refractive index for: "+str(Objective_Immersion)+"...")
	Refractive_Indices = {
		"Air": 1.0003,
		"Water": 1.333,
		"Oil": 1.515,
		"Glycerin": 1.47,
		"Silicone": 1.40,
	}
	Refractive_Index = Refractive_Indices.get(Objective_Immersion, 1.0)
	Log_Message("Getting refractive index for: "+str(Objective_Immersion)+" objective. Done.\nRefractive Index = "+str(Refractive_Index))
	return Refractive_Index



def Normalize_SpaceUnit(SpaceUnit): # Match SpaceUnit (str) with a Standard SpaceUnit string: m, cm, mm, micronSymbo+"m" or um for printing purposes
	Log_Message("Standardizing space unit: " + SpaceUnit + "...")
	SpaceUnitStd = Acceptable_SpaceUnits.get(SpaceUnit.lower(), "pixels")
	Log_Message("Standardizing space unit from " + SpaceUnit + " to "+SpaceUnitStd+".")
	return SpaceUnitStd



def Get_Image_Info(imp): # Return Image_Info a dictionnary including all image information, This function also Standardize the SpaceUnit without writing it to the file
	ImageName=imp.getTitle()
	Log_Message("Getting Image Info for: " + ImageName + "...")
	file_info = imp.getOriginalFileInfo()
	filename = file_info.fileName
	basename, extension = os.path.splitext(filename)
	input_dir = file_info.directory
	input_file_path = os.path.join(input_dir, filename)
	image_name = imp.getTitle()
	width = imp.getWidth()
	height = imp.getHeight()
	nb_channels = imp.getNChannels()
	nb_slices = imp.getNSlices()
	nb_timepoints = imp.getNFrames()
	bit_depth = imp.getBitDepth()
	current_channel = imp.getChannel()
	current_slice = imp.getSlice()
	current_frame = imp.getFrame()
	calibration = imp.getCalibration()
	pixel_width = calibration.pixelWidth
	pixel_height = calibration.pixelHeight
	pixel_depth = calibration.pixelDepth
	space_unit = calibration.getUnit()
	time_unit = calibration.getTimeUnit()
	frame_interval = calibration.frameInterval
	calibration_status = calibration.scaled()
	space_unit_std = Normalize_SpaceUnit(space_unit)

	if space_unit_std == "" + micronSymbol + "m": # I was not able to display micronSymbol in a CSV file so I convert it to um
		space_unit_print = "um"
	else:
		space_unit_print = str(space_unit_std)

	# Dictionnary storing  all image information
	Image_Info = {
		'InputFilePath': str(input_file_path),
		'InputDir': str(input_dir),
		'Filename': str(filename),
		'Basename': str(basename),
		'Extension': str(extension),
		'ImageName': str(image_name),
		'Width': int(width),
		'Height': int(height),
		'NbChannels': int(nb_channels),
		'NbSlices': int(nb_slices),
		'NbTimepoints': int(nb_timepoints),
		'BitDepth': int(bit_depth),
		'CurrentChannel': int(current_channel),
		'CurrentSlice': int(current_slice),
		'CurrentFrame': int(current_frame),
		'Calibration': calibration,
		'PixelWidth': float(pixel_width),
		'PixelHeight': float(pixel_height),
		'PixelDepth': float(pixel_depth),
		'SpaceUnit': space_unit,
		'SpaceUnitStd': space_unit_std,
		'TimeUnit': str(time_unit),
		'FrameInterval': float(frame_interval),
		'CalibrationStatus': bool(calibration_status),
		'SpaceUnitPrint': str(space_unit_print),
		}
	Log_Message("Getting Image Info for: "+ImageName+". Done.")
	return Image_Info



def Get_Metadata(imp): # Return Channel_Names_Metadata (list of channel Names as strings), Channel_WavelengthsEM_Metadata a list of Integer, Objective_NA_Metadata a floating, Objective_Immersion_Metadata a string
	ImageName = imp.getTitle()
	Log_Message("Getting Metadata for: " + ImageName + "...")
	Image_Info = Get_Image_Info(imp)
	options = ImporterOptions()
	options.setId(Image_Info['InputFilePath'])
	Metadata = MetadataTools.createOMEXMLMetadata()
	Reader = ImageReader()
	Reader.setMetadataStore(Metadata)
	Reader.setId(Image_Info['InputFilePath'])
	try:
		if Image_Info['NbChannels'] > 0:
			Channel_Names_Metadata = [str(Metadata.getChannelName(0, i-1)) for i in range(1, Image_Info['NbChannels']+1)]
			Channel_WavelengthsEM_Metadata = []
			for i in range(1, Image_Info['NbChannels']+1 ):
				WavelengthEM = Metadata.getChannelEmissionWavelength(0, i-1)
				if WavelengthEM is not None:
					# Extract numeric value from the wavelength metadata
					value_str = str(WavelengthEM)
					start = value_str.find('value[') + 6
					end = value_str.find(']', start)
					if start != -1 and end != -1:
						value = value_str[start:end]
						Channel_WavelengthsEM_Metadata.append(int(round(float(value))))
					else:
						Channel_WavelengthsEM_Metadata.append(0)
				else:
					Channel_WavelengthsEM_Metadata.append(0)
			# Check if metadata contains objective and instrument information
			if Metadata.getInstrumentCount() > 0 and Metadata.getObjectiveCount(0) > 0:
				Objective_NA_Metadata = float(Metadata.getObjectiveLensNA(0, 0))
				Objective_Immersion_Metadata = str(Metadata.getObjectiveImmersion(0, 0))
				Log_Message("Getting Metadata for: " + ImageName + ". Done.")
				return Channel_Names_Metadata, Channel_WavelengthsEM_Metadata, Objective_NA_Metadata, Objective_Immersion_Metadata
			else:
				IJ.log(ImageName+" does not contain metadata. Proceeding with information from Preferences...")
				return None, None, None, None
	except Exception as e:
		IJ.log("Error retrieving metadata: " + str(e))
		return None, None, None, None




def Get_Calibration(imp): # Get the Space Unit and Normalize the name, if image is not calibrated prompt to enter calibration
	Image_Info=Get_Image_Info(imp)
	ImageName=Image_Info['ImageName']
	Log_Message("Getting Image Calibration for: " + ImageName + "...")
	if not Image_Info['CalibrationStatus']:
		ImageName = imp.getTitle()
		CalibrationDialog = NonBlockingGenericDialog("Channel Registration with Batch Trackmate")
		CalibrationDialog.addMessage(ImageName)
		CalibrationDialog.addMessage(" == = Image Settings == = ")
		CalibrationDialog.addMessage("Image is "+"Calibrated" if Image_Info['CalibrationStatus'] else "Uncalibrated")
		CalibrationDialog.addNumericField("Pixel Width ({0}):".format("Metadata" if Image_Info['SpaceUnit'] != "pixels" else "Uncalibrated"),
		Image_Info['PixelWidth'], 4, 8, Image_Info['SpaceUnit']+"/px")
		CalibrationDialog.addRadioButtonGroup("Unit per pixel", ["nm", ""+micronSymbol+"m", "mm", "cm", "m", "pixels"], 2, 3, ""+micronSymbol+"m")
		CalibrationDialog.addNumericField("Pixel Height ({0}):".format("Metadata" if Image_Info['SpaceUnit'] != "pixels" else "Uncalibrated"),
		Image_Info['PixelHeight'], 4, 8, Image_Info['SpaceUnit']+"/px")
		CalibrationDialog.addToSameRow()
		CalibrationDialog.addNumericField("Bit Depth:", Image_Info['BitDepth'], 0, 3, "")
		CalibrationDialog.addNumericField("Voxel size ({0}):".format("Metadata" if Image_Info['SpaceUnit'] != "pixels" else "Uncalibrated"),
		Image_Info['PixelDepth'], 4, 8, Image_Info['SpaceUnit']+"/px")
		CalibrationDialog.showDialog()

	# Results from the Dialog
		if CalibrationDialog.wasOKed():
			PixelWidth_User = gd.getNextNumber()
			SpaceUnit_User = gd.getNextRadioButton()
			PixelHeight_User = gd.getNextNumber()
			BitDepth_User = gd.getNextNumber()
			PixelDepth_User = gd.getNextNumber()
			Log_Message("Updating Image Calibration for: " + ImageName + "...")
			ImageCalibration = imp.getCalibration()
			ImageCalibration.pixelWidth = PixelWidth_User if isinstance(PixelWidth_User, (float, int)) else float(1)
			ImageCalibration.pixelHeight = PixelHeight_User if isinstance(PixelHeight_User, (float, int)) else float(1)
			ImageCalibration.pixelDepth = PixelDepth_User if isinstance(PixelDepth_User, (float, int)) else float(1)
			SpaceUnitStd = Acceptable_SpaceUnits.get(SpaceUnit_User.lower(), "pixels")
			ImageCalibration.setUnit(SpaceUnitStd)
			imp.setCalibration(ImageCalibration)
			Log_Message("Updating Image Calibration: " + ImageName + ". Done.")
		elif gd.wasCanceled():
			IJ.log("User clicked Cancel while getting calibration for: "+ImageName+".")
			sys.exit("Script ended because User clicked cancel.")
	else:
		SpaceUnitStd = Acceptable_SpaceUnits.get(Image_Info['SpaceUnit'].lower(), "pixels")
		ImageCalibration = imp.getCalibration()
		ImageCalibration.setUnit(SpaceUnitStd)
		imp.setCalibration(ImageCalibration)
	Log_Message("Getting Image Calibration for: " + ImageName + ". Done.")
	return



# Functions more specific

def Run_Trackmate(imp, Channel, GetSpotData): # Run Trackmate on a specific Channel.
	# Return NbDetectedSpotsCh (an integer), Max_QualityCh (an integer), SpotDataCh a dictionnary
	# Max_QualityCh is an Integer of the Max Quality of all Detected spots in a given channel
	# SpotDataCh is Dictionnary with all data for a all spots found in a given Channel
 	Image_Info = Get_Image_Info(imp)
 	ImageName=Image_Info['ImageName']
 	Log_Message("Running Trackmate for: "+str(ImageName)+" Channel "+str(Channel)+".")
 	TrackmateSettings_Stored=Read_Preferences(TrackmateSettings_Template)
 	MicroscopeSettings_Stored=Read_Preferences(MicroscopeSettings_Template)

 	imp.setDisplayMode(IJ.COLOR)
	imp.setC(Channel) # Channel starts from 1 to Image_Info[NbChannels]
	imp.updateAndDraw()
	model = Model()
	trackmate_settings = Settings(imp)
	model.setPhysicalUnits(Image_Info['SpaceUnitStd'], Image_Info['TimeUnit'])
	trackmate_settings.detectorFactory = DogDetectorFactory()
	trackmate_settings.detectorSettings = {
		'DO_SUBPIXEL_LOCALIZATION': TrackmateSettings_Stored['ChRegistration.Trackmate.Subpixel_Localization'],
		'RADIUS': TrackmateSettings_Stored['ChRegistration.Trackmate.Spot_Diameter'] / 2,
		'TARGET_CHANNEL': Channel,
		'THRESHOLD': TrackmateSettings_Stored['ChRegistration.Trackmate.Threshold_Value'],
		'DO_MEDIAN_FILTERING': TrackmateSettings_Stored['ChRegistration.Trackmate.Median_Filtering']
	}
	trackmate_settings.trackerFactory = SparseLAPTrackerFactory()
	trackmate_settings.trackerSettings = trackmate_settings.trackerFactory.getDefaultSettings()
	trackmate_settings.trackerSettings['ALLOW_TRACK_SPLITTING'] = True
	trackmate_settings.trackerSettings['ALLOW_TRACK_MERGING'] = True
	trackmate_settings.addAllAnalyzers()

	trackmate = TrackMate(model, trackmate_settings)
	ok1 = trackmate.checkInput()
	ok2 = trackmate.process()

	if not ok1 or not ok2:
		Log_Message("Trackmate could not detect any spot for: "+ImageName+". Falling back.")
		NbDetectedSpotsCh = 0
		Max_QualityCh = TrackmateSettings_Stored['ChRegistration.Trackmate.Threshold_Value'] #If Detection fails use the last stored value
		if GetSpotData:
			SpotDataCh = {
			'Filename': Image_Info['Filename'],
			'Channel_Nb': Channel,
			'Channel_Name': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names'][Channel-1],
			'Channel_WavelengthEM': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM'][Channel-1],
			'Spot ID': 0,
			'Quality': 0,
			'X': 0,
			'Y': 0,
			'Z': 0,
			'T': 0,
			'Frame': 0,
			'Radius': 0,
			'Diameter':0,
			'Visibility': 0,
			}
		else:
			SpotDataCh=None

	else: # Detection works display it
		Log_Message("Tracking successful for: "+ImageName+". Rendering detection results...")
		selection_model = SelectionModel(model)
		ds = DisplaySettingsIO.readUserDefault()
		ds.setSpotDisplayRadius(0.9)
		ds.setSpotDisplayedAsRoi(True)
		ds.setSpotShowName(True)
		ds.setSpotTransparencyAlpha(0.7)
		ds.setSpotFilled(True)
		displayer = HyperStackDisplayer(model, selection_model, imp, ds)
		displayer.render()
		displayer.refresh()

		NbDetectedSpotsCh = int(model.getSpots().getNSpots(True))

		Max_QualityCh = 0
		if NbDetectedSpotsCh > 0:
			for Spot in model.getSpots().iterable(True):
				if GetSpotData: # Get the data for all Spots in the current Channel
					Log_Message("Tracking successful for: "+ImageName+". Storing results...")
					SpotDataCh = {
						'Filename': Image_Info['Filename'],
						'Channel_Nb': Channel,
						'Channel_Name': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names'][Channel-1],
						'Channel_WavelengthEM': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM'][Channel-1],
						'Spot ID': Spot.ID(),
						'Quality': Spot.getFeature('QUALITY'),
						'X': Spot.getFeature('POSITION_X'),
						'Y': Spot.getFeature('POSITION_Y'),
						'Z': Spot.getFeature('POSITION_Z'),
						'T': Spot.getFeature('POSITION_T'),
						'Frame': Spot.getFeature('FRAME'),
						'Radius': Spot.getFeature('RADIUS'),
						'Diameter': 2*Spot.getFeature('RADIUS'),
						'Visibility': Spot.getFeature('VISIBILITY'),
						}
				else:
					SpotDataCh=None
				# Get the Max Spot Quality for each channel
				Spot_Quality = Spot.getFeature('QUALITY')
				if Max_QualityCh is None or Spot_Quality > Max_QualityCh:
					Max_QualityCh = int(Spot_Quality)
			# If GetSpotData And Save CSVs and Debug save the original Trackmate tables per Ch
			if GetSpotData and TrackmateSettings_Stored['ChRegistration.Trackmate.Save_Individual_CSVs'] and TrackmateSettings_Stored['ChRegistration.Trackmate.Debug']:
				Spots_TableCh = AllSpotsTableView(model, selection_model, ds, Image_Info['Filename'])
				Output_Trackmate_SpotData_Path = Generate_Unique_Filepath(Output_Dir, Image_Info['Basename'], "Channel-Registration_Trackmate_Spot-Data_Ch-0" + str(Channel), ".csv")
				Spots_TableCh.exportToCsv(Output_Trackmate_SpotData_Path)
		else: #Else NbDetectedSpots inferior or equal to 0
			NbDetectedSpotsCh=0
			Max_QualityCh=10
			if GetSpotData:
				SpotDataCh = {
				'Filename': Image_Info['Filename'],
				'Channel_Nb': Channel,
				'Channel_Name': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names'][Channel-1],
				'Channel_WavelengthEM': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM'][Channel-1],
				'Spot ID': 0,
				'Quality': 0,
				'X': 0,
				'Y': 0,
				'Z': 0,
				'T': 0,
				'Frame': 0,
				'Radius': 0,
				'Diameter': 0,
				'Visibility': 0,
				}
			else:
				SpotDataCh=None
	return NbDetectedSpotsCh, Max_QualityCh, SpotDataCh



def Run_Trackmate_All_Ch(imp, SaveFile, GetSpotData): # Run Trackmate on all channels.
	# Return NbDetectedSpotsPerCh a list of Integer
	# MaxQualityThresholdPerCh a list of integer
	# SpotDataAllCh a list of Dictionnary containing the data for all spots and all Ch
	Image_Info = Get_Image_Info(imp)
	ImageName=Image_Info['ImageName']
	Log_Message("Running Detection on all channels for: " + ImageName + "...")
	CurrentChannel=Image_Info['CurrentChannel']
	TrackmateSettings_Stored=Read_Preferences(TrackmateSettings_Template)
	NbDetectedSpotsPerCh = []  # Store Nb of Detected Spot for each channel int
	MaxQualityThresholdPerCh = [] # Store Max Spot Quality for each channel  int
	SpotDataAllCh = [] # Store the dictionnaries containing the data

	for Channel in range(1, Image_Info['NbChannels']+1):
		NbDetectedSpotsCh, Max_QualityCh, SpotDataCh = Run_Trackmate(imp, Channel, GetSpotData)
		NbDetectedSpotsPerCh.append(NbDetectedSpotsCh)
		MaxQualityThresholdPerCh.append(Max_QualityCh)
		SpotDataAllCh.append(SpotDataCh)

	global SpotDataOrderedKeys
	global SpotDataHeader
	SpotDataOrderedKeys = ['Filename', 'Channel_Nb', 'Channel_Name', 'Channel_WavelengthEM', 'Spot ID', 'Quality', 'X', 'Y', 'Z', 'T', 'Frame', 'Radius', 'Diameter', 'Visibility']
	SpotDataHeader = ['Filename', 'Channel Nb', 'Channel Name', 'Channel EmWavelength (nm)', 'Spot ID', 'Quality', 'X ('+Image_Info['SpaceUnitPrint']+')', 'Y ('+Image_Info['SpaceUnitPrint']+')', 'Z ('+Image_Info['SpaceUnitPrint']+')', 'T ('+Image_Info['TimeUnit']+')', 'Frame', 'Radius ('+Image_Info['SpaceUnitPrint']+')', 'Diameter ('+Image_Info['SpaceUnitPrint']+')', 'Visibility']
	Output_SpotData_CSVPath = Generate_Unique_Filepath(Output_Dir, Image_Info['Basename'], "Channel-Registration_Spots-Data", ".csv")

	if SaveFile and TrackmateSettings_Stored['ChRegistration.Trackmate.Save_Individual_CSVs'] and TrackmateSettings_Stored['ChRegistration.Trackmate.Debug'] :
		with open(Output_SpotData_CSVPath, 'wb') as CSVFile:
			CSVWriter = csv.writer(CSVFile)
  			CSVWriter.writerow(SpotDataHeader)
  			for ChData in SpotDataAllCh:
  				Row=[]
  				for key in SpotDataOrderedKeys:
  					Row.append(ChData[key])
				CSVWriter.writerow(Row)
	Log_Message("Running Detection on all channel for: " + ImageName + ". Done. Detected Spots per Channel: {}".format(", ".join(map(str, NbDetectedSpotsPerCh))))

	Log_Message("Running Detection for display purposes for: " + ImageName + "...")
	Run_Trackmate(imp, CurrentChannel, GetSpotData=False) # Run Trackmate on a specific Channel for display purposes
	Log_Message("Running Detection for display purpose for: " + ImageName + ". Done. Detected Spots per Channel: {}".format(", ".join(map(str, NbDetectedSpotsPerCh))))

	return NbDetectedSpotsPerCh, MaxQualityThresholdPerCh, SpotDataAllCh



# Read Metadata, Run Pre-detection, and display a dialog, Recalibrate image
def Display_Dialog(imp, Dialog_Counter, Test_Detection, BatchMessage): # Display a dialog with Metadata and results from predetection
	# Return TrackmateSettings_User, MicroscopeSettings_User, User_Click, NbDetectedSpotsPerCh, Dialog_Counter, Test_Detection, to BatchMessage transfert
	Image_Info=Get_Image_Info(imp)
	ImageName=Image_Info['ImageName']
	CurrentChannel=Image_Info['CurrentChannel']
	Log_Message("Displaying Ch Registration Dialog for: " + ImageName + "...")
	# Getting Metadata and stored settings
	Channel_Names_Metadata, Channel_WavelengthsEM_Metadata, Objective_NA_Metadata, Objective_Immersion_Metadata = Get_Metadata(imp)
	TrackmateSettings_Stored = Read_Preferences(TrackmateSettings_Template)
	MicroscopeSettings_Stored = Read_Preferences(MicroscopeSettings_Template)

	# Displaying Metadata in priority and Stored values as fall back
	Objective_NA = Objective_NA_Metadata if Objective_NA_Metadata is not None and Dialog_Counter == 0 else MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_NA']
	Objective_Immersion = Objective_Immersion_Metadata if Objective_Immersion_Metadata and Dialog_Counter == 0 else MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_Immersion']
	Channel_Names = Channel_Names_Metadata if Channel_Names_Metadata and Dialog_Counter == 0 else MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names']
	Channel_WavelengthsEM = Channel_WavelengthsEM_Metadata if Channel_WavelengthsEM_Metadata and Dialog_Counter == 0 else MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM']
	Channel_Names_Stored = MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names']
	Channel_WavelengthsEM_Stored = MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM']

	# Running PreDetection to Get NbDetectedSpots and MaxQuality threhsold
	NbDetectedSpotsPerCh, MaxQualityThresholdPerCh, _ = Run_Trackmate_All_Ch(imp, SaveFile=False, GetSpotData=False)
	# Running Predection to display detection on the selected channel
	Run_Trackmate(imp, CurrentChannel, GetSpotData=False)

	# Create a dialog
	MainDialog = NonBlockingGenericDialog("Channel Registration with Batch Trackmate")
	MainDialog.addMessage(ImageName)
	# Microscope Settings section
	MainDialog.addMessage(" === Microscope Settings === ")
	MainDialog.addNumericField("Objective NA ({}):".format("Metadata" if Objective_NA_Metadata and Dialog_Counter == 0 else "Pref"), Objective_NA, 2, 4, "")
	MainDialog.addRadioButtonGroup("Objective Immersion ({}):".format("Metadata" if Objective_Immersion_Metadata and Dialog_Counter == 0 else "Pref"),
						 ["Air", "Water", "Oil", "Glycerin", "Silicone"], 1, 6, Objective_Immersion)
	MainDialog.addMessage("Image is "+"Calibrated" if Image_Info['CalibrationStatus'] else "Uncalibrated")
	MainDialog.addNumericField("Pixel Width ({0}):".format("Metadata" if Image_Info['SpaceUnitStd'] != "pixels" else "Uncalibrated"),
	Image_Info['PixelWidth'], 4, 5, Image_Info['SpaceUnitStd'])
	MainDialog.addToSameRow()
	MainDialog.addStringField("Unit:", Image_Info['SpaceUnitStd'], 2)
	MainDialog.addNumericField("Pixel Height ({0}):".format("Metadata" if Image_Info['SpaceUnitStd'] != "pixels" else "Uncalibrated"),
	Image_Info['PixelHeight'], 4, 5, Image_Info['SpaceUnitStd'])
	MainDialog.addToSameRow()
	MainDialog.addNumericField("Bit Depth:", Image_Info['BitDepth'], 0, 2, "bit")
	MainDialog.addNumericField("Voxel size ({0}):".format("Metadata" if Image_Info['SpaceUnitStd'] != "pixels" else "Uncalibrated"),
	Image_Info['PixelDepth'], 4, 5, Image_Info['SpaceUnitStd'])

	# Channel Settings section
	MainDialog.addMessage(" === Channel Settings === ")
	for Channel in range (1, Image_Info['NbChannels']+1):
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

		MainDialog.addStringField("Channel {} Name ({}):".format(Channel, Channel_Names_Source), str(Channel_Name), 6)
		MainDialog.addNumericField("Wavelength ({}):".format(Channel_WavelengthsEM_Source), Channel_WavelengthEM,0, 3, "nm")

	# Detection Settings
	MainDialog.addMessage(" === Detection Settings === ")
	MainDialog.addNumericField("Spot Diameter", TrackmateSettings_Stored['ChRegistration.Trackmate.Spot_Diameter'], 1, 4, Image_Info['SpaceUnitStd'])
	MainDialog.addSlider("Threshold Value:", 0, min(MaxQualityThresholdPerCh), TrackmateSettings_Stored['ChRegistration.Trackmate.Threshold_Value'])
	MainDialog.addCheckbox("Enable Subpixel Localization", TrackmateSettings_Stored['ChRegistration.Trackmate.Subpixel_Localization'])
	MainDialog.addToSameRow()
	MainDialog.addCheckbox("Test Detection", Test_Detection)
	MainDialog.addCheckbox("Apply Median Filtering", TrackmateSettings_Stored['ChRegistration.Trackmate.Median_Filtering'])
	MainDialog.addToSameRow()
	MainDialog.addCheckbox("Save individual CSVs", TrackmateSettings_Stored['ChRegistration.Trackmate.Save_Individual_CSVs'])
	MainDialog.addCheckbox("Batch Mode", TrackmateSettings_Stored['ChRegistration.Trackmate.BatchMode'])
	MainDialog.addToSameRow()
	MainDialog.addCheckbox("Prolix Mode", TrackmateSettings_Stored['ChRegistration.Trackmate.Debug'])

	# Results from Predetection amd other options
	if sum(NbDetectedSpotsPerCh) > Image_Info['NbChannels']:
		Advice = "Nb of detected spots too high. Increase the threshold."
	elif sum(NbDetectedSpotsPerCh) < Image_Info['NbChannels']:
		Advice = "Nb of detected spots too low. Decrease the threshold."
	elif sum(NbDetectedSpotsPerCh) == Image_Info['NbChannels'] and all(Spots == 1 for Spots in NbDetectedSpotsPerCh):
		Advice = "Exactly one spot detected per Channel. You can proceed."
	else:
		Advice = "{} spots detected but not one spot detected per channel.\n{} can't be processed here. You need different detection thresholds for each channel.".format(sum(NbDetectedSpotsPerCh), Image_Info['NbChannels'])
		IJ.log(Advice)
		return None, None, None, None, None, None

	NbDetectedSpotsPerCh_Str = [str(NbSpots) for NbSpots in NbDetectedSpotsPerCh]
	NbDetectedSpotsPerCh_String = "+ ".join(NbDetectedSpotsPerCh_Str)
	MaxQualityThresholdPerCh_Str = [str(int(Quality)) for Quality in MaxQualityThresholdPerCh]
	MaxQualityThresholdPerCh_String = ", ".join(MaxQualityThresholdPerCh_Str)
	MessageDetectedSpotPerCh = "Detected spots per channel: {} = {}. Nb of Channels: {}".format(
	NbDetectedSpotsPerCh_String, sum(NbDetectedSpotsPerCh), Image_Info['NbChannels'])
	MessageSpotQuality = "Max Spot Quality per channel: {}".format(MaxQualityThresholdPerCh_String)

	MainDialog.addMessage("{}\n{}\n{}\n{}".format(BatchMessage, Advice, MessageDetectedSpotPerCh, MessageSpotQuality))

	# Showing the Dialog
	MainDialog.showDialog()

	# Results from the Dialog
	if MainDialog.wasOKed():
		User_Click = "OK" # Flag to continue
		MicroscopeSettings_User = {}
		TrackmateSettings_User = {}
		MicroscopeSettings_User['ChRegistration.Microscope.Objective_NA'] = MainDialog.getNextNumber()
		MicroscopeSettings_User['ChRegistration.Microscope.Objective_Immersion'] = MainDialog.getNextRadioButton()
		PixelWidth_User = MainDialog.getNextNumber()
		SpaceUnit_User = MainDialog.getNextString()
		PixelHeight_User = MainDialog.getNextNumber()
		BitDepth_User = MainDialog.getNextNumber()
		PixelDepth_User = MainDialog.getNextNumber()

		Channel_Names = []
		Channel_WavelengthsEM = []
		for Channel in range(1, Image_Info['NbChannels']+1):
			Channel_Name = MainDialog.getNextString()
			Channel_WavelengthEM = MainDialog.getNextNumber()
			Channel_Names.append(Channel_Name)
			Channel_WavelengthsEM.append(Channel_WavelengthEM)

		MicroscopeSettings_User['ChRegistration.Microscope.Channel_Names'] = Channel_Names
		MicroscopeSettings_User['ChRegistration.Microscope.Channel_WavelengthsEM'] = Channel_WavelengthsEM
		TrackmateSettings_User['ChRegistration.Trackmate.Spot_Diameter'] = MainDialog.getNextNumber()
		TrackmateSettings_User['ChRegistration.Trackmate.Threshold_Value'] = MainDialog.getNextNumber()
		TrackmateSettings_User['ChRegistration.Trackmate.Subpixel_Localization'] = MainDialog.getNextBoolean()
		Test_Detection = MainDialog.getNextBoolean()
		TrackmateSettings_User['ChRegistration.Trackmate.Median_Filtering'] = MainDialog.getNextBoolean()
		TrackmateSettings_User['ChRegistration.Trackmate.Save_Individual_CSVs'] = MainDialog.getNextBoolean()
		TrackmateSettings_User['ChRegistration.Trackmate.BatchMode'] = MainDialog.getNextBoolean()
		TrackmateSettings_User['ChRegistration.Trackmate.Debug'] = MainDialog.getNextBoolean()
		Save_Preferences(MicroscopeSettings_User)
		Save_Preferences(TrackmateSettings_User)

		Log_Message("Updating Image Calibration for: " + ImageName + "...")
		ImageCalibration = imp.getCalibration()
		ImageCalibration.pixelWidth = PixelWidth_User if isinstance(PixelWidth_User, (float, int)) else float(1)
		ImageCalibration.pixelHeight = PixelHeight_User if isinstance(PixelHeight_User, (float, int)) else float(1)
		ImageCalibration.pixelDepth = PixelDepth_User if isinstance(PixelDepth_User, (float, int)) else float(1)
		SpaceUnit_User_Std=Normalize_SpaceUnit(SpaceUnit_User)
		ImageCalibration.setUnit(SpaceUnit_User_Std)
		imp.setCalibration(ImageCalibration)
		Log_Message("Updating Image Calibration: " + ImageName + ". Done.")
		BatchMessage=""
		Dialog_Counter += 1
	elif MainDialog.wasCanceled():
		User_Click = "Cancel"
		IJ.log("User clicked Cancel while processing "+ ImageName +".")
		sys.exit("Script ended because User clicked cancel.")
	Log_Message("Displaying Ch Registration Dialog for: " + ImageName + ". Done.")
	return TrackmateSettings_User, MicroscopeSettings_User, User_Click, NbDetectedSpotsPerCh, Dialog_Counter, Test_Detection, BatchMessage



# Main Processing function for Channel Registration
def Processing_Data(imp, SpotDataAllCh, Image): # Compute the Channel Registration for all pair of channels in SpotDataAllCh
	# Image (integer going through the list of files is used to initiate the OuputCSV File
	# Return ProcessedData
# 				For Information SpotDataCh is a dictionary with the following keys
#				SpotDataCh{
#				'Filename': Image_Info['Filename'],
#				'Channel_Nb': Channel,
#				'Channel_Name': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names'][Channel-1],
#				'Channel_WavelengthEM': MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM'][Channel-1],
#				'Spot ID': 0,
#				'Quality': 0,
#				'X': 0,
#				'Y': 0,
#				'Z': 0,
#				'T': 0,
#				'Frame': 0,
#				'Radius': 0,
#				'Diameter': 0,
#				'Visibility': 0,
#				}
# SpotDataAllCh is a list of NbChannels each being a dictionnary

	Image_Info = Get_Image_Info(imp)
	ImageName=Image_Info['ImageName']
	Log_Message("Computing Ch Registration for: "+ImageName+"...")

	ProcessedData=[] # List to Store Ch Registration Data for all pair of Channels
	NbChannels=Image_Info['NbChannels']

	# Collect Channel Info from SpotDataAllCh
	Channels_Info = {}
	for SpotDataCh in SpotDataAllCh:
		Channel_Nb = int(SpotDataCh['Channel_Nb'])
		Channel_Name = str(SpotDataCh['Channel_Name'])
		Channel_WavelengthEM = float(SpotDataCh['Channel_WavelengthEM'])
		if Channel_Nb not in Channels_Info:
			Channels_Info[Channel_Nb] = (Channel_Nb, Channel_Name, Channel_WavelengthEM)
	Channels = sorted(Channels_Info.keys())
	Channel_Nb = [Channels_Info[Ch][0] for Ch in Channels]
	Channel_Names = [Channels_Info[Ch][1] for Ch in Channels]
	Channel_WavelengthsEM = [Channels_Info[Ch][2] for Ch in Channels]

	# Collect Microscope Settings
	MicroscopeSettings_Stored = Read_Preferences(MicroscopeSettings_Template)
	Objective_NA = MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_NA']
	Objective_Immersion = MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_Immersion']
	Refractive_Index = Get_Refractive_Index(Objective_Immersion)

	for SpotDataCh in SpotDataAllCh:
		Original_Filename = SpotDataCh['Filename']
		Cleaned_Filename = Clean_Filename(Original_Filename)
		#SpotDataAllCh['Filename_Cleaned'] = Cleaned_Filename # Add the cleaned filename to the dictionary


	# Loop through all pair of Channels for calculating Ch Shifts
	for Ch1 in range(0, len(Channels)):
		for Ch2 in range(0, len(Channels)):
			Channel_Ch1 = int(Channels[Ch1])
			Channel_Ch2 = int(Channels[Ch2])
			Channel_Name_Ch1 = str(Channel_Names[Ch1])
			Channel_Name_Ch2 = str(Channel_Names[Ch2])
			Channel_Pair = "%s x %s" % (Channel_Name_Ch1, Channel_Name_Ch2)

			Spot_Channel_Ch1 = next((Spot for Spot in SpotDataAllCh if Spot['Channel_Nb'] == Channel_Ch1), None)
			Spot_Channel_Ch2 = next((Spot for Spot in SpotDataAllCh if Spot['Channel_Nb'] == Channel_Ch2), None)


			# Extract position values for both channels
		  	X_Ch1 = float(Spot_Channel_Ch1['X'])
			Y_Ch1 = float(Spot_Channel_Ch1['Y'])
			Z_Ch1 = float(Spot_Channel_Ch1['Z'])

			X_Ch2 = float(Spot_Channel_Ch2['X'])
			Y_Ch2 = float(Spot_Channel_Ch2['Y'])
			Z_Ch2 = float(Spot_Channel_Ch2['Z'])

			# Compute differences
			dX = (X_Ch2 - X_Ch1)
			dY = (Y_Ch2 - Y_Ch1)
			dZ = (Z_Ch2 - Z_Ch1)

			# Convert differences into Pixels
			PixelWidth=float(Image_Info['PixelWidth'])
			PixelHeight=float(Image_Info['PixelHeight'])
			PixelDepth=float(Image_Info['PixelDepth'])

			dX_Pix = dX / PixelWidth
			dY_Pix = dY / PixelHeight
			dZ_Pix = dZ / PixelDepth

			# Compute distances
			Distance_Lateral, Distance_Axial, Distance_3D = Euclidean_Distance(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2)


			# Extract wavelengths for each Channel
			EMWavelength_Ch1 = float(Spot_Channel_Ch1['Channel_WavelengthEM'])
			EMWavelength_Ch2 = float(Spot_Channel_Ch2['Channel_WavelengthEM'])

			Conversion_Factors = { #Space Unit Std: Conversion facotr
			""+micronSymbol+"m": 1000,	# 1 nm = 0.001  m
			"nm": 1,		# 1 nm = 1 nm
			"mm": 1000000,	 # 1 nm = 0.000001 mm
			"cm": 10000000,	 # 1 nm = 0.0000001 cm
			"m": 1000000000,	 # 1 nm = 0.0000000001 m
			"in": 2540000, # 1 nm = 0.0000000393701 in (approx.)
			"pixels": 1,	# Assuming pixels is the default unit and conversion factor for pixels is 1 (since no physical measurement)
			}
			SpaceUnitStd=Image_Info['SpaceUnitStd']
			SpaceUnitPrint=str(Image_Info['SpaceUnitPrint'])

			ConversionFactor = float(Conversion_Factors[SpaceUnitStd])

			EMWavelength_Unit_Ch1 = EMWavelength_Ch1 / ConversionFactor
			EMWavelength_Unit_Ch2 = EMWavelength_Ch2 / ConversionFactor


			Nyquist_PixelSize_Lateral_Ch1, Nyquist_PixelSize_Axial_Ch1, Nyquist_Ratio_Lateral_Ch1, Nyquist_Ratio_Axial_Ch1 = NyquistCalculator(EMWavelength_Unit_Ch1, Objective_NA, Refractive_Index, PixelWidth, PixelHeight, PixelDepth)
			Nyquist_PixelSize_Lateral_Ch2, Nyquist_PixelSize_Axial_Ch2, Nyquist_Ratio_Lateral_Ch2, Nyquist_Ratio_Axial_Ch2 = NyquistCalculator(EMWavelength_Unit_Ch2, Objective_NA, Refractive_Index, PixelWidth, PixelHeight, PixelDepth)


			Resolution_Lateral_Theoretical_Ch1, Resolution_Axial_Theoretical_Ch1, Resolution_Lateral_Practical_Ch1, Resolution_Axial_Practical_Ch1 = ResolutionCalculator(EMWavelength_Unit_Ch1, Objective_NA, Refractive_Index, Nyquist_Ratio_Lateral_Ch1, Nyquist_Ratio_Axial_Ch1)
			Resolution_Lateral_Theoretical_Ch2, Resolution_Axial_Theoretical_Ch2, Resolution_Lateral_Practical_Ch2, Resolution_Axial_Practical_Ch2 = ResolutionCalculator(EMWavelength_Unit_Ch2, Objective_NA, Refractive_Index, Nyquist_Ratio_Lateral_Ch2, Nyquist_Ratio_Axial_Ch2)



			# Resolution is in nm must convert it to match the distance values
			Semi_Minor_Axis = (max(Resolution_Lateral_Practical_Ch1, Resolution_Lateral_Practical_Ch2))/2  # Using the largest number to calculate the Ratios
			Semi_Major_Axis = (max(Resolution_Axial_Practical_Ch1, Resolution_Axial_Practical_Ch2))/2 # Using the largest number to calculate the Ratios

			# Calculate the terms of the ellipse equation
			#Colocalization_Ratio = ((X2 - X1) ** 2) / (Semi_Minor_Axis ** 2) + ((Y2 - Y1) ** 2) / (Semi_Minor_Axis ** 2) + ((Z2 - Z1) ** 2) / (Semi_Major_Axis ** 2)
			Colocalization_Ratio_Lateral = Distance_Lateral/Semi_Minor_Axis
			Colocalization_Ratio_Axial = abs(Distance_Axial)/Semi_Major_Axis

			# If spots are not already colocalized project the Spot1->Spot2 vector to the Ellipse
			if X_Ch1 != X_Ch2 and Y_Ch1 != Y_Ch2 and Z_Ch1 != Z_Ch2:
				X_Proj, Y_Proj, Z_Proj = Project_on_Ellipse(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, max_iterations=1000, initial_step=10, tolerance=1e-12)
			else:
				X_Proj=X_Ch1
				Y_Proj=Y_Ch1
				Z_Proj=Z_Ch1

			dX_Ref = X_Proj - X_Ch1
			dY_Ref = Y_Proj - Y_Ch1
			dZ_Ref = Z_Proj - Z_Ch1

			Distance_Lateral_Ref, Distance_Axial_Ref, Distance_3D_Ref = Euclidean_Distance(X_Ch1, Y_Ch1, Z_Ch1, X_Proj, Y_Proj, Z_Proj)


			if Distance_3D_Ref==0:
				Colocalization_Ratio_3D = 0
			else:
				Colocalization_Ratio_3D = Distance_3D / Distance_3D_Ref


			# Split the filename at each _
			Filename=Spot_Channel_Ch1['Filename']
			Filename_Parts = Filename.split('_')
			Max_Filename_Variables = len(Filename_Parts)

			# Append data to ProcessedData
			ProcessedData.append([
				Filename,
				'Channel '+str(Ch1+1), "Channel "+str(Ch2+1), Channel_Name_Ch1, Channel_Name_Ch2, Channel_Pair,
				round(X_Ch1, 2), round(Y_Ch1, 2), round(Z_Ch1, 2), round(X_Ch2, 2), round(Y_Ch2, 2), round(Z_Ch2, 2),
				round(dX, 2), round(dY, 2), round(dZ, 2),
				round(PixelWidth, 3), round(PixelHeight, 3), round(PixelDepth, 3),
				round(dX_Pix, 2), round(dY_Pix, 2), round(dZ_Pix, 2),
				round(Distance_Lateral, 2), round(Distance_Axial, 2), round(Distance_3D, 2),
				round(Objective_NA, 2), Objective_Immersion, round(Refractive_Index, 2),
				round(EMWavelength_Ch1, 2), round(EMWavelength_Ch2, 2), round(ConversionFactor, 2), round(EMWavelength_Unit_Ch1, 3), round(EMWavelength_Unit_Ch2, 3),
				round(Nyquist_PixelSize_Lateral_Ch1, 3), round(Nyquist_PixelSize_Axial_Ch1, 3), round(Nyquist_Ratio_Lateral_Ch1, 1), round(Nyquist_Ratio_Axial_Ch1, 1),
				round(Nyquist_PixelSize_Lateral_Ch2, 3), round(Nyquist_PixelSize_Axial_Ch2, 3), round(Nyquist_Ratio_Lateral_Ch2, 1), round(Nyquist_Ratio_Axial_Ch2, 1),
				round(Resolution_Lateral_Theoretical_Ch1, 2), round(Resolution_Axial_Theoretical_Ch1, 2), round(Resolution_Lateral_Practical_Ch1, 2), round(Resolution_Axial_Practical_Ch1, 2),
				round(Resolution_Lateral_Theoretical_Ch2, 2), round(Resolution_Axial_Theoretical_Ch2, 2), round(Resolution_Lateral_Practical_Ch2, 2), round(Resolution_Axial_Practical_Ch2, 2),
				round(Semi_Minor_Axis, 2), round(Semi_Major_Axis, 2),
				round(X_Proj, 2), round(Y_Proj, 2), round(Z_Proj, 2), round(dX_Ref, 2), round(dY_Ref, 2), round(dZ_Ref, 2),
				round(Distance_3D_Ref, 2),
				round(Colocalization_Ratio_Lateral, 1), round(Colocalization_Ratio_Axial, 1), round(Colocalization_Ratio_3D, 1)
				]+Filename_Parts)
	
	global ProcessedCSVHeader # Keep the header global  to be used for simple version of the output file

	ProcessedCSVHeader =[
				'Filename',
				'Channel 1', 'Channel 2',  'Name Channel 1', 'Name Channel 2', 'Channel Pair',
				'X Channel 1', 'Y Channel 1', 'Z Channel 1', 'X Channel 2', 'Y Channel 2', 'Z Channel 2',
				'X Shift ('+SpaceUnitPrint+')', 'Y Shift ('+SpaceUnitPrint+')', 'Z Shift ('+SpaceUnitPrint+')',
				'Pixel Width ('+SpaceUnitPrint+')', 'Pixel Height ('+SpaceUnitPrint+')', 'Pixel Depth ('+SpaceUnitPrint+')',
				'X Shift (pixels)', 'Y Shift (pixels)', 'Z Shift (pixels)',
				'Distance Lateral ('+SpaceUnitPrint+')', 'Distance Axial ('+SpaceUnitPrint+')', 'Distance 3D ('+SpaceUnitPrint+')',
				'Objective NA','Objective Immersion', 'Refractive Index',
				'EM Wavelength Channel 1 (nm)', 'EM Wavelength Channel 2 (nm)', 'Conversion Factor', 'EM Wavelength Channel 1 ('+SpaceUnitPrint+')','EM Wavelength Channel 2 ('+SpaceUnitPrint+')',
				'Nyquist Pixel Size Lateral Channel 1 ('+SpaceUnitPrint+')', 'Nyquist Pixel Size Axial Channel 1 ('+SpaceUnitPrint+')', 'Nyquist Ratio Lateral Channel 1 ('+SpaceUnitPrint+')', 'Nyquist Ratio Axial Channel 1 ('+SpaceUnitPrint+')',
				'Nyquist Pixel Size Lateral Channel 2 ('+SpaceUnitPrint+')', 'Nyquist Pixel Size Axial Channel 2 ('+SpaceUnitPrint+')', 'Nyquist Ratio Lateral Channel 2 ('+SpaceUnitPrint+')', 'Nyquist Ratio Axial Channel 2 ('+SpaceUnitPrint+')',
				'Resolution Lateral Theoretical Channel 1 ('+SpaceUnitPrint+')', 'Resolution Axial Theoretical Channel 1 ('+SpaceUnitPrint+')', 'Resolution Lateral Practical Channel 1 ('+SpaceUnitPrint+')', 'Resolution Axial Practical Channel 1 ('+SpaceUnitPrint+')',
				'Resolution Lateral Theoretical Channel 2 ('+SpaceUnitPrint+')', 'Resolution Axial Theoretical Channel 2 ('+SpaceUnitPrint+')', 'Resolution Lateral Practical Channel 2 ('+SpaceUnitPrint+')', 'Resolution Axial Practical Channel 2 ('+SpaceUnitPrint+')',
				'Distance Lateral Ref ('+SpaceUnitPrint+')', 'Distance Axial Ref ('+SpaceUnitPrint+')',
				'X Ref ('+SpaceUnitPrint+')', 'Y Ref ('+SpaceUnitPrint+')', 'Z Ref ('+SpaceUnitPrint+')',
				'X Ref Shift ('+SpaceUnitPrint+')', 'Y Ref Shift ('+SpaceUnitPrint+')', 'Z Ref Shift ('+SpaceUnitPrint+')',
				'Distance 3D Ref ('+SpaceUnitPrint+')', 'Colocalization Ratio Lateral', 'Colocalization Ratio Axial', 'Colocalization Ratio 3D'
				]
	# Add  Variable-001 to the header
	for i in range(1, Max_Filename_Variables + 1):
		ProcessedCSVHeader.append('Variable-%03d' % i)


	# Save Individual CSVs
	TrackmateSettings_Stored=Read_Preferences(TrackmateSettings_Template)
	if TrackmateSettings_Stored['ChRegistration.Trackmate.Save_Individual_CSVs']:
		IndividualOutputProcessedData_CSV_Path = Generate_Unique_Filepath(Output_Dir, Image_Info['Basename'], "Channel-Registration_Full-Data", ".csv")
		with open(IndividualOutputProcessedData_CSV_Path, 'wb') as CSVFile:
			CSVWriter = csv.writer(CSVFile, delimiter=',', lineterminator='\n')
			CSVWriter.writerow(ProcessedCSVHeader)
			for SpotData in range(0, len(ProcessedData)):
				Data = ProcessedData[SpotData]
				CSVWriter.writerow(Data)

# Save and append data to Merged Ouput
	if Image==0:
		global OutputProcessedData_CSV_Path #Keep the CSV file global to be reused at each iteration
		OutputProcessedData_CSV_Path = Generate_Unique_Filepath(Output_Dir, "Channel-Registration_Full-Data", "Merged", ".csv")
		with open(OutputProcessedData_CSV_Path, 'wb') as CSVFile:
			CSVWriter = csv.writer(CSVFile, delimiter=',', lineterminator='\n')
			CSVWriter.writerow(ProcessedCSVHeader)
			for SpotData in range(0, len(ProcessedData)):
				Data = ProcessedData[SpotData]
				CSVWriter.writerow(Data)
	else:
		global OutputProcessedData_CSV_Path
		with open(OutputProcessedData_CSV_Path, 'a') as CSVFile: # We append data
				CSVWriter = csv.writer(CSVFile, delimiter=',', lineterminator='\n')
				for SpotData in range(0, len(ProcessedData)):
					Data = ProcessedData[SpotData]
					CSVWriter.writerow(Data)
	Log_Message("Computing Ch Registration for: "+ImageName+". Done.")
	return ProcessedData



# Calculate the Nyquist Pixel Size and Nyquist Ratios
def NyquistCalculator(EMWavelength_Unit, Objective_NA, Refractive_Index, PixelWidth, PixelHeight, PixelDepth):
	Nyquist_PixelSize_Lateral = EMWavelength_Unit / (4 * Objective_NA)
	Theta  = math.asin(Objective_NA/Refractive_Index)
	Nyquist_PixelSize_Axial = EMWavelength_Unit / (2 * Refractive_Index * (1-math.cos(Theta)))
	Nyquist_Ratio_Lateral = PixelWidth / Nyquist_PixelSize_Lateral # Or Take the average of PixelWidth and Pixel Height for non square pixels
	Nyquist_Ratio_Axial = PixelDepth/Nyquist_PixelSize_Axial
	return Nyquist_PixelSize_Lateral, Nyquist_PixelSize_Axial, Nyquist_Ratio_Lateral, Nyquist_Ratio_Axial



# Compute the xy, z and xyz distances between two points. z is oriented
def Euclidean_Distance(x1, y1, z1, x2, y2, z2):
	dxy=math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
	dz= z2-z1 # Oriented Distance
	d3D=math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
	return dxy, dz, d3D


# Calculate the Resolution Theortical and Practical (weighted by the Nyquist Ratio if it is > 1
def ResolutionCalculator(EMWavelengthUnit, Objective_NA, Refractive_Index, Nyquist_Ratio_Lateral, Nyquist_Ratio_Axial):
	Resolution_Lateral_Theoretical = (0.51 * EMWavelengthUnit) / (Objective_NA) # Compute resolution based on wavelengths and NA
	# Resolution_Axial = (Refractive_Index * EMWavelengthUnit) / (Objective_NA ** 2)
	Resolution_Axial_Theoretical = (1.77 * Refractive_Index * EMWavelengthUnit) / (Objective_NA ** 2)

	# Get the Effective resolution based on the Nyquist Ratio
	if Nyquist_Ratio_Lateral>1:
		Resolution_Lateral_Practical = Nyquist_Ratio_Lateral * Resolution_Lateral_Theoretical
	else:
		Resolution_Lateral_Practical = Resolution_Lateral_Theoretical

	if Nyquist_Ratio_Axial>1:
		Resolution_Axial_Practical = Nyquist_Ratio_Axial * Resolution_Axial_Theoretical
	else:
		Resolution_Axial_Practical = Resolution_Axial_Theoretical
	return Resolution_Lateral_Theoretical, Resolution_Axial_Theoretical, Resolution_Lateral_Practical, Resolution_Axial_Practical




# Calculate the Ellipse_Ratio (equation given)
def Compute_Ellipse_Ratio(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, t):

	# Get the coordinates of a point on the Spot1 Spot2 line  for parameter t
	x, y, z = Line(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, t)

	# Compute the Ellipse Ratio value from this new point
	Ellipse_Ratio = ((x - X_Ch1)**2 / Semi_Minor_Axis**2 +
		   (y - Y_Ch1)**2 / Semi_Minor_Axis**2 +
		   (z - Z_Ch1)**2 / Semi_Major_Axis**2)
	return Ellipse_Ratio


# Calculate the xyz coordinates of a point in the Spot1 Spot2 Line depedning on t
def Line(X_Ch1,  Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, t):
	x = X_Ch1 + t * (X_Ch2 - X_Ch1)
	y = Y_Ch1 + t * (Y_Ch2 - Y_Ch1)
	z = Z_Ch1 + t * (Z_Ch2 - Z_Ch1)
	return x, y, z



# Find iteratively the coordinates xyz of a point at the intersection of the Spot1-Spot2 line and an ellipse with Minor and Major Axis characteristics and centered on Spot1
def Project_on_Ellipse(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, max_iterations, initial_step, tolerance):
	t = 0 # Starting from point X1 Y1 Z1
	step = initial_step  # Start with an initial step size

	for iteration in range(max_iterations):
		Ellipse_Ratio = Compute_Ellipse_Ratio(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, Semi_Minor_Axis, Semi_Major_Axis, t)
		if math.fabs(Ellipse_Ratio - 1.0) < tolerance:  # Close enough to 1
			# print "Found t =", t, "where Ellipse Ratio is ",Ellipse_Ratio," after ",iteration," iterations"
			Log_Message("Found t = "+str(t)+" where Ellipse Ratio = "+str(Ellipse_Ratio)+" after "+str(iteration)+" iterations")
			X_Ref, Y_Ref, Z_Ref = Line(X_Ch1, Y_Ch1, Z_Ch1, X_Ch2, Y_Ch2, Z_Ch2, t) # Retrieve the Coordinates
			#print X_Ref, Y_Ref, Z_Ref
			return X_Ref, Y_Ref, Z_Ref

		# Adjust step size
		# The smaller the difference, the smaller the step
		if Ellipse_Ratio > 1.0:
			step = step * 0.5  # Reduce step
			t -= step  # Move backwards if Ellipse_Ratio > 1
		else:
			step = step * 1.5  # Increase step
			t += step  # Move forward  if Ellipse_Ratio < 1

		# Ensure step doesn't become too small
		# step = max(step, 0.0001)  # Prevent step from becoming too small (optional)

	IJ.log( "Could not compute accurate reference point coordinates aka Ellipse Ratio further than "+str(float(1.0+tolerance))+".")
	return None



def Process_Image(imp, Image, BatchMessage): # Process an image showing the dialog and Compute Ch Registration
	# Return SpotDataAllCh, ProcessedData sotring the SpotData and The Ch registration Data
	Image_Info=Get_Image_Info(imp)
	ImageName=Image_Info['ImageName']
	IJ.log("Processing: " + ImageName + "...")
	Dialog_Counter = 0
	User_Click = None
	Test_Detection = False
	while True:
		TrackmateSettings_Stored = Read_Preferences(TrackmateSettings_Template)
		MicroscopeSettings_Stored = Read_Preferences(MicroscopeSettings_Template)
		TrackmateSettings_User, MicroscopeSettings_User, User_Click, NbDetectedSpotsPerCh, Dialog_Counter, Test_Detection, BatchMessage =  Display_Dialog(imp, Dialog_Counter, Test_Detection, BatchMessage) # Display a dialog with Metadata and results from predetection
		# Filtereing some Keys to be ignored
		TrackmateSettings_Stored_Filtered = {
			key: value for key, value in TrackmateSettings_Stored.items()
			if key not in [
				'ChRegistration.Trackmate.BatchMode',
				'ChRegistration.Trackmate.Save_Individual_CSVs',
				'ChRegistration.Trackmate.Debug'
			]}

		TrackmateSettings_User_Filtered = {
			key: value for key, value in TrackmateSettings_User.items()
			if key not in [
				'ChRegistration.Trackmate.BatchMode',
				'ChRegistration.Trackmate.Save_Individual_CSVs',
				'ChRegistration.Trackmate.Debug'
			]}
		# All conditions  must be fullfilled to  proceed
		if User_Click == "OK" and sum(NbDetectedSpotsPerCh) == Image_Info['NbChannels'] and not Test_Detection and all(Spot == 1 for Spot in NbDetectedSpotsPerCh) and TrackmateSettings_Stored_Filtered == TrackmateSettings_User_Filtered and MicroscopeSettings_User==MicroscopeSettings_Stored :
			break
		elif User_Click == "Cancel":
			IJ.log("Processing Image:" + ImageName + ". User canceled operation.")
			sys.exit(1)
	_, _, SpotDataAllCh = Run_Trackmate_All_Ch(imp, SaveFile=True, GetSpotData=True) # Running Trackmate and collect the results
	ProcessedData = Processing_Data(imp, SpotDataAllCh, Image) # Computing Ch Registration Image is the index of the image being processed when Iamge=0 CSV File is open otherwise results are added
	IJ.log("Processing: " + ImageName + ". Done.")
	return SpotDataAllCh, ProcessedData



def Process_Image_Batch(imp, SpotDataAllFiles, ProcessedImages, Image): #Process Image without Prompt Check for metadata compatibility
	# Return SpotDataAllFiles, ProcessedImages, BatchMessage
	Image_Info=Get_Image_Info(imp)
	ImageName=Image_Info['ImageName']
	NbChannels=Image_Info['NbChannels']
	IJ.log("Processing in batch: " + ImageName + "...")
	TrackmateSettings_Stored = Read_Preferences(TrackmateSettings_Template)
	MicroscopeSettings_Stored = Read_Preferences(MicroscopeSettings_Template)
	# Try to get some metadata
	Channel_Names_Metadata, Channel_WavelengthsEM_Metadata, Objective_NA_Metadata, Objective_Immersion_Metadata= Get_Metadata(imp)
	# Check if metadata and compare it with stored preferences
	BatchMessage=""
	if Channel_Names_Metadata or Channel_Names_Metadata or Objective_NA_Metadata or Objective_Immersion_Metadata:
		if float(Objective_NA_Metadata) != float(MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_NA']):
			BatchMessage=BatchMessage+"Objective NA is different. Metadata: "+str(Objective_NA_Metadata)+". Preferences: "+str(MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_NA'])+".\n"
		if str(Objective_Immersion_Metadata) != str(MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_Immersion']):
			BatchMessage=BatchMessage+"Objective Immersion is different. Metadata: "+str(Objective_Immersion_Metadata)+". Preferences: "+str(MicroscopeSettings_Stored['ChRegistration.Microscope.Objective_Immersion'])+".\n"
		if int(NbChannels) > int(len(MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names'])):
			BatchMessage=BatchMessage+"Nb of Channels do not match.\nImage: "+str(NbChannels)+". Preferences : "+str(len(MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names']))+"."
		else: # Nb of Channels is sufficient check Matching values
			if Channel_Names_Metadata != MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names'][:NbChannels]:
				BatchMessage=BatchMessage+"Channel Names are different:\nMetadata: "+", ".join(Channel_Names_Metadata)+"\nPreferences: "+", ".join(MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_Names'][:NbChannels])+".\n"
			if Channel_WavelengthsEM_Metadata != MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM'][:NbChannels]:
				BatchMessage=BatchMessage+"Channel Emission Wavelengths are different:\nMetadata: "+", ".join(map(str, Channel_WavelengthsEM_Metadata))+"\nPreferences: "+", ".join(map(str,MicroscopeSettings_Stored['ChRegistration.Microscope.Channel_WavelengthsEM'][:NbChannels]))+"."
		if BatchMessage !="":
			BatchMessage="Metadata different from Preferences.\n"+BatchMessage
			IJ.log(BatchMessage)
			Detection="Fail"
		else:
			NbDetectedSpotsPerCh, MaxQualityThresholdPerCh, SpotDataAllCh = Run_Trackmate_All_Ch(imp, SaveFile=False, GetSpotData=False) # Run Trackmate on all channels
			if sum(NbDetectedSpotsPerCh) == Image_Info['NbChannels'] and all(spot == 1 for spot in NbDetectedSpotsPerCh):
				Detection="Pass"
			else:
				Detection="Fail"
				NbDetectedSpotsPerCh_Str = [str(NbSpots) for NbSpots in NbDetectedSpotsPerCh]
				NbDetectedSpotsPerCh_String = "+ ".join(NbDetectedSpotsPerCh_Str)
				MessageDetectedSpotPerCh = "Detected spots per channel: {} = {}. Nb of Channels: {}".format(
				NbDetectedSpotsPerCh_String, sum(NbDetectedSpotsPerCh), Image_Info['NbChannels'])
				BatchMessage=("Detection failed.\n{}\n{}".format(BatchMessage, MessageDetectedSpotPerCh))
	else: # No Metadata found try with stored data
		NbDetectedSpotsPerCh, MaxQualityThresholdPerCh, SpotDataAllCh = Run_Trackmate_All_Ch(imp, SaveFile=False, GetSpotData=False) # Run Trackmate on all channels.
		if sum(NbDetectedSpotsPerCh) == Image_Info['NbChannels'] and all(spot == 1 for spot in NbDetectedSpotsPerCh):
			Detection="Pass"
		else:
			NbDetectedSpotsPerCh_Str = [str(NbSpots) for NbSpots in NbDetectedSpotsPerCh]
			NbDetectedSpotsPerCh_String = "+ ".join(NbDetectedSpotsPerCh_Str)
			MessageDetectedSpotPerCh = "Detected spots per channel: {} = {}. Nb of Channels: {}".format(
			NbDetectedSpotsPerCh_String, sum(NbDetectedSpotsPerCh), Image_Info['NbChannels'])
			BatchMessage=("Detection failed for {}.\n{}\n{}".format(ImageName, BatchMessage, MessageDetectedSpotPerCh))
			Detection="Fail"
	if Detection=="Pass":
		NbDetectedSpotsPerCh, MaxQualityThresholdPerCh, SpotDataAllCh = Run_Trackmate_All_Ch(imp, SaveFile=True, GetSpotData=True) # Run Trackmate on all channels. Re
		ProcessedData = Processing_Data(imp, SpotDataAllCh, Image)
		SpotDataAllFiles.append(SpotDataAllCh)
		ProcessedImages.append(ImageName)
		IJ.log("Success in batch processing " + ImageName + ".")
	else:
		IJ.log("Batch processing failed for " + ImageName + ".\n"+BatchMessage)
		SpotDataAllCh, ProcessedData = Process_Image(imp, Image, BatchMessage)
	 	SpotDataAllFiles.append(SpotDataAllCh)
	 	ProcessedImages.append(ImageName)
		IJ.log("Success processing " + ImageName + ".")
	return SpotDataAllFiles, ProcessedImages, BatchMessage



def Process_Image_List(Image_List, OpenedvsFolder, SpotDataAllFiles): # Process a list of opened images or a list of filepath
	# Return ProcessedImages, SpotDataAllFiles
	ProcessedImages=[] # List of processed images
	for Image, Image_File  in enumerate(Image_List):
		if OpenedvsFolder=="Opened":
			imp = WindowManager.getImage(Image_File)
			image = WindowManager.getFrame(imp.getTitle())
			image.toFront()
		elif OpenedvsFolder=="Folder":
			imp = Open_Image_Bioformats(Image_File)
		Image_Info=Get_Image_Info(imp)
		ImageName=Image_Info['ImageName']
		if Image == 0:
			SpotDataAllCh, ProcessedData = Process_Image(imp, Image, BatchMessage="") # Process the first image with a prompt
			SpotDataAllFiles.append(SpotDataAllCh)
			IJ.log("Success processing " + ImageName + ".")
			ProcessedImages.append(ImageName)
		else:
			# For subsequent images, check if batch mode is enabled
			TrackmateSettings_Stored = Read_Preferences(TrackmateSettings_Template)
			if TrackmateSettings_Stored['ChRegistration.Trackmate.BatchMode']:
				SpotDataAllFiles, ProcessedImages, BatchMessage = Process_Image_Batch(imp, SpotDataAllFiles, ProcessedImages, Image) # Process the image in batch mode
			else:
			 	SpotDataAllCh, ProcessedData = Process_Image(imp, Image, BatchMessage)
				SpotDataAllFiles.append(SpotDataAllCh)
				ProcessedImages.append(ImageName)
				IJ.log("Success processing " + ImageName + ".")
		if OpenedvsFolder=="Folder":
			imp.close()
	return ProcessedImages, SpotDataAllFiles




# We are done with functions... Getting to work now.

SpotDataAllFiles = [] # Initialize List for Storing Spot Data for All files

if not os.path.exists(Output_Dir): os.makedirs(Output_Dir) # Make sure the Ouput_Dir exists

Image_List, OpenedvsFolder = Get_Images() # Get some images Opened or Selected from a folder

ProcessedImages, SpotDataAllFiles = Process_Image_List(Image_List, OpenedvsFolder, SpotDataAllFiles) # Process the List of Images

# Save Spot Data if debug mode only
TrackmateSettings_Stored=Read_Preferences(TrackmateSettings_Template)
if TrackmateSettings_Stored['ChRegistration.Trackmate.Debug']:
	SpotDataMerged_CSV_Path = Generate_Unique_Filepath(Output_Dir, "Channel-Registration_Spot-Data", "Merged", ".csv")
	with open(SpotDataMerged_CSV_Path, 'wb') as CSVFile:
		CSVWriter = csv.writer(CSVFile, delimiter=',', lineterminator='\n')
		CSVWriter.writerow(SpotDataHeader)
		for File in range(0, len(SpotDataAllFiles)):
			SpotDataFile = SpotDataAllFiles[File]
			for ChData in SpotDataFile:
				Row=[]
				for key in SpotDataOrderedKeys:
					Row.append(ChData[key])
				CSVWriter.writerow(Row)


OutputSimplifiedData_CSV_Path = Generate_Unique_Filepath(Output_Dir, "Channel-Registration_Essential-Data", "Merged", ".csv")
# Read the full data CSV file and filter columns by index
with open(OutputProcessedData_CSV_Path, 'rb') as InputFile:
	Reader = csv.reader(InputFile, delimiter=',', lineterminator='\n')
	Header = next(Reader)
#0  Filename
#1  Channel 1
#2  Channel 2
#3  Name Channel 1
#4  Name Channel 2
#5  Channel Pair
#6  X Channel 1
#7  Y Channel 1
#8  Z Channel 1
#9  X Channel 2
#10 Y Channel 2
#11 Z Channel 2
#12 X Shift (SpaceUnitPrint)
#13 Y Shift (SpaceUnitPrint)
#14 Z Shift (SpaceUnitPrint)
#15 Pixel Width (SpaceUnitPrint)
#16 Pixel Height (SpaceUnitPrint)
#17 Pixel Depth (SpaceUnitPrint)
#18 X Shift (pixels)
#19 Y Shift (pixels)
#20 Z Shift (pixels)
#21 Distance Lateral (SpaceUnitPrint)
#22 Distance Axial (SpaceUnitPrint)
#23 Distance 3D (SpaceUnitPrint)
#24 Objective NA
#25 Objective Immersion
#26 Refractive Index
#27 EM Wavelength Channel 1 (nm)
#28 EM Wavelength Channel 2 (nm)
#29 Conversion Factor
#30 EM Wavelength Channel 1 (SpaceUnitPrint)
#31 EM Wavelength Channel 2 (SpaceUnitPrint)
#32 Nyquist Pixel Size Lateral Channel 1 (SpaceUnitPrint)
#33 Nyquist Pixel Size Axial Channel 1 (SpaceUnitPrint)
#34 Nyquist Ratio Lateral Channel 1 (SpaceUnitPrint)
#35 Nyquist Ratio Axial Channel 1 (SpaceUnitPrint)
#36 Nyquist Pixel Size Lateral Channel 2 (SpaceUnitPrint)
#37 Nyquist Pixel Size Axial Channel 2 (SpaceUnitPrint)
#38 Nyquist Ratio Lateral Channel 2 (SpaceUnitPrint)
#39 Nyquist Ratio Axial Channel 2 (SpaceUnitPrint)
#40 Resolution Lateral Theoretical Channel 1 (SpaceUnitPrint)
#41 Resolution Axial Theoretical Channel 1 (SpaceUnitPrint)
#42 Resolution Lateral Practical Channel 1 (SpaceUnitPrint)
#43 Resolution Axial Practical Channel 1 (SpaceUnitPrint)
#44 Resolution Lateral Theoretical Channel 2 (SpaceUnitPrint)
#45 Resolution Axial Theoretical Channel 2 (SpaceUnitPrint)
#46 Resolution Lateral Practical Channel 2 (SpaceUnitPrint)
#47 Resolution Axial Practical Channel 2 (SpaceUnitPrint)
#48 Semi Minor Axis (SpaceUnitPrint)
#49 Semi Major Axis (SpaceUnitPrint)
#50 X Ref (SpaceUnitPrint)
#51 Y Ref (SpaceUnitPrint)
#52 Z Ref (SpaceUnitPrint)
#53 X Ref Shift (SpaceUnitPrint)
#54 Y Ref Shift (SpaceUnitPrint)
#55 Z Ref Shift (SpaceUnitPrint)
#56 Distance 3D Ref (SpaceUnitPrint)
#57 Colocalization Ratio Lateral
#58 Colocalization Ratio Axial
#59 Colocalization Ratio 3D


	Selected_Columns = list(range(0, 6)) + [18, 19, 20, 21, 22, 23, 48, 49, 56, 57, 58, 59] # Select additional columns here
	FilenameVariableIndex = [Index for Index, value in enumerate(Header) if value.startswith('Variable-')] # Add file name variable
	if FilenameVariableIndex:
		Selected_Columns = Selected_Columns + FilenameVariableIndex

	Selected_Header = [Header[i] for i in Selected_Columns] # Transform Selected column indexes to a their respective name
	with open(OutputSimplifiedData_CSV_Path, 'wb') as OutputFile:
		Writer = csv.writer(OutputFile, delimiter=',', lineterminator='\n')
		Writer.writerow(Selected_Header) # Write the header
		for Row in Reader: # Get the data from the Saved Full data CSV File
			Selected_Row = [Row[i] for i in Selected_Columns]
			Writer.writerow(Selected_Row)


# Log the success message indicating the number of processed images
MessageProcessing = "Channel Registration with Batch Trackmate completed.\n" + str(len(ProcessedImages)) + " images have been processed successfully.\n"
MessageProcessing=MessageProcessing+"Files are saved in "+str(Output_Dir)
IJ.log(MessageProcessing)
JOptionPane.showMessageDialog(None, MessageProcessing, "Channel Registration with Batch Trackmate", JOptionPane.INFORMATION_MESSAGE)

import java.lang.System
java.lang.System.gc() # Cleaning up my mess ;-)