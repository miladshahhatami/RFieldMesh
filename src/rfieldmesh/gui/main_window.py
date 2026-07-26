"""Five-tab RFieldMesh desktop workflow."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rfieldmesh.application.batch import BatchProgress, BatchResult
from rfieldmesh.application.preview import PreviewResult
from rfieldmesh.config.enums import (
    CorrelationKind,
    DistributionKind,
    GenerationAlgorithm,
    MappingMethod,
    PropertyKind,
    SeedStrategy,
)
from rfieldmesh.config.models import (
    BatchConfig,
    BoundsConfig,
    CorrelationConfig,
    GenerationConfig,
    MomentSpecification,
    RandomVariableConfig,
)
from rfieldmesh.gui.project_view_model import PartOptions, ProjectViewModel
from rfieldmesh.gui.widgets.plot_view import PlotView
from rfieldmesh.gui.workers import FunctionWorker
from rfieldmesh.infrastructure.concurrency import CancellationToken


class VariablePanel(QGroupBox):
    """Controls for one random material property."""

    def __init__(
        self,
        title: str,
        *,
        default_mean: float,
        default_cv: float,
        default_unit: str,
        checked: bool,
    ) -> None:
        super().__init__(title)
        self.setCheckable(True)
        self.setChecked(checked)
        form = QFormLayout(self)

        self.mean = QDoubleSpinBox()
        self.mean.setDecimals(8)
        self.mean.setRange(1.0e-12, 1.0e18)
        self.mean.setValue(default_mean)
        self.mean.setKeyboardTracking(False)
        form.addRow("Point-scale mean", self.mean)

        self.cv = QDoubleSpinBox()
        self.cv.setDecimals(6)
        self.cv.setRange(1.0e-6, 10.0)
        self.cv.setSingleStep(0.01)
        self.cv.setValue(default_cv)
        self.cv.setKeyboardTracking(False)
        form.addRow("Coefficient of variation", self.cv)

        self.unit = QLineEdit(default_unit)
        form.addRow("Unit label", self.unit)

        self.distribution = QComboBox()
        for item in DistributionKind:
            self.distribution.addItem(item.value.replace("_", " ").title(), item.value)
        self.distribution.setCurrentIndex(
            self.distribution.findData(DistributionKind.LOGNORMAL.value)
        )
        form.addRow("Distribution", self.distribution)

        self.lower_input = QLineEdit()
        self.lower_input.setPlaceholderText("Optional; required with no upper bound")
        form.addRow("Lower bound", self.lower_input)
        self.upper_input = QLineEdit()
        self.upper_input.setPlaceholderText("Optional; required with no lower bound")
        form.addRow("Upper bound", self.upper_input)
        self.distribution.currentIndexChanged.connect(self._update_bounds)
        self._update_bounds()

    def _update_bounds(self) -> None:
        truncated = self.distribution.currentData() == DistributionKind.TRUNCATED_NORMAL.value
        self.lower_input.setEnabled(truncated)
        self.upper_input.setEnabled(truncated)

    @staticmethod
    def _optional_float(text: str) -> float | None:
        stripped = text.strip()
        return None if not stripped else float(stripped)

    def variable(self, property_kind: PropertyKind) -> RandomVariableConfig | None:
        """Return the validated property configuration when enabled."""
        if not self.isChecked():
            return None
        distribution = DistributionKind(str(self.distribution.currentData()))
        bounds = None
        if distribution is DistributionKind.TRUNCATED_NORMAL:
            bounds = BoundsConfig(
                lower=self._optional_float(self.lower_input.text()),
                upper=self._optional_float(self.upper_input.text()),
            )
        mean = self.mean.value()
        return RandomVariableConfig(
            property_kind=property_kind,
            moments=MomentSpecification(
                mean=mean,
                standard_deviation=mean * self.cv.value(),
                unit_label=self.unit.text().strip(),
            ),
            distribution=distribution,
            correlation=CorrelationConfig(scales=(1.0, 1.0)),
            bounds=bounds,
        )


class MainWindow(QMainWindow):
    """Main application window coordinating the desktop workflow."""

    def __init__(self, *, view_model: ProjectViewModel | None = None) -> None:
        super().__init__()
        self.view_model = view_model if view_model is not None else ProjectViewModel()
        self.thread_pool = QThreadPool.globalInstance()
        self.cancellation = CancellationToken()
        self._workers: set[FunctionWorker] = set()
        self._part_options: dict[str, PartOptions] = {}
        self._dimension = 2

        self.setWindowTitle("RFieldMesh")
        self.resize(1240, 820)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._build_model_tab()
        self._build_region_tab()
        self._build_simulation_tab()
        self._build_preview_tab()
        self._build_output_tab()
        self.statusBar().showMessage("Select an Abaqus input file to begin.")

    def _build_model_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        source_row = QHBoxLayout()
        self.source_path = QLineEdit()
        self.source_path.setPlaceholderText("Abaqus .inp source model")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_source)
        inspect = QPushButton("Inspect model")
        inspect.clicked.connect(self._inspect_source)
        source_row.addWidget(self.source_path, 1)
        source_row.addWidget(browse)
        source_row.addWidget(inspect)
        layout.addLayout(source_row)
        self.model_summary = QPlainTextEdit()
        self.model_summary.setReadOnly(True)
        self.model_summary.setPlaceholderText(
            "Model structure, materials, sections, element types, and eligibility will appear here."
        )
        layout.addWidget(self.model_summary, 1)
        self.tabs.addTab(tab, "1. Model")

    def _build_region_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        region_box = QGroupBox("Region")
        region_form = QFormLayout(region_box)
        self.part = QComboBox()
        self.part.currentTextChanged.connect(self._part_changed)
        self.element_set = QComboBox()
        self.instance = QComboBox()
        region_form.addRow("Part", self.part)
        region_form.addRow("Element set", self.element_set)
        region_form.addRow("Instance", self.instance)
        layout.addWidget(region_box)

        variables = QGridLayout()
        self.youngs = VariablePanel(
            "Young's modulus",
            default_mean=20_000_000.0,
            default_cv=0.30,
            default_unit="Pa",
            checked=True,
        )
        self.density = VariablePanel(
            "Density",
            default_mean=1800.0,
            default_cv=0.10,
            default_unit="kg/m³",
            checked=False,
        )
        variables.addWidget(self.youngs, 0, 0)
        variables.addWidget(self.density, 0, 1)
        layout.addLayout(variables)
        layout.addStretch(1)
        self.tabs.addTab(tab, "2. Region and variables")

    def _build_simulation_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        correlation = QGroupBox("Latent Gaussian correlation")
        form = QFormLayout(correlation)
        self.correlation_model = QComboBox()
        for correlation_kind in CorrelationKind:
            self.correlation_model.addItem(
                correlation_kind.value.replace("_", " ").title(),
                correlation_kind.value,
            )
        form.addRow("Model", self.correlation_model)
        self.scale_x = self._positive_spin(10.0)
        self.scale_y = self._positive_spin(1.0)
        self.scale_z = self._positive_spin(1.0)
        form.addRow("Scale of fluctuation — x", self.scale_x)
        form.addRow("Scale of fluctuation — y", self.scale_y)
        form.addRow("Scale of fluctuation — z", self.scale_z)
        layout.addWidget(correlation)

        simulation = QGroupBox("Algorithm and reproducibility")
        sim_form = QFormLayout(simulation)
        self.algorithm = QComboBox()
        for algorithm_kind in GenerationAlgorithm:
            self.algorithm.addItem(
                algorithm_kind.value.replace("_", " ").title(),
                algorithm_kind.value,
            )
        self.mapping = QComboBox()
        for mapping_method in MappingMethod:
            self.mapping.addItem(
                mapping_method.value.replace("_", " ").title(),
                mapping_method.value,
            )
        self.first_seed = QSpinBox()
        self.first_seed.setRange(0, 2_147_483_647)
        self.first_seed.setValue(1403)
        self.seed_strategy = QComboBox()
        for seed_strategy in SeedStrategy:
            self.seed_strategy.addItem(seed_strategy.value.title(), seed_strategy.value)
        self.start_index = QSpinBox()
        self.start_index.setRange(0, 1_000_000)
        sim_form.addRow("Generation algorithm", self.algorithm)
        sim_form.addRow("Observation mapping", self.mapping)
        sim_form.addRow("First seed", self.first_seed)
        sim_form.addRow("Seed strategy", self.seed_strategy)
        sim_form.addRow("Preview realization index", self.start_index)
        layout.addWidget(simulation)
        layout.addStretch(1)
        self.tabs.addTab(tab, "3. Correlation and simulation")

    @staticmethod
    def _positive_spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(8)
        spin.setRange(1.0e-9, 1.0e12)
        spin.setValue(value)
        spin.setKeyboardTracking(False)
        return spin

    def _build_preview_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        actions = QHBoxLayout()
        self.preview_button = QPushButton("Generate preview")
        self.preview_button.clicked.connect(self._generate_preview)
        self.export_preview_button = QPushButton("Export current preview…")
        self.export_preview_button.setEnabled(False)
        self.export_preview_button.clicked.connect(self._export_preview)
        self.preview_status = QLabel("No preview generated.")
        actions.addWidget(self.preview_button)
        actions.addWidget(self.export_preview_button)
        actions.addWidget(self.preview_status, 1)
        layout.addLayout(actions)
        self.plot_view = PlotView()
        layout.addWidget(self.plot_view.widget, 1)
        self.tabs.addTab(tab, "4. Preview and statistics")

    def _build_output_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        output_box = QGroupBox("Batch outputs")
        form = QFormLayout(output_box)
        output_row = QHBoxLayout()
        self.output_directory = QLineEdit()
        self.output_directory.setPlaceholderText("Output directory")
        output_browse = QPushButton("Browse…")
        output_browse.clicked.connect(self._browse_output_directory)
        output_row.addWidget(self.output_directory, 1)
        output_row.addWidget(output_browse)
        form.addRow("Directory", output_row)
        self.filename_template = QLineEdit("RFieldMesh_{index:04d}_seed{seed}.inp")
        self.realization_count = QSpinBox()
        self.realization_count.setRange(1, 100_000)
        self.realization_count.setValue(1)
        self.overwrite = QCheckBox("Permit replacement of existing batch outputs")
        self.continue_on_error = QCheckBox("Continue after a controlled realization failure")
        form.addRow("Filename template", self.filename_template)
        form.addRow("Number of realizations", self.realization_count)
        form.addRow("", self.overwrite)
        form.addRow("", self.continue_on_error)
        layout.addWidget(output_box)

        action_row = QHBoxLayout()
        self.generate_button = QPushButton("Generate batch")
        self.generate_button.clicked.connect(self._generate_batch)
        self.cancel_button = QPushButton("Cancel after current stage")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_batch)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        action_row.addWidget(self.generate_button)
        action_row.addWidget(self.cancel_button)
        action_row.addWidget(self.progress, 1)
        layout.addLayout(action_row)
        self.output_log = QPlainTextEdit()
        self.output_log.setReadOnly(True)
        layout.addWidget(self.output_log, 1)
        self.tabs.addTab(tab, "5. Output and batch generation")

    def _browse_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Abaqus input model",
            "",
            "Abaqus input files (*.inp);;All files (*)",
        )
        if filename:
            self.source_path.setText(filename)
            self._inspect_source()

    def _browse_output_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select output directory")
        if directory:
            self.output_directory.setText(directory)

    def _run_worker(
        self,
        function: Callable[[Callable[[object], None]], Any],
        *,
        success: Callable[[Any], None],
        progress: Callable[[object], None] | None = None,
    ) -> None:
        worker = FunctionWorker(function)
        self._workers.add(worker)

        def cleanup() -> None:
            self._workers.discard(worker)

        def failed(message: str) -> None:
            cleanup()
            self._operation_failed(message)

        def finished(result: object) -> None:
            cleanup()
            success(result)

        worker.signals.failed.connect(failed)
        worker.signals.finished.connect(finished)
        if progress is not None:
            worker.signals.progress.connect(progress)
        self.thread_pool.start(worker)

    def _inspect_source(self) -> None:
        path = self.source_path.text().strip()
        if not path:
            self._operation_failed("Select an Abaqus input file.")
            return
        self.statusBar().showMessage("Inspecting model…")
        self._run_worker(
            lambda _emit: self.view_model.load_model(path),
            success=self._inspection_complete,
        )

    def _inspection_complete(self, result: object) -> None:
        summary = cast(dict[str, Any], result)
        self.model_summary.setPlainText(json.dumps(summary, indent=2, sort_keys=True))
        self._part_options = {option.name: option for option in self.view_model.part_options()}
        self.part.clear()
        self.part.addItems(list(self._part_options))
        if self.view_model.source_path is not None and not self.output_directory.text():
            self.output_directory.setText(
                str(self.view_model.source_path.parent / "rfieldmesh_outputs")
            )
        self._part_changed(self.part.currentText())
        self.statusBar().showMessage("Model inspection complete.")
        self.tabs.setCurrentIndex(1)

    def _part_changed(self, name: str) -> None:
        option = self._part_options.get(name)
        self.element_set.clear()
        self.instance.clear()
        self.instance.addItem("(automatic)", None)
        if option is None:
            return
        self.element_set.addItems(option.element_sets)
        for instance in option.instances:
            self.instance.addItem(instance, instance)
        if self.view_model.inspection is not None:
            part_summary = next(
                part for part in self.view_model.inspection["parts"] if str(part["name"]) == name
            )
            element_types = tuple(str(item) for item in part_summary["element_types"])
            self._dimension = (
                3 if any(item.startswith(("C3D", "AC3D")) for item in element_types) else 2
            )
            self.scale_z.setEnabled(self._dimension == 3)

    def _configured_variables(self) -> tuple[RandomVariableConfig, ...]:
        base = [
            self.youngs.variable(PropertyKind.YOUNGS_MODULUS),
            self.density.variable(PropertyKind.DENSITY),
        ]
        variables = tuple(variable for variable in base if variable is not None)
        if not variables:
            raise ValueError("Enable at least one material property.")
        scales = (
            (self.scale_x.value(), self.scale_y.value())
            if self._dimension == 2
            else (self.scale_x.value(), self.scale_y.value(), self.scale_z.value())
        )
        correlation = CorrelationConfig(
            model=CorrelationKind(str(self.correlation_model.currentData())),
            scales=scales,
        )
        return tuple(
            variable.model_copy(update={"correlation": correlation}) for variable in variables
        )

    def _generation_config(self) -> GenerationConfig:
        if self.view_model.source_path is None:
            raise ValueError("Inspect an Abaqus model first.")
        output_directory = Path(
            self.output_directory.text().strip()
            or self.view_model.source_path.parent / "rfieldmesh_outputs"
        ).expanduser()
        return GenerationConfig(
            source_path=str(self.view_model.source_path),
            output_path=str(output_directory / "_preview_not_written.inp"),
            part_name=self.part.currentText(),
            set_name=self.element_set.currentText(),
            instance_name=self.instance.currentData(),
            variables=self._configured_variables(),
            first_seed=self.first_seed.value(),
            realization_index=self.start_index.value(),
            seed_strategy=SeedStrategy(str(self.seed_strategy.currentData())),
            algorithm=GenerationAlgorithm(str(self.algorithm.currentData())),
            mapping=MappingMethod(str(self.mapping.currentData())),
            overwrite=self.overwrite.isChecked(),
        )

    def _generate_preview(self) -> None:
        try:
            config = self._generation_config()
        except Exception as exc:
            self._operation_failed(str(exc))
            return
        self.preview_button.setEnabled(False)
        self.preview_status.setText("Generating…")
        self.statusBar().showMessage("Generating unsaved field preview…")
        self._run_worker(
            lambda _emit: self.view_model.create_preview(config),
            success=self._preview_complete,
        )

    def _preview_complete(self, result: object) -> None:
        preview, rendered = cast(tuple[PreviewResult, str], result)
        assert isinstance(preview, PreviewResult)
        self.plot_view.set_html(str(rendered))
        self.preview_status.setText(
            f"{preview.eligible_count:,} eligible; {preview.excluded_count:,} excluded."
        )
        self.preview_button.setEnabled(True)
        self.export_preview_button.setEnabled(True)
        self.statusBar().showMessage("Preview complete.")
        self.tabs.setCurrentIndex(3)

    def _export_preview(self) -> None:
        if self.view_model.preview_result is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export interactive preview",
            "rfieldmesh_preview.html",
            "HTML files (*.html)",
        )
        if not filename:
            return
        try:
            from rfieldmesh.visualization.figures import export_preview_html

            export_preview_html(
                self.view_model.preview_result,
                filename,
                overwrite=self.overwrite.isChecked(),
            )
        except Exception as exc:
            self._operation_failed(str(exc))
        else:
            self.statusBar().showMessage(f"Preview exported to {filename}")

    def _generate_batch(self) -> None:
        try:
            generation = self._generation_config()
            batch = BatchConfig(
                generation=generation,
                output_directory=self.output_directory.text().strip(),
                realization_count=self.realization_count.value(),
                start_index=self.start_index.value(),
                filename_template=self.filename_template.text().strip(),
                continue_on_error=self.continue_on_error.isChecked(),
            )
        except Exception as exc:
            self._operation_failed(str(exc))
            return
        self.cancellation.reset()
        self.generate_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, batch.realization_count)
        self.progress.setValue(0)
        self.output_log.clear()
        self.tabs.setCurrentIndex(4)
        self._run_worker(
            lambda emit: self.view_model.generate_batch(
                batch,
                cancellation=self.cancellation,
                progress=lambda update: emit(update),
            ),
            success=self._batch_complete,
            progress=self._batch_progress,
        )

    def _batch_progress(self, update: object) -> None:
        if not isinstance(update, BatchProgress):
            return
        self.progress.setMaximum(update.total)
        self.progress.setValue(update.completed)
        self.output_log.appendPlainText(f"[{update.completed}/{update.total}] {update.message}")

    def _batch_complete(self, result: object) -> None:
        assert isinstance(result, BatchResult)
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setValue(result.completed_count + result.failed_count)
        status = f"Batch complete: {result.completed_count} generated, {result.failed_count} failed"
        if result.cancelled:
            status += ", cancelled"
        self.output_log.appendPlainText(status + ".")
        self.output_log.appendPlainText(f"Summary: {result.summary_path}")
        self.statusBar().showMessage(status)

    def _cancel_batch(self) -> None:
        self.cancellation.cancel()
        self.cancel_button.setEnabled(False)
        self.output_log.appendPlainText(
            "Cancellation requested; the current numerical or file stage will finish safely."
        )

    def _operation_failed(self, message: str) -> None:
        self.preview_button.setEnabled(True)
        self.generate_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.preview_status.setText("Operation failed.")
        self.statusBar().showMessage("Operation failed.")
        QMessageBox.critical(self, "RFieldMesh", message)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        """Request cooperative cancellation before closing."""
        self.cancellation.cancel()
        super().closeEvent(event)
