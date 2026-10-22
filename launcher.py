"""Entry point of WInLabAdmin.exe.

The exe only carries Python and the libraries. The actual program is admin.py / build.py in the
folder next to the exe, so when those files are updated from GitHub the exe uses the new code
without being rebuilt. (Copies of both are bundled as a fallback if the files are missing.)
"""
import importlib, importlib.util, os, sys, traceback

ROOT = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))


def load(name):
    path = os.path.join(ROOT, name + ".py")
    if os.path.exists(path):
        try:
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            traceback.print_exc()
            print(f"[!] {name}.py in this folder could not be loaded; using the built-in copy.")
            sys.modules.pop(name, None)
    return importlib.import_module(name)


if __name__ == "__main__":
    try:
        load("admin").main(ROOT)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        input("\nSomething went wrong (details above). Press Enter to close.")
