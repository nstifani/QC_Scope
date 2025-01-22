# Written by Nicolas Stifani nstifani@gmail.com for info

# Import General Features
import os
import sys
import csv
from math import sqrt, floor, asin, cos, fabs

# Import ImageJ Features
from ij import IJ, ImagePlus, Prefs, WindowManager
from ij.process import ImageProcessor, FloatProcessor, ByteProcessor, ImageStatistics, ImageConverter
from ij.gui import Overlay, TextRoi
from ij.plugin import Duplicator, Zoom
from ij.measure import Measurements, ResultsTable
from ij.plugin.frame import RoiManager
from ij.plugin.filter import GaussianBlur
from ij.macro import MacroRunner

# Import Bioformat Features
from loci.plugins import BF
from loci.plugins.in import ImporterOptions
from loci.formats import MetadataTools, ImageReader

# Import Java Features
from java.io import File
from java.awt import Font, Color, GridLayout, GridBagLayout, GridBagConstraints, Insets, Frame, Panel, Button, Label, Toolkit, Window
from javax.swing import JOptionPane, JFileChooser, JTextField, JLabel, JSeparator, JRadioButton, ButtonGroup, JSlider,JButton, JCheckBox, JPanel, JFrame, SwingUtilities, JDialog
from java.awt.event import ActionListener
from javax.swing.event import ChangeListener, DocumentListener
import java.lang.System

# Import TrackMate features
from fiji.plugin.trackmate import Model, Settings, TrackMate, SelectionModel, Logger
from fiji.plugin.trackmate.detection import DogDetectorFactory, LogDetectorFactory
from fiji.plugin.trackmate.tracking.jaqaman import SparseLAPTrackerFactory
from fiji.plugin.trackmate.features import FeatureFilter
from fiji.plugin.trackmate.features.track import TrackIndexAnalyzer
from fiji.plugin.trackmate.gui.displaysettings import DisplaySettingsIO
from fiji.plugin.trackmate.visualization.table import TrackTableView, AllSpotsTableView
from fiji.plugin.trackmate.visualization.hyperstack import HyperStackDisplayer


# -*- coding: utf-8 -*-
reload(sys)
sys.setdefaultencoding("utf-8")


# Defining some constants
Plugin_Name = "QC Scope"
Function_Name = "Toolbar"

def Check_Window(Window_Title):
	Windows = Window.getWindows()
	for Opened_Window in Windows:
		try:
			if isinstance(Opened_Window, (JFrame, JDialog)) and Opened_Window.isVisible():
				Opened_Window_Title = Opened_Window.getTitle()
				if Window_Title in Opened_Window_Title:
					return True
		except AttributeError:
			continue
	return False

# Display a Dialog when Processing an image excepted in Batch_Mode
# Return Ch_Alignment_Settings_User, Microscope_Settings_User, User_Click, Dialog_Counter, Test_Processing, Batch_Message
# The Dialog uses Javax Swing and takes some lines... Sorry...
def Start_Toolbar():

	# Create the Dialog. Sorry it is long and messy but looks good huh?
	Toolbar_Dialog = JDialog(None, "{} {}".format(Plugin_Name, Function_Name), False)  # "True" makes it modal
	Toolbar_Panel = JPanel()
	Toolbar_Panel.setLayout(GridBagLayout())
	Constraints = GridBagConstraints()
	Pos_X = 0
	Pos_Y = 0

	# Uniformity Button
	Field_Uniformity_Button = JButton("Uniformity")
	def On_Field_Uniformity(Event):
		# Create a MacroRunner instance and run the script because runninn directly does not work
		Field_Uniformity_Macro = 'run("Field Uniformity");'
		Field_Uniformity_Runner = MacroRunner()
		Field_Uniformity_Runner.run(Field_Uniformity_Macro)
		return

	Field_Uniformity_Button.addActionListener(On_Field_Uniformity)
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.weightx = 1.0
	Constraints.fill = GridBagConstraints.HORIZONTAL
	Constraints.insets = Insets(2, 2, 2, 2)
	Toolbar_Panel.add(Field_Uniformity_Button, Constraints)

	# Ch Alignment Button
	Ch_Alignment_Button = JButton("Ch Alignment")
	def On_Ch_Alignment(Event):
		Ch_Alignement_Macro = 'run("Ch Alignment");'
		Ch_Alignement_Runner = MacroRunner()
		Ch_Alignement_Runner.run(Ch_Alignement_Macro)
		return
	Ch_Alignment_Button.addActionListener(On_Ch_Alignment)
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.weightx = 1.0
	Constraints.fill = GridBagConstraints.HORIZONTAL
	Constraints.insets = Insets(2, 2, 2, 2)
	Toolbar_Panel.add(Ch_Alignment_Button, Constraints)

	Pos_Y += 1

	# Autostart Button
	Autostart_Button = JButton("Autostart")
	def On_Autostart(Event):
		QCScope_Autostart_Macro = 'run("QC Scope Toolbar Autostart");'
		QCScope_Autostart_Runner = MacroRunner()
		QCScope_Autostart_Runner.run(QCScope_Autostart_Macro)
		#IJ.run("QC Scope Toolbar Autostart");
		return

	Autostart_Button.addActionListener(On_Autostart)
	Constraints.gridx = Pos_X
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.weightx = 1.0
	Constraints.fill = GridBagConstraints.HORIZONTAL

	Constraints.insets = Insets(2, 2, 2, 2)
	Toolbar_Panel.add(Autostart_Button, Constraints)


	# Cancel Button
	Close_Button = JButton("Close")
	def On_Close(Event):
		Toolbar_Dialog.dispose()
		return

	Close_Button.addActionListener(On_Close)
	Constraints.gridx = Pos_X + 1
	Constraints.gridy = Pos_Y
	Constraints.gridwidth = 1
	Constraints.gridheight = 1
	Constraints.anchor = GridBagConstraints.CENTER
	Constraints.weightx = 1.0
	Constraints.fill = GridBagConstraints.HORIZONTAL
	Constraints.insets = Insets(2, 2, 2, 2)
	Toolbar_Panel.add(Close_Button, Constraints)
	Toolbar_Dialog.add(Toolbar_Panel)
	Toolbar_Dialog.pack()
	Screen_Size = Toolkit.getDefaultToolkit().getScreenSize()
	Screen_Width = Screen_Size.width
	Screen_Height = Screen_Size.height
	Toolbar_Dialog.setLocation(Screen_Width/2, 0)
	Toolbar_Dialog.setVisible(True)
	return


if not Check_Window("{} {}".format(Plugin_Name, "Toolbar")):
	Start_Toolbar()
