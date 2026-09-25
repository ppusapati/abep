"""Maxwellian rate-coefficient tables from cross sections, in HallThruster.jl's format (mean energy = 3/2 Te).

    k(Te) = sqrt(8/(pi m_e)) (e Te)^(-3/2) * int sigma(E) E exp(-E/Te) dE      (E, Te in joules inside the integral)

Used to produce the N-ionisation, N2-dissociation, N2-excitation and N-elastic tables that HallThruster.jl does not ship.
Cross sections must come from a cited source (LXCat: Itikawa 2006 N2; Cosby 1993 dissociation; Kim/Desclaux or BEB for N);
this module does the integration and the file format, nothing more.
"""
from __future__ import annotations
import math
import numpy as np

ME = 9.10938e-31; QE = 1.602176634e-19


def maxwellian_rate(E_eV: np.ndarray, sigma_m2: np.ndarray, Te_eV: float) -> float:
    E = np.asarray(E_eV, float); s = np.asarray(sigma_m2, float)
    if Te_eV <= 0:
        return 0.0
    Emax = max(E.max(), 60 * Te_eV)
    x = np.concatenate([E, [Emax]]) if Emax > E.max() else E
    sx = np.concatenate([s, [s[-1]]]) if Emax > E.max() else s
    grid = np.unique(np.concatenate([x, np.linspace(0, Emax, 20000)]))
    sg = np.interp(grid, x, sx, left=0.0, right=sx[-1])
    integrand = sg * grid * np.exp(-grid / Te_eV)
    integral = np.trapezoid(integrand, grid) * QE ** 2                  # sigma * E dE, E in J
    return float(math.sqrt(8.0 / (math.pi * ME)) * (QE * Te_eV) ** -1.5 * integral)


def write_hallthruster_table(path: str, E_eV, sigma_m2, threshold_eV: float, eps_max: float = 300.0, source: str = ""):
    rows = []
    for eps in np.arange(0.0, eps_max + 1.0, 1.0):
        Te = eps / 1.5
        rows.append((eps, maxwellian_rate(E_eV, sigma_m2, Te) if Te > 0 else 0.0))
    with open(path, "w") as f:
        f.write(f"Ionization energy (eV): {threshold_eV}\n")
        f.write("Energy (eV)\tRate coefficient (m^3/s)\n")
        for eps, k in rows:
            f.write(f"{eps:.1f}\t{k:.6e}\n")
    if source:
        with open(path + ".source", "w") as f:
            f.write(source + "\n")
    return rows


def step_cross_section_rate(sigma0: float, E_th: float, Te: float) -> float:
    """Closed form for sigma = sigma0 H(E - E_th): k = sigma0 sqrt(8 e Te/(pi m_e)) (1 + E_th/Te) exp(-E_th/Te)."""
    return sigma0 * math.sqrt(8 * QE * Te / (math.pi * ME)) * (1 + E_th / Te) * math.exp(-E_th / Te)
