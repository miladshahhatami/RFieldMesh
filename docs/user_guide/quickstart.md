# RFieldMesh quick start

## Windows packaged application

Extract the complete `RFieldMesh-1.0.0-windows-x64.zip` to a writable local
directory and run `RFieldMesh.exe`. Do not run the executable from inside the
ZIP.

The five tabs implement one sequential workflow:

1. open and inspect a copy of an Abaqus `.inp` model;
2. select one part, optional instance, element set, and material properties;
3. define marginal moments, correlation scales, algorithm, mapping, and seeds;
4. generate and inspect an unsaved preview;
5. generate one realization or a preflighted batch.

Use a new output directory during initial testing. Retain each generated
`.rfieldmesh.json` manifest with its corresponding `.inp` file.

## Python installation

```bash
python -m pip install "rfieldmesh[desktop]"
rfieldmesh-gui
```

The core CLI does not require desktop dependencies:

```bash
python -m pip install rfieldmesh
rfieldmesh inspect model.inp
```

## Algorithm selection

`Auto` selects the spectral route for a complete, axis-aligned, structured 2D
quadrilateral mesh with supported correlation. Other regions use dense KL when
its estimated workspace fits the configured budget and a matrix-free pivoted
covariance factor otherwise.

Large rotated, skewed, or unstructured regions have no fixed point cap, but
their feasible retained rank remains memory- and time-dependent. Do not create
statistically independent subregions unless that independence is part of the
intended stochastic model. Consult `KNOWN_LIMITATIONS.md`.

The Region and Variables tab provides Young's modulus, density, Poisson's
ratio, friction angle, and dilation angle. Friction or dilation randomization
is permitted only when the source material already contains one scalar
`*Mohr Coulomb` row. When one member of a shared row is selected, the other is
preserved exactly.

## Reproducibility

Archive the following together:

- original input model checksum;
- complete generation or batch configuration;
- output model;
- `.rfieldmesh.json` manifest;
- RFieldMesh version;
- relevant Abaqus version and analysis records.

The same configuration, source bytes, application version, and seed reproduce
the same generated field.
