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
    child
        .stdin
        .take()
        .expect("stdin")
        .write_all(stdin.as_bytes())
        .expect("write stdin");
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
    assert_eq!(v["key"], "k2:S|123|N|MAIN|ST||FL|33101");
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
