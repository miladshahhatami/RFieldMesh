# Third-party notices

RFieldMesh is distributed under BSD-3-Clause. A desktop distribution also
contains third-party software under its own terms.

The principal runtime components are:

| Component | Principal licence |
|---|---|
| NumPy | BSD-3-Clause |
| SciPy | BSD-3-Clause |
| Pydantic | MIT |
| Typer | MIT |
| Plotly.py | MIT |
| PySide6 / Qt for Python | LGPL-3.0-only, GPL-3.0-only, or commercial terms |
| PyInstaller bootloader | GPL-2.0-or-later with a distribution exception |

The Windows build generates `PYTHON_PACKAGE_LICENCES.txt` from the exact
installed environment and places it beside this notice. The distribution also
includes `LGPL-3.0.txt` and `GPL-3.0.txt`.

## Qt for Python

The community-edition Windows build uses PySide6 and Qt for Python under the
GNU Lesser General Public License, version 3. Qt is loaded through separate
shared-library files in the one-folder distribution. Those files are not
modified by RFieldMesh and may be replaced with interface-compatible builds.
RFieldMesh imposes no contractual restriction on reverse engineering for the
purpose of debugging a user modification to those libraries.

The exact PySide6, PySide6 Addons, PySide6 Essentials, shiboken6, and Qt
versions are listed in `PYTHON_PACKAGE_LICENCES.txt` and the release evidence.
Corresponding upstream sources are published by the Qt Company through
<https://code.qt.io/cgit/pyside/pyside-setup.git/> and
<https://code.qt.io/cgit/qt/>. Build and installation information is retained
in the RFieldMesh source distribution, `uv.lock`, PyInstaller specification,
and Windows build script.

RFieldMesh itself remains BSD-3-Clause licensed. The LGPL terms apply to the
covered Qt libraries, not by themselves to independent RFieldMesh source code.

Redistributors remain responsible for retaining these notices and complete
licence texts, preserving the shared-library replacement mechanism, and
satisfying the applicable terms of every bundled dependency.
