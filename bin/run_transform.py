"""Run src/transform.py locally with live data and print what the views get.

Usage: python bin/run_transform.py [city] [letterboxd username]

This lives outside src/transform.py on purpose: TRMNL's runtime executes that file as a script,
so a __main__ block there would run on every refresh.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import transform  # noqa: E402

settings = {"city": sys.argv[1] if len(sys.argv) > 1 else "Leipzig"}
if len(sys.argv) > 2:
    settings["letterboxd_username"] = sys.argv[2]
output = transform.run({"trmnl": {"plugin_settings": {"custom_fields_values": settings}}})
output.pop("trmnl_state")
print(json.dumps(output, indent=2, ensure_ascii=False))
