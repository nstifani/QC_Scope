import ij.*;
import ij.plugin.*;
import java.io.*;
import org.python.util.PythonInterpreter;
import org.python.core.*;
import java.io.InputStreamReader;
import java.io.BufferedReader;
import java.nio.charset.StandardCharsets;

public class QC_Scope implements PlugIn {

    String Path_in_Jar = "/Scripts/";
    static boolean showArgs = true;

	public void run(String arg) {
        String msg = "";
        if (arg.equals("Field_Uniformity")) {
            Uniformity(); return;
        } else if (arg.equals("Ch_Alignment")) {
            Alignment(); return;
        } else if (arg.equals("QCScope_Autostart")) {
            Autostart(); return;
        } else if (arg.equals("QCScope_Toolbar")) {
            Toolbar(); return;
        }
    }

    public void Uniformity() {
        String Script_Path = Path_in_Jar + "Field_Uniformity.py";
        if (!Script_Path.isEmpty()) {
            Run_Python_Script(Script_Path);
        }
    }

    public void Alignment() {
        String Script_Path = Path_in_Jar + "Ch_Alignment.py";
        if (!Script_Path.isEmpty()) {
            Run_Python_Script(Script_Path);
        }
    }

    public void Autostart() {
        String Script_Path = Path_in_Jar + "Autostart.py";
        if (!Script_Path.isEmpty()) {
            Run_Python_Script(Script_Path);
        }
    }

    public void Toolbar() {
        String Script_Path = Path_in_Jar + "QC_Scope_Toolbar.py";
        if (!Script_Path.isEmpty()) {
            Run_Python_Script(Script_Path);
        }
    }

    public void Run_Python_Script(String Script_Path) {
        InputStream Script_Stream = getClass().getResourceAsStream(Script_Path);
        if (Script_Stream == null) {
            IJ.error("Error: Script not found in JAR file: " + Script_Path);
            return;
        }
        PythonInterpreter Python_Interpreter = new PythonInterpreter();
        try (BufferedReader Script_Reader = new BufferedReader(new InputStreamReader(Script_Stream, StandardCharsets.UTF_8))) {
            StringBuilder Script_Content = new StringBuilder();
            String Line;
            while ((Line = Script_Reader.readLine()) != null) {
                Script_Content.append(Line).append("\n");
            }
            Python_Interpreter.exec(Script_Content.toString());
        } catch (Exception e) {
            IJ.error("Error running the Python script: " + e.getMessage());
        }
    }
}
