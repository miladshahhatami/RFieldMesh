# Manuscript-ready limitation statement

## Discussion or limitations subsection

The current implementation employs a dense covariance-based
Karhunen–Loève formulation for general meshes, resulting in quadratic memory
requirements and a computationally demanding eigendecomposition as the number
of field locations increases. Consequently, a numerical safeguard limits this
approach to moderate-sized domains. Larger models can be processed using the
spectral formulation; however, the current spectral mapping procedure requires
a complete, axis-aligned, structured two-dimensional quadrilateral mesh.
Therefore, large rotated, skewed, or unstructured meshes are not supported by
the present release. Future development will incorporate automatic recognition
of rotated structured grids and a scalable auxiliary-grid spectral approach
with interpolation or element averaging for general meshes. This extension
will remove an application-wide point-count restriction while retaining
method-specific safeguards based on available computational resources.

## Short conclusion statement

Future versions will extend scalable random-field generation to large rotated
and unstructured meshes, which are outside the applicability range of the
current implementation.

The manuscript should also state that independently generating adjacent
subregions is not equivalent to a single continuous field because it removes
cross-boundary spatial correlation.
