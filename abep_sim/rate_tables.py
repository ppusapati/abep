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


def maxwellian_rate(E_eV: np.ndarray, sigma_m2: np.ndarray, Te_eV: float, tail: str = "hold") -> float:
    """Below the first tabulated energy sigma = 0. Above the last one, `tail` decides: "hold" keeps the last value
    (an extrapolation assumption), "zero" drops it. Build scripts that care report both (see tail_sensitivity)."""
    E = np.asarray(E_eV, float); s = np.asarray(sigma_m2, float)
    if tail not in ("hold", "zero"):
        raise ValueError(f"tail must be 'hold' or 'zero', got {tail!r}")
    if Te_eV <= 0:
        return 0.0
    Emax = max(E.max(), 60 * Te_eV)
    x, sx = E, s
    if Emax > E.max():
        if tail == "hold":
            x, sx = np.append(E, Emax), np.append(s, s[-1])
        else:
            x, sx = np.append(E, [np.nextafter(E[-1], np.inf), Emax]), np.append(s, [0.0, 0.0])
    grid = np.unique(np.concatenate([x, np.linspace(0, Emax, 20000)]))
    sg = np.interp(grid, x, sx, left=0.0, right=sx[-1])
    integrand = sg * grid * np.exp(-grid / Te_eV)
    integral = np.trapezoid(integrand, grid) * QE ** 2                  # sigma * E dE, E in J
    return float(math.sqrt(8.0 / (math.pi * ME)) * (QE * Te_eV) ** -1.5 * integral)


def tail_sensitivity(E_eV, sigma_m2, eps_values) -> list[tuple[float, float]]:
    """(mean energy, relative rate difference hold-vs-zero tail) — how much of each rate rests on the extrapolation."""
    out = []
    for eps in eps_values:
        a = maxwellian_rate(E_eV, sigma_m2, eps / 1.5, "hold"); b = maxwellian_rate(E_eV, sigma_m2, eps / 1.5, "zero")
        out.append((float(eps), (a - b) / a if a > 0 else 0.0))
    return out


def write_hallthruster_table(path: str, E_eV, sigma_m2, threshold_eV: float, eps_max: float = 300.0, source: str = "",
                             tail: str = "hold", header_label: str = "Ionization energy"):
    rows = []
    for eps in np.arange(0.0, eps_max + 1.0, 1.0):
        Te = eps / 1.5
        rows.append((eps, maxwellian_rate(E_eV, sigma_m2, Te, tail) if Te > 0 else 0.0))
    with open(path, "w") as f:
        f.write(f"{header_label} (eV): {threshold_eV}\n")      # HallThruster.jl reads the number after ':' only
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
