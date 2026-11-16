"""Run a packaged exe safely: no console window, no Python on PATH, output to files,
the whole process tree killed after a timeout."""
import os, subprocess, sys, time
exe, *args = sys.argv[1:]
env = {k: v for k, v in os.environ.items() if k.upper() not in ("PATH", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "QT_PLUGIN_PATH")}
env["PATH"] = r"C:\Windows\System32;C:\Windows"
for run in (1, 2):
    with open("exe-out.txt", "w") as out, open("exe-err.txt", "w") as err:
        t = time.perf_counter()
        p = subprocess.Popen([exe, *args], env=env, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
        while p.poll() is None and time.perf_counter() - t < 60:
            time.sleep(0.05)
        elapsed = time.perf_counter() - t
        if p.poll() is None:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            print(f"run {run}: TIMEOUT after {elapsed:.0f}s, tree killed"); break
    print(f"run {run}: exit {p.returncode} in {elapsed:.2f}s")
    if p.returncode:
        print(open("exe-err.txt").read()[-1500:]); break
