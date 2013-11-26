import javax.script.ScriptEngine;
import javax.script.ScriptEngineManager;
import javax.script.ScriptException;
import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.io.FileNotFoundException;


public class RunScriptDemo {

    public static void main (String[] args) {
        ScriptEngineManager manager = new ScriptEngineManager ();
        ScriptEngine engine = manager.getEngineByName ("js");
        String line;
        String script = "";

        try {
            BufferedReader reader = new BufferedReader(new FileReader(args[0]));
            while ((line = reader.readLine()) != null) {
                script += line;
            }
        } catch (IOException e) {

        }
        //String script = "eval(" + args[0] + ")";        
        try {
            engine.eval (script);
        } catch (ScriptException e) {
            e.printStackTrace();
        }
    }
}
