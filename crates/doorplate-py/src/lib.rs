//! Python bindings for `doorplate`, built with PyO3 and maturin.
//!
//! A thin layer: every value comes from `doorplate`, nothing is parsed or
//! formatted here. `ParsedAddress` wraps the core type and reads it; the
//! emitters are the core's. This library formats and parses; it does not
//! validate deliverability.
//!
//! Built with maturin as the extension module `doorplate._core`; the
//! package (`python/doorplate/`) re-exports it.

use std::path::PathBuf;
use std::sync::OnceLock;

use doorplate::{
    Anonymizer, CustomLayer, Fields, Highway, KeyOptions, OptionsError,
    ParseError as CoreParseError, ParseOptions, ParsedAddress, Parser, PlaceKind,
};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

pyo3::create_exception!(
    _core,
    ParseError,
    PyValueError,
    "The input has no address text at all (empty or only punctuation)."
);

pyo3::create_exception!(
    _core,
    LayerError,
    PyValueError,
    "A custom layer that cannot be loaded; the message lists every problem."
);

/// A loaded custom layer (#3): your own spellings, words, places and ZIPs on top of the shipped
/// tables. Load one with `doorplate.load_layer(folder)` and pass it as `custom_layer=`. A layer
/// can change a key: keep `fingerprint` with stored keys.
#[pyclass(name = "CustomLayer", module = "doorplate", frozen)]
#[derive(Clone)]
struct PyCustomLayer {
    inner: CustomLayer,
}

#[pymethods]
impl PyCustomLayer {
    #[getter]
    fn name(&self) -> &'static str {
        self.inner.info().name
    }

    #[getter]
    fn version(&self) -> &'static str {
        self.inner.info().version
    }

    /// 16 hex digits over the layer's files; it changes when any byte changes.
    #[getter]
    fn fingerprint(&self) -> &'static str {
        self.inner.info().fingerprint
    }

    /// What the layer holds, as `{what: count}` (what is empty is left out).
    fn counts<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        for (what, n) in self.inner.counts() {
            d.set_item(what, n)?;
        }
        Ok(d)
    }

    fn __repr__(&self) -> String {
        let i = self.inner.info();
        format!("CustomLayer({} {}, {})", i.name, i.version, i.fingerprint)
    }

    fn __eq__(&self, other: &Self) -> bool {
        self.inner == other.inner
    }
}

fn layer_err(e: &doorplate::LayerError) -> PyErr {
    LayerError::new_err(e.to_string())
}

/// Load a custom layer from a folder (`layer.toml` and any of `aliases.toml`, `overrides.toml`,
/// `places.tsv`, `zips.tsv`). Raises `LayerError` listing every problem.
#[pyfunction]
fn load_layer(path: PathBuf) -> PyResult<PyCustomLayer> {
    CustomLayer::from_dir(&path)
        .map(|inner| PyCustomLayer { inner })
        .map_err(|e| layer_err(&e))
}

/// A `custom_layer=` argument: a `CustomLayer`, or the path of a layer folder (loaded now).
fn resolve_layer(layer: Option<&Bound<'_, PyAny>>) -> PyResult<Option<CustomLayer>> {
    let Some(l) = layer.filter(|l| !l.is_none()) else {
        return Ok(None);
    };
    if let Ok(c) = l.extract::<PyRef<'_, PyCustomLayer>>() {
        return Ok(Some(c.inner));
    }
    let path: PathBuf = l.extract().map_err(|_| {
        PyTypeError::new_err(
            "custom_layer must be a doorplate.CustomLayer or the path of a layer folder",
        )
    })?;
    CustomLayer::from_dir(&path)
        .map(Some)
        .map_err(|e| layer_err(&e))
}

fn parse_err(e: &CoreParseError) -> PyErr {
    ParseError::new_err(e.to_string())
}

/// The parser for a `default_state` hint and a custom layer (`None` and `None` is the shared
/// default one).
fn parser_for(
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<Parser> {
    static DEFAULT: OnceLock<Parser> = OnceLock::new();
    let layer = resolve_layer(custom_layer)?;
    if default_state.is_none() && layer.is_none() {
        return Ok(DEFAULT.get_or_init(Parser::new).clone());
    }
    let mut options = ParseOptions::new();
    if let Some(s) = default_state {
        options = options.default_state(s);
    }
    if let Some(l) = layer {
        options = options.custom_layer(l);
    }
    Parser::with_options(options).map_err(|e: OptionsError| PyValueError::new_err(e.to_string()))
}

/// A parsed address. Read-only; the values are the core's.
#[pyclass(name = "ParsedAddress", module = "doorplate", frozen)]
struct PyParsedAddress {
    inner: ParsedAddress,
}

fn dict_or_none<'py>(
    py: Python<'py>,
    items: Option<Vec<(&'static str, Option<String>)>>,
) -> PyResult<Option<Bound<'py, PyDict>>> {
    let Some(items) = items else { return Ok(None) };
    let d = PyDict::new(py);
    for (k, v) in items {
        d.set_item(k, v)?;
    }
    Ok(Some(d))
}

#[pymethods]
impl PyParsedAddress {
    /// The input as given (for fields, the non-empty fields joined with ", ").
    #[getter]
    fn input(&self) -> &str {
        &self.inner.source.original
    }

    #[getter]
    fn street_number(&self) -> Option<&str> {
        self.inner.street_number.as_deref()
    }

    /// Directional before the name, as its USPS abbreviation (`N`, `SW`).
    #[getter]
    fn street_dir_prefix(&self) -> Option<&'static str> {
        self.inner.street_dir_prefix.map(|d| d.abbr())
    }

    #[getter]
    fn street_name(&self) -> Option<&str> {
        self.inner.street_name.as_deref()
    }

    /// Street suffix, as its USPS abbreviation (`ST`, `AVE`).
    #[getter]
    fn street_suffix(&self) -> Option<&'static str> {
        self.inner.street_suffix.map(|s| s.abbr())
    }

    #[getter]
    fn street_dir_suffix(&self) -> Option<&'static str> {
        self.inner.street_dir_suffix.map(|d| d.abbr())
    }

    /// A street named after a highway: `{"state", "prefix", "route",
    /// "name"}`, or `None`.
    #[getter]
    fn highway<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        dict_or_none(
            py,
            self.inner.highway.as_ref().map(|h: &Highway| {
                vec![
                    ("state", h.state.map(|s| s.code().to_string())),
                    ("prefix", Some(h.prefix.standard().to_string())),
                    ("route", Some(h.route.clone())),
                    ("name", Some(h.name())),
                ]
            }),
        )
    }

    #[getter]
    fn unit_type(&self) -> Option<&'static str> {
        self.inner.unit_type.map(|u| u.abbr())
    }

    #[getter]
    fn unit_number(&self) -> Option<&str> {
        self.inner.unit_number.as_deref()
    }

    #[getter]
    fn second_unit_type(&self) -> Option<&'static str> {
        self.inner.second_unit_type.map(|u| u.abbr())
    }

    #[getter]
    fn second_unit_number(&self) -> Option<&str> {
        self.inner.second_unit_number.as_deref()
    }

    #[getter]
    fn po_box(&self) -> Option<&str> {
        self.inner.po_box.as_deref()
    }

    /// `{"kind": "RR" | "HC", "route", "box"}`, or `None`.
    #[getter]
    fn rural_route<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        dict_or_none(
            py,
            self.inner.rural_route.as_ref().map(|r| {
                vec![
                    ("kind", Some(r.kind.abbr().to_string())),
                    ("route", Some(r.route.clone())),
                    ("box", r.box_number.clone()),
                ]
            }),
        )
    }

    #[getter]
    fn general_delivery(&self) -> bool {
        self.inner.general_delivery
    }

    /// `{"kind": "CPR" | "OPC" | "PSC" | "UPR" | "UNIT", "number", "box"}`, or `None`.
    #[getter]
    fn military<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        dict_or_none(
            py,
            self.inner.military.as_ref().map(|m| {
                vec![
                    ("kind", Some(m.kind.abbr().to_string())),
                    ("number", Some(m.number.clone())),
                    ("box", m.box_number.clone()),
                ]
            }),
        )
    }

    /// `APO`, `FPO` or `DPO` where the city goes.
    #[getter]
    fn military_post_office(&self) -> Option<&'static str> {
        self.inner.military_post_office.map(|m| m.abbr())
    }

    #[getter]
    fn attention(&self) -> Option<&str> {
        self.inner.attention.as_deref()
    }

    #[getter]
    fn building(&self) -> Option<&str> {
        self.inner.building.as_deref()
    }

    /// The city as the input wrote it.
    #[getter]
    fn city(&self) -> Option<&str> {
        self.inner.city.as_deref()
    }

    /// Two-letter USPS state code.
    #[getter]
    fn state(&self) -> Option<&'static str> {
        self.inner.state.map(|s| s.code())
    }

    #[getter]
    fn zip5(&self) -> Option<&str> {
        self.inner.zip5.as_deref()
    }

    #[getter]
    fn zip4(&self) -> Option<&str> {
        self.inner.zip4.as_deref()
    }

    /// The place the city stands for: `{"name", "state", "county", "kind",
    /// "source"}`, or `None`. `city` is never changed.
    #[getter]
    fn place<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        dict_or_none(
            py,
            self.inner.place.map(|m| {
                vec![
                    ("name", Some(m.place.name().to_string())),
                    ("state", Some(m.place.state().to_string())),
                    ("county", Some(m.place.county().to_string())),
                    (
                        "kind",
                        Some(
                            match m.place.kind() {
                                PlaceKind::Municipality => "municipality",
                                PlaceKind::Place => "place",
                                PlaceKind::Subdivision => "subdivision",
                                // A kind added later reads as the generic one.
                                _ => "place",
                            }
                            .to_string(),
                        ),
                    ),
                    ("source", Some(m.source.code().to_string())),
                ]
            }),
        )
    }

    /// Warning codes (`"missing_zip"`, ...), in the order they were raised.
    #[getter]
    fn warnings(&self) -> Vec<&'static str> {
        self.inner
            .diagnostics
            .warnings
            .iter()
            .map(|w| w.code())
            .collect()
    }

    /// Text the parse could not place, or `None`.
    #[getter]
    fn unparsed(&self) -> Option<&str> {
        self.inner.diagnostics.unparsed.as_deref()
    }

    #[getter]
    fn library_version(&self) -> &'static str {
        self.inner.diagnostics.library_version
    }

    /// The version of the curated data for the address's state, or `None`.
    #[getter]
    fn state_data_version(&self) -> Option<&'static str> {
        self.inner.diagnostics.state_data_version
    }

    /// The custom layer the parse used, as `{name, version, fingerprint}`, or `None`. A layer can
    /// change a key: keep the fingerprint with stored keys.
    #[getter]
    fn custom_layer<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        layer_dict(py, self.inner.diagnostics.custom_layer)
    }

    /// `street`, `po_box`, `rural_route`, `military`, `general_delivery`,
    /// `dual` or `unknown`.
    fn address_type(&self) -> &'static str {
        self.inner.address_type().code()
    }

    /// The match key (`k4:...`), or `None` when there is nothing to key on.
    /// With `unit=True` the unit numbers are part of it.
    #[pyo3(signature = (unit=false))]
    fn key(&self, unit: bool) -> Option<String> {
        self.inner.key(if unit {
            KeyOptions::unit()
        } else {
            KeyOptions::property()
        })
    }

    /// A URL-safe label, for display only. Use `key()` for identity.
    fn slug(&self) -> Option<String> {
        self.inner.slug()
    }

    /// The USPS Publication 28 form: `{"line1", "line2", "city", "state",
    /// "zip", "last_line"}`. With `max_line`, a unit that does not fit on
    /// `line1` moves to `line2`.
    #[pyo3(signature = (max_line=None))]
    fn to_usps<'py>(
        &self,
        py: Python<'py>,
        max_line: Option<usize>,
    ) -> PyResult<Bound<'py, PyDict>> {
        let u = match max_line {
            Some(n) => self.inner.to_usps_wrapped(n),
            None => self.inner.to_usps(),
        };
        let d = PyDict::new(py);
        d.set_item("line1", u.line1.clone())?;
        d.set_item("line2", u.line2.clone())?;
        d.set_item("city", u.city.clone())?;
        d.set_item("state", u.state.clone())?;
        d.set_item("zip", u.zip.clone())?;
        d.set_item("last_line", u.last_line())?;
        Ok(d)
    }

    /// Mixed case with Pub 28 abbreviations, `123 N Main St Apt 4`, for
    /// showing to people: `{"line1", "city", "state", "zip", "last_line"}`.
    /// Not a Pub 28 form (see `to_usps`).
    fn to_display<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        display_dict(py, &self.inner.to_display())
    }

    /// Mixed case with directionals, suffixes and units spelled out,
    /// `123 North Main Street Apartment 4`. Same keys as `to_display`.
    fn to_long<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        display_dict(py, &self.inner.to_long())
    }

    /// RESO Data Dictionary 2.0 fields by name; a field with no value is left
    /// out.
    fn to_reso<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let d = PyDict::new(py);
        for (k, v) in self.inner.to_reso().fields() {
            d.set_item(k, v)?;
        }
        Ok(d)
    }

    /// Every input token with the label usaddress would give it:
    /// `[(token, label)]`; `label` is `None` for a token the parse did not
    /// place.
    fn to_usaddress_tags(&self) -> Vec<(String, Option<&'static str>)> {
        self.inner
            .to_usaddress_tags()
            .into_iter()
            .map(|t| (t.text, t.label))
            .collect()
    }

    /// The counterpart of `usaddress.tag()`: `(dict, address_type)` with
    /// usaddress's label names and its three type names. It never raises
    /// `RepeatedLabelError`: the runs are joined and `repeated_labels()`
    /// lists the labels.
    fn tag<'py>(&self, py: Python<'py>) -> PyResult<(Bound<'py, PyDict>, &'static str)> {
        let t = self.inner.tag();
        let d = PyDict::new(py);
        for (label, value) in t.components() {
            d.set_item(label, value)?;
        }
        Ok((d, t.usaddress_type()))
    }

    /// The labels `tag()` joined from separate runs (two units give
    /// `OccupancyType`); empty when none.
    fn repeated_labels(&self) -> Vec<&'static str> {
        self.inner.tag().repeated_labels().to_vec()
    }

    /// Everything as plain Python values: the components (absent ones are
    /// `None`), `warnings`, `unparsed`, `place`, `address_type`, `key`,
    /// `key_unit`, `slug`, `usps` and `reso`.
    fn to_dict<'py>(slf: &Bound<'py, Self>) -> PyResult<Bound<'py, PyDict>> {
        let py = slf.py();
        let a = slf.get();
        let d = PyDict::new(py);
        d.set_item("input", a.input())?;
        for name in [
            "street_number",
            "street_dir_prefix",
            "street_name",
            "street_suffix",
            "street_dir_suffix",
            "highway",
            "unit_type",
            "unit_number",
            "second_unit_type",
            "second_unit_number",
            "po_box",
            "rural_route",
            "general_delivery",
            "military",
            "military_post_office",
            "attention",
            "building",
            "city",
            "state",
            "zip5",
            "zip4",
            "place",
            "warnings",
            "unparsed",
        ] {
            d.set_item(name, slf.getattr(name)?)?;
        }
        d.set_item("address_type", a.address_type())?;
        d.set_item("key", a.key(false))?;
        d.set_item("key_unit", a.key(true))?;
        d.set_item("slug", a.slug())?;
        d.set_item("usps", a.to_usps(py, None)?)?;
        d.set_item("reso", a.to_reso(py)?)?;
        // The same group the command-line JSON carries (#85).
        let provenance = PyDict::new(py);
        provenance.set_item("library_version", a.inner.diagnostics.library_version)?;
        provenance.set_item("state_data_version", a.inner.diagnostics.state_data_version)?;
        provenance.set_item(
            "custom_layer",
            layer_dict(py, a.inner.diagnostics.custom_layer)?,
        )?;
        d.set_item("provenance", provenance)?;
        Ok(d)
    }

    fn __repr__(&self) -> String {
        format!("ParsedAddress({:?})", self.inner.source.original)
    }
}

fn display_dict<'py>(
    py: Python<'py>,
    d: &doorplate::DisplayAddress,
) -> PyResult<Bound<'py, PyDict>> {
    let out = PyDict::new(py);
    out.set_item("line1", d.line1.clone())?;
    out.set_item("city", d.city.clone())?;
    out.set_item("state", d.state.clone())?;
    out.set_item("zip", d.zip.clone())?;
    out.set_item("last_line", d.last_line())?;
    Ok(out)
}

/// An address parser with settings. Cheap to construct and thread-safe.
#[pyclass(name = "Parser", module = "doorplate", frozen)]
struct PyParser {
    inner: Parser,
}

fn layer_dict<'py>(
    py: Python<'py>,
    info: Option<doorplate::LayerInfo>,
) -> PyResult<Option<Bound<'py, PyDict>>> {
    let Some(i) = info else { return Ok(None) };
    let d = PyDict::new(py);
    d.set_item("name", i.name)?;
    d.set_item("version", i.version)?;
    d.set_item("fingerprint", i.fingerprint)?;
    Ok(Some(d))
}

fn wrap(a: ParsedAddress) -> PyParsedAddress {
    PyParsedAddress { inner: a }
}

#[pymethods]
impl PyParser {
    /// `default_state` (a USPS code or a state name) is a hint for lookups
    /// when the input names no state: it never fills `state`. Raises
    /// `ValueError` for anything that is not a US state, DC or territory.
    #[new]
    #[pyo3(signature = (default_state=None, custom_layer=None))]
    fn new(default_state: Option<&str>, custom_layer: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        Ok(Self {
            inner: parser_for(default_state, custom_layer)?,
        })
    }

    /// Parse one address string. Raises `ParseError` only when there is no
    /// address text at all; anything else comes back with warnings.
    fn parse(&self, text: &str) -> PyResult<PyParsedAddress> {
        self.inner.parse(text).map(wrap).map_err(|e| parse_err(&e))
    }

    /// Parse pre-split fields.
    #[pyo3(signature = (line1=None, line2=None, city=None, state=None, zip=None))]
    fn parse_fields(
        &self,
        line1: Option<String>,
        line2: Option<String>,
        city: Option<String>,
        state: Option<String>,
        zip: Option<String>,
    ) -> PyResult<PyParsedAddress> {
        let fields = Fields {
            line1,
            line2,
            city,
            state,
            zip,
        };
        self.inner
            .parse_fields(&fields)
            .map(wrap)
            .map_err(|e| parse_err(&e))
    }

    /// Parse a batch. The GIL is released while Rust parses (in parallel).
    /// An element with no address text gives `None`.
    fn parse_many(&self, py: Python<'_>, texts: Vec<String>) -> Vec<Option<PyParsedAddress>> {
        let parser = &self.inner;
        let results = py.detach(|| {
            let refs: Vec<&str> = texts.iter().map(String::as_str).collect();
            parser.parse_many(&refs)
        });
        results.into_iter().map(|r| r.ok().map(wrap)).collect()
    }

    /// Parse a batch of pre-split addresses given as columns: each of
    /// `line1`, `line2`, `city`, `state` and `zip` is a sequence (an element
    /// may be `None`) or omitted, and the given columns must have the same
    /// length. The GIL is released while Rust parses (in parallel). An element
    /// with no address text gives `None`.
    #[pyo3(signature = (line1=None, line2=None, city=None, state=None, zip=None))]
    fn parse_fields_many(
        &self,
        py: Python<'_>,
        line1: Option<Vec<Option<String>>>,
        line2: Option<Vec<Option<String>>>,
        city: Option<Vec<Option<String>>>,
        state: Option<Vec<Option<String>>>,
        zip: Option<Vec<Option<String>>>,
    ) -> PyResult<Vec<Option<PyParsedAddress>>> {
        let mut columns = [line1, line2, city, state, zip];
        let mut lens = columns.iter().flatten().map(Vec::len);
        let Some(n) = lens.next() else {
            return Err(PyValueError::new_err(
                "parse_fields_many needs at least one column",
            ));
        };
        if lens.any(|l| l != n) {
            return Err(PyValueError::new_err(
                "parse_fields_many columns must all have the same length",
            ));
        }
        let mut take = |i: usize, row: usize| {
            columns[i]
                .as_mut()
                .and_then(|c| c.get_mut(row))
                .and_then(Option::take)
        };
        let rows: Vec<Fields> = (0..n)
            .map(|row| Fields {
                line1: take(0, row),
                line2: take(1, row),
                city: take(2, row),
                state: take(3, row),
                zip: take(4, row),
            })
            .collect();
        let parser = &self.inner;
        let results = py.detach(|| parser.parse_fields_many(&rows));
        Ok(results.into_iter().map(|r| r.ok().map(wrap)).collect())
    }

    fn __repr__(&self) -> &'static str {
        "Parser()"
    }
}

/// Parse one address string (see `Parser.parse`).
#[pyfunction]
#[pyo3(signature = (text, default_state=None, custom_layer=None))]
fn parse(
    text: &str,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyParsedAddress> {
    parser_for(default_state, custom_layer)?
        .parse(text)
        .map(wrap)
        .map_err(|e| parse_err(&e))
}

/// Parse pre-split fields (see `Parser.parse_fields`).
#[pyfunction]
#[pyo3(signature = (line1=None, line2=None, city=None, state=None, zip=None, default_state=None, custom_layer=None))]
fn parse_fields(
    line1: Option<String>,
    line2: Option<String>,
    city: Option<String>,
    state: Option<String>,
    zip: Option<String>,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyParsedAddress> {
    parser_for(default_state, custom_layer)?
        .parse_fields(&Fields {
            line1,
            line2,
            city,
            state,
            zip,
        })
        .map(wrap)
        .map_err(|e| parse_err(&e))
}

/// Parse a batch (see `Parser.parse_many`).
#[pyfunction]
#[pyo3(signature = (texts, default_state=None, custom_layer=None))]
fn parse_many(
    py: Python<'_>,
    texts: Vec<String>,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<Option<PyParsedAddress>>> {
    let parser = PyParser {
        inner: parser_for(default_state, custom_layer)?,
    };
    Ok(parser.parse_many(py, texts))
}

/// Parse a batch of pre-split addresses (see `Parser.parse_fields_many`).
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (line1=None, line2=None, city=None, state=None, zip=None, default_state=None, custom_layer=None))]
fn parse_fields_many(
    py: Python<'_>,
    line1: Option<Vec<Option<String>>>,
    line2: Option<Vec<Option<String>>>,
    city: Option<Vec<Option<String>>>,
    state: Option<Vec<Option<String>>>,
    zip: Option<Vec<Option<String>>>,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<Option<PyParsedAddress>>> {
    let parser = PyParser {
        inner: parser_for(default_state, custom_layer)?,
    };
    parser.parse_fields_many(py, line1, line2, city, state, zip)
}

/// One column of string values from parsed results (the names `doorplate._columns` accepts); a
/// row with no result is `None`. `None` for a name that is not a column.
fn column_of(parsed: &[Option<ParsedAddress>], name: &str) -> Option<Vec<Option<String>>> {
    type Get = fn(&ParsedAddress) -> Option<String>;
    let get: Get = match name {
        "street_number" => |a| a.street_number.clone(),
        "street_dir_prefix" => |a| a.street_dir_prefix.map(|d| d.abbr().to_string()),
        "street_name" => |a| a.street_name.clone(),
        "street_suffix" => |a| a.street_suffix.map(|s| s.abbr().to_string()),
        "street_dir_suffix" => |a| a.street_dir_suffix.map(|d| d.abbr().to_string()),
        "unit_type" => |a| a.unit_type.map(|u| u.abbr().to_string()),
        "unit_number" => |a| a.unit_number.clone(),
        "second_unit_type" => |a| a.second_unit_type.map(|u| u.abbr().to_string()),
        "second_unit_number" => |a| a.second_unit_number.clone(),
        "po_box" => |a| a.po_box.clone(),
        "military_post_office" => |a| a.military_post_office.map(|m| m.abbr().to_string()),
        "attention" => |a| a.attention.clone(),
        "building" => |a| a.building.clone(),
        "city" => |a| a.city.clone(),
        "state" => |a| a.state.map(|s| s.code().to_string()),
        "zip5" => |a| a.zip5.clone(),
        "zip4" => |a| a.zip4.clone(),
        "unparsed" => |a| a.diagnostics.unparsed.clone(),
        "address_type" => |a| Some(a.address_type().code().to_string()),
        "key" => |a| a.key(KeyOptions::property()),
        "key_unit" => |a| a.key(KeyOptions::unit()),
        "slug" => |a| a.slug(),
        "warnings" => |a| {
            let codes: Vec<&str> = a.diagnostics.warnings.iter().map(|w| w.code()).collect();
            Some(codes.join(","))
        },
        "usps_line1" => |a| a.to_usps().line1,
        "usps_line2" => |a| a.to_usps().line2,
        "usps_last_line" => |a| Some(a.to_usps().last_line()),
        _ => return None,
    };
    Some(parsed.iter().map(|a| a.as_ref().and_then(get)).collect())
}

/// Parse a batch and return `(columns, present)`: one list of strings per column name, in
/// `columns` order, with the same values as reading the attributes off `parse_many`'s results
/// but without a Python object per row, and `present[i]`, False for a row with no result
/// (that row is `None` in every column). Private: `doorplate.pandas`, `.polars` and
/// `.duckdb` use it. The GIL is released while Rust parses and builds the columns (a thread
/// per column).
#[pyfunction]
#[pyo3(signature = (texts, columns, default_state=None, custom_layer=None))]
fn _parse_columns<'py>(
    py: Python<'py>,
    texts: Vec<String>,
    columns: Vec<String>,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<(Vec<Bound<'py, PyList>>, Bound<'py, PyList>)> {
    if let Some(bad) = columns.iter().find(|c| column_of(&[], c).is_none()) {
        return Err(PyValueError::new_err(format!("unknown column {bad:?}")));
    }
    let parser = parser_for(default_state, custom_layer)?;
    let (built, present) = py.detach(|| {
        let refs: Vec<&str> = texts.iter().map(String::as_str).collect();
        let parsed: Vec<Option<ParsedAddress>> = parser
            .parse_many(&refs)
            .into_iter()
            .map(Result::ok)
            .collect();
        let present: Vec<bool> = parsed.iter().map(Option::is_some).collect();
        let built = std::thread::scope(|scope| {
            let handles: Vec<_> = columns
                .iter()
                .map(|name| scope.spawn(|| column_of(&parsed, name).unwrap_or_default()))
                .collect();
            handles
                .into_iter()
                .map(|h| h.join().ok())
                .collect::<Option<Vec<_>>>()
        });
        (built, present)
    });
    let built =
        built.ok_or_else(|| PyValueError::new_err("internal error while building the columns"))?;
    let lists = built
        .into_iter()
        .map(|col| PyList::new(py, col))
        .collect::<PyResult<Vec<_>>>()?;
    Ok((lists, PyList::new(py, present)?))
}

/// The counterpart of `usaddress.tag()`: `(dict, address_type)`.
#[pyfunction]
#[pyo3(signature = (text, default_state=None, custom_layer=None))]
fn tag<'py>(
    py: Python<'py>,
    text: &str,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<(Bound<'py, PyDict>, &'static str)> {
    parse(text, default_state, custom_layer)?.tag(py)
}

/// The counterpart of `usaddress.parse()`: `[(token, label)]`.
#[pyfunction]
#[pyo3(signature = (text, default_state=None, custom_layer=None))]
fn parse_tokens(
    text: &str,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<Vec<(String, Option<&'static str>)>> {
    Ok(parse(text, default_state, custom_layer)?.to_usaddress_tags())
}

/// The kind of address in `text`: `street`, `po_box`, `rural_route`,
/// `military`, `general_delivery`, `dual` or `unknown`.
#[pyfunction]
#[pyo3(signature = (text, default_state=None, custom_layer=None))]
fn address_type(
    text: &str,
    default_state: Option<&str>,
    custom_layer: Option<&Bound<'_, PyAny>>,
) -> PyResult<&'static str> {
    Ok(parse(text, default_state, custom_layer)?.address_type())
}

/// The result of `Anonymizer.anonymize`: the obfuscated `text` and whether the parser
/// reads it like the original (`faithful`).
#[pyclass(name = "Anonymized", module = "doorplate", frozen, get_all)]
struct PyAnonymized {
    text: String,
    faithful: bool,
}

#[pymethods]
impl PyAnonymized {
    fn __repr__(&self) -> String {
        format!(
            "Anonymized(text=<{} chars>, faithful={})",
            self.text.chars().count(),
            if self.faithful { "True" } else { "False" }
        )
    }
}

/// Shape-preserving obfuscation of address-like text. This is not anonymity: read the output
/// before you share it.
#[pyclass(name = "Anonymizer", module = "doorplate", frozen)]
struct PyAnonymizer {
    inner: Anonymizer,
}

#[pymethods]
impl PyAnonymizer {
    /// `seed=None` picks a random seed; a fixed seed repeats the output.
    #[new]
    #[pyo3(signature = (seed=None))]
    fn new(seed: Option<u64>) -> Self {
        PyAnonymizer {
            inner: seed.map_or_else(Anonymizer::new, Anonymizer::with_seed),
        }
    }

    #[getter]
    fn seed(&self) -> u64 {
        self.inner.seed()
    }

    fn anonymize(&self, text: &str) -> PyAnonymized {
        let r = self.inner.anonymize(text);
        PyAnonymized {
            text: r.text,
            faithful: r.faithful,
        }
    }

    /// A batch; the same value gets the same replacement across it. Releases the GIL.
    fn anonymize_many(&self, py: Python<'_>, texts: Vec<String>) -> Vec<PyAnonymized> {
        let a = &self.inner;
        py.detach(|| {
            texts
                .iter()
                .map(|t| {
                    let r = a.anonymize(t);
                    PyAnonymized {
                        text: r.text,
                        faithful: r.faithful,
                    }
                })
                .collect()
        })
    }
}

/// Obfuscate one text with a new random seed (or `seed`). Returns the text only.
#[pyfunction]
#[pyo3(signature = (text, seed=None))]
fn anonymize(text: &str, seed: Option<u64>) -> String {
    seed.map_or_else(Anonymizer::new, Anonymizer::with_seed)
        .anonymize(text)
        .text
}

/// Rule firing counts (#401, feature `rule-stats`): parse each record's fields on this thread and
/// count which rules fire. Returns the number parsed.
#[cfg(feature = "rule-stats")]
#[pyfunction]
fn _rule_stats_run(
    line1: Vec<Option<String>>,
    line2: Vec<Option<String>>,
    city: Vec<Option<String>>,
    state: Vec<Option<String>>,
    zip: Vec<Option<String>>,
) -> usize {
    let parser = Parser::new();
    let n = line1.len();
    for i in 0..n {
        let get = |v: &Vec<Option<String>>| v.get(i).cloned().flatten();
        let _ = parser.parse_fields(&Fields {
            line1: get(&line1),
            line2: get(&line2),
            city: get(&city),
            state: get(&state),
            zip: get(&zip),
        });
        doorplate::rulestats::end_parse();
    }
    n
}

/// The rule firing counts of this thread so far, as `(kind, site, label, fires, inputs)`, and the
/// number of parses; then reset (feature `rule-stats`).
#[cfg(feature = "rule-stats")]
#[pyfunction]
fn _rule_stats_take() -> (Vec<(String, String, String, u64, u64)>, u64) {
    let (rows, parses) = doorplate::rulestats::take();
    (
        rows.into_iter()
            .map(|r| (r.kind, r.site, r.label, r.fires, r.inputs))
            .collect(),
        parses,
    )
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", doorplate::VERSION)?;
    m.add("ParseError", m.py().get_type::<ParseError>())?;
    m.add("LayerError", m.py().get_type::<LayerError>())?;
    m.add_class::<PyCustomLayer>()?;
    m.add_function(wrap_pyfunction!(load_layer, m)?)?;
    m.add_class::<PyParser>()?;
    m.add_class::<PyParsedAddress>()?;
    m.add_class::<PyAnonymizer>()?;
    m.add_class::<PyAnonymized>()?;
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    m.add_function(wrap_pyfunction!(parse_fields, m)?)?;
    m.add_function(wrap_pyfunction!(parse_many, m)?)?;
    m.add_function(wrap_pyfunction!(_parse_columns, m)?)?;
    m.add_function(wrap_pyfunction!(parse_fields_many, m)?)?;
    #[cfg(feature = "rule-stats")]
    {
        m.add_function(wrap_pyfunction!(_rule_stats_run, m)?)?;
        m.add_function(wrap_pyfunction!(_rule_stats_take, m)?)?;
    }
    m.add_function(wrap_pyfunction!(tag, m)?)?;
    m.add_function(wrap_pyfunction!(parse_tokens, m)?)?;
    m.add_function(wrap_pyfunction!(address_type, m)?)?;
    m.add_function(wrap_pyfunction!(anonymize, m)?)?;
    Ok(())
}
