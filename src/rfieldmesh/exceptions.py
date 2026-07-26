"""Project-specific exception hierarchy."""


class RFieldMeshError(Exception):
    """Base class for controlled RFieldMesh failures."""


class ConfigurationError(RFieldMeshError, ValueError):
    """Raised when a scientifically invalid configuration is requested."""


class NumericalStabilityError(RFieldMeshError, ArithmeticError):
    """Raised when a numerical decomposition or covariance is unreliable."""


class ComputationalBudgetError(RFieldMeshError, MemoryError):
    """Raised before an operation that exceeds its configured cost budget."""


class UnsupportedObservationError(RFieldMeshError, NotImplementedError):
    """Raised for a distribution/observation combination not yet supported."""


class AbaqusParseError(RFieldMeshError, ValueError):
    """Raised when required Abaqus semantics cannot be resolved safely."""


class UnsupportedModelError(RFieldMeshError, NotImplementedError):
    """Raised when a syntactically valid model uses an unsupported construct."""


class GeometryError(RFieldMeshError, ValueError):
    """Raised when element geometry cannot support the requested operation."""


class UnsafeWriteError(RFieldMeshError, RuntimeError):
    """Raised before a write that could produce an ambiguous or unsafe model."""


class VisualizationExportError(RFieldMeshError, RuntimeError):
    """Raised when a requested visualization cannot be constructed or exported."""


class BatchConfigurationError(ConfigurationError):
    """Raised when batch output planning is ambiguous or unsafe."""
