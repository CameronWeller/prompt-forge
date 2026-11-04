using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;

// A native Windows entry point lets the app use the same bare command name
// locally and over SSH. The actual backend and its helpers stay together.
class BackendLauncher {
    static void Pump(Stream source, Stream target) {
        var buffer = new byte[65536];
        int count;
        while ((count = source.Read(buffer, 0, buffer.Length)) > 0) {
            target.Write(buffer, 0, count);
            target.Flush();
        }
    }
    static string Quote(string value) {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') {
                result.Append('\\', slashes * 2 + 1).Append(c);
            } else {
                result.Append('\\', slashes).Append(c);
            }
            slashes = 0;
        }
        return result.Append('\\', slashes * 2).Append('"').ToString();
    }
    static int Main(string[] args) {
        try {
            string binary = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
                ".local", "share", "prompt-forge", "native", "0.166.0-alpha.6", "codex.exe");
            var command = new StringBuilder();
            foreach (string arg in args) {
                if (command.Length > 0) command.Append(' ');
                command.Append(Quote(arg));
            }
            var info = new ProcessStartInfo(binary, command.ToString());
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.RedirectStandardInput = true;
            info.RedirectStandardOutput = true;
            info.RedirectStandardError = true;
            using (var process = Process.Start(info)) {
                Task.Factory.StartNew(() => {
                    try { Pump(Console.OpenStandardInput(), process.StandardInput.BaseStream); }
                    catch (IOException) { }
                    finally { try { process.StandardInput.Close(); } catch { } }
                });
                var output = Task.Factory.StartNew(() => Pump(process.StandardOutput.BaseStream, Console.OpenStandardOutput()));
                var errors = Task.Factory.StartNew(() => Pump(process.StandardError.BaseStream, Console.OpenStandardError()));
                process.WaitForExit();
                Task.WaitAll(output, errors);
                return process.ExitCode;
            }
        } catch {
            Console.Error.WriteLine("Prompt Forge backend could not start. Check its installation.");
            return 1;
        }
    }
}
