# Windows desktop build

Build the Windows application on a Windows x64 host with Python 3.12:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\packaging\windows\build.ps1
```

The script creates an isolated environment, installs dependencies from
`uv.lock` with hashes, runs all source-quality gates, builds Python
distributions and the PyInstaller one-folder application, exercises the source
and packaged GUI, inventories licences, and writes a versioned ZIP, checksum,
and native evidence.

The build environment contains Python by definition and cannot satisfy the
clean-machine gate. Extract the resulting ZIP on a separate Windows x64 account
with no `python`, `python3`, or `py` command and run:

```powershell
.\validation\clean_machine_test.ps1
```

Copy the resulting `windows_clean_machine.json` into the release-evidence
directory without editing it.

PyInstaller is not a cross-compiler. A Windows executable must therefore be
created and tested on Windows. The GitHub Actions workflow
`.github/workflows/windows-build.yml` automates the same process on
`windows-2022`.

Successful Windows packaging satisfies only the `windows_build` gate.
Clean-machine execution, native Abaqus import and analysis, and the
user-acceptance protocol remain mandatory for a new native binary or
maintenance release. See `packaging/abaqus/README.md` and
`docs/developer_guide/release_process.md`.

The version is read from the installed package. A `0.9.0rc1` archive must never
be renamed to `1.0.0`; rebuild from the exact stable source instead.
