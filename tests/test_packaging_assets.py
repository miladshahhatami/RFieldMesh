"""Release-packaging asset consistency tests."""

import importlib.util
import json
import tomllib
from pathlib import Path
from types import ModuleType

from rfieldmesh import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_entry_points_and_windows_build_assets_are_present() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert (
        pyproject["project"]["gui-scripts"]["rfieldmesh-gui"] == "rfieldmesh.gui.application:main"
    )
    desktop = pyproject["project"]["optional-dependencies"]["desktop"]
    assert any(requirement.startswith("PySide6") for requirement in desktop)
    assert any(requirement.startswith("plotly") for requirement in desktop)

    specification = ROOT / "packaging" / "pyinstaller" / "rfieldmesh-gui.spec"
    build = ROOT / "packaging" / "windows" / "build.ps1"
    smoke = ROOT / "packaging" / "windows" / "smoke_test.ps1"
    clean_machine = ROOT / "packaging" / "windows" / "clean_machine_test.ps1"
    windows_evidence = ROOT / "packaging" / "windows" / "write_evidence.py"
    abaqus_validator = ROOT / "packaging" / "abaqus" / "validate_generated_model.py"
    abaqus_wrapper = ROOT / "packaging" / "abaqus" / "validate.ps1"
    workflow = ROOT / ".github" / "workflows" / "windows-build.yml"
    assert all(
        path.is_file()
        for path in (
            specification,
            build,
            smoke,
            clean_machine,
            windows_evidence,
            abaqus_validator,
            abaqus_wrapper,
            workflow,
        )
    )
    assert "console=False" in specification.read_text(encoding="utf-8")
    assert 'copy_metadata("rfieldmesh"' in specification.read_text(encoding="utf-8")
    assert "PyInstaller" in build.read_text(encoding="utf-8")
    assert "uv.lock" not in build.read_text(encoding="utf-8")
    assert "--frozen" in build.read_text(encoding="utf-8")
    assert "--require-hashes" in build.read_text(encoding="utf-8")
    assert "windows-2022" in workflow.read_text(encoding="utf-8")


def test_binary_redistribution_contains_qt_licence_materials() -> None:
    licence_directory = ROOT / "packaging" / "licences"
    gpl = licence_directory / "GPL-3.0.txt"
    lgpl = licence_directory / "LGPL-3.0.txt"
    notice = licence_directory / "THIRD_PARTY_NOTICES.md"
    assert gpl.stat().st_size > 30_000
    assert lgpl.stat().st_size > 7_000
    assert "shared-library" in notice.read_text(encoding="utf-8")


def test_licence_inventory_renderer_omits_build_host_paths() -> None:
    module_path = ROOT / "packaging" / "licences" / "render_inventory.py"
    specification = importlib.util.spec_from_file_location("render_inventory", module_path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    content = module.render(
        [
            {
                "Name": "Example",
                "Version": "1.0",
                "License": "MIT",
                "LicenseFile": "C:/secret/build/path/LICENSE",
                "LicenseText": "Example licence text.",
            }
        ]
    )
    assert "Example licence text." in content
    assert "C:/secret" not in content


def _windows_evidence_module() -> ModuleType:
    path = ROOT / "packaging" / "windows" / "write_evidence.py"
    specification = importlib.util.spec_from_file_location("write_windows_evidence", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_windows_build_evidence_requires_frozen_five_tab_gui(tmp_path: Path) -> None:
    source_report = tmp_path / "source.json"
    packaged_report = tmp_path / "packaged.json"
    source_report.write_text(
        json.dumps(
            {
                "application_version": __version__,
                "tab_count": 5,
                "frozen": False,
            }
        ),
        encoding="utf-8",
    )
    packaged_report.write_text(
        json.dumps(
            {
                "application_version": __version__,
                "tab_count": 5,
                "frozen": True,
                "qt_version": "test",
                "pyside_version": "test",
            }
        ),
        encoding="utf-8",
    )
    executable = tmp_path / "RFieldMesh.exe"
    inventory = tmp_path / "PYTHON_PACKAGE_LICENCES.txt"
    notice = tmp_path / "THIRD_PARTY_NOTICES.md"
    for path in (executable, inventory, notice):
        path.write_bytes(b"release evidence fixture")
    gpl = ROOT / "packaging" / "licences" / "GPL-3.0.txt"
    lgpl = ROOT / "packaging" / "licences" / "LGPL-3.0.txt"

    module = _windows_evidence_module()
    kwargs = {
        "source_report": source_report,
        "packaged_report": packaged_report,
        "executable": executable,
        "licence_inventory": inventory,
        "third_party_notice": notice,
        "gpl_text": gpl,
        "lgpl_text": lgpl,
    }
    passing = module.build_evidence(**kwargs)
    broken = packaged_report
    broken.write_text(
        json.dumps(
            {
                "application_version": __version__,
                "tab_count": 4,
                "frozen": False,
            }
        ),
        encoding="utf-8",
    )
    failing = module.build_evidence(**kwargs)
    assert passing["status"] == "passed"
    assert failing["status"] == "failed"
