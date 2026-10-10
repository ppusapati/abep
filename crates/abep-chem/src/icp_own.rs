//! Own ICP tables (NP-ICP-CHEM-AIR addendum_01 A1-OWN / A1-XE-SRC): the source representation of each table built for
//! the ICP registry, and its `.dat` / `.source` rendered by the admitted port of `rate_tables.write_hallthruster_table`
//! (`reference::hallthruster_table`, eps_max 300 eV). `examples/build_icp_own_tables.rs` writes the files once per
//! table; `tests/icp_own_tables.rs` regenerates every committed file byte for byte.


use crate::reference::{self, Tail, TailArg};
use abep_provenance::sha256_hex;
use abep_types::{AbepError, AbepResult};
use serde_json::{json, Value};
use std::f64::consts::PI;

pub const OWN_DIR: &str = "data/chemistry/icp";
pub const EPS_MAX_EV: f64 = 300.0;

/// Mukundan & Bhardwaj, arXiv:1604.08449v1 (document sha256 below), Table 2 (Krishnakumar-Srivastava form, Eq. 5).
pub const MB2016_SHA256: &str = "352c3233a4c914d50ebb84ebf8b7a6a333a94a7a3c98f2036a1523741333a5ca";
/// GK2008 (JPL DESCANSO open copy), the registered document of scaling_similarity.json sources.GK2008.
pub const GK2008_SHA256: &str = "a373c8a26137b7c7cd989880c303c4f6c1f84f20a11a02770047f6ba4c249e4e";
/// Unit of the Table 2 fit: 1e-18 cm^2 = 1e-22 m^2 (inferred; confirmed by two independent datasets, addendum_01).
pub const MB2016_UNIT_M2: f64 = 1e-22;

/// One Table 2 row: threshold I [eV], A, B_1..B_n.
pub struct KsFit {
    pub ion: &'static str,
    pub i_ev: f64,
    pub a: f64,
    pub b: &'static [f64],
}

pub const MB2016_XE1: KsFit = KsFit { ion: "Xe+", i_ev: 12.12, a: 5.1810e5, b: &[-5.5272e5, 4.3084e5, -1.0138e6, 4.3057e5] };
pub const MB2016_XE2: KsFit = KsFit {
    ion: "Xe2+",
    i_ev: 33.0,
    a: 2.0e5,
    b: &[-1.9897e5, 1.4518e6, -2.8675e7, 2.1198e8, -7.046e8, 1.1679e9, -9.4364e8, 2.9592e8],
};

impl KsFit {
    /// sigma(E) = (1 / (I E)) [A ln(E / I) + sum_i B_i (1 - I/E)^i] x unit, 0 at E <= I; negative fit values are 0.
    pub fn sigma_m2(&self, e_ev: f64) -> f64 {
        if e_ev <= self.i_ev {
            return 0.0;
        }
        let x = 1.0 - self.i_ev / e_ev;
        let mut s = self.a * (e_ev / self.i_ev).ln();
        let mut p = 1.0;
        for b in self.b {
            p *= x;
            s += b * p;
        }
        (s / (self.i_ev * e_ev) * MB2016_UNIT_M2).max(0.0)
    }
}

/// The ionization grid of A1-XE-SRC: I, then 0.5 eV steps to 20 eV, 1 eV to 100 eV, 10 eV to 1000 eV.
pub fn ks_grid(i_ev: f64) -> Vec<f64> {
    let mut g = vec![i_ev];
    let mut e = (i_ev * 2.0).floor() / 2.0 + 0.5;
    while e <= 20.0 + 1e-9 {
        if e > i_ev {
            g.push(e);
        }
        e += 0.5;
    }
    let mut e = e.ceil().max(21.0);
    while e <= 100.0 + 1e-9 {
        if e > i_ev {
            g.push(e);
        }
        e += 1.0;
    }
    let mut e = 110.0;
    while e <= 1000.0 + 1e-9 {
        if e > i_ev {
            g.push(e);
        }
        e += 10.0;
    }
    g
}

/// GK2008 Appendix D Table D-1, Hayashi [2] total excitation (pp. 473-474), transcribed from the PDF word layout
/// (rows matched to the energy column by vertical position). The onset 0 at 8.315 eV is the lowest Xe level
/// (Mukundan & Bhardwaj Table 3, 1s5). The value 2.6e-22 printed above the 9.0 eV row has no energy label and is
/// omitted (recorded in the xs provenance).
pub const GK2008_HAYASHI_EXC: &[(f64, f64)] = &[
    (8.315, 0.0),
    (9.0, 1.26e-21),
    (9.5, 1.31e-21),
    (10.0, 1.8e-21),
    (10.5, 2.4e-21),
    (11.0, 4.0e-21),
    (11.5, 6.2e-21),
    (12.0, 8.4e-21),
    (12.5, 1.05e-20),
    (13.0, 1.28e-20),
    (14.0, 1.7e-20),
    (15.0, 2.14e-20),
    (16.0, 2.55e-20),
    (18.0, 3.35e-20),
    (20.0, 3.73e-20),
    (25.0, 3.85e-20),
    (30.0, 3.57e-20),
    (40.0, 2.85e-20),
    (50.0, 2.4e-20),
    (60.0, 2.1e-20),
    (70.0, 1.85e-20),
    (80.0, 1.66e-20),
    (90.0, 1.52e-20),
    (100.0, 1.38e-20),
];

/// Mukundan & Bhardwaj Table 1: elastic differential cross sections [cm^2 / sr] at 0, 10, ..., 180 degrees
/// (Adibzadeh & Theodosiou), energies 5, 10, 100, 500, 1000 eV (the bracketed extrapolated rows are not used).
pub const MB2016_DCS: &[(f64, [f64; 19])] = &[
    (
        5.0,
        [
            2.34e-15, 1.74e-15, 1.20e-15, 7.52e-16, 4.49e-16, 3.00e-16, 2.72e-16, 2.97e-16, 3.06e-16, 2.57e-16, 1.56e-16,
            4.99e-17, 2.44e-18, 6.63e-17, 2.55e-16, 5.35e-16, 8.31e-16, 1.06e-15, 1.14e-15,
        ],
    ),
    (
        10.0,
        [
            3.74e-15, 2.76e-15, 1.93e-15, 1.24e-15, 7.11e-16, 3.70e-16, 1.89e-16, 1.10e-16, 8.01e-17, 6.43e-17, 5.03e-17,
            4.14e-17, 4.73e-17, 7.73e-17, 1.29e-16, 1.99e-16, 2.70e-16, 3.23e-16, 3.43e-16,
        ],
    ),
    (
        100.0,
        [
            4.34e-15, 1.11e-15, 1.28e-16, 2.37e-17, 6.94e-17, 4.34e-17, 4.87e-18, 5.59e-18, 2.29e-17, 2.38e-17, 1.20e-17,
            7.70e-18, 1.16e-17, 8.96e-18, 5.31e-19, 1.06e-17, 5.58e-17, 1.15e-16, 1.42e-16,
        ],
    ),
    (
        500.0,
        [
            6.10e-15, 8.66e-16, 1.29e-16, 4.46e-17, 1.70e-17, 1.06e-17, 1.06e-17, 8.27e-18, 3.18e-18, 6.85e-19, 4.20e-18,
            1.00e-17, 1.11e-17, 5.57e-18, 8.15e-19, 6.92e-18, 2.60e-17, 4.79e-17, 5.76e-17,
        ],
    ),
    (
        1000.0,
        [
            7.07e-15, 5.71e-16, 7.86e-17, 2.49e-17, 1.25e-17, 7.52e-18, 4.55e-18, 2.82e-18, 2.36e-18, 2.82e-18, 3.11e-18,
            2.33e-18, 8.21e-19, 2.47e-19, 2.54e-18, 8.32e-18, 1.61e-17, 2.29e-17, 2.55e-17,
        ],
    ),
];

/// sigma_m = 2 pi int (1 - cos t) dsigma/dOmega sin t dt, trapezoid rule on the 10-degree grid [m^2].
pub fn momentum_transfer_m2(dcs_cm2: &[f64; 19]) -> f64 {
    let f = |k: usize| {
        let t = (10.0 * k as f64).to_radians();
        dcs_cm2[k] * t.sin() * (1.0 - t.cos())
    };
    let h = 10f64.to_radians();
    let mut s = 0.0;
    for k in 0..18 {
        s += 0.5 * h * (f(k) + f(k + 1));
    }
    2.0 * PI * s * 1e-4
}

/// One own table: names, points and the text of every committed file.
#[derive(Debug, Clone)]
pub struct OwnTable {
    pub name: String,
    pub process: &'static str,
    pub threshold_ev: f64,
    pub header_label: &'static str,
    pub tail: Tail,
    pub points: Vec<(f64, f64)>,
    pub source_text: String,
    pub provenance: Value,
}

impl OwnTable {
    pub fn table_rel(&self) -> String {
        format!("{OWN_DIR}/tables/{}.dat", self.name)
    }

    pub fn xs_rel(&self) -> String {
        format!("xs/{}.json", self.name)
    }

    /// (dat text, source text) by the admitted writer port.
    pub fn render(&self) -> AbepResult<(String, String)> {
        let (e, s): (Vec<f64>, Vec<f64>) = self.points.iter().copied().unzip();
        let t = reference::hallthruster_table(
            &e,
            &s,
            self.threshold_ev,
            EPS_MAX_EV,
            &TailArg::from(self.tail),
            self.header_label,
            &self.source_text,
        )
        .map_err(AbepError::from)?;
        Ok((t.text, t.source_text.unwrap_or_default()))
    }

    /// The xs file text (schema icp_chem_xs_v1), naming the rendered table and its sha256.
    pub fn xs_text(&self) -> AbepResult<String> {
        let (dat, src) = self.render()?;
        let v = json!({
            "schema": "icp_chem_xs_v1",
            "kind": "CROSS_SECTION",
            "process": self.process,
            "table": self.table_rel(),
            "table_sha256": sha256_hex(dat.as_bytes()),
            "table_source": format!("{}.source", self.table_rel()),
            "table_source_sha256": sha256_hex(src.as_bytes()),
            "threshold_eV": self.threshold_ev,
            "header_label": self.header_label,
            "tail": self.tail.as_str(),
            "eps_max_eV": EPS_MAX_EV,
            "interpolation": "linear in sigma(E) between points; sigma = 0 below the first point; above the last point the declared tail (NP-ICP-CHEM-AIR IX-02..IX-04; abep_chem::reference::maxwellian_rate)",
            "units": {"E": "eV", "sigma": "m^2"},
            "n_points": self.points.len(),
            "points": self.points.iter().map(|(e, s)| json!([e, s])).collect::<Vec<_>>(),
            "provenance": self.provenance,
        });
        let mut t = serde_json::to_string_pretty(&v).map_err(|e| AbepError::Model { message: e.to_string() })?;
        t.push('\n');
        Ok(t)
    }
}

fn common_provenance(source: &str, check: &str, level: u32, extra: Value) -> Value {
    json!({
        "addendum": "NP-ICP-CHEM-AIR addendum_01 (A1-OWN, A1-XE-SRC)",
        "source": source,
        "independent_check": check,
        "evidence_level": level,
        "builder": "crates/abep-chem/src/icp_own.rs + examples/build_icp_own_tables.rs (admitted reference::hallthruster_table)",
        "detail": extra,
    })
}

/// The Xe tables of A1-XE-SRC, in build order (one table per commit).
pub fn xe_tables() -> Vec<OwnTable> {
    let ion_pts: Vec<(f64, f64)> = ks_grid(MB2016_XE1.i_ev).into_iter().map(|e| (e, MB2016_XE1.sigma_m2(e))).collect();
    let el_pts: Vec<(f64, f64)> = MB2016_DCS.iter().map(|(e, d)| (*e, momentum_transfer_m2(d))).collect();
    vec![
        OwnTable {
            name: "ionization_Xe_mb2016".into(),
            process: "XE-ION-01",
            threshold_ev: 12.13,
            header_label: "Ionization energy",
            tail: Tail::Hold,
            points: ion_pts,
            source_text: "NP-ICP-CHEM-AIR XE-ION-01 (NOMINAL). e + Xe -> Xe+ + 2e partial ionization. Cross section: V. Mukundan & A. Bhardwaj, arXiv:1604.08449v1 (2016; Proc. R. Soc. A, doi 10.1098/rspa.2015.0727), sha256 352c3233..., Table 2 row Xe+ (Eq. 5 Krishnakumar-Srivastava form fitted to Rejoub, Lindsay & Stebbings, PRA 65, 042713 (2002)); unit 1e-22 m^2 inferred and cross-checked (Stephan & Maerk sigma(Xe+) and Rapp & Englander-Golden gross, GK2008 Table D-1); evaluated on the addendum_01 grid 12.12-1000 eV, held above. Header 12.13 eV (contract threshold, GK2008 p. 118). Maxwellian-integrated by the admitted Rust port of rate_tables.write_hallthruster_table. Energy column = mean electron energy 3/2 Te. Evidence level 4.".into(),
            provenance: common_provenance(
                "Mukundan & Bhardwaj 2016, arXiv:1604.08449v1, Table 2 row Xe+ (I 12.12 eV, A 5.1810E5, B 5.5272E5 neg, 4.3084E5, 1.0138E6 neg, 4.3057E5)",
                "unit 1e-22 m^2: sigma(Xe+) within -5 % / +3 % of Stephan & Maerk (GK2008 Table D-1) at 35-100 eV; sigma(Xe+) + 2 sigma(Xe2+) within -4 % / +3 % of Rapp & Englander-Golden gross at 20-100 eV; -35 % at 15 eV (near-threshold fit, recorded uncertainty)",
                4,
                json!({"grid": "I, 0.5 eV steps to 20 eV, 1 eV to 100 eV, 10 eV to 1000 eV", "fit_range": "9-10000 eV (paper)"}),
            ),
        },
        OwnTable {
            name: "excitation_Xe_total_hayashi_gk2008".into(),
            process: "XE-EXC-01",
            threshold_ev: 10.0,
            header_label: "Excitation energy",
            tail: Tail::Hold,
            points: GK2008_HAYASHI_EXC.to_vec(),
            source_text: "NP-ICP-CHEM-AIR XE-EXC-01 (NOMINAL, lumped). e + Xe -> e + Xe* total excitation. Cross section: Hayashi, J. Phys. D 16, 581 (1983) as tabulated in D. M. Goebel & I. Katz, Fundamentals of Electric Propulsion (JPL 2008), Appendix D Table D-1 (pp. 473-474), document sha256 a373c8a2...; transcribed from the PDF word layout; onset 0 at 8.315 eV (lowest level, Mukundan & Bhardwaj 2016 Table 3); the unlabelled 2.6e-22 above the 9.0 eV row omitted; held above 100 eV. Header 10.0 eV = the representative energy loss per event (GK2008 p. 97 'average excitation potential is 10 V'). Maxwellian-integrated by the admitted Rust port of rate_tables.write_hallthruster_table. Energy column = mean electron energy 3/2 Te. Evidence level 5 (textbook compilation).".into(),
            provenance: common_provenance(
                "GK2008 Appendix D Table D-1, Hayashi [2] Total Excitation column",
                "Maxwellian rates against GK2008 Table E-1 excitation column (same data, independent integration)",
                5,
                json!({"omitted": "2.6e-22 m^2 printed above the 9.0 eV row without an energy label", "header_basis": "GK2008 p. 97"}),
            ),
        },
        OwnTable {
            name: "elastic_Xe_mb2016_dcs".into(),
            process: "XE-EL-01",
            threshold_ev: 0.0,
            header_label: "Momentum transfer, no inelastic energy loss",
            tail: Tail::Hold,
            points: el_pts,
            source_text: "NP-ICP-CHEM-AIR XE-EL-01 (NOMINAL). e + Xe elastic momentum transfer. sigma_m(E) = 2 pi int (1 - cos t) dsigma/dOmega sin t dt by the trapezoid rule on the 10-degree grid of the Mukundan & Bhardwaj 2016 Table 1 differential cross sections (Adibzadeh & Theodosiou), arXiv:1604.08449v1 sha256 352c3233..., at 5, 10, 100, 500, 1000 eV; sigma = 0 below 5 eV (rate is a lower bound below T_e ~ 5 eV), held above 1000 eV. Header 0 eV (no inelastic loss). Maxwellian-integrated by the admitted Rust port of rate_tables.write_hallthruster_table. Energy column = mean electron energy 3/2 Te. Evidence level 5 (derived from tabulated theory).".into(),
            provenance: common_provenance(
                "Mukundan & Bhardwaj 2016 Table 1 (DCS, cm^2/sr)",
                "information: GK2008 Eq. (3.6-13) Maxwellian sigma_en 3.1e-19 m^2 at T_e 5 eV against sigma_m(5 eV) 3.4e-19 m^2",
                5,
                json!({"integration": "trapezoid in theta, 19 nodes 0-180 deg"}),
            ),
        },
    ]
}
