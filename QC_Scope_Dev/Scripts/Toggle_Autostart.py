# Function written by Nicolas Stifani nstifani@gmail.com for more info
import os
from ij import IJ, Prefs
from ij.gui import GenericDialog
from javax.swing import JOptionPane

# Defines Global Variables
Plugin_Name = "QC Scope"
Function_Name = "Autostart"

def Check_Autostart_Status(Plugin_Name, Function_Name):
	Autostart_Directory = IJ.getDirectory("imagej") + "macros/AutoRun/"
	Autostart_File_Name = Plugin_Name + "_" + Function_Name + ".ijm"
	Autostart_File_Path = os.path.join(Autostart_Directory, Autostart_File_Name)
	return os.path.exists(Autostart_File_Path)

def Activate_Autostart(Plugin_Name, Function_Name):
	Autostart_Directory = IJ.getDirectory("imagej") + "macros/AutoRun/"
	Autostart_File_Name = Plugin_Name + "_" + Function_Name + ".ijm"
	Autostart_File_Path = os.path.join(Autostart_Directory, Autostart_File_Name)
	if not os.path.exists(Autostart_Directory):
		os.makedirs(Autostart_Directory)
	with open(Autostart_File_Path, "w") as Autostart_File:
		Autostart_File.write('run("QC Scope Toolbar");\n')

def Remove_Autostart(Plugin_Name, Function_Name):
	Autostart_Directory = IJ.getDirectory("imagej") + "macros/AutoRun/"
	Autostart_File_Name = Plugin_Name + "_" + Function_Name + ".ijm"
	Autostart_File_Path = os.path.join(Autostart_Directory, Autostart_File_Name)
	os.remove(Autostart_File_Path)

def Display_Message(Plugin_Name, Function_Name, Message):
	JOptionPane.showMessageDialog(None, Message, Plugin_Name + " " + Function_Name, JOptionPane.INFORMATION_MESSAGE)

def Display_Options(Plugin_Name, Function_Name, Message, Option_List, Message_Type, Default_Option_Index):
	if Message_Type == "Error":
		Message_Type = JOptionPane.ERROR_MESSAGE
	if Message_Type == "Info":
		Message_Type = JOptionPane.INFORMATION_MESSAGE
	if Message_Type == "Warning":
		Message_Type = JOptionPane.WARNING_MESSAGE
	if Message_Type == "Question":
		Message_Type = JOptionPane.QUESTION_MESSAGE

	Option_Choice_Index = JOptionPane.showOptionDialog(None,
		Message,
		Plugin_Name + " " + Function_Name,
		JOptionPane.DEFAULT_OPTION,
		Message_Type,
		None,
		Option_List,
		Default_Option_Index
	)
	Option_Choice = Option_List[Option_Choice_Index]
	return Option_Choice

def Main(Plugin_Name, Function_Name):
	Autostart_Status = Check_Autostart_Status(Plugin_Name, Function_Name)
	if Autostart_Status:
		Message = Plugin_Name + " " + Function_Name + " is active."
		Option_List = ["Inactivate", "Keep it", "Cancel"]
		Option_Choice = Display_Options(Plugin_Name, Function_Name, Message, Option_List, "Info", Default_Option_Index = 1)	
	else:
		Message = Plugin_Name + " " + Function_Name + " is not active."
		Option_List = ["Activate", "Keep it inactive", "Cancel"]
		Option_Choice = Display_Options(Plugin_Name, Function_Name, Message, Option_List, "Info", Default_Option_Index = 0)
	
	if Option_Choice == "Inactivate":
		Remove_Autostart(Plugin_Name, Function_Name)
		Message = Plugin_Name + " will no longer start with ImageJ."
		Display_Message(Plugin_Name, Function_Name, Message)
	elif Option_Choice == "Activate":
		Activate_Autostart(Plugin_Name, Function_Name)
		IJ.run("QC Scope Toolbar", "")
	elif Option_Choice == "Cancel":
		Message = "User clicked Cancel"
		IJ.log(Message)

Main(Plugin_Name, Function_Name)