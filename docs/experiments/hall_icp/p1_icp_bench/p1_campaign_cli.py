#!/usr/bin/env python3
"""P1 campaign CLI (lane fo_a9_6_p1_workflow_completion): read a campaign directory or one bundle file, run the pure
driver p1_campaign.run_campaign and write the campaign report.

Input (either):
  <bundle.json>                    {"schema": "p1_campaign_bundle_v1", "manifest", "registrations", "records"}
  <campaign_dir>/                  manifest.json, registrations.json and records/*.json (each file one raw record
                                   or a list of raw records; read in sorted file-name order)
Usage:
  python docs/experiments/hall_icp/p1_icp_bench/p1_campaign_cli.py <bundle.json | campaign_dir> [--out report.json]
The report is checked against p1_campaign_report_schema_v1.json (structure; full metaschema validation when the
optional jsonschema package is installed). Exit code 0 = report written, 2 = bundle refused (the reason is printed;
nothing is written).
"""
import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "p1_campaign_report_schema_v1.json")


def _campaign():
    spec = importlib.util.spec_from_file_location("p1_campaign_for_cli", os.path.join(HERE, "p1_campaign.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_bundle(path):
    """A bundle file, or a campaign directory assembled into a bundle (no record is filtered or altered)."""
    if os.path.isfile(path):
        return _read(path)
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    recs = []
    rdir = os.path.join(path, "records")
    for name in sorted(os.listdir(rdir)):
        if name.endswith(".json"):
            x = _read(os.path.join(rdir, name))
            recs.extend(x if isinstance(x, list) else [x])
    return {"schema": "p1_campaign_bundle_v1", "manifest": _read(os.path.join(path, "manifest.json")),
            "registrations": _read(os.path.join(path, "registrations.json")), "records": recs}


def check_report(report, schema):
    """Required top-level keys and enumerations of the report schema; full validation when jsonschema exists."""
    missing = [k for k in schema["required"] if k not in report]
    if missing:
        raise ValueError("report misses required keys %s" % missing)
    try:
        import jsonschema
    except ImportError:
        return "structural"
    jsonschema.Draft202012Validator(schema).validate(report)
    return "jsonschema"


def main(argv=None):
    ap = argparse.ArgumentParser(description="P1 ICP bench campaign driver (engineering-only)")
    ap.add_argument("source", help="bundle .json file or campaign directory")
    ap.add_argument("--out", help="report path (default: stdout)")
    a = ap.parse_args(argv)
    camp = _campaign()
    bundle = load_bundle(a.source)
    try:
        report = camp.run_campaign(bundle)
    except camp.red.P1RecordError as e:
        print("REFUSED (%s): %s" % (type(e).__name__, e), file=sys.stderr)
        return 2
    how = check_report(report, _read(SCHEMA))
    text = json.dumps(report, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote %s (schema check: %s; ICP45 %s)" % (a.out, how, report["icp45_status"]["status"]),
              file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
