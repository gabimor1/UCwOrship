# UCwOrship

Worship songs presenter and projector by UCO Galilee.

## Installation

### Prerequisite: tkinter

You must have **Python>=3.11** installed with the [tkinter](https://docs.python.org/3/library/tkinter.html) extension module.
It is automatically included in the Windows installation, and in the system Python in other systems.

If you use a custom installation, e.g. via Homebrew for MacOS, then you may need to specifically install it.
For example, with Homebrew, you need to do
```shell
brew install tcl-tk
brew reinstall python3 --with-tcl-tk
echo 'export PATH="/opt/homebrew/opt/tcl-tk/bin:$PATH"' >> ~/.zprofile
export LDFLAGS="-L/opt/homebrew/opt/tcl-tk/lib"
export CPPFLAGS="-I/opt/homebrew/opt/tcl-tk/include"
```

To check your installation, run
```shell
python3 -m tkinter
```

### Building the dependencies

Run the following command to install UCwOrship and its dependencies:
```shell
pip3 install -e .
```

**Note:** It is of course always a good idea to use a Python virtual environment. To use the standard method, run this before installing anything:
```shell
python3 -m venv .venv
source .venv/bin/activate
```

Then you can just run
```shell
pip install -e .
```
without specifying the version, as it is implied by the environment.

_Hint: If you use PyCharm IDE, you might need to use the old editable mode for the IDE to resolve imports of `ucworship`.
This is done by appending the flag `--config-settings editable_mode=compat` to the command above._

### Running

Run UCwOrship using
```shell
python3 -m ucworship
```

If you are currently in an activated virtual environment, then you do not have to specify the Python version:
```shell
python -m ucworship
```
