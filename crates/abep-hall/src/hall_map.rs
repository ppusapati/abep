//! Frozen Hall-discharge response maps produced offline by HallThruster.jl (port of abep_sim/hall_map.py).
//!
//! The loader refuses maps of another schema, maps missing required meta or fields, maps of a member that is not an
//! ADMITTED transport-ensemble member, maps using a calibration-nuisance variable as an axis and maps not produced with
//! the pinned HallThruster.jl commit. A query is multilinear on the regular grid (scipy 1.17.1
//! RegularGridInterpolator, method 'linear', reproduced operation for operation) and refuses extrapolation. It is
//! `trustworthy` only if every surrounding node converged, the interpolated `sustained` exceeds 0.999 and every
//! surrounding node is `chemistry_trustworthy`; `wall_life_trustworthy` additionally needs meta `ion_wall_losses` true
//! and every surrounding node wall-life trustworthy.

use crate::ensemble;
use crate::error::{HallError, HallResult, Kind, NumpySub};
use crate::py::{self, PyValue};
use crate::schema::{self, HallMapSchema, SCHEMA_NAME};

pub const BRIDGE_REL: &str = "hallthruster_bridge";

/// `hall_map.pinned_commit(bridge_dir)`: the first PINNED.toml line whose stripped text starts with "commit", value
/// after the first '=', before any '#', stripped of whitespace and double quotes. `None` / "" = the repository bridge.
pub fn pinned_commit(repo: &str, bridge_dir: Option<&str>) -> HallResult<String> {
    let dir = match bridge_dir {
        Some(d) if !d.is_empty() => d.to_string(),
        _ => py::join(repo, BRIDGE_REL),
    };
    let text = py::read_text(&py::join(&dir, "PINNED.toml"))?;
    for line in text.split_inclusive('\n') {
        if py::py_strip(line).starts_with("commit") {
            let value = line.split('=').nth(1).ok_or_else(|| HallError::index("list index out of range"))?;
            let value = value.split('#').next().unwrap_or_default();
            return Ok(py::py_strip(value).trim_matches('"').to_string());
        }
    }
    Err(HallError::value("HM_NO_PINNED_COMMIT", "no pinned commit"))
}

#[derive(Debug, Clone)]
enum Axis {
    Flat(Vec<f64>),
    /// A two-level nested axis (`np.asarray` gives a 2-D array; `len` is the row count).
    Nested(Vec<Vec<f64>>),
}

impl Axis {
    fn len(&self) -> usize {
        match self {
            Axis::Flat(a) => a.len(),
            Axis::Nested(rows) => rows.len(),
        }
    }
}

/// One value of a query result.
#[derive(Debug, Clone, PartialEq)]
pub enum QueryValue {
    Float(f64),
    Bool(bool),
    Str(String),
}

impl QueryValue {
    pub fn to_py(&self) -> PyValue {
        match self {
            QueryValue::Float(f) => PyValue::Float(*f),
            QueryValue::Bool(b) => PyValue::Bool(*b),
            QueryValue::Str(s) => PyValue::Str(s.clone()),
        }
    }
}

/// A loaded, admitted, pinned Hall map.
#[derive(Debug, Clone)]
pub struct HallMap {
    pub path: String,
    pub meta: PyValue,
    pub names: Vec<String>,
    pub shape: Vec<usize>,
    axes: Vec<Axis>,
    fields: Vec<(String, Vec<f64>)>,
    bad: Vec<bool>,
    repo: String,
}

fn truth(bits: Vec<bool>) -> HallResult<bool> {
    match bits.len() {
        1 => Ok(bits[0]),
        0 => Err(HallError::numpy(
            NumpySub::Truth,
            "The truth value of an empty array is ambiguous. Use `array.size > 0` to check that an array is not empty.",
        )),
        _ => Err(HallError::numpy(
            NumpySub::Truth,
            "The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()",
        )),
    }
}

fn np_row_str(row: &[f64]) -> String {
    let item = |x: &f64| {
        if x.is_finite() && x.fract() == 0.0 && x.abs() < 1e16 {
            format!("{}.", *x as i64)
        } else {
            py::float_repr(*x)
        }
    };
    format!("[{}]", row.iter().map(item).collect::<Vec<_>>().join(" "))
}

/// scipy `find_interval_ascending` (extrapolate = 1).
fn find_interval_ascending(x: &[f64], xval: f64, prev_interval: isize) -> isize {
    let nx = x.len() as isize;
    let (a, b) = (x[0], x[x.len() - 1]);
    let mut interval = prev_interval;
    if interval < 0 || interval >= nx {
        interval = 0;
    }
    if !(a <= xval && xval <= b) {
        if xval < a {
            0
        } else if xval > b {
            nx - 2
        } else {
            -1
        }
    } else if xval == b {
        nx - 2
    } else {
        let (mut low, mut high) = if xval >= x[interval as usize] { (interval, nx - 2) } else { (0, interval) };
        if xval < x[(low + 1) as usize] {
            high = low;
        }
        while low < high {
            let mid = (high + low) / 2;
            if xval < x[mid as usize] {
                high = mid;
            } else if xval >= x[(mid + 1) as usize] {
                low = mid + 1;
            } else {
                low = mid;
                break;
            }
        }
        low
    }
}

/// numpy `searchsorted(a, v, side='left')` (binary search with numpy's NaN-last ordering).
fn searchsorted_left(a: &[f64], v: f64) -> usize {
    let less = |x: f64, y: f64| x < y || (y.is_nan() && !x.is_nan());
    let (mut lo, mut hi) = (0usize, a.len());
    while lo < hi {
        let mid = lo + ((hi - lo) >> 1);
        if less(a[mid], v) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    lo
}

/// Python slice(start, start + 2) on a dimension of length n: the covered indices.
fn slice2(start: isize, n: usize) -> std::ops::Range<usize> {
    let n = n as isize;
    let norm = |i: isize| if i < 0 { (i + n).max(0) } else { i.min(n) };
    let (a, b) = (norm(start), norm(start + 2));
    (a as usize)..(b.max(a) as usize)
}

fn insert(out: &mut Vec<(String, QueryValue)>, key: &str, value: QueryValue) {
    match out.iter_mut().find(|(k, _)| k == key) {
        Some(slot) => slot.1 = value,
        None => out.push((key.to_string(), value)),
    }
}

impl HallMap {
    /// `HallMap(path, bridge_dir, ensemble)`. `ensemble` is a raw override document (tests only, not validated, as in
    /// Python); `None` loads and validates the repository ensemble.
    pub fn load(repo: &str, path: &str, bridge_dir: Option<&str>, ensemble: Option<&PyValue>) -> HallResult<Self> {
        let schema = schema::repo_schema(repo)?;
        Self::load_with(repo, &schema, path, bridge_dir, ensemble)
    }

    pub fn load_with(
        repo: &str,
        schema: &HallMapSchema,
        path: &str,
        bridge_dir: Option<&str>,
        ensemble: Option<&PyValue>,
    ) -> HallResult<Self> {
        let d = py::load_json_file(path)?;
        let meta = py::getitem(&d, "meta")?;
        let meta_schema = py::get(meta, "schema")?.cloned().unwrap_or(PyValue::None);
        if !meta_schema.py_eq(&py::s(SCHEMA_NAME)) {
            return Err(HallError::value(
                "HM_NOT_SCHEMA_V1",
                format!("Hall map {path} is not {SCHEMA_NAME} (meta.schema = {})", py::repr(&meta_schema)),
            ));
        }
        let mut missing_meta = Vec::new();
        for k in &schema.meta {
            if !py::contains(meta, &py::s(k.as_str()))? {
                missing_meta.push(k.clone());
            }
        }
        if !missing_meta.is_empty() {
            return Err(HallError::value(
                "HM_MISSING_META",
                format!("Hall map {path} missing required meta: {}", py::repr_strs(&missing_meta)),
            ));
        }
        let loaded;
        let ens = match ensemble {
            Some(e) => e,
            None => {
                loaded = ensemble::load_ensemble(repo, None)?;
                &loaded
            }
        };
        let member_id = py::getitem(meta, "ensemble_member_id")?;
        let members = ensemble::member_ids(ens)?;
        py::require_hashable(member_id)?;
        if !members.iter().any(|m| m.py_eq(member_id)) {
            return Err(HallError::value(
                "HM_NOT_ADMITTED",
                format!(
                    "Hall map {path}: ensemble_member_id {} is not an admitted transport-ensemble member (credible set \
                     pending or id unknown)",
                    py::repr(member_id)
                ),
            ));
        }
        let nuisance = py::set_from(py::iterate(py::getitem(ens, "calibration_nuisance")?)?)?;
        let axes_doc = py::getitem(&d, "axes")?;
        let axis_names = py::set_from(py::iterate(axes_doc)?)?;
        let leaked = py::intersection(&nuisance, &axis_names);
        if !leaked.is_empty() {
            return Err(HallError::value(
                "HM_NUISANCE_AXES",
                format!(
                    "Hall map {path}: calibration-nuisance variables {} used as map axes",
                    py::repr(&PyValue::List(py::sorted(leaked)?))
                ),
            ));
        }
        let pin = pinned_commit(repo, bridge_dir)?;
        let pinned = py::get(meta, "pinned")?.cloned().unwrap_or_else(|| py::s(""));
        if !py::contains(&pinned, &py::s(pin))? {
            return Err(HallError::value(
                "HM_NOT_PINNED",
                format!("Hall map {path} was not produced with the pinned HallThruster.jl commit"),
            ));
        }
        let fields_doc = py::getitem(&d, "fields")?;
        let mut missing = Vec::new();
        for f in &schema.fields {
            if !py::contains(fields_doc, &py::s(f.as_str()))? {
                missing.push(f.clone());
            }
        }
        if !missing.is_empty() {
            return Err(HallError::value(
                "HM_MISSING_FIELDS",
                format!("Hall map {path} missing required fields: {}", py::repr_strs(&missing)),
            ));
        }
        let PyValue::Dict(axis_entries) = axes_doc else {
            return Err(HallError::type_error(format!("'{}' object has no attribute 'items'", axes_doc.type_name())));
        };
        let mut arrays = Vec::new();
        for (_, v) in axis_entries {
            arrays.push(py::ndarray(v)?);
        }
        let names: Vec<String> = axis_entries.iter().map(|(k, _)| py::py_str(k)).collect();
        let mut axes = Vec::new();
        for a in arrays {
            axes.push(match a.shape.len() {
                0 => return Err(HallError::type_error("len() of unsized object")),
                1 => Axis::Flat(a.data),
                2 => {
                    let cols = a.shape[1];
                    Axis::Nested((0..a.shape[0]).map(|r| a.data[r * cols..(r + 1) * cols].to_vec()).collect())
                }
                _ => return Err(HallError::type_error("axis nested deeper than two levels (unsupported, DIV-03)")),
            });
        }
        let shape: Vec<usize> = axes.iter().map(Axis::len).collect();
        let size: usize = shape.iter().product();
        let PyValue::Dict(field_entries) = fields_doc else {
            return Err(HallError::type_error(format!("'{}' object has no attribute 'items'", fields_doc.type_name())));
        };
        let mut fields = Vec::new();
        for (k, v) in field_entries {
            let a = py::ndarray(v)?;
            if a.data.len() != size {
                return Err(HallError::numpy(
                    NumpySub::Reshape,
                    format!("cannot reshape array of size {} into shape {}", a.data.len(), py::shape_text(&shape)),
                ));
            }
            fields.push((py::py_str(k), a.data));
        }
        let converged = &fields.iter().find(|(k, _)| k == "converged").expect("required field present").1;
        let bad = converged.iter().map(|x| *x == 0.0).collect();
        Ok(HallMap {
            path: path.to_string(),
            meta: meta.clone(),
            names,
            shape,
            axes,
            fields,
            bad,
            repo: repo.to_string(),
        })
    }

    fn field(&self, name: &str) -> Option<&Vec<f64>> {
        self.fields.iter().find(|(k, _)| k == name).map(|(_, v)| v)
    }

    /// `HallMap.__call__(**q)`: every field interpolated, then `trustworthy`, `wall_life_trustworthy` and
    /// `hallthruster_commit` (dict order of Python: a key already present keeps its position).
    pub fn query(&self, q: &[(String, f64)]) -> HallResult<Vec<(String, QueryValue)>> {
        let mut pt = Vec::with_capacity(self.names.len());
        for (k, axis) in self.names.iter().zip(&self.axes) {
            let v = q
                .iter()
                .find(|(n, _)| n == k)
                .map(|(_, v)| *v)
                .ok_or_else(|| HallError::new(Kind::Key, "KEY", py::repr_str(k)))?;
            match axis {
                Axis::Flat(a) => {
                    if a.is_empty() {
                        return Err(HallError::index("index 0 is out of bounds for axis 0 with size 0"));
                    }
                    let (lo, hi) = (a[0], a[a.len() - 1]);
                    if !(lo - 1e-12 <= v && v <= hi + 1e-12) {
                        return Err(HallError::value(
                            "HM_QUERY_OUTSIDE",
                            format!(
                                "Hall map query {k}={} outside [{}, {}] — no extrapolation",
                                py::float_repr(v),
                                py::float_repr(lo),
                                py::float_repr(hi)
                            ),
                        ));
                    }
                }
                Axis::Nested(rows) => {
                    let (first, last) = (&rows[0], &rows[rows.len() - 1]);
                    let inside = truth(first.iter().map(|x| x - 1e-12 <= v).collect())?
                        && truth(last.iter().map(|x| v <= x + 1e-12).collect())?;
                    if !inside {
                        return Err(HallError::value(
                            "HM_QUERY_OUTSIDE",
                            format!(
                                "Hall map query {k}={} outside [{}, {}] — no extrapolation",
                                py::float_repr(v),
                                np_row_str(first),
                                np_row_str(last)
                            ),
                        ));
                    }
                }
            }
            pt.push(v);
        }
        let grid = self.rgi_grid()?;
        // scipy _prepare_xi (bounds_error=True): strict bounds of the ascending grid, dimension by dimension
        for (i, ((g, _), &p)) in grid.iter().zip(&pt).enumerate() {
            if !(g[0] <= p && p <= g[g.len() - 1]) {
                return Err(HallError::scipy(
                    "RGI_OUT_OF_BOUNDS",
                    format!("One of the requested xi is out of bounds in dimension {i}"),
                ));
            }
        }
        let mut out: Vec<(String, QueryValue)> = Vec::new();
        for (k, values) in &self.fields {
            let value = self.interpolate(&grid, values, &pt);
            insert(&mut out, k, QueryValue::Float(value));
        }
        let ranges: Vec<std::ops::Range<usize>> = self
            .axes
            .iter()
            .zip(&pt)
            .map(|(axis, v)| {
                let Axis::Flat(a) = axis else { unreachable!("nested axes are refused by the interpolator") };
                let i = (searchsorted_left(a, *v) as isize - 1).max(0).min(a.len() as isize - 2);
                slice2(i, a.len())
            })
            .collect();
        let block = self.block_indices(&ranges);
        let cube_any = block.iter().any(|&i| self.bad[i]);
        let all_above = |name: &str| self.field(name).is_some_and(|f| block.iter().all(|&i| f[i] > 0.5));
        let sustained = match out.iter().find(|(k, _)| k == "sustained") {
            Some((_, QueryValue::Float(x))) => *x,
            _ => f64::NAN,
        };
        let trustworthy = !cube_any && sustained > 0.999 && all_above("chemistry_trustworthy");
        let wall = trustworthy
            && matches!(py::getitem(&self.meta, "ion_wall_losses")?, PyValue::Bool(true))
            && all_above("wall_life_trustworthy");
        insert(&mut out, "trustworthy", QueryValue::Bool(trustworthy));
        insert(&mut out, "wall_life_trustworthy", QueryValue::Bool(wall));
        insert(&mut out, "hallthruster_commit", QueryValue::Str(pinned_commit(&self.repo, None)?));
        Ok(out)
    }

    /// C-order flat indices of the block `ranges` (one range per axis).
    fn block_indices(&self, ranges: &[std::ops::Range<usize>]) -> Vec<usize> {
        let mut out = vec![0usize];
        for (r, n) in ranges.iter().zip(&self.shape) {
            out = out.iter().flat_map(|base| r.clone().map(move |i| base * n + i)).collect();
        }
        out
    }

    /// scipy `_check_points` / `_check_dimensionality` / `_prepare_xi` of the per-field interpolator construction:
    /// ascending grids (descending axes flipped) or the scipy refusal.
    fn rgi_grid(&self) -> HallResult<Vec<(Vec<f64>, bool)>> {
        if self.axes.is_empty() {
            return Err(HallError::scipy("RGI_NO_AXES", "cannot reshape array of size 0 into shape (0)"));
        }
        let mut grid = Vec::new();
        for (i, axis) in self.axes.iter().enumerate() {
            let (asc, desc) = match axis {
                Axis::Flat(p) => (p.windows(2).all(|w| w[1] > w[0]), p.windows(2).all(|w| w[1] < w[0])),
                Axis::Nested(rows) => (
                    rows.windows(2).all(|w| w[1].iter().zip(&w[0]).all(|(b, a)| b > a)),
                    rows.windows(2).all(|w| w[1].iter().zip(&w[0]).all(|(b, a)| b < a)),
                ),
            };
            if !asc && !desc {
                return Err(HallError::scipy(
                    "RGI_NOT_MONOTONE",
                    format!("The points in dimension {i} must be strictly ascending or descending"),
                ));
            }
            grid.push((axis, !asc));
        }
        let mut out = Vec::new();
        for (i, (axis, descending)) in grid.into_iter().enumerate() {
            match axis {
                Axis::Nested(_) => {
                    return Err(HallError::scipy(
                        "RGI_NOT_1D",
                        format!("The points in dimension {i} must be 1-dimensional"),
                    ))
                }
                Axis::Flat(p) => {
                    let mut g = p.clone();
                    if descending {
                        g.reverse();
                    }
                    out.push((g, descending));
                }
            }
        }
        Ok(out)
    }

    /// `float(RegularGridInterpolator(points, values)(pt)[0])` for one field (bounds already checked).
    fn interpolate(&self, grid: &[(Vec<f64>, bool)], values: &[f64], pt: &[f64]) -> f64 {
        let n = grid.len();
        let mut idx = vec![0isize; n];
        let mut nd = vec![0.0f64; n];
        let mut index: isize = 0;
        for (k, ((g, _), &v)) in grid.iter().zip(pt).enumerate() {
            if g.len() == 1 {
                idx[k] = -1;
            } else {
                index = find_interval_ascending(g, v, index);
                idx[k] = index;
                nd[k] = if !v.is_nan() {
                    let denom = g[(index + 1) as usize] - g[index as usize];
                    (v - g[index as usize]) / denom
                } else {
                    f64::NAN
                };
            }
        }
        // value at multi-index (numpy indexing: negative wraps; descending axes read the flipped array)
        let at = |ix: &[isize]| -> f64 {
            let mut flat = 0usize;
            for (k, &i) in ix.iter().enumerate() {
                let len = self.shape[k] as isize;
                let mut i = if i < 0 { i + len } else { i };
                if grid[k].1 {
                    i = len - 1 - i;
                }
                flat = flat * self.shape[k] + i as usize;
            }
            values[flat]
        };
        if n == 2 {
            let (g0, g1) = (grid[0].0.len(), grid[1].0.len());
            if g0 == 1 && g1 == 1 {
                return at(&[0, 0]);
            }
            if g1 == 1 {
                let (i0, y0) = (idx[0], nd[0]);
                return at(&[i0, 0]) * (1.0 - y0) + at(&[i0 + 1, 0]) * y0;
            }
            if g0 == 1 {
                let (i1, y1) = (idx[1], nd[1]);
                return at(&[0, i1]) * (1.0 - y1) + at(&[0, i1 + 1]) * y1;
            }
            let (i0, i1, y0, y1) = (idx[0], idx[1], nd[0], nd[1]);
            let mut r = 0.0;
            r += at(&[i0, i1]) * (1.0 - y0) * (1.0 - y1);
            r += at(&[i0, i1 + 1]) * (1.0 - y0) * y1;
            r += at(&[i0 + 1, i1]) * y0 * (1.0 - y1);
            r += at(&[i0 + 1, i1 + 1]) * y0 * y1;
            return r;
        }
        let mut value = 0.0f64;
        let mut corner = vec![0isize; n];
        for c in 0..(1usize << n) {
            let mut weight = 1.0f64;
            for k in 0..n {
                let upper = (c >> (n - 1 - k)) & 1 == 1;
                let (i, w) = if upper { (idx[k] + 1, nd[k]) } else { (idx[k], 1.0 - nd[k]) };
                corner[k] = i;
                weight *= w;
            }
            value += at(&corner) * weight;
        }
        value
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn interval_and_searchsorted_follow_scipy_and_numpy() {
        let g = [250.0, 275.0, 300.0];
        assert_eq!(find_interval_ascending(&g, 250.0, 0), 0);
        assert_eq!(find_interval_ascending(&g, 275.0, 0), 1);
        assert_eq!(find_interval_ascending(&g, 300.0, 0), 1);
        assert_eq!(find_interval_ascending(&g, 299.0, 5), 1);
        assert_eq!(searchsorted_left(&g, 275.0), 1);
        assert_eq!(searchsorted_left(&g, 276.0), 2);
        assert_eq!(slice2(-1, 1), 0..1);
        assert_eq!(slice2(1, 3), 1..3);
    }

    #[test]
    fn truth_of_arrays_is_numpy() {
        assert!(truth(vec![true]).unwrap());
        assert_eq!(truth(vec![true, true]).unwrap_err().kind, Kind::Numpy(NumpySub::Truth));
        assert_eq!(truth(vec![]).unwrap_err().kind, Kind::Numpy(NumpySub::Truth));
    }
}
