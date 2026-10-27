//! Runs the built `doorplate` binary.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::io::Write;
use std::process::{Command, Stdio};

fn cli(args: &[&str], stdin: &str) -> (String, String, i32) {
    let mut child = Command::new(env!("CARGO_BIN_EXE_doorplate"))
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn doorplate");
    // A command that rejects its arguments may exit before it reads stdin: a broken pipe is fine.
    let _ = child
        .stdin
        .take()
        .expect("stdin")
        .write_all(stdin.as_bytes());
    let out = child.wait_with_output().expect("wait");
    (
        String::from_utf8_lossy(&out.stdout).into_owned(),
        String::from_utf8_lossy(&out.stderr).into_owned(),
        out.status.code().unwrap_or(-1),
    )
}

#[test]
fn parse_prints_one_json_line() {
    let (out, _, code) = cli(&["parse", "123 N Main St Apt 4, Miami, FL 33101"], "");
    assert_eq!(code, 0);
    assert_eq!(out.lines().count(), 1);
    let v: serde_json::Value = serde_json::from_str(&out).expect("json");
    assert_eq!(v["components"]["street_name"], "MAIN");
    assert_eq!(v["components"]["unit_type"], "APT");
    assert_eq!(v["usps"]["line1"], "123 N MAIN ST APT 4");
    assert_eq!(v["usps"]["last_line"], "MIAMI FL 33101");
    assert_eq!(v["key"], "k3:S|123|N|MAIN|ST||FL|33101");
    assert_eq!(v["provenance"]["library_version"], doorplate::VERSION);
    // Miami is in Florida, which has curated state data; the version is the `state.toml` one.
    assert_eq!(
        v["provenance"]["state_data_version"],
        doorplate::Lexicons::builtin()
            .state_data_version("FL")
            .unwrap()
    );
    assert_eq!(v["reso"]["City"], "MIAMI");
    assert_eq!(v["warnings"], serde_json::json!([]));
}

#[test]
fn fields_and_usps_output() {
    let (out, _, code) = cli(
        &[
            "parse",
            "--line1",
            "413 OLD CORRY FIELD RD B 32506",
            "--line2",
            "PENSACOLA, FL- 32506",
            "--usps",
        ],
        "",
    );
    assert_eq!(code, 0);
    assert_eq!(out, "413 OLD CORRY FIELD RD # B\nPENSACOLA FL 32506\n");
}

#[test]
fn display_and_long_output() {
    let input = "123 north main street apt 4, miami fl 33101";
    let (out, _, code) = cli(&["parse", input, "--display"], "");
    assert_eq!(code, 0);
    assert_eq!(out, "123 N Main St Apt 4\nMiami FL 33101\n");
    let (out, _, _) = cli(&["parse", input, "--long"], "");
    assert_eq!(out, "123 North Main Street Apartment 4\nMiami FL 33101\n");
}

#[test]
fn stdin_gives_one_json_line_per_address_and_reports_blank_lines() {
    let (out, err, code) = cli(&["parse"], "1 MAIN ST\n\n2 ELM AVE\n");
    assert_eq!(out.lines().count(), 2);
    assert!(err.contains("line 2"), "{err}");
    assert_eq!(code, 2);
}

#[test]
fn empty_input_and_bad_usage_use_distinct_exit_codes() {
    assert_eq!(cli(&["parse", "  "], "").2, 2);
    assert_eq!(cli(&["parse", "--bogus"], "").2, 1);
    assert_eq!(cli(&[], "").2, 1);
}

#[test]
fn parse_file_appends_prefixed_columns() {
    let dir = std::env::temp_dir().join(format!("doorplate-cli-test-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("mkdir");
    let input = dir.join("in.csv");
    std::fs::write(&input, "id,address,city\n1,12 OAK ST #4,TAMPA\n2,,X\n").expect("write");
    let input = input.to_str().expect("utf-8 path");
    let (out, _, code) = cli(
        &["parse-file", input, "--column", "address", "--city", "city"],
        "",
    );
    assert_eq!(code, 0);
    let mut lines = out.lines();
    let header = lines.next().expect("header");
    assert!(
        header.starts_with("id,address,city,addr_street_number,"),
        "{header}"
    );
    let row = lines.next().expect("row");
    assert!(row.starts_with("1,12 OAK ST #4,TAMPA,12,"), "{row}");
    assert_eq!(lines.count(), 1);
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn default_state_is_a_hint_and_must_be_a_state() {
    let (out, err, code) = cli(
        &["parse", "281 EVELYN DR DOTHAN", "--default-state", "AL"],
        "",
    );
    assert_eq!(code, 0, "{out}\n{err}");
    assert!(out.contains("\"default_state_applied\""), "{out}");
    assert!(out.contains("\"DOTHAN\""), "{out}");
    let (out, _, _) = cli(&["parse", "281 EVELYN DR DOTHAN"], "");
    assert!(!out.contains("default_state_applied"), "{out}");
    let (_, err, code) = cli(&["parse", "1 MAIN ST", "--default-state", "ZZ"], "");
    assert_eq!(code, 1, "{err}");
    assert!(err.contains("not a US state"), "{err}");
}

#[test]
fn corpus_test_runs_the_golden_corpus() {
    let dir = concat!(env!("CARGO_MANIFEST_DIR"), "/../../tests/corpus");
    let (out, err, code) = cli(&["corpus", "test", "--dir", dir], "");
    assert_eq!(code, 0, "{out}\n{err}");
    assert!(out.contains("whole address:"), "{out}");
}

#[test]
fn corpus_test_reports_a_regression_and_a_malformed_corpus() {
    let tmp = std::env::temp_dir().join(format!("doorplate-cli-corpus-{}", std::process::id()));
    std::fs::create_dir_all(&tmp).expect("mkdir");
    let case = r#"{"id": "x-1", "input": "1 MAIN ST", "expect": {"street_number": "1", "street_name": "ELM", "street_suffix": "ST"}, "warnings": ["missing_city", "missing_state", "missing_zip"]}"#;
    std::fs::write(tmp.join("c.jsonl"), format!("{case}\n")).expect("write");
    let dir = tmp.to_str().expect("utf-8 path");
    // The case fails; with no baseline that is not a regression.
    assert_eq!(cli(&["corpus", "test", "--dir", dir], "").2, 0);
    // Listed as passing but failing: regression.
    std::fs::write(tmp.join("passing.txt"), "x-1\n").expect("write");
    assert_eq!(cli(&["corpus", "test", "--dir", dir], "").2, 3);
    // Not valid JSON: malformed.
    std::fs::write(tmp.join("c.jsonl"), "not json\n").expect("write");
    assert_eq!(cli(&["corpus", "test", "--dir", dir], "").2, 2);
    std::fs::remove_dir_all(&tmp).ok();
}

#[test]
fn version_flag_prints_the_library_version() {
    for flag in ["--version", "-V"] {
        let (out, err, code) = cli(&[flag], "");
        assert_eq!(code, 0, "{flag}");
        assert_eq!(out.trim(), format!("doorplate {}", doorplate::VERSION));
        assert!(err.is_empty());
    }
}

#[test]
fn help_prints_the_usage_and_succeeds() {
    for flag in ["--help", "-h"] {
        let (out, err, code) = cli(&[flag], "");
        assert_eq!(code, 0, "{flag}");
        assert!(out.starts_with("usage:"));
        assert!(err.is_empty());
    }
    // No command at all is still a usage error.
    let (_, err, code) = cli(&[], "");
    assert_eq!(code, 1);
    assert!(err.contains("usage:"));
}

#[test]
fn anonymize_stdin_keeps_the_shape_and_reports() {
    let line = "123 N Zephyrmill Ave Apt 4, Miami, FL 33101";
    let (out, err, code) = cli(&["anonymize", "--seed", "3"], &format!("{line}\n\n"));
    assert_eq!(code, 0);
    let lines: Vec<&str> = out.lines().collect();
    assert_eq!(lines.len(), 2);
    assert_eq!(lines[1], "", "an empty line stays empty");
    assert_ne!(lines[0], line);
    assert_eq!(lines[0].chars().count(), line.chars().count());
    assert!(
        lines[0].contains(" N ")
            && lines[0].contains(" Ave Apt ")
            && lines[0].contains("Miami, FL 331")
    );
    assert!(!lines[0].contains("Zephyrmill"));
    assert!(
        err.contains("1 value(s) anonymized") && err.contains("obfuscation, not anonymity"),
        "{err}"
    );
    // The same seed repeats the output; a different one does not.
    let (again, _, _) = cli(&["anonymize", "--seed", "3"], &format!("{line}\n\n"));
    assert_eq!(out, again);
    let (other, _, _) = cli(&["anonymize", "--seed", "4"], &format!("{line}\n\n"));
    assert_ne!(out, other);
}

#[test]
fn anonymize_csv_changes_only_the_named_columns() {
    let dir = std::env::temp_dir().join(format!("doorplate-anon-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let input = dir.join("in.csv");
    let output = dir.join("out.csv");
    std::fs::write(
        &input,
        "id,street,city\n1,55 Bayview Dr,Tampa\n2,55 Bayview Dr,Tampa\n",
    )
    .unwrap();
    let (_, err, code) = cli(
        &[
            "anonymize",
            input.to_str().unwrap(),
            "--column",
            "street",
            "-o",
            output.to_str().unwrap(),
            "--seed",
            "1",
        ],
        "",
    );
    assert_eq!(code, 0, "{err}");
    let text = std::fs::read_to_string(&output).unwrap();
    let rows: Vec<Vec<&str>> = text.lines().map(|l| l.split(',').collect()).collect();
    assert_eq!(rows[0], ["id", "street", "city"]);
    assert_eq!(rows[1][0], "1");
    assert_eq!(rows[1][2], "Tampa");
    assert_ne!(rows[1][1], "55 Bayview Dr");
    assert_eq!(
        rows[1][1], rows[2][1],
        "the same value gets the same replacement"
    );
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn anonymize_errors_do_not_quote_the_data() {
    let dir = std::env::temp_dir().join(format!("doorplate-anon-err-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let input = dir.join("in.csv");
    std::fs::write(&input, "street\nSECRETROW 1\nSECRET,TOO,MANY\n").unwrap();
    let (_, err, code) = cli(
        &["anonymize", input.to_str().unwrap(), "--column", "street"],
        "",
    );
    assert_eq!(code, 2);
    assert!(!err.contains("SECRET"), "{err}");
    let (_, _, code) = cli(&["anonymize", input.to_str().unwrap()], "");
    assert_eq!(code, 1, "--column is required for a file");
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn anonymize_usage_errors_and_empty_input() {
    let (_, err, code) = cli(&["anonymize", "--column", "street"], "55 Bayview Dr\n");
    assert_eq!(code, 1);
    assert!(err.contains("--column needs an input CSV file"), "{err}");
    let (_, err, code) = cli(&["anonymize", "a.csv", "b.csv"], "");
    assert_eq!(code, 1);
    assert!(err.contains("at most one input"), "{err}");
    let (_, _, code) = cli(&["anonymize", "--seed", "x"], "");
    assert_eq!(code, 1);
    // No input at all is not an error; nothing is anonymized and the report says so.
    let (out, err, code) = cli(&["anonymize", "-"], "");
    assert_eq!((out.as_str(), code), ("", 0));
    assert!(
        err.contains("0 value(s) anonymized") && err.contains("(100.0%)"),
        "{err}"
    );
}

#[test]
fn anonymize_csv_unknown_column_and_missing_file() {
    let dir = std::env::temp_dir().join(format!("doorplate-anon-col-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let input = dir.join("in.csv");
    std::fs::write(&input, "street\n55 Bayview Dr\n").unwrap();
    let (_, err, code) = cli(
        &["anonymize", input.to_str().unwrap(), "--column", "nope"],
        "",
    );
    assert_eq!(code, 2);
    assert!(err.contains("no column named \"nope\""), "{err}");
    let (_, err, code) = cli(
        &["anonymize", "/no/such/file.csv", "--column", "street"],
        "",
    );
    assert_eq!(code, 2);
    assert!(err.contains("could not open"), "{err}");
    std::fs::remove_dir_all(&dir).unwrap();
}

// ---- custom layers (#3) ----

const LAYER_TOML: &str = "name = \"county\"\nversion = \"7\"\n";
const ALIASES: &str =
    "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"TRAYL\"]\nevidence = \"invented for the test\"\n";

/// A layer folder in a fresh temp dir; `files` are (name, text).
fn layer_dir(tag: &str, files: &[(&str, &str)]) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("doorplate-layer-{tag}-{}", std::process::id()));
    std::fs::remove_dir_all(&dir).ok();
    std::fs::create_dir_all(&dir).unwrap();
    for (name, text) in files {
        std::fs::write(dir.join(name), text).unwrap();
    }
    dir
}

fn path(p: &std::path::Path) -> &str {
    p.to_str().unwrap()
}

#[test]
fn layer_check_lists_what_a_layer_holds() {
    let dir = layer_dir(
        "ok",
        &[
            ("layer.toml", LAYER_TOML),
            ("aliases.toml", ALIASES),
            (
                "places.tsv",
                "state\tname\tevidence\nFL\tQUINCEWOOD HEIGHTS\tinvented\n",
            ),
            ("NOTES.md", "free text is ignored"),
        ],
    );
    let (out, err, code) = cli(&["layer", "check", path(&dir)], "");
    assert_eq!(code, 0, "{err}");
    assert!(out.starts_with("ok: layer county 7 (fingerprint "), "{out}");
    assert!(
        out.contains("1 suffix spellings") && out.contains("1 places"),
        "{out}"
    );
    assert!(out.contains("A layer can change a key"), "{out}");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn layer_check_lists_every_problem_and_exits_2() {
    let bad = "[[suffix]]\nabbr = \"TRL\"\nspellings = [\"ST\"]\nevidence = \"x\"\n[[unit]]\nabbr = \"NOPE\"\nspellings = [\"AA\"]\nevidence = \"x\"\n";
    let dir = layer_dir(
        "bad",
        &[
            ("layer.toml", LAYER_TOML),
            ("aliases.toml", bad),
            ("alias.toml", "a typo of aliases.toml"),
        ],
    );
    let (out, err, code) = cli(&["layer", "check", path(&dir)], "");
    assert_eq!(code, 2);
    assert!(out.is_empty());
    assert!(err.contains("the custom layer has 3 problems"), "{err}");
    assert!(err.contains("alias.toml: not a layer file"), "{err}");
    assert!(err.contains("already in the shipped tables"), "{err}");
    assert!(
        err.contains("no unit designator with the abbreviation \"NOPE\""),
        "{err}"
    );
    std::fs::remove_dir_all(&dir).ok();
    // A folder with no layer.toml, a missing folder, and the usage errors.
    let empty = layer_dir("empty", &[]);
    let (_, err, code) = cli(&["layer", "check", path(&empty)], "");
    assert_eq!(code, 2);
    assert!(err.contains("has no layer.toml"), "{err}");
    std::fs::remove_dir_all(&empty).ok();
    assert_eq!(cli(&["layer", "check", "/no/such/folder"], "").2, 2);
    assert_eq!(cli(&["layer"], "").2, 1);
    assert_eq!(cli(&["layer", "check"], "").2, 1);
    assert_eq!(cli(&["layer", "fix", "x"], "").2, 1);
}

#[test]
fn parse_with_a_layer_reads_the_spelling_and_reports_the_layer() {
    let dir = layer_dir(
        "parse",
        &[("layer.toml", LAYER_TOML), ("aliases.toml", ALIASES)],
    );
    let text = "123 Oak Trayl, Miami, FL 33101";
    let (out, err, code) = cli(&["parse", text, "--custom-layer", path(&dir)], "");
    assert_eq!(code, 0, "{err}");
    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    assert_eq!(v["components"]["street_suffix"], "TRL");
    assert_eq!(v["provenance"]["custom_layer"]["name"], "county");
    assert_eq!(v["provenance"]["custom_layer"]["version"], "7");
    assert_eq!(
        v["provenance"]["custom_layer"]["fingerprint"]
            .as_str()
            .unwrap()
            .len(),
        16
    );
    let layered_key = v["key"].clone();
    // Without the layer: no suffix, a different key, and no layer in the provenance.
    let (out, _, _) = cli(&["parse", text], "");
    let base: serde_json::Value = serde_json::from_str(&out).unwrap();
    assert!(base["components"].get("street_suffix").is_none());
    assert_ne!(base["key"], layered_key);
    assert!(base["provenance"]["custom_layer"].is_null());
    // The hint option and fields work together with a layer; a bad layer is exit 2.
    let (out, _, code) = cli(
        &[
            "parse",
            "--line1",
            "123 Oak Trayl",
            "--city",
            "Miami",
            "--state",
            "FL",
            "--custom-layer",
            path(&dir),
        ],
        "",
    );
    assert_eq!(code, 0);
    assert!(out.contains("\"street_suffix\":\"TRL\""), "{out}");
    assert_eq!(
        cli(&["parse", text, "--custom-layer", "/no/such/folder"], "").2,
        2
    );
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn parse_file_and_stdin_take_a_layer() {
    let dir = layer_dir(
        "file",
        &[("layer.toml", LAYER_TOML), ("aliases.toml", ALIASES)],
    );
    let csv = dir.join("in.csv");
    std::fs::write(&csv, "id,address\n1,\"123 Oak Trayl, Miami, FL 33101\"\n").unwrap();
    let (out, err, code) = cli(
        &[
            "parse-file",
            path(&csv),
            "--column",
            "address",
            "--custom-layer",
            path(&dir),
        ],
        "",
    );
    assert_eq!(code, 0, "{err}");
    assert!(out.contains("TRL"), "{out}");
    let (out, _, code) = cli(
        &["parse", "-", "--custom-layer", path(&dir)],
        "123 Oak Trayl, Miami, FL 33101\n",
    );
    assert_eq!(code, 0);
    assert!(out.contains("\"street_suffix\":\"TRL\""), "{out}");
    std::fs::remove_dir_all(&dir).ok();
}

#[test]
fn corpus_test_can_run_a_corpus_against_a_layer() {
    let layer = layer_dir(
        "corpus-layer",
        &[("layer.toml", LAYER_TOML), ("aliases.toml", ALIASES)],
    );
    let corpus = layer_dir("corpus", &[]);
    let case = r#"{"id": "x-1", "input": "123 OAK TRAYL, MIAMI, FL 33101", "expect": {"street_number": "123", "street_name": "OAK", "street_suffix": "TRL", "city": "MIAMI", "state": "FL", "zip5": "33101"}, "warnings": ["non_standard_abbreviation"]}"#;
    std::fs::write(corpus.join("c.jsonl"), format!("{case}\n")).unwrap();
    std::fs::write(corpus.join("passing.txt"), "x-1\n").unwrap();
    // With the layer the case passes; without it, it regresses.
    let (out, err, code) = cli(
        &[
            "corpus",
            "test",
            "--dir",
            path(&corpus),
            "--custom-layer",
            path(&layer),
        ],
        "",
    );
    assert_eq!(code, 0, "{out}{err}");
    assert_eq!(cli(&["corpus", "test", "--dir", path(&corpus)], "").2, 3);
    std::fs::remove_dir_all(&layer).ok();
    std::fs::remove_dir_all(&corpus).ok();
}

#[test]
fn the_shipped_demo_and_template_layers_check_ok() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../examples/layers");
    for (name, layer) in [
        ("riverbend-demo", "riverbend-demo 1"),
        ("template", "my-layer 1"),
    ] {
        let dir = root.join(name);
        let (out, err, code) = cli(&["layer", "check", path(&dir)], "");
        assert_eq!(code, 0, "{name}: {err}");
        assert!(
            out.starts_with(&format!("ok: layer {layer} (fingerprint ")),
            "{out}"
        );
    }
}
