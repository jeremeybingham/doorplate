"""Anonymizer: shape-preserving obfuscation (invented input only)."""
import doorplate


def test_function_keeps_the_shape():
    line = "123 N Zephyrmill Ave Apt 4, Miami, FL 33101"
    out = doorplate.anonymize(line, seed=3)
    assert out != line and len(out) == len(line)
    assert " N " in out and " Ave Apt " in out and "Miami, FL 331" in out
    assert "Zephyrmill" not in out
    assert out == doorplate.anonymize(line, seed=3)
    assert out != doorplate.anonymize(line, seed=4)


def test_anonymizer_reports_faithfulness_and_batches():
    a = doorplate.Anonymizer(seed=1)
    assert a.seed == 1
    r = a.anonymize("55 Bayview Dr, Tampa, FL 33602")
    assert r.faithful and r.text != "55 Bayview Dr, Tampa, FL 33602"
    assert "Bayview" not in repr(r)  # the repr never shows the text
    batch = a.anonymize_many(["55 Bayview Dr", "55 Bayview Dr", "", "???"])
    assert batch[0].text == batch[1].text != "55 Bayview Dr"
    assert batch[2].text == "" and batch[3].text == "???"


def test_random_seed_differs_between_instances():
    seeds = {doorplate.Anonymizer().seed for _ in range(5)}
    assert len(seeds) == 5
