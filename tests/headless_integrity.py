#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import configparser
import re
import sys
from pathlib import Path


PLUGIN_ID = "planx_suitability_lab"
ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_plugin_ids(text: str) -> set[str]:
    return set(re.findall(rf"{PLUGIN_ID}:[a-z0-9_]+", text))


def _extract_processing_ids() -> tuple[set[str], list[str], set[str]]:
    ids: set[str] = set()
    duplicates: list[str] = []
    class_names: set[str] = set()
    for path in (ROOT / "processing").rglob("*.py"):
        if path.name == "__init__.py":
            continue
        source = _read(path)
        try:
            node = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            duplicates.append(f"Syntax error in {path}: {exc}")
            continue
        for cls in [n for n in node.body if isinstance(n, ast.ClassDef)]:
            is_processing_algo = False
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id == "QgsProcessingAlgorithm":
                    is_processing_algo = True
                elif isinstance(base, ast.Attribute) and base.attr == "QgsProcessingAlgorithm":
                    is_processing_algo = True
            if is_processing_algo:
                class_names.add(cls.name)
            for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "name"]:
                ret = None
                for stmt in fn.body:
                    if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                        ret = stmt.value.value
                        break
                if ret:
                    pid = f"{PLUGIN_ID}:{ret}"
                    if pid in ids:
                        duplicates.append(f"Duplicate processing id: {pid} ({path})")
                    ids.add(pid)
    return ids, duplicates, class_names


def _extract_provider_classes(provider_text: str) -> tuple[set[str], set[str]]:
    imported = set(re.findall(r"from\s+\.[\w\.]+\s+import\s+([A-Za-z_][A-Za-z0-9_]*)", provider_text))
    added = set(re.findall(r"addAlgorithm\((\w+)\(\)\)", provider_text))
    return imported, added


def _validate_metadata(errors: list[str]) -> None:
    meta = ROOT / "metadata.txt"
    if not meta.exists():
        errors.append("metadata.txt missing")
        return
    cp = configparser.ConfigParser()
    try:
        cp.read(meta, encoding="utf-8")
    except Exception as exc:
        errors.append(f"metadata parse failed: {exc}")
        return
    if "general" not in cp:
        errors.append("metadata [general] section missing")
        return
    req = ["name", "version", "qgisMinimumVersion", "description", "author", "email", "icon"]
    for k in req:
        if not cp.get("general", k, fallback="").strip():
            errors.append(f"metadata missing field: {k}")
    icon_rel = cp.get("general", "icon", fallback="").strip()
    if icon_rel:
        icon_path = ROOT / icon_rel
        if not icon_path.exists():
            errors.append(f"metadata icon not found: {icon_rel}")


def run() -> int:
    errors: list[str] = []

    # 1) metadata
    _validate_metadata(errors)

    # 2) processing ids
    processing_ids, id_parse_errors, processing_classes = _extract_processing_ids()
    errors.extend(id_parse_errors)
    if not processing_ids:
        errors.append("No processing ids found in processing/*.py")

    # 3) provider integrity
    provider_path = ROOT / "provider.py"
    provider_text = _read(provider_path)
    imported_classes, added_classes = _extract_provider_classes(provider_text)
    for cls in sorted(added_classes):
        if cls not in imported_classes:
            errors.append(f"Provider addAlgorithm class not imported: {cls}")
    if len(added_classes) != len(set(added_classes)):
        errors.append("Duplicate addAlgorithm class entries in provider.")
    missing_in_provider = sorted(processing_classes - added_classes)
    if missing_in_provider:
        errors.append("Processing algorithm classes not registered in provider: " + ", ".join(missing_in_provider))

    # 4) dashboard references should resolve to real processing ids
    dashboard_text = _read(ROOT / "dashboard.py")
    dashboard_ids = _extract_plugin_ids(dashboard_text)
    for pid in sorted(dashboard_ids):
        if pid not in processing_ids:
            errors.append(f"Dashboard references unknown processing id: {pid}")

    # 5) synthetic pipeline references should resolve
    pipe_text = _read(ROOT / "processing" / "core" / "synthetic_pipeline_runner.py")
    pipe_ids = _extract_plugin_ids(pipe_text)
    for pid in sorted(pipe_ids):
        if pid not in processing_ids:
            errors.append(f"Synthetic pipeline references unknown processing id: {pid}")

    # 6) beta evidence required ids should resolve
    evidence_text = _read(ROOT / "processing" / "reporting" / "beta_evidence_report.py")
    evidence_ids = _extract_plugin_ids(evidence_text)
    for pid in sorted(evidence_ids):
        if pid not in processing_ids:
            errors.append(f"Beta evidence report references unknown processing id: {pid}")

    # 7) core docs should mention plugin id at least once
    readme = _read(ROOT / "README.md")
    if "PlanX Suitability Lab" not in readme:
        errors.append("README missing plugin title.")

    if errors:
        print("HEADLESS INTEGRITY: FAIL")
        for e in errors:
            print(f"- {e}")
        return 1

    print("HEADLESS INTEGRITY: PASS")
    print(f"- Processing ids discovered: {len(processing_ids)}")
    print(f"- Dashboard ids checked: {len(dashboard_ids)}")
    print(f"- Pipeline ids checked: {len(pipe_ids)}")
    print(f"- Evidence ids checked: {len(evidence_ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
