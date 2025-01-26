# Function written by Nicolas Stifani nstifani@gmail.com for more info
import os
from ij import IJ
from javax.swing import JOptionPane
from java.awt import Window
# Constants
PLUGIN_NAME = "QC Scope"
FUNCTION_NAME = "Autostart"

def check_running_app():
	"""Check if ImageJ or FIJI is running."""
	windows = Window.getWindows()
	for window in windows:
		if window.isVisible():
			title = window.getTitle()
			if "(Fiji Is Just) ImageJ" in title:
				running_app="FIJI"
				return running_app
	running_app="ImageJ"
	return running_app

def read_imagej_startup_macro():
	startup_macro_path = IJ.getDirectory("macros") + "RunAtStartup.ijm"
	try:
		with open(startup_macro_path, 'r') as file:
			startup_macro_content = file.read()
			if 'run("QC Scope Toolbar");' in startup_macro_content:
				autostart_status = True
			else:
				autostart_status = False
			return autostart_status
	except Exception as e:
		IJ.log("Error reading startup macro: " + str(e))
		return False

def check_autostart_status(plugin_name, function_name):
	"""Check if the autostart script exists."""
	running_app = check_running_app()
	if running_app == "FIJI":
		autostart_file_path = os.path.join(IJ.getDirectory("imagej"), "macros/AutoRun", "{} {}.ijm".format(plugin_name, function_name))
		if  os.path.exists(autostart_file_path):
			autostart_status = True
		else:
			autostart_status = False
	else:
		autostart_status = read_imagej_startup_macro()
	return autostart_status

def activate_autostart(plugin_name, function_name):
	"""Activate autostart by creating the appropriate script."""
	running_app = check_running_app()
	if running_app == "FIJI":
		if not os.path.exists(os.path.join(IJ.getDirectory("imagej"), "macros/AutoRun")):
			os.makedirs(IJ.getDirectory("imagej"), "macros/AutoRun")
		autostart_file_path = os.path.join(IJ.getDirectory("imagej"), "macros/AutoRun", "{} {}.ijm".format(plugin_name, function_name))
		with open(autostart_file_path, "w") as autostart_file:
			autostart_file.write('run("QC Scope Toolbar");\n')
	else:
		startup_macro_path = IJ.getDirectory("macros") + "RunAtStartup.ijm"
		with open(startup_macro_path, 'r') as file:
			startup_macro_content = file.read()
		startup_macro_new_content = startup_macro_content + 'run("QC Scope Toolbar");\n'
		with open(startup_macro_path, 'w') as file_write:
			file_write.write(startup_macro_new_content)

def remove_autostart(plugin_name, function_name):
	"""Remove the autostart script if it exists."""
	running_app = check_running_app()
	if running_app == "FIJI":
		autostart_file_path = os.path.join(IJ.getDirectory("imagej"), "macros/AutoRun", "{} {}.ijm".format(plugin_name, function_name))
		if os.path.exists(autostart_file_path):
			os.remove(autostart_file_path)
	else:
		startup_macro_path = IJ.getDirectory("macros") + "RunAtStartup.ijm"
		with open(startup_macro_path, 'r') as file:
			startup_macro_content = file.read()
		if 'run("QC Scope Toolbar");' in startup_macro_content:
			startup_macro_new_content = startup_macro_content.replace('run("QC Scope Toolbar");', '')
			with open(startup_macro_path, 'w') as file_write:
	 			file_write.write(startup_macro_new_content)

def display_message(plugin_name, function_name, message):
	"""Display a simple message dialog."""
	JOptionPane.showMessageDialog(None, message, "{} {}".format(plugin_name, function_name), JOptionPane.INFORMATION_MESSAGE)

def display_options(plugin_name, function_name, message, option_list, message_type="Info", default_option=None):
	"""Display a dialog with selectable options."""
	message_types = {
		"Error": JOptionPane.ERROR_MESSAGE,
		"Info": JOptionPane.INFORMATION_MESSAGE,
		"Warning": JOptionPane.WARNING_MESSAGE,
		"Question": JOptionPane.QUESTION_MESSAGE
	}
	message_type = message_types.get(message_type, JOptionPane.INFORMATION_MESSAGE)

	option_choice_index = JOptionPane.showOptionDialog(
		None,
		message,
		"{} {}".format(plugin_name, function_name),
		JOptionPane.DEFAULT_OPTION,
		message_type,
		None,
		option_list,
		default_option
	)
	return option_list[option_choice_index] if option_choice_index != -1 else None

def check_window(window_title):
	"""Check if a window with the given title is open and visible."""
	from java.awt import Window
	from javax.swing import JFrame, JDialog
	windows = Window.getWindows()
	for opened_window in windows:
		try:
			if isinstance(opened_window, (JFrame, JDialog)) and opened_window.isVisible():
				if window_title in opened_window.getTitle():
					return True
		except AttributeError:
			continue
	return False

# Main function
def main(plugin_name, function_name):
	"""Main logic to manage the autostart feature."""
	autostart_status = check_autostart_status(plugin_name, function_name)
	if autostart_status:
		message = "{} {} is active.".format(plugin_name, function_name)
		option_list = ["Inactivate", "Keep it", "Cancel"]
		option_choice = display_options(plugin_name, function_name, message, option_list, "Info", "Keep it")
	else:
		message = "{} {} is not active.".format(plugin_name, function_name)
		option_list = ["Activate", "Keep it inactive", "Cancel"]
		option_choice = display_options(plugin_name, function_name, message, option_list, "Info", "Activate")

	if option_choice == "Inactivate":
		remove_autostart(plugin_name, function_name)
		message = "{} {} will no longer start with ImageJ.".format(plugin_name, function_name)
		display_message(plugin_name, function_name, message)
	elif option_choice == "Activate":
		activate_autostart(plugin_name, function_name)
		if not check_window("{} Toolbar".format(plugin_name)):
			IJ.run("{} Toolbar".format(plugin_name), "")
	elif option_choice == "Cancel":
		message = "User clicked Cancel"
		# IJ.log(message)  # Optional logging

# Run the main function
main(PLUGIN_NAME, FUNCTION_NAME)
