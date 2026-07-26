"""Regression metadata for the supplied MATLAB realization."""

from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

REFERENCE = Path(__file__).resolve().parents[1] / "validation/matlab/E_field_lognormal_seed1403.csv"


@pytest.mark.regression
def test_reference_checksum_shape_and_summary() -> None:
    digest = sha256(REFERENCE.read_bytes()).hexdigest()
    assert digest == "c3deee11b547cacd6c357ffa3efc4581514040bcd6584066def0729319dd45e6"
    field = np.loadtxt(REFERENCE, delimiter=",")
    assert field.shape == (200, 100)
    assert np.isfinite(field).all()
    assert float(np.mean(field)) == pytest.approx(19_887_935.88986645)
    assert float(np.std(field, ddof=0)) == pytest.approx(5_364_469.667455978)
    assert float(np.min(field)) == pytest.approx(6_928_120.62453868)
    assert float(np.max(field)) == pytest.approx(50_853_261.6186983)


@pytest.mark.regression
def test_reference_has_plausible_correlated_field_statistics() -> None:
    field = np.loadtxt(REFERENCE, delimiter=",")
    mean = float(np.mean(field))
    coefficient_of_variation = float(np.std(field) / mean)
    assert abs(mean - 20.0e6) / 20.0e6 < 0.02
    assert 0.20 < coefficient_of_variation < 0.32
