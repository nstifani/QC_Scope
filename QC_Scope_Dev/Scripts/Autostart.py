# Function written by Nicolas Stifani nstifani@gmail.com for more info
import os
from ij import IJ, Prefs
from java.awt import Window
from javax.swing import SwingUtilities, JFrame, JOptionPane, JDialog

# Defines Global Variables
Plugin_Name = "QC Scope"
Function_Name = "Autostart"

def Check_Autostart_Status(Plugin_Name, Function_Name):
	Autostart_Directory = IJ.getDirectory("imagej") + "macros/AutoRun/"
	Autostart_File_Name = "{} {}.ijm".format(Plugin_Name, Function_Name)
	Autostart_File_Path = os.path.join(Autostart_Directory, Autostart_File_Name)
	return os.path.exists(Autostart_File_Path)

def Activate_Autostart(Plugin_Name, Function_Name):
	Autostart_Directory = IJ.getDirectory("imagej") + "macros/AutoRun/"
	Autostart_File_Name = "{} {}.ijm".format(Plugin_Name, Function_Name)
	Autostart_File_Path = os.path.join(Autostart_Directory, Autostart_File_Name)
	if not os.path.exists(Autostart_Directory):
		os.makedirs(Autostart_Directory)
	with open(Autostart_File_Path, "w") as Autostart_File:
		Autostart_File.write('run("QC Scope Toolbar");\n')

def Remove_Autostart(Plugin_Name, Function_Name):
	Autostart_Directory = IJ.getDirectory("imagej") + "macros/AutoRun/"
	Autostart_File_Name = "{} {}.ijm".format(Plugin_Name, Function_Name)
	Autostart_File_Path = os.path.join(Autostart_Directory, Autostart_File_Name)
	if os.path.exists(Autostart_Directory):
		os.remove(Autostart_File_Path)

def Display_Message(Plugin_Name, Function_Name, Message):
	JOptionPane.showMessageDialog(None, Message, "{} {}".format(Plugin_Name, Function_Name), JOptionPane.INFORMATION_MESSAGE)

def Display_Options(Plugin_Name, Function_Name, Message, Option_List, Message_Type, Default_Option):
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
		"{} {}".format(Plugin_Name, Function_Name),
		JOptionPane.DEFAULT_OPTION,
		Message_Type,
		None,
		Option_List,
		Default_Option
	)
	Option_Choice = Option_List[Option_Choice_Index]
	return Option_Choice

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
	




def Main(Plugin_Name, Function_Name):
	Autostart_Status = Check_Autostart_Status(Plugin_Name, Function_Name)
	if Autostart_Status:
		Message = "{} {} is active.".format(Plugin_Name, Function_Name)
		Option_List = ["Inactivate", "Keep it", "Cancel"]
		Option_Choice = Display_Options(Plugin_Name, Function_Name, Message, Option_List, "Info", Default_Option = "Keep it")
	else:
		Message = "{} {} is not active.".format(Plugin_Name, Function_Name)
		Option_List = ["Activate", "Keep it inactive", "Cancel"]
		Option_Choice = Display_Options(Plugin_Name, Function_Name, Message, Option_List, "Info", Default_Option = "Activate")
	
	if Option_Choice == "Inactivate":
		Remove_Autostart(Plugin_Name, Function_Name)
		Message = "{} {} will no longer start with ImageJ.".format(Plugin_Name, Function_Name)
		Display_Message(Plugin_Name, Function_Name, Message)
	elif Option_Choice == "Activate":
		Activate_Autostart(Plugin_Name, Function_Name)
		if not Check_Window("{} {}".format(Plugin_Name, "Toolbar")):
			IJ.run("{} {}".format(Plugin_Name, "Toolbar"), "")
	elif Option_Choice == "Cancel":
		Message = "User clicked Cancel"
		IJ.log(Message)

Main(Plugin_Name, Function_Name)