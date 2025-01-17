import ij.*;
import ij.process.*;
import ij.gui.*;
import ij.plugin.*;
//import ij.text.TextWindow;
//import ij.io.Opener;
//import java.awt.*;
import java.io.*;
//import java.net.*;
//import java.awt.image.IndexColorModel;
import org.python.util.PythonInterpreter;
import org.python.core.*;
//import java.io.InputStreamReader;
//import java.io.BufferedReader;
import java.nio.charset.StandardCharsets;

public class QC_Scope implements PlugIn {
	
    String pathInJar = "/Scripts/";
    static boolean showArgs = true;

    public void run(String arg) {
        String msg = "";
        if (arg.equals("Field Uniformity")) {
            Uniformity(); return;
        }
        else if (arg.equals("Ch Alignment")) {
            Ch_Alignment(); return;
        }
        else if (arg.equals("Toggle Autostart")) {
            Toggle_Autostart(); return;
        }
    }

    public void Uniformity() {
        String scriptPath = pathInJar + "Field_Uniformity.py";
        if (!scriptPath.isEmpty()) {
            runPythonScript(scriptPath);
        }
    }

    public void Ch_Alignment() {
        String scriptPath = pathInJar + "Ch_Alignment.py";
        if (!scriptPath.isEmpty()) {
            runPythonScript(scriptPath);
        }
    }
	
	public void Toggle_Autostart() {
	  	String scriptPath = pathInJar + "Toggle_Autostart.py";
	     if (!scriptPath.isEmpty()) {
	            runPythonScript(scriptPath);
        }
    }


	
	public void runPythonScript(String ScriptPath) {
	    InputStream inputStream = getClass().getResourceAsStream(ScriptPath);
	    if (inputStream == null) {
	        IJ.error("Error: Script not found in JAR file: " + ScriptPath);
	        return;
	    }
	    PythonInterpreter interpreter = new PythonInterpreter();
	    try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
	        StringBuilder scriptContent = new StringBuilder();
	        String line;
	        while ((line = reader.readLine()) != null) {
	            scriptContent.append(line).append("\n");
	        }
	        interpreter.exec("import sys");
	        interpreter.exec("reload(sys)");
	        interpreter.exec("sys.setdefaultencoding('utf-8')");
	        interpreter.exec(scriptContent.toString());
	    } catch (Exception e) {
	        IJ.error("Error running the Python script: " + e.getMessage());
	    }
	}
}
