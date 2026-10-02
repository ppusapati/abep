# HWM14 provenance (atmosphere_msis21_hwm14_orbit_v2)

Authority: `docs/decisions/OD_2026_10_01_A9_17_data_artifact_owner_decisions.json` (sha256 9fd77c95…c3ad), decision key
**WINDS** (`AUTHORIZE_HWM14_ATMOSPHERE_V2_KEEP_V1_IMMUTABLE`); ORBIT and DATA_SIZE from the same record also apply.
The machine-readable register is `hwm14_source_register_v1.json` (in this directory). `abep_sim/atmosphere_orbit_v2.py` pins
the same file hashes, and the test suite checks that the two agree.

## Source
- **NRL public repository**: <https://map.nrl.navy.mil/map/pub/nrl/HWM/HWM14/>. Package
  `HWM14_ess224-sup-0002-supinfo.tgz` (sha256 4de451be…7978, 216,852 B) is the Supporting Information "Software S1" of
  Drob et al. 2015, *Earth and Space Science* 2, 301–319, doi:10.1002/2014EA000089. The version is **HWM14.123114**,
  released 31 Dec 2014. The package contains `hwm14.f90`, `hwm123114.bin`, `dwm07b104i.dat`, `gd2qd.dat`, NRL's test
  driver `checkhwm14.f90` and the reference outputs `Check/{gfortran,ifort.nopt,ifort.opt}.txt`. Every file's sha256 is
  in the register.
  - On 2026-10-01 the direct URLs of the two `.dat` files in the unpacked directory returned an HTML "Page not found"
    page. The `.tgz` is therefore the authoritative copy.
- **NASA CCMC**: the model page <https://ccmc.gsfc.nasa.gov/models/HWM14~2014/> lists the NRL URL above as the HWM14
  "Public Repository". The CMR URL the owner cited now redirects (HTTP 301) to a CCMC news page; the owner's description
  of it is kept verbatim in the register.
- **PyPI `pyhwm2014` 1.1**: not used. Its `hwm14.f90` is byte-identical to NRL's, but the sdist has no coefficient files.
  It also builds with `numpy.distutils` and installs unrelated packages from `setup.py`. Its MIT classifier covers only
  the wrapper.

## Terms
None of the package files contains licence, copyright or distribution text. The article is CC BY-NC-ND (the register
quotes it verbatim), and it does not say whether that licence covers the software. The repository therefore holds **no
HWM14 code or data**: only URLs, sha256 identities and HWM14 *outputs*. `python -m abep_sim.atmosphere_orbit_v2
fetch-hwm14 DIR` downloads the package from NRL and verifies every hash. **Open for the owner:** neither NRL nor CCMC
states terms for using HWM14 outputs in a commercial bid (TERMS_NOT_EXPLICIT, verify).

## Build and validation
- Compiler: gfortran 13.3.0 (Ubuntu 24.04), no flags (the gfortran default, -O0), matching NRL's `Check/gfortran.txt`.
- Validation: NRL's `checkhwm14` output is **text-identical** to `Check/gfortran.txt`. Every build and every HWM14-enabled
  `check` re-runs this comparison and refuses on any difference.
- The project's batch driver (`DRIVER_F90` in the module, sha256 recorded in the manifest) calls `hwm14` twice per point:
  quiet-time with ap = [-1, -1], and total with ap = [0, ap(2)].
- HWM14 arguments are `real(4)`. The `iyd` year is irrelevant (`mod(iyd,1000)`); this was measured with 0.0 difference.

## Inputs recorded per row
`iyd` (YYDDD), UT seconds, geodetic altitude, latitude and longitude, and `ap(2)`. The ap value is the scenario's ECSS
Table 6-3 Ap (0 / 15 / 45 / 240), held constant as the 3-hour ap. This matches v1's constant `[Ap]*7` NRLMSIS input.
DWM07 converts these to Kp 0 / 3 / 4.89 / 8.35. HWM14 ignores F10.7, so the quiet winds are the same in every scenario,
and the build checks this.
