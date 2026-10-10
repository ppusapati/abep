//! F7 records of `abep_sim/design/architecture_optimizer.py` that read the committed lane deliverables: the common
//! design vector (`design_vector_blocks`), the system-objective refusals that are not admitted elsewhere
//! (`heat_rejection`, `electron_margin`, `hall_gated_thrust`), the A9.19 flight-configuration element list
//! (`flight_configuration_elements`), the architecture-question map (`architecture_questions`) and the TPMC backend
//! policy. Values are the reference's insertion-ordered Python-shaped JSON (`abep_types::pyjson`), so dict iteration
//! order and every embedded `repr` match the reference.

use crate::err::{model, DResult, DesignError};
use crate::f1view::F1View;
use crate::inputs::{F3D_REL, F3_REL, F4_REL, F5_REL, F6_REL, MP_REL, P3_REL, PARITY_REL};
use crate::pv::Pv;
use abep_gaspath::compressor_synthesis as cs;
use abep_gaspath::plenum_feed::FilterCase;
use abep_types::pyjson::{loads, py_repr, py_repr_str, read_text_utf8, Dict, Value};
use std::path::Path;

pub const F1_REL: &str = "docs/design_synthesis/f1_intake/f1_intake_synthesis_v1.json";
pub const P2_REL: &str = "docs/experiments/hall_icp/p2_impedance_map/p2_impedance_prep_v1.json";
pub const RFQ_REL: &str = "docs/procurement/rfq_a9_v3/rfq_a9_v3.json";
pub const ENS_REL: &str = abep_mission::objective::ENS_REL;
pub const FLIGHT_CONFIGURATION: &str = "hall_icp_neutralizer";
pub const GROUND_REFERENCE_CONFIGURATION: &str = "hall_c1_reference";
pub const RF_FREQUENCY_HZ: f64 = 13.56e6;
pub const LAB_RF_FORWARD_W_RANGE: (f64, f64) = (0.0, 500.0);
pub const DESIGN_STATE_SET_ID: &str = "atmosphere_msis21_orbit_v1_design_states_v2";
pub const DESIGN_STATE_SET_SHA256: &str = "60073e214cf5edb92d7eacf70be1491ad29ff72f19db0ef3b96a4b30da6f4049";
pub const ORBIT_BASIS_LABEL: &str = "BROAD_ENVELOPE_ALL_INCLINATIONS_ALL_LTAN_NOT_MISSION_ICD";

pub const UNLOCK_Q_REJECT: &str = "the P3 coupled network solved: ICP geometry P3-G-01..08, emittances P3-R-01..04, \
conductances P3-K-01..06, heat terms from P1/P2 data (Q_RF/match, Q_collector) and Phase-1 plume data (Q_plume)";
pub const UNLOCK_I_E_MARGIN: &str = "registered I_d,max,H1 (A9.3 OQ-A907-02, from measured H-1 operation) AND a P1 \
ICP-45A result EVALUATED_ENGINEERING_ONLY (discharge-OFF capacity, one-sided LCB, A9.4 P1Q-10 / A9.5 P1Q-16) for the \
single flight configuration hall_icp_neutralizer (A9.19; the ground C1 reference is never a flight objective, A9.20)";

/// Ordered dict builder.
#[derive(Default)]
pub struct D(Dict);

impl D {
    pub fn new() -> Self {
        D(Dict::new())
    }
    pub fn v(mut self, k: &str, v: Value) -> Self {
        self.0.insert(k, v);
        self
    }
    pub fn s(self, k: &str, v: &str) -> Self {
        self.v(k, Value::str(v))
    }
    pub fn f(self, k: &str, x: f64) -> Self {
        self.v(k, Value::Float(x))
    }
    pub fn build(self) -> Value {
        Value::Dict(self.0)
    }
}

pub fn strs(xs: &[&str]) -> Value {
    Value::List(xs.iter().map(|s| Value::str(*s)).collect())
}

pub fn floats(xs: &[f64]) -> Value {
    Value::List(xs.iter().map(|x| Value::Float(*x)).collect())
}

/// Read a pinned deliverable as insertion-ordered Python JSON.
pub fn read_py(repo: &Path, rel: &str) -> DResult<Value> {
    let sha = crate::inputs::PINNED
        .iter()
        .find(|(p, _)| *p == rel)
        .map(|(_, s)| *s)
        .ok_or_else(|| model(format!("RuntimeError: {rel} is not a registered pinned input")))?;
    let bytes = abep_provenance::read_verified(&repo.join(rel), sha)?;
    let text = read_text_utf8(&bytes).map_err(|e| model(format!("RuntimeError: {rel}: {e:?}")))?;
    loads(&text).map_err(|e| model(format!("RuntimeError: {rel}: {e:?}")))
}

fn sch(rel: &str, what: &str) -> DesignError {
    model(format!("RuntimeError: {rel}: schema: {what}"))
}

/// `_obj(name, status, value, units, evidence_class, source, reason, unlock, **extra)`.
pub fn obj(name: &str, status: &str, value: Value, units: &str, reason: Value, unlock: Value) -> D {
    D::new()
        .s("objective", name)
        .s("status", status)
        .v("value", value)
        .s("units", units)
        .v("evidence_class", Value::Null)
        .v("source", Value::Null)
        .v("reason", reason)
        .v("unlock", unlock)
}

fn var(
    id: &str,
    block: &str,
    symbol: &str,
    value: Value,
    units: &str,
    basis: &str,
    source: &str,
    ec: &str,
    status: &str,
) -> D {
    D::new()
        .s("id", id)
        .s("block", block)
        .s("symbol", symbol)
        .v("value", value)
        .s("units", units)
        .s("basis", basis)
        .s("source", source)
        .s("evidence_class", ec)
        .s("status", status)
}

fn var_v(
    id: &str,
    block: &str,
    symbol: &str,
    value: Value,
    units: &Value,
    basis: &Value,
    source: &str,
    ec: &Value,
    status: &Value,
) -> D {
    D::new()
        .s("id", id)
        .s("block", block)
        .s("symbol", symbol)
        .v("value", value)
        .v("units", units.clone())
        .v("basis", basis.clone())
        .s("source", source)
        .v("evidence_class", ec.clone())
        .v("status", status.clone())
}

/// `isy.f1q02_label()`.
pub fn f1q02_label() -> Value {
    D::new()
        .s("label", "PARAMETRIC_SENSITIVITY")
        .s("use", "BUDGETING_ONLY")
        .v("not", strs(&["CBE", "FROZEN_INTAKE_MASS", "STRUCTURAL_QUALIFICATION"]))
        .s("lock1_condition", "SOURCED_STRUCTURAL_DEFINITION_REQUIRED_BEFORE_LOCK_1")
        .v("structural_inputs", F1Q02_STRUCTURAL_INPUTS.with(|x| x.clone()))
        .s("authority", "A9.13 S6.1 / F1Q-02 (BUDGETING_ASSUMPTION_SOURCED_BEFORE_LOCK_1)")
        .s(
            "statement",
            "parametric budgeting sensitivity only: never a CBE, a frozen intake mass or a structural qualification \
             statement; sourced structural definition required before LOCK-1",
        )
        .build()
}

thread_local! {
    static F1Q02_STRUCTURAL_INPUTS: Value = strs(&[
        "wall_material", "wall_thickness_mm", "coating_ao", "coating_density_kg_m3", "support_mass_frac",
    ]);
}

/// `design_vector_blocks(repo)`: the common design vector, block by block, from the lanes that own each block.
pub fn design_vector_blocks(repo: &Path, f1: &F1View, filters: &[FilterCase], n_required: usize) -> DResult<Value> {
    let f3 = read_py(repo, F3_REL)?;
    let f4 = read_py(repo, F4_REL)?;
    let f5 = read_py(repo, F5_REL)?;
    let f6 = read_py(repo, F6_REL)?;
    let p3 = read_py(repo, P3_REL)?;
    let mp = read_py(repo, MP_REL)?;
    let mut blocks = vec![];
    let fs = |x: &[f64]| floats(x);
    let intake =
        vec![
        var("x_intake.A", "x_intake", "A", fs(&f1.area_m2), "m^2", "intake frontal (ram) area grid",
            &format!("{F1_REL} design_space.variables.area_m2"), "assumed", "SEARCHED (F1 grid)").build(),
        var("x_intake.d", "x_intake", "d", fs(&f1.d_mm), "mm", "channel diameter; flow, drag and wall area are \
d-invariant at fixed L/d (F1-02), so d is collapsed in the coupled search", &format!("{F1_REL} design_space"),
            "assumed", "COLLAPSED (d-invariant objectives)").build(),
        var("x_intake.L_over_d", "x_intake", "L/d", fs(&f1.l_over_d), "-", "channel aspect ratio grid (frozen TPMC \
surface nodes)", &format!("{F1_REL} design_space"), "assumed", "SEARCHED (F1 grid)").build(),
        var("x_intake.phi", "x_intake", "phi", fs(&f1.phi), "-", "open-area fraction grid (frozen surface nodes)",
            &format!("{F1_REL} design_space"), "assumed", "SEARCHED (F1 grid)").build(),
        var("x_intake.alpha_kernel", "x_intake", "(alpha, kernel)", f1.scenario_axes.clone(), "-",
            "surface accommodation and gas-surface kernel: TBD evidence (F1-P-07 / F1-P-08), carried as scenario \
axis, never optimised", &format!("{F1_REL} items F1-P-07, F1-P-08"), "TBD", "CONTEXT_AXIS (uncertainty, F8)").build(),
        var("x_intake.theta", "x_intake", "theta", floats(&[0.0, 5.0]), "deg", "pointing error: no AOCS budget \
(F1-P-09); 0 deg everywhere, 5 deg (largest frozen node) at the design state only", &format!("{F1_REL} items F1-P-09"),
            "TBD", "CONTEXT_AXIS (uncertainty, F8)").build(),
        var("x_intake.structure", "x_intake", "(t_wall, coating, support)", Value::str("TBD"), "mixed",
            "structural inputs of the geometric mass model are TBD (F1-P-02..05); the code-default case is a labelled \
parametric sensitivity case; the wall area is the mass proxy. A9.13 S6.1 / F1Q-02: PARAMETRIC_SENSITIVITY, budgeting \
only; never a CBE, frozen intake mass or structural qualification; sourced structural definition required before \
LOCK-1", &format!("{F1_REL} items F1-P-02..05"), "TBD", "TBD")
            .v("f1q02", f1q02_label())
            .build(),
        var("x_intake.orbit_states", "x_intake", "orbit / atmosphere states",
            D::new()
                .s("design_state_set", DESIGN_STATE_SET_ID)
                .s("sha256", DESIGN_STATE_SET_SHA256)
                .v("n_required_states", Value::int(n_required as i64))
                .s("design_case_reference", abep_mission::intake_drag::DESIGN_CASE_STATE_ID)
                .s("orbit_basis", ORBIT_BASIS_LABEL)
                .build(),
            "-", "every required state of the frozen design-state set v2 (A9.14 S9.8 OD3) plus the design-case \
reference point; broad envelope, inclination / LTAN TBD (A9.21)", &format!("{F1_REL} coverage_rule.design_state_set"),
            "model-derived", "FROZEN_DATASET (all states evaluated)").build(),
    ];
    blocks.push(
        D::new()
            .s("block", "x_intake")
            .s("lane", "F1")
            .s("path", F1_REL)
            .s("state", "SEARCHED")
            .v("variables", Value::List(intake))
            .build(),
    );

    let case_ids: Vec<Value> = filters.iter().map(|f| Value::str(f.case_id.clone())).collect();
    let mut roles = Dict::new();
    for f in filters {
        roles.insert(f.case_id.clone(), Value::str(f.role.clone()));
    }
    let filt = vec![
        var("x_filter.case", "x_filter", "filter case", Value::List(case_ids), "-", "F4 filter cases built through \
F2's public API: 'none' (FC-00 REFERENCE BOUND only, A9.13 S6.5), loss-free parametric screens tau 0.9 / 0.7 / 0.5 and \
the repository placeholder law (PLACEHOLDER_NOT_A_FLIGHT_DESIGN). Every real filter concept is TBD in F2. Context axis: \
the filter's protection benefit is NOT_EVALUATED, so a flow-only comparison against 'none' would score that TBD \
benefit as zero", &format!("{F2_REL}; abep_sim/design/plenum_feed.py filter_cases()"), "TBD",
            "CONTEXT_AXIS (every filter number is PARAMETRIC_SENSITIVITY)").build(),
        var("x_filter.mass", "x_filter", "m_filter", Value::str("TBD"), "kg", "filter areal mass / face area TBD (F2)",
            F2_REL, "TBD", "TBD").build(),
        var("x_filter.role", "x_filter", "role", Value::Dict(roles), "-", "A9.13 S6.4 / S6.5 / S6.19: separate \
production-path element between IF-A1 and IF-A2; baseline inert / low-recombination; catalytic O -> O2 research \
variant only; FC-00 reference bound only", "abep_sim/design/filter_stage.py ROLES / INTERFACE_POSITION", "definition",
            "DEFINITION").build(),
    ];
    blocks.push(
        D::new()
            .s("block", "x_filter")
            .s("lane", "F2 (through F4 filter cases)")
            .s("path", F2_REL)
            .s("state", "CONTEXT_AXIS_NOT_SEARCHED")
            .v("variables", Value::List(filt))
            .build(),
    );

    let sv: Vec<&Value> =
        f3.g("search_variables").arr().ok_or_else(|| sch(F3_REL, "search_variables"))?.iter().collect();
    let f4sv = f4.g("search_variables").arr().ok_or_else(|| sch(F4_REL, "search_variables"))?;
    let x_comp =
        f4sv.iter().find(|x| x.g("id").s() == Some("x_compressor")).ok_or_else(|| sch(F4_REL, "x_compressor"))?;
    let comp_ids = x_comp.g("value").cloned().ok_or_else(|| sch(F4_REL, "x_compressor.value"))?;
    let n_comp = comp_ids.arr().map(|a| a.len()).unwrap_or(0);
    let mut comp_vars = vec![var(
        "x_compressor.design_id",
        "x_compressor",
        "design",
        comp_ids,
        "-",
        "union of the F3 per-case Pareto ids (the compressor set F4 coupled; N_drag = 0 for every member: no drag-stage \
design is feasible, F3-01)",
        &format!("{F4_REL} search_variables x_compressor; {F3D_REL}"),
        "model-derived (PARAMETRIC_SENSITIVITY)",
        &format!(
            "SEARCHED (F3 front union only: {n_comp} designs, a subset of those passing F3's inlet-independent gates; \
sets are Pareto within this subset, INT-01)"
        ),
    )
    .build()];
    for k in ["N_turbo", "A_turbo", "R_turbo", "N_drag", "R_rotor", "RPM", "h", "w", "L", "xi"] {
        if let Some(x) = sv.iter().find(|x| x.g("id").s() == Some(k)) {
            let src = x.g("source").map(py_str_value).unwrap_or_default();
            comp_vars.push(
                var_v(
                    &format!("x_compressor.{k}"),
                    "x_compressor",
                    k,
                    x.g("value").cloned().unwrap_or(Value::Null),
                    x.g("units").unwrap_or(&Value::Null),
                    x.g("basis").unwrap_or(&Value::Null),
                    &format!("{F3_REL} search_variables {k} ({src})"),
                    x.g("evidence_class").unwrap_or(&Value::Null),
                    x.g("status").unwrap_or(&Value::Null),
                )
                .build(),
            );
        }
    }
    let mut fixed = Dict::new();
    for c in f3.g("coefficients").arr().ok_or_else(|| sch(F3_REL, "coefficients"))? {
        if c.g("role").s() == Some("FIXED_CODE_DEFAULT") {
            fixed.insert(c.g("id").s().unwrap_or_default().to_string(), c.g("value").cloned().unwrap_or(Value::Null));
        }
    }
    comp_vars.push(
        var(
            "x_compressor.fixed_coefficients",
            "x_compressor",
            "DragCompressor coefficients",
            Value::Dict(fixed),
            "mixed",
            "uncited code defaults (not searched: no accessed open source gives a value or a range, \
compressor_downselect CD-01); local elasticities only in F8",
            &format!("{F3_REL} coefficients (role FIXED_CODE_DEFAULT)"),
            "assumed",
            "FIXED_CODE_DEFAULT_UNCITED",
        )
        .build(),
    );
    comp_vars.push(
        var("x_compressor.hub_ratio", "x_compressor", "nu = R_hub / R_tip", floats(&cs::HUB_RATIO_PARAMETRIC), "-",
            "A9.13 S6.7 explicit hub ratio / blade span; searched values are a declared PARAMETRIC_SENSITIVITY coverage \
of [0, 1); nu = 0 = zero-hub analytical bound only; bounds TBD from shaft / bearing, rotor structural, motor / \
interface, manufacturability and pumping interfaces", "abep_sim/design/compressor_synthesis.py HUB_RATIO_PARAMETRIC",
            "assumed", "SEARCHED_IN_F3 (PARAMETRIC_SENSITIVITY; the F7 front-union subset predates it)").build(),
    );
    blocks.push(
        D::new()
            .s("block", "x_compressor")
            .s("lane", "F3")
            .s("path", F3_REL)
            .s("state", "SEARCHED")
            .v("variables", Value::List(comp_vars))
            .build(),
    );

    let mut pv = vec![];
    for x in f4sv {
        let id = x.g("id").s().unwrap_or_default();
        if !id.starts_with("x_plenum.") {
            continue;
        }
        let sym = id.split_once('.').map(|p| p.1).unwrap_or(id);
        pv.push(
            var_v(
                &format!("x_plenum.{sym}"),
                "x_plenum",
                sym,
                x.g("value").cloned().unwrap_or(Value::Null),
                x.g("units").unwrap_or(&Value::Null),
                x.g("basis").unwrap_or(&Value::Null),
                &format!("{F4_REL} search_variables {id}"),
                x.g("evidence_class").unwrap_or(&Value::Null),
                x.g("status").unwrap_or(&Value::Null),
            )
            .build(),
        );
    }
    pv.push(
        var("x_plenum.P_set", "x_plenum", "P_set", floats(&crate::optimizer::UPSTREAM_TARGETS_PA), "Pa",
            "plenum set pressure (H-1 required inlet state TBD, F4-P-10 / F5 IFD-F4-01..05): requirement-level context \
axis of the <= 0.1 Pa sensitivity / fallback branch (A9.13 S6.11); the higher-pressure primary direction is \
NOT_EVALUATED_OUT_OF_DOMAIN (S6.8) and not repeated here", &format!("{F4_REL} requirement_sweep.P_req_Pa (<= 0.1 Pa)"),
            "TBD", "CONTEXT_AXIS (requirement sweep)").build(),
    );
    pv.push(
        var(
            "x_plenum.wall_gamma",
            "x_plenum",
            "gamma_O wall",
            Value::str("TBD"),
            "-",
            "plenum wall O recombination \
probability (F4-P-06): WALL-G0 (gamma = 0 bound, owner H1F-IN-02 lining) nominal context, WALL-TI64-DB (uncited DB \
prior) sensitivity context",
            &format!("{F4_REL} items F4-P-06"),
            "TBD",
            "CONTEXT_AXIS",
        )
        .build(),
    );
    pv.push(
        var(
            "x_plenum.mass",
            "x_plenum",
            "m_plenum",
            Value::str("TBD"),
            "kg",
            "plenum mass TBD (F4-P-16); volume is \
the mass proxy",
            &format!("{F4_REL} items F4-P-16"),
            "TBD",
            "TBD",
        )
        .build(),
    );
    pv.push(
        var(
            "x_plenum.control_mode",
            "x_plenum",
            "control mode",
            D::new()
                .s("ORBIT_STATE_SCHEDULED_SETPOINT", "BASELINE_CONTROL_MODE")
                .s("FIXED_SETPOINT", "FALLBACK_DEGRADED_MODE_AND_COMPARISON_REFERENCE")
                .build(),
            "-",
            "A9.13 S6.10: orbit-state-scheduled setpoint = baseline (controller-available inputs only, schedule \
NOT_FROZEN); fixed setpoint = fallback / reference",
            "abep_sim/design/plenum_feed.py scheduled_operation / \
compare_control_modes",
            "definition",
            "DEFINITION",
        )
        .build(),
    );
    blocks.push(
        D::new()
            .s("block", "x_plenum")
            .s("lane", "F4")
            .s("path", F4_REL)
            .s("state", "SEARCHED")
            .v("variables", Value::List(pv))
            .build(),
    );

    let xd = f5.ptr("/x_hall_design_space/definition").ok_or_else(|| sch(F5_REL, "x_hall_design_space"))?;
    let mut hv = vec![];
    for (k, b) in xd.g("variables").obj().ok_or_else(|| sch(F5_REL, "variables"))?.iter() {
        hv.push(
            var(
                &format!("x_Hall.{k}"),
                "x_Hall",
                k,
                D::new().v("window", b.clone()).build(),
                "mm",
                "F5 x_Hall bound (window, OPEN)",
                &format!("{F5_REL} x_hall_design_space.definition.variables.{k}"),
                "model-derived",
                "OPEN (window)",
            )
            .build(),
        );
    }
    hv.push(
        var(
            "x_Hall.constraints",
            "x_Hall",
            "geometric windows",
            xd.g("constraints").cloned().unwrap_or(Value::Null),
            "mixed",
            "area, d/h, L/h windows and the inner-coil solid-core floor; admissibility via the F5 builder's \
geometric_admissibility (fail closed)",
            &format!("{F5_REL} x_hall_design_space.definition.constraints"),
            "model-derived",
            "OPEN",
        )
        .build(),
    );
    hv.push(
        var(
            "x_Hall.freeze_rollup",
            "x_Hall",
            "77 H-1 parameters",
            f5.ptr("/freeze_rollup/counts").cloned().unwrap_or(Value::Null),
            "-",
            "freeze-status counts of the H-1 \
engineering-article parameters (FREEZE_CANDIDATE items are owner rules, not design values)",
            &format!("{F5_REL} freeze_rollup"),
            "assumed",
            "NOT_FROZEN",
        )
        .build(),
    );
    blocks.push(
        D::new()
            .s("block", "x_Hall")
            .s("lane", "F5")
            .s("path", F5_REL)
            .s("state", "BOUNDED_NOT_SEARCHED_NO_EVALUABLE_OBJECTIVE")
            .v("variables", Value::List(hv))
            .v("not_evaluated", xd.g("not_evaluated").cloned().unwrap_or(Value::Null))
            .build(),
    );

    let mut iv = vec![];
    for x in f6.ptr("/design_vector/variables").arr().ok_or_else(|| sch(F6_REL, "design_vector"))? {
        let sym = x.g("symbol").s().unwrap_or_default();
        let b = x.g("bounds").ok_or_else(|| sch(F6_REL, "bounds"))?;
        let ec = match b.g("evidence_class") {
            Some(v) if v.truthy() => v.clone(),
            _ => Value::str("TBD"),
        };
        iv.push(
            var_v(
                &format!("x_ICP.{sym}"),
                "x_ICP",
                sym,
                D::new()
                    .v("lo", b.g("lo").cloned().unwrap_or(Value::Null))
                    .v("hi", b.g("hi").cloned().unwrap_or(Value::Null))
                    .build(),
                x.g("units").unwrap_or(&Value::Null),
                x.g("name").unwrap_or(&Value::Null),
                &format!("{F6_REL} design_vector.variables {}", py_str_value(x.g("id").unwrap_or(&Value::Null))),
                &ec,
                b.g("status").unwrap_or(&Value::Null),
            )
            .v("requires", b.g("requires").cloned().unwrap_or(Value::Null))
            .build(),
        );
    }
    blocks.push(
        D::new()
            .s("block", "x_ICP")
            .s("lane", "F6")
            .s("path", F6_REL)
            .s("state", "NOT_SEARCHABLE_BOUNDS_TBD")
            .v("variables", Value::List(iv))
            .build(),
    );

    let chain = mp.ptr("/power/icp_rf_chain").ok_or_else(|| sch(MP_REL, "power.icp_rf_chain"))?;
    let rv = vec![
        var("x_RF.frequency", "x_RF", "f_RF", Value::Float(RF_FREQUENCY_HZ), "Hz", "13.56 MHz ICP drive (row 72 / A9)",
            &format!("{MP_REL} items_v2 MPV2-P07; abep_sim/bus_boundary_a9_v2.py RF_FREQUENCY_HZ"), "owner-allocation",
            "OWNER_GIVEN").build(),
        var("x_RF.chain_topology", "x_RF", "RF chain", chain.g("chain").cloned().unwrap_or(Value::Null), "-",
            "flight-representative DC-RF source, directional coupler, 50-ohm line, local adjustable match, antenna (A9.2 \
/ A9.3 decisions)", &format!("{MP_REL} power.icp_rf_chain"), "assumed", "LOCAL_MATCH_SELECTED_FOR_DEVELOPMENT")
            .build(),
        var("x_RF.component_ratings", "x_RF", "ratings", Value::str("TBD"), "W; V; A", "RF component ratings",
            &format!("{P2_REL}; {RFQ_REL}"), "TBD", "TBD_AFTER_IMPEDANCE_MAP").build(),
        var_v("x_RF.source_efficiency", "x_RF", "eta_DC->RF", Value::str("TBD"), &Value::str("-"),
            chain.g("flight_source_efficiency").unwrap_or(&Value::Null), &format!("{MP_REL} items_v2 MPV2-P08"),
            &Value::str("TBD"), &Value::str("TBD")).build(),
        var("x_RF.lab_forward_range", "x_RF", "P_fwd lab", floats(&[LAB_RF_FORWARD_W_RANGE.0, LAB_RF_FORWARD_W_RANGE.1]),
            "W", "laboratory source + inline chain sizing: a TEST capability, never a flight allowance (row 72)",
            "abep_sim/bus_boundary_a9_v2.py LAB_RF_FORWARD_W_RANGE", "owner-allocation", "TEST_CAPABILITY_ONLY").build(),
    ];
    blocks.push(
        D::new()
            .s("block", "x_RF")
            .s("lane", "P2 framework / RFQ v3 / mass-power v3")
            .s("path", P2_REL)
            .s("state", "NOT_SEARCHABLE_BOUNDS_TBD")
            .v("variables", Value::List(rv))
            .build(),
    );

    let mut tv = vec![];
    for it in p3.g("items").arr().ok_or_else(|| sch(P3_REL, "items"))? {
        let id = it.g("id").s().unwrap_or_default();
        let kind = id.split('-').nth(1).unwrap_or("");
        if !["G", "R", "K", "M"].contains(&kind) {
            continue;
        }
        let val = match it.g("value") {
            Some(Value::Dict(_)) | Some(Value::List(_)) => Value::str("see source"),
            Some(v) => v.clone(),
            None => Value::Null,
        };
        let status_v = it.g("status").cloned().unwrap_or(Value::Null);
        let status_s = match it.g("status") {
            None => String::new(),
            Some(v) => py_str_value(v),
        };
        let ec = if status_s.starts_with("TBD") || status_s.starts_with("PENDING") {
            "TBD"
        } else if it.g("status").s() == Some("OWNER_GIVEN") {
            "owner-allocation"
        } else {
            "assumed"
        };
        tv.push(
            var_v(
                &format!("x_thermal.{id}"),
                "x_thermal",
                id,
                val,
                it.g("units").unwrap_or(&Value::str("-")),
                it.g("name").unwrap_or(&Value::str("")),
                &format!("{P3_REL} items {id}"),
                &Value::str(ec),
                &status_v,
            )
            .build(),
        );
    }
    blocks.push(
        D::new()
            .s("block", "x_thermal")
            .s("lane", "P3")
            .s("path", P3_REL)
            .s("state", "NOT_SEARCHABLE_BOUNDS_TBD")
            .v("variables", Value::List(tv))
            .build(),
    );
    Ok(Value::List(blocks))
}

pub const F2_REL: &str = "docs/design_synthesis/f2_filter/f2_filter_stage_v1.json";

/// Python `str(v)` of a JSON value (strings verbatim, other values by repr).
pub fn py_str_value(v: &Value) -> String {
    match v {
        Value::Str(s) => s.clone(),
        other => py_repr(other),
    }
}

/// `hall_gated_thrust(name, rec, repo)`: a non-synthetic supplied thrust record is refused (NOT_EVALUATED) while the
/// credible Hall set is EMPTY.
pub fn hall_gated_thrust(name: &str, rec: &Value, admitted_members: bool) -> Value {
    if matches!(rec, Value::Null)
        || rec.g("status").s() == Some(abep_mission::objective::SYNTHETIC_ONLY)
        || admitted_members
    {
        return rec.clone();
    }
    let st = rec.g("status").cloned().unwrap_or(Value::Null);
    let units = match rec.g("units") {
        Some(u) => u.clone(),
        None => Value::str("N"),
    };
    let st_s = py_str_value(&st);
    let mut d = obj(
        name,
        abep_mission::objective::NOT_EVALUATED,
        Value::Null,
        "",
        Value::str(format!(
            "a {st_s} thrust record was supplied but the credible Hall set is EMPTY (no admitted transport member: \
refused)"
        )),
        Value::List(vec![Value::str(abep_mission::objective::UNLOCK_T)]),
    );
    d = d.v("units", units).v("refused_supplied_status", st);
    d.build()
}

/// `heat_rejection(compressor_P_W, supplied=None, repo)`: NOT_EVALUATED while the P3 evaluations are incomplete; the
/// only partial term is an UPPER bound on the compressor-local dissipation (PARAMETRIC).
pub fn heat_rejection(repo: &Path, compressor_p_w: Option<f64>) -> DResult<Value> {
    let p3 = read_py(repo, P3_REL)?;
    let mut fce = Dict::new();
    for (k, v) in p3.g("fail_closed_evaluations").obj().ok_or_else(|| sch(P3_REL, "fail_closed_evaluations"))?.iter() {
        fce.insert(k.clone(), v.g("status").cloned().unwrap_or(Value::Null));
    }
    let fce_v = Value::Dict(fce);
    let status = py_str_value(p3.g("status").unwrap_or(&Value::Null));
    let reason = format!(
        "P3 framework {status}; fail-closed evaluations {}; ICP_COUPLED_THERMAL and ANODE_THERMAL_CLOSURE UNRESOLVED \
(never reported as PASS); the H2-5 C-1 cathode-body node CB / Q_cath 9-101 W inherited by P3 v2 is a ground-article C1 \
term, NOT_USABLE_FOR_FLIGHT_THERMAL_CLOSURE (A9.24 AFI-03)",
        py_repr(&fce_v)
    );
    Ok(obj("Q_reject_W", "NOT_EVALUATED", Value::Null, "W", Value::str(reason),
        Value::List(vec![Value::str(UNLOCK_Q_REJECT)]))
    .v("p3_evaluations", fce_v)
    .v(
        "partial",
        D::new()
            .v("compressor_local_dissipation_upper_bound_W", compressor_p_w.map(Value::Float).unwrap_or(Value::Null))
            .s(
                "basis",
                "electrical input = local dissipation + energy carried by the gas, so the local dissipation is at most \
P_el (PARAMETRIC, code-default coefficients)",
            )
            .build(),
    )
    .build())
}

fn mp_items(mp: &Value) -> Dict {
    let mut d = Dict::new();
    for k in ["items", "items_v2", "items_v3"] {
        if let Some(a) = mp.g(k).arr() {
            for i in a {
                if let Some(id) = i.g("id").s() {
                    d.insert(id, i.clone());
                }
            }
        }
    }
    d
}

/// `electron_margin(config, supplied=None, repo)`: NOT_EVALUATED today (ICP-45 NOT_EVALUATED, I_d,max,H1 TBD).
pub fn electron_margin(repo: &Path, config: &str) -> DResult<Value> {
    let mp = read_py(repo, MP_REL)?;
    let it = mp_items(&mp);
    let p09 = it.get("MPV2-P09").g("value").map(py_str_value).ok_or_else(|| sch(MP_REL, "MPV2-P09"))?;
    let p10 = it.get("MPV2-P10").g("value").cloned().ok_or_else(|| sch(MP_REL, "MPV2-P10"))?;
    let reason = if config == FLIGHT_CONFIGURATION {
        format!(
            "ICP-45 NOT_EVALUATED: I_d,max,H1 {p09} (not registered) and no P1 data; ICP electron-current capacity \
PENDING_ICP45"
        )
    } else {
        "not a flight configuration (A9.19 / A9.20: C1 ground-only)".to_string()
    };
    Ok(obj(
        "I_e_cap_minus_I_d_max_A",
        "NOT_EVALUATED",
        Value::Null,
        "A",
        Value::str(reason),
        Value::List(vec![Value::str(UNLOCK_I_E_MARGIN)]),
    )
    .v(
        "context",
        D::new()
            .v("bench_discharge_ceiling_A", p10)
            .s("rule", "the 8.33 A stand ceiling is a ground rating, never I_d,max,H1")
            .build(),
    )
    .build())
}

/// `tpmc_backend_policy(repo)`: F7 / F8 run no TPMC (they consume the committed F1 records).
pub fn tpmc_backend_policy(repo: &Path) -> DResult<Value> {
    let pr = read_py(repo, PARITY_REL)?;
    let verdicts = pr.g("verdicts").cloned().unwrap_or_else(|| Value::Dict(Dict::new()));
    Ok(D::new()
        .v("tpmc_invoked_by_f7_f8", Value::Bool(false))
        .s("default_backend", "python")
        .v("parity_verdicts", verdicts)
        .s(
            "rule",
            "Rust (abep_sim/design/tpmc_backend.py) only as an explicitly requested accelerator for ADMITTED kernels; no \
Rust result is authoritative; no silent fallback",
        )
        .build())
}

// ------------------------------------------------------------------------------------------------ A9.19 elements
/// `a919.is_conditional_c1_text(text)`: `re.search(r"if\s+c-?1\s+(is\s+)?selected", text, re.I)` (CPython `re`
/// semantics through the shared configuration matcher).
pub fn is_conditional_c1_text(text: &Value) -> bool {
    use abep_config::textmatch::{is_match, lit_i, opt, plus, space, Node};
    let Some(t) = text.as_str() else { return false };
    let mut p = lit_i("if");
    p.push(plus(space()));
    p.push(Node::CharI('c'));
    p.push(opt(Node::Char('-')));
    p.push(Node::Char('1'));
    p.push(plus(space()));
    let mut is_ = lit_i("is");
    is_.push(plus(space()));
    p.push(opt(Node::Seq(is_)));
    p.extend(lit_i("selected"));
    is_match(&p, t)
}

fn line_hc_elements(ln: &Value, config: &str) -> Vec<Value> {
    use abep_config::architecture::{
        hollow_cathode_elements, is_c1_absence_text, is_c1_absent_branch_state, C1_BOOKING_CONDITIONAL,
        C1_DECLARED_ABSENT,
    };
    let lid = ln.g("line").cloned().unwrap_or(Value::Null);
    let lid_s = py_str_value(&lid);
    let name = ln.g("name").or(ln.g("owner_name")).cloned().unwrap_or(Value::Null);
    let mut el = D::new()
        .v("id", lid.clone())
        .v("name", name.clone())
        .s("kind", "mass_line")
        .s("source", &format!("{MP_REL} lines.{config}.{lid_s}"));
    if is_conditional_c1_text(&name) && !hollow_cathode_elements(std::slice::from_ref(&name)).is_empty() {
        el = el.s("booking", C1_BOOKING_CONDITIONAL);
    } else if is_c1_absence_text(&name) {
        el = el.s("booking", C1_DECLARED_ABSENT);
    }
    let mut out = vec![el.build()];
    if let Some(fcs) = ln.g("floor_constituents").arr() {
        for (i, fc) in fcs.iter().enumerate() {
            let what = fc.g("what").cloned().unwrap_or(Value::Null);
            let mut e = D::new()
                .s("id", &format!("{lid_s}.floor[{i}]"))
                .v("name", what.clone())
                .s("kind", "floor_constituent")
                .v("kg", fc.g("kg").cloned().unwrap_or(Value::Null))
                .s("source", &format!("{MP_REL} lines.{config}.{lid_s}.floor_constituents[{i}]"));
            if is_conditional_c1_text(&what) && !hollow_cathode_elements(std::slice::from_ref(&what)).is_empty() {
                e = e.s("booking", C1_BOOKING_CONDITIONAL);
            } else if is_c1_absence_text(&what) {
                e = e.s("booking", C1_DECLARED_ABSENT);
            }
            out.push(e.build());
        }
    }
    if let Some(br) = ln.g("c1_branch") {
        if !matches!(br, Value::Null) {
            let st = py_str_value(br.g("state").unwrap_or(&Value::Null));
            let in_line = br.g("in_AL08").cloned().unwrap_or(Value::Null);
            let mut e = D::new()
                .s("id", &format!("{lid_s}.c1_branch"))
                .s("name", &format!("C1 branch ({st})"))
                .s("kind", "c1_branch")
                .s("state", &st)
                .v("in_line", in_line.clone())
                .s("source", &format!("{MP_REL} lines.{config}.{lid_s}.c1_branch"));
            if st.contains("NOT_SELECTED") && !in_line.truthy() {
                e = e.s("booking", C1_BOOKING_CONDITIONAL);
            } else if is_c1_absent_branch_state(&Value::str(st.clone()), &in_line) {
                e = e.s("booking", C1_DECLARED_ABSENT);
            }
            out.push(e.build());
        }
    }
    out
}

/// `_EMBEDDED_C1_RE = r"C1 cathode Xe branch ([0-9.]+) kg \(([^)]*)\) is already inside the (AL-\d+) floor"` (search).
fn embedded_c1(text: &str) -> Option<(String, String, String)> {
    let pre = "C1 cathode Xe branch ";
    let mut start = 0;
    while let Some(off) = text[start..].find(pre) {
        let i = start + off + pre.len();
        let rest = &text[i..];
        let kg_len = rest.chars().take_while(|c| c.is_ascii_digit() || *c == '.').count();
        if kg_len > 0 {
            let kg = &rest[..kg_len];
            if let Some(r2) = rest[kg_len..].strip_prefix(" kg (") {
                if let Some(close) = r2.find(')') {
                    let refs = &r2[..close];
                    if let Some(r3) = r2[close..].strip_prefix(") is already inside the AL-") {
                        let dlen = r3.chars().take_while(|c| c.is_ascii_digit()).count();
                        if dlen > 0 && r3[dlen..].starts_with(" floor") {
                            return Some((kg.to_string(), refs.to_string(), format!("AL-{}", &r3[..dlen])));
                        }
                    }
                }
            }
        }
        start = start + off + 1;
    }
    None
}

fn floor_c1_resolution(line: &Value) -> Option<(String, String)> {
    for (k, v) in line.obj()?.iter() {
        if k.starts_with("c1_hardware_in_flight") {
            if let Some(s) = v.as_str() {
                if s.trim().to_uppercase().starts_with("NONE") {
                    return Some((k.clone(), s.to_string()));
                }
            }
        }
    }
    None
}

/// `flight_configuration_elements(config, repo)`: every element a flight configuration books (A9-02 installed power
/// slots, mass / power lines with floor constituents and C1-branch records, and any C1 branch the ground reference's
/// own text places inside a flight floor).
pub fn flight_configuration_elements(repo: &Path, config: &str) -> DResult<Value> {
    if config == GROUND_REFERENCE_CONFIGURATION {
        return Err(DesignError::new(
            "ArchitectureRuleError",
            "REFUSED: hall_c1_reference is not a flight configuration (A9.19: no conventional hollow cathode; A9.20: C1 \
is a GROUND-ONLY laboratory reference, never flight hardware, never in the flight mass / power / Xe budgets); use \
ground_reference() where a comparison needs it",
        ));
    }
    if config != FLIGHT_CONFIGURATION {
        return Err(DesignError::new(
            "ArchitectureRuleError",
            format!("unknown configuration {}; flight configurations ('{FLIGHT_CONFIGURATION}',)", py_repr_str(config)),
        ));
    }
    let mp = read_py(repo, MP_REL)?;
    let slots = abep_subsystems::power::slots::installed_slots(&Value::str(config), &Value::List(vec![]))
        .map_err(|e| model(format!("RuntimeError: {e:?}")))?;
    let mut els: Vec<Value> =
        slots.iter().map(|s| D::new().s("id", s.name()).s("kind", "power_slot").build()).collect();
    let flight_lines = mp.g("lines").g(config).arr().ok_or_else(|| sch(MP_REL, "lines"))?;
    for ln in flight_lines {
        els.extend(line_hc_elements(ln, config));
    }
    let present = |lid: &str| flight_lines.iter().find(|l| l.g("line").s() == Some(lid));
    let mut ground: Vec<(&str, &[Value])> = vec![];
    if let Some(l) = mp.g("lines").g(GROUND_REFERENCE_CONFIGURATION).arr() {
        ground.push(("lines", l));
    }
    if let Some(l) = mp.ptr("/retired_flight_configuration_history/lines").g(GROUND_REFERENCE_CONFIGURATION).arr() {
        ground.push(("retired_flight_configuration_history.lines", l));
    }
    for (where_, glines) in ground {
        for ln in glines {
            let text = ln.g("floor_arithmetic").map(py_str_value).unwrap_or_else(|| "None".into());
            let Some((kg, refs, al)) = embedded_c1(&text) else { continue };
            let Some(fl) = present(&al) else { continue };
            let src = format!(
                "{MP_REL} {where_}.{GROUND_REFERENCE_CONFIGURATION}.{}.floor_arithmetic",
                py_str_value(ln.g("line").unwrap_or(&Value::Null))
            );
            let kgf: f64 =
                kg.parse().map_err(|_| model(format!("ValueError: could not convert string to float: '{kg}'")))?;
            if let Some((key, stmt)) = floor_c1_resolution(fl) {
                els.push(
                    D::new()
                        .s("id", &format!("{al}.embedded_c1_cathode_xe_branch"))
                        .s("name", "C1 cathode Xe branch")
                        .s("kind", "c1_branch")
                        .s("state", &format!("NO_C1_HARDWARE_IN_FLIGHT_FLOOR ({stmt})"))
                        .v("in_line", Value::Bool(false))
                        .f("kg_history", kgf)
                        .s("ref", &refs)
                        .s("booking", abep_config::architecture::C1_DECLARED_ABSENT)
                        .s("source", &format!("{src}; {MP_REL} lines.{config}.{al}.{key}"))
                        .build(),
                );
                continue;
            }
            els.push(
                D::new()
                    .s("id", &format!("{al}.embedded_c1_cathode_xe_branch"))
                    .s("name", "C1 cathode Xe branch")
                    .s("kind", "embedded_floor_branch")
                    .f("kg", kgf)
                    .s("ref", &refs)
                    .s("booking", abep_config::architecture::C1_BOOKING_EMBEDDED)
                    .s("source", &src)
                    .build(),
            );
        }
    }
    Ok(Value::List(els))
}

// ------------------------------------------------------------------------------------------------ architecture questions
fn unlock_list(xs: &[&str]) -> Value {
    Value::List(xs.iter().map(|s| Value::str(*s)).collect())
}

/// `architecture_questions()`: which architecture-level questions the current evidence can and cannot answer.
pub fn architecture_questions(repo: &Path) -> DResult<Value> {
    use abep_mission::objective::{UNLOCK_D_SPACECRAFT, UNLOCK_T};
    use abep_subsystems::life::indicators::UNLOCK_LIFE;
    use abep_subsystems::mass::wet_mass::UNLOCK_M_WET;
    use abep_subsystems::power::objective::UNLOCK_P_BUS;
    let can = "CAN_ANSWER_UNDER_PARAMETRIC_INPUTS";
    let cannot = "CANNOT_ANSWER";
    let w =
        abep_subsystems::mass::wet_mass::wet_mass(repo, &Value::str(FLIGHT_CONFIGURATION), &Value::Null, &Value::Null)
            .map_err(|e| DesignError::new(e.class, e.message))?;
    let env = w.g("wet_known_allocation_envelope_kg").arr().ok_or_else(|| model("RuntimeError: wet_mass envelope"))?;
    let lo = env.first().f().ok_or_else(|| model("RuntimeError: wet_mass envelope"))?;
    let hi = env.get(1).f().ok_or_else(|| model("RuntimeError: wet_mass envelope"))?;
    let states = py_repr(w.g("wet_rollup_states").unwrap_or(&Value::Null));
    let aq06 = format!(
        "no CBE for any BOM line (m_wet NOT_EVALUATED); mass/power v3 wet roll-ups against HARD_40_WET (MEV-level owner \
reading, Xe cases 2 / 5 / 10 kg): {FLIGHT_CONFIGURATION} {states} (known terms {lo:.2}-{hi:.2} kg) (flight \
configuration only; A9.19 / A9.20: C1 is a GROUND_REFERENCE, never a flight roll-up)"
    );
    let q = |id: &str, question: &str, state: &str, basis: &str, unlock: Value| {
        D::new()
            .s("id", id)
            .s("question", question)
            .s("answer_state", state)
            .s("basis", basis)
            .v("unlock", unlock)
            .build()
    };
    Ok(Value::List(vec![
        q(
            "AQ-01",
            "Which upstream intake / compressor / plenum combinations deliver the most flow for the least drag, \
compressor power, mass proxy and ripple, per surface scenario and set pressure?",
            can,
            "F7 upstream Pareto sets \
(PARAMETRIC_SENSITIVITY: code-default compressor coefficients, parametric filter / leak / chain temperature)",
            Value::Null,
        ),
        q(
            "AQ-02",
            "Where does the delivered upstream flow sit relative to the 0.38-3.2 mg/s ground-characterization \
COVERAGE (not a flight requirement, A9.13 S6.21) at every orbit state with one plenum setpoint?",
            can,
            "F7 upstream frontier per context (see findings); F4-01; coverage only, never PASS / FAIL",
            Value::Null,
        ),
        q(
            "AQ-02b",
            "Is the delivered feed state sufficient (AG-12) for the required drag-compensation thrust at every \
required state?",
            cannot,
            "AG-12 is statewise feed-state sufficiency against a VALIDATED H-1 map (A9.13 S6.21): no such \
map",
            unlock_list(&[UNLOCK_T]),
        ),
        q(
            "AQ-03",
            "Which set pressures can the upstream chain hold at all?",
            can,
            "feasible counts per P_set; > 0.1 Pa out of domain (F3/F4)",
            Value::Null,
        ),
        q(
            "AQ-04",
            "Does the architecture produce T(state) - D(state) >= 0 at EVERY required state (statewise, A9.13 \
S6.15) and >= 12 mN at 180-230 km?",
            cannot,
            "no admitted Hall response map; host-spacecraft drag ICD absent \
(reference drag is REFERENCE_PARAMETRIC only, S6.18)",
            unlock_list(&[UNLOCK_T, UNLOCK_D_SPACECRAFT]),
        ),
        q(
            "AQ-05",
            "Does the system close P_bus < 1.5 kW (and the 1.35 kW allocation)?",
            cannot,
            "A9-02 ledger PARTIAL_BOUNDARY",
            unlock_list(&[UNLOCK_P_BUS]),
        ),
        q("AQ-06", "Does the system close < 40 kg wet?", cannot, &aq06, unlock_list(&[UNLOCK_M_WET])),
        q(
            "AQ-07",
            "Can the ICP neutralize the H-1 discharge current with margin (both supply modes; no hollow cathode in \
flight, A9.19)?",
            cannot,
            "ICP-45 NOT_EVALUATED; I_d,max,H1 not registered",
            unlock_list(&[UNLOCK_I_E_MARGIN]),
        ),
        q(
            "AQ-08",
            "Does the coupled H-1 / ICP thermal design close with >= 50 K margin?",
            cannot,
            "P3 INCOMPLETE_EVIDENCE; closures UNRESOLVED",
            unlock_list(&[UNLOCK_Q_REJECT]),
        ),
        q(
            "AQ-09",
            "Does the ICP neutralizer match or exceed the ground C1 reference (bench control, GROUND_REFERENCE) \
in the C1-vs-ICP bench comparison?",
            cannot,
            "A9.19 / A9.20: hall_c1_reference is no longer a flight configuration; \
the comparison is a ground bench comparison with C1 as GROUND_ONLY_LAB_EQUIPMENT; no bench data (P1 / ICP-45 \
NOT_EVALUATED)",
            unlock_list(&[UNLOCK_I_E_MARGIN]),
        ),
        q(
            "AQ-10",
            "Which H-1 geometry inside the F5 windows is preferable?",
            cannot,
            "every Hall performance quantity NOT_EVALUATED; only geometric admissibility is evaluable",
            unlock_list(&[UNLOCK_T]),
        ),
        q(
            "AQ-11",
            "Which ICP geometry is preferable?",
            cannot,
            "F6 bounds all TBD; P1 / P2 no data",
            unlock_list(&["F6-IF-N01..N08 (F6 interface demands)"]),
        ),
        q(
            "AQ-12",
            "Is the upstream Pareto set robust to the TBD surface state, wall recombination, pointing and TPMC \
statistics?",
            can,
            "F8 robust filter (scenario set + seeded MC over quantified TPMC statistics); probabilities only \
over quantified uncertainty",
            Value::Null,
        ),
        q(
            "AQ-13",
            "Is the architecture life-capable (> 15,000 h firing, AO compatibility)?",
            cannot,
            "no life model or life evidence",
            unlock_list(&[UNLOCK_LIFE]),
        ),
    ]))
}

/// The reference `UNLOCK` map (key order T, D_spacecraft, P_bus, m_wet, Q_reject, I_e_margin, life), carried by the
/// REFUSED_INCOMPLETE ranking refusal.
pub fn unlock_map() -> serde_json::Value {
    use abep_mission::objective::{UNLOCK_D_SPACECRAFT, UNLOCK_T};
    use abep_subsystems::life::indicators::UNLOCK_LIFE;
    use abep_subsystems::mass::wet_mass::UNLOCK_M_WET;
    use abep_subsystems::power::objective::UNLOCK_P_BUS;
    let mut m = serde_json::Map::new();
    for (k, v) in [
        ("T", UNLOCK_T),
        ("D_spacecraft", UNLOCK_D_SPACECRAFT),
        ("P_bus", UNLOCK_P_BUS),
        ("m_wet", UNLOCK_M_WET),
        ("Q_reject", UNLOCK_Q_REJECT),
        ("I_e_margin", UNLOCK_I_E_MARGIN),
        ("life", UNLOCK_LIFE),
    ] {
        m.insert(k.to_string(), serde_json::Value::String(v.to_string()));
    }
    serde_json::Value::Object(m)
}
