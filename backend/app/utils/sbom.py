"""SBOM generation in CycloneDX 1.5 JSON (CERT-In SBOM Guidelines, 03-Oct-2024; TS Ch.7 p.53-55; FRD NFR-21).

Captures component name, version, supplier, licence, unique identifier (purl) and dependency relationship
for backend (Python) and frontend (npm) components.

Usage:  python -m app.utils.sbom  ->  writes ../sbom/oms-poc.cdx.json
"""
import json
import uuid
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def python_components() -> list[dict]:
    out = []
    for d in sorted(metadata.distributions(), key=lambda x: (x.metadata["Name"] or "").lower()):
        name, ver = d.metadata["Name"], d.version
        if not name:
            continue
        lic = d.metadata.get("License-Expression") or d.metadata.get("License") or ""
        out.append({"type": "library", "bom-ref": f"pkg:pypi/{name.lower()}@{ver}", "name": name, "version": ver,
                    "supplier": {"name": d.metadata.get("Author") or d.metadata.get("Maintainer") or "PyPI"},
                    "licenses": [{"license": {"name": lic[:120]}}] if lic else [], "purl": f"pkg:pypi/{name.lower()}@{ver}",
                    "properties": [{"name": "oms:tier", "value": "backend"}]})
    return out


def npm_components() -> list[dict]:
    lock = ROOT / "frontend" / "package-lock.json"
    if not lock.exists():
        return []
    data = json.loads(lock.read_text(encoding="utf-8"))
    out = []
    for path, info in (data.get("packages") or {}).items():
        if not path.startswith("node_modules/") or "version" not in info:
            continue
        name = path.split("node_modules/")[-1]
        out.append({"type": "library", "bom-ref": f"pkg:npm/{name}@{info['version']}", "name": name, "version": info["version"],
                    "licenses": [{"license": {"name": info["license"]}}] if info.get("license") else [],
                    "purl": f"pkg:npm/{name}@{info['version']}", "scope": "optional" if info.get("dev") else "required",
                    "properties": [{"name": "oms:tier", "value": "frontend"}]})
    return out


def build() -> dict:
    comps = python_components() + npm_components()
    root_ref = "pkg:generic/grid-india-oms-poc@0.1.0"
    return {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1,
            "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(),
                         "component": {"type": "application", "bom-ref": root_ref, "name": "Pan-Grid-India OMS (POC)", "version": "0.1.0",
                                       "supplier": {"name": "Bidder (POC)"}},
                         "tools": [{"name": "oms-sbom", "version": "1.0"}]},
            "components": comps, "dependencies": [{"ref": root_ref, "dependsOn": [c["bom-ref"] for c in comps]}]}


def main() -> Path:
    out = ROOT / "sbom" / "oms-poc.cdx.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(build(), indent=2), encoding="utf-8")
    print(f"SBOM written: {out}")
    return out


if __name__ == "__main__":
    main()
