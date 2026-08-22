# RFieldMesh 1.0.0 automatic spectral-budget correction

## Outcome

The reported `ComputationalBudgetError` is corrected for the GUI's automatic
structured-2D workflow. Both reported configurations now complete on the
representative `2D-Model.inp` file:

- cohesion only with the GUI defaults; and
- Young's modulus, density, Poisson's ratio, friction angle, dilation angle,
  and cohesion with the values shown in the reported GUI configuration.

The package and application version remain exactly `1.0.0`.

## Root cause

The GUI creates the default `SpectralConfig` with a directional
retained-variance target of `0.99999`. Automatic mapping uses rectangular
Gaussian averaging for normal and lognormal variables, which suppresses
high-frequency modes, but it uses centroid sampling for bounded
truncated-normal variables. On the 20,000-element mesh with correlation scales
`(10, 1)`, the centroid representation cannot reach `0.99999` before
`max_mode_cap=100000`. The former power-of-two mode search could also select
more coefficients than necessary when a lower mode count already met a
feasible target.

This is a numerical-default and budget-selection issue; the material means,
coefficients of variation, and bounds shown in the GUI are valid.

## Correction

RFieldMesh now behaves as follows:

1. It first attempts the requested spectral target unchanged.
2. Only if that attempt raises `ComputationalBudgetError`, and only when both
   the algorithm and mapping are automatic with centroid sampling, it retries
   at `0.995` retained variance per spatial direction.
3. If the doubling search would exceed `max_coefficient_count`, the mode set is
   compacted to the smallest symmetric directional sets that still meet the
   effective target.
4. Requested/effective targets and both automatic decisions are stored in
   preview and realization diagnostics.
5. The GUI preview status reports when the automatic adjustment was used.
6. Explicit `algorithm=spectral` requests remain strict and still fail rather
   than relaxing a user-required target.

This control flow preserves all previously successful spectral realizations:
their historical mode sets are retained because adjustment and compaction are
entered only after the old path would have failed. The lognormal Young's
modulus and density fields in the reported all-six case therefore retain the
original `0.99999` observation-variance target.

For the adjusted 2D centroid representation, the directional mode counts are
`(1135, 4377)`, the coefficient count is `4,967,895`, and the retained combined
point variance is `0.9900260092`. Truncated-normal latent values are normalized
before the marginal transformation, so the configured point-scale moments and
bounds remain the governing marginal specification.

## Validation results

| Case | Eligible | Verified properties | Result |
|---|---:|---:|---|
| 2D cohesion only, GUI defaults | 20,000 | 1 | passed |
| 2D all six, reported GUI values | 20,000 | 6 | passed |
| 3D all six, representative configuration | 10,032 plus 600 preserved | 6 | passed |

The 2D cohesion-only realization was nonnegative, ranging from
`949.7900324` to `8808.6052043`. The all-six 2D and 3D outputs were written,
reparsed independently, and verified element by element. The two uploaded
source-model hashes remained unchanged.

The final source-quality gate reported:

- 101 tests passed and one GUI smoke test skipped because this Linux runtime
  lacks `libEGL.so.1`;
- 73% aggregate coverage;
- Ruff lint and format checks passed;
- strict mypy passed for 47 source files;
- wheel and source-distribution builds passed; and
- an installed-wheel cohesion preview passed on all 20,000 2D elements.

No native Windows executable or Abaqus analysis is claimed from this Linux
environment. Rebuild the executable from this corrected source on Windows by
running `packaging/windows/build.ps1`; retain the generated Windows evidence
and perform the documented clean-machine and Abaqus-native checks.
