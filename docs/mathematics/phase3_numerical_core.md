# Phase 3 numerical core

## 1. Statistical semantics

The configured mean and standard deviation are point-scale physical-property
statistics. A local-average observation has lower variance. For non-Gaussian
fields, the configured correlation applies to the latent Gaussian field.

## 2. Correlation functions

The separable exponential model is

\[
\rho(\mathbf h)
=
\exp\left[
-2\sum_{j=1}^{d}\frac{|h_j|}{\theta_j}
\right].
\]

The squared-exponential model is

\[
\rho(\mathbf h)
=
\exp\left[
-\pi\sum_{j=1}^{d}
\left(\frac{h_j}{\theta_j}\right)^2
\right].
\]

Both conventions satisfy

\[
\int_{-\infty}^{+\infty}\rho(h)\,dh=\theta
\]

in one dimension.

## 3. Spectral representation

For period \(L\), scale \(\theta\), \(k=2/\theta\), and
\(\omega_m=2\pi m/L\), the Fourier coefficient of the periodicized
unit-variance exponential covariance is

\[
c_m=
\frac{2}{L}
\frac{k\left[1-(-1)^m e^{-kL/2}\right]}
{k^2+\omega_m^2}.
\]

The two-dimensional covariance coefficient is \(q_{mn}=c_m^{(x)}c_n^{(z)}\).
The zero-mean field is generated as

\[
G(x,z)=
\Re\left[
\sum_m\sum_n
\sqrt{q_{mn}}(A_{mn}+iB_{mn})
e^{i(\omega_mx+\nu_nz)}
\right],
\]

where \(A_{mn}\) and \(B_{mn}\) are independent standard-normal variables.

Unlike the MATLAB implementation, the corrected code uses the exact
cell-average basis

\[
\bar\psi_m
=
e^{i\omega_m x_c}
\frac{\sin(\omega_mD/2)}{\omega_mD/2}.
\]

The zero-frequency limit is evaluated through `numpy.sinc`; it is not replaced
by machine epsilon.

For centroid sampling, mode truncation is measured against point variance. For
rectangular averaging, truncation is measured after applying the analytical
cell-average filter. This prevents the algorithm from retaining high-frequency
modes whose contribution to the element-average variance is negligible.

## 4. Rectangular local averaging

For

\[
\rho(h)=e^{-2|h|/\theta}
\]

and an interval of length \(D\), define \(r=D/\theta\). The variance ratio is

\[
v(r)
=
\frac{e^{-2r}+2r-1}{2r^2}.
\]

For a rectangular cell and separable covariance,

\[
v_A=v(D_x/\theta_x)v(D_z/\theta_z).
\]

The implementation calculates the actual variance implied by the retained
Fourier modes and observation filter, rather than assuming the infinite-series
value.

## 5. Lognormal transformation

For physical mean \(\mu_X\), standard deviation \(\sigma_X\), and
\(\delta=\sigma_X/\mu_X\),

\[
\sigma_Y^2=\ln(1+\delta^2),
\qquad
\mu_Y=\ln(\mu_X)-\frac12\sigma_Y^2.
\]

For a locally averaged latent value with variance \(v\), the mean-corrected
surrogate is

\[
X=
\exp(\mu_Y+\sigma_Y\bar G)
\exp\left[\frac12\sigma_Y^2(1-v)\right].
\]

The correction restores \(E[X]=\mu_X\), but the resulting coefficient of
variation is

\[
\sqrt{\exp(v\sigma_Y^2)-1},
\]

which is smaller than the point-scale coefficient of variation.

## 6. Covariance/Karhunen–Loève method

For observation coordinates \(\mathbf x_i\), the correlation matrix is

\[
C_{ij}=\rho(\mathbf x_i-\mathbf x_j).
\]

After a symmetric eigendecomposition,

\[
C=V\Lambda V^\mathsf T,
\]

the smallest number of descending eigenvalues satisfying the retained-variance
tolerance is kept. The prepared realization factor is

\[
L=V_r\Lambda_r^{1/2},
\qquad
\mathbf G=L\boldsymbol\xi,
\]

where \(\boldsymbol\xi\) is standard normal. Optional row normalization restores
unit point variance after eigenvalue truncation; the manifest must record
whether normalization was applied.
