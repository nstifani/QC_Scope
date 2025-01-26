# Written by Nicolas Stifani nstifani@gmail.com for info

# Import General Features
import sys
reload(sys)
sys.setdefaultencoding("utf-8")

# Import ImageJ Features
from ij import IJ, WindowManager
from ij.macro import MacroRunner

# Import Java Features
from java.awt import GridBagLayout, GridBagConstraints, Toolkit, Insets, Window
from javax.swing import JFrame, JDialog, JPanel, JButton
from java.awt.event import ActionListener

# Constants
PLUGIN_NAME = "QC Scope"
FUNCTION_NAME = "Toolbar"

# Helper Functions
def check_window(window_title):
    """Check if a window with the given title is open and visible."""
    for opened_window in Window.getWindows():
        try:
            if isinstance(opened_window, (JFrame, JDialog)) and opened_window.isVisible():
                if window_title in opened_window.getTitle():
                    return True
        except AttributeError:
            continue
    return False

def add_button(panel, text, constraints, action_listener, pos_x, pos_y):
    """Helper to create and add a button to a panel with constraints."""
    button = JButton(text)
    button.addActionListener(action_listener)
    constraints.gridx = pos_x
    constraints.gridy = pos_y
    constraints.gridwidth = 1
    constraints.gridheight = 1
    constraints.anchor = GridBagConstraints.CENTER
    constraints.weightx = 1.0
    constraints.fill = GridBagConstraints.HORIZONTAL
    constraints.insets = Insets(2, 2, 2, 2)
    panel.add(button, constraints)
    return button

def start_toolbar():
    """Create and display the QC Scope Toolbar."""
    toolbar_dialog = JDialog(None, "{0} {1}".format(PLUGIN_NAME, FUNCTION_NAME), False)
    toolbar_panel = JPanel()
    toolbar_panel.setLayout(GridBagLayout())

    constraints = GridBagConstraints()

    # Add "Field Uniformity" button
    add_button(
        toolbar_panel,
        "Uniformity",
        constraints,
        lambda event: MacroRunner().run('run("Field Uniformity");'),
        pos_x=0,
        pos_y=0
    )

    # Add "Ch Alignment" button
    add_button(
        toolbar_panel,
        "Ch Alignment",
        constraints,
        lambda event: MacroRunner().run('run("Ch Alignment");'),
        pos_x=1,
        pos_y=0
    )

    # Add "Autostart" button
    add_button(
        toolbar_panel,
        "Autostart",
        constraints,
        lambda event: MacroRunner().run('run("QC Scope Toolbar Autostart");'),
        pos_x=0,
        pos_y=1
    )

    # Add "Close" button
    add_button(
        toolbar_panel,
        "Close",
        constraints,
        lambda event: toolbar_dialog.dispose(),
        pos_x=1,
        pos_y=1
    )

    # Configure and display the dialog
    toolbar_dialog.add(toolbar_panel)
    toolbar_dialog.pack()
    screen_size = Toolkit.getDefaultToolkit().getScreenSize()
    toolbar_dialog.setLocation(screen_size.width // 2, 0)
    toolbar_dialog.setVisible(True)

# Main Execution
if not check_window("{0} {1}".format(PLUGIN_NAME, FUNCTION_NAME)):
    start_toolbar()
