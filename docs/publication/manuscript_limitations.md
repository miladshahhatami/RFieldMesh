# Manuscript-ready limitation statement

## Discussion or limitations subsection

The implementation employs dense covariance-based Karhunen–Loève decomposition
only when its estimated workspace fits the configured memory budget. General
eligible two- and three-dimensional meshes otherwise use a matrix-free pivoted
covariance factor, whose residual-trace stopping rule enforces the requested
retained-variance fraction without allocating an \(N\times N\) matrix. This
removes the former fixed point-count restriction, but computation is not
unlimited: weak correlation or stringent variance retention can require a
high rank and produce a controlled resource error. The spectral formulation
remains the preferred scalable route for complete, axis-aligned, structured
two-dimensional quadrilateral meshes.

## Short conclusion statement

Future versions will investigate auxiliary-grid spectral methods and general
element-area or volume-averaging operators for rotated and unstructured meshes.

The manuscript should also state that independently generating adjacent
subregions is not equivalent to a single continuous field because it removes
cross-boundary spatial correlation.
