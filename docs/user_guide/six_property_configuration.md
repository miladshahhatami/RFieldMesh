# Six-property configuration

RFieldMesh 1.0.0 supports independent spatial fields for the following
registry identifiers:

| Identifier | Abaqus row | Column | Admissible interval |
|---|---|---:|---|
| `elastic_modulus` | `*Elastic` | 1 | \(E>0\) |
| `density` | `*Density` | 1 | \(\rho>0\) |
| `poissons_ratio` | `*Elastic` | 2 | \(-1<\nu<0.5\) |
| `friction_angle` | `*Mohr Coulomb` | 1 | \(0<\phi<90^\circ\) |
| `dilation_angle` | `*Mohr Coulomb` | 2 | \(0\leq\psi<90^\circ\) |
| `cohesion` | `*Mohr Coulomb Hardening` | 1 | \(c\geq0\) |

The legacy identifier `youngs_modulus` remains accepted in pre-publication
JSON files and is serialized as `elastic_modulus` in new manifests. Existing
configurations containing only the original five properties require no edits.

Each variable uses the existing `moments`, `distribution`, `bounds`,
`correlation`, and optional `seed` fields. The GUI exposes the same schema; the
CLI and public Python API both validate `GenerationConfig` before computation.
Complete configurations are provided in `examples/all_six_2d.json` and
`examples/all_six_3d.json`.

## Abaqus column preservation

Young's modulus and Poisson's ratio occupy the same `*Elastic` row. Friction
and dilation angles occupy the same `*Mohr Coulomb` row. Cohesion is the first
numerical value in the first data row under `*Mohr Coulomb Hardening`; for the
supplied 2D soil material this source value is `5000 Pa`. Units remain
model-consistent and are not converted automatically.

RFieldMesh changes only selected columns. It independently reparses the output
and confirms both selected values and unselected source values. When cohesion
is selected, every value after the first hardening value is preserved exactly.
When cohesion is not selected, the complete hardening card remains unchanged.

Selecting an angle or cohesion for a material without the corresponding Abaqus
keyword causes a pre-write error. The software never inserts a constitutive
model on the user's behalf. Duplicate, multirow, temperature-dependent,
field-dependent, and dependency-based hardening forms are rejected explicitly.

All generated values are checked against the registry interval before writing.
Invalid values are rejected with examples; they are never silently clipped.
For cohesion, truncated normal with a lower bound of zero is the default, while
normal and lognormal remain available. A normal configuration that produces a
negative realization fails validation.

The common constitutive recommendation \(\psi\leq\phi\) is not an Abaqus
syntax rule and is not imposed silently; users must select joint statistics and
bounds appropriate to their material model.

## Reproducible independent streams

Each property has a stable numerical stream code. Its realization is derived
from the master or property seed, realization index, and seed strategy. Adding
cohesion does not change any stream used by the original five properties.
Cross-property correlation is not implemented in version 1.0.0.

## Automatic spectral budget handling

On a structured two-dimensional region, automatic generation uses centroid
sampling for truncated-normal variables such as the default cohesion field.
RFieldMesh first attempts the configured spectral target unchanged. If that
attempt cannot fit `max_mode_cap` or `max_coefficient_count`, `algorithm=auto`
retries at `0.995` retained variance per direction and removes only the
power-of-two mode overshoot needed to fit the coefficient budget. The resulting
two-dimensional retained point variance is approximately `0.990` or greater.

This behavior is visible through
`requested_directional_retained_variance`,
`effective_directional_retained_variance`,
`automatic_budget_adjustment`, and `coefficient_budget_compaction` in the
field diagnostics and realization manifest. The GUI preview also reports when
the automatic adjustment was used. Previously successful cases retain their
original mode sets. Choose `algorithm=spectral` to require the configured
target strictly and receive a controlled budget error if it cannot be met.

## Large general meshes

`covariance_kl` first estimates dense covariance and eigensolver workspace. If
that estimate exceeds `dense_memory_limit_mb`, it uses matrix-free pivoted
covariance factorization. Relevant controls are `retained_variance`,
`dense_memory_limit_mb`, `iterative_memory_limit_mb`, `iterative_max_modes`,
`block_size`, and `normalize_point_variance`.

The scalable factorization evaluates covariance columns in blocks and stores
an \(N\times r\) factor. It stops when the unresolved diagonal trace satisfies
the retained-variance criterion. If the criterion cannot be met within the
configured budgets, it reports the attained fraction and required action. The
deprecated `max_points` field remains accepted for compatibility but is not an
element-count limit.
