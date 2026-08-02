# Five-property configuration

RFieldMesh 1.0.0 supports independent spatial fields for the following
registry identifiers:

| Identifier | Abaqus row | Column | Admissible interval |
|---|---|---:|---|
| `elastic_modulus` | `*Elastic` | 1 | \(E>0\) |
| `density` | `*Density` | 1 | \(\rho>0\) |
| `poissons_ratio` | `*Elastic` | 2 | \(-1<\nu<0.5\) |
| `friction_angle` | `*Mohr Coulomb` | 1 | \(0<\phi<90^\circ\) |
| `dilation_angle` | `*Mohr Coulomb` | 2 | \(0\leq\psi<90^\circ\) |

The legacy identifier `youngs_modulus` remains accepted in pre-publication
JSON files and is serialized as `elastic_modulus` in new manifests.

Each variable uses the existing `moments`, `distribution`, `bounds`,
`correlation`, and optional `seed` fields. The GUI exposes the same schema; the
CLI and public Python API both validate `GenerationConfig` before computation.
Complete configurations are provided in `examples/all_five_2d.json` and
`examples/all_five_3d.json`.

## Shared Abaqus rows

Young's modulus and Poisson's ratio occupy the same `*Elastic` row. Friction
and dilation angles occupy the same `*Mohr Coulomb` row. RFieldMesh changes
only selected columns. It independently reparses the output and confirms that
unselected companion values equal the source-material values.

Selecting friction or dilation angle for a material without `*Mohr Coulomb`
causes a pre-write error. The software never inserts a constitutive model on
the user's behalf. Multirow, temperature-dependent, field-dependent, and
dependency-based forms remain outside the supported scope.

All generated values are checked against the registry interval before writing.
Invalid values are rejected with examples; they are never silently clipped.
For bounded variables, a truncated-normal distribution with defensible bounds
is recommended. The common constitutive recommendation \(\psi\leq\phi\) is not
an Abaqus syntax rule and is not imposed silently; users must select joint
statistics and bounds that are appropriate for their material model.

## Reproducible independent streams

Each property has a stable numerical stream code. Its realization is derived
from the master or property seed, realization index, and seed strategy. Stream
derivation does not use Python's `hash()` function, and adding another selected
property does not change an existing property's stream.

## Large general meshes

`covariance_kl` first estimates dense covariance and eigensolver workspace. If
that estimate exceeds `dense_memory_limit_mb`, it uses matrix-free pivoted
covariance factorization. Relevant controls are:

- `retained_variance`;
- `dense_memory_limit_mb`;
- `iterative_memory_limit_mb`;
- `iterative_max_modes`;
- `block_size`;
- `normalize_point_variance`.

The scalable factorization evaluates covariance columns in blocks and stores
an \(N\times r\) factor. It stops when the unresolved diagonal trace satisfies
the retained-variance criterion. If the criterion cannot be met within the
configured budgets, it reports the attained fraction and required action.
The deprecated `max_points` field is accepted for compatibility but is not an
element-count limit.
