#!/usr/bin/env python3
"""Reproduce readback design budgets from the existing face-only benchmark.

No device access, model execution, throughput forecast, or source mutation.
All byte counts are logical payloads, not measured bus traffic.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK = ROOT / (
    "artifacts/facelandmarker/registration-lab/"
    "rgb-first-benchmark-20261102-193415/performance-data/component-comparison.json"
)
SOURCE = ROOT / "FaceLandmarkerApp/src/main/java/com/pico/spatial/ml/sample/facelandmarker"


def analyze(benchmark):
    data = json.loads(benchmark.read_text())["rgb"]
    # Top-level groups contain mixed face/no-face tasks. Use only matched face chains.
    groups = data["faceCompleteChainGroups"]
    operators = data["faceOperatorTimings"]
    budget = data["faceBudget"]
    count = data["faceCompleteChains"]["count"]
    assert count > 0 and len(operators) == 39
    assert all(op["durationMs"]["count"] == count for op in operators)
    assert all(group["count"] == count for group in groups.values())
    total = sum(op["durationMs"]["mean"] for op in operators)
    assert math.isclose(total, budget["operatorMs"]["mean"], abs_tol=1e-7)
    assert math.isclose(total, sum(g["mean"] for g in groups.values()), abs_tol=1e-7)
    reconciliation = sum(
        budget[key]["mean"]
        for key in ("operatorMs", "withinTaskOverheadMs", "interTaskGapMs", "outsideServiceSpanMs")
    )
    assert math.isclose(reconciliation, budget["submitReadbackMs"]["mean"], abs_tol=1e-7)

    by_kind = {}
    for op in operators:
        item = by_kind.setdefault(op["kind"], {"operators": 0, "meanMs": 0})
        item["operators"] += 1
        item["meanMs"] += op["durationMs"]["mean"]
    for item in by_kind.values():
        item["percentOfOperatorTime"] = 100 * item["meanMs"] / total

    tail_names = [
        "Tracking and geometry fits", "Registration diagnostics", "Fit snapshot",
        "Mesh projection, unprojection and conversion", "Blendshape inference",
        "Result packing", "Mesh snapshot", "Terminal completion marker",
    ]
    tail = sum(groups[name]["mean"] for name in tail_names)
    copies = sum(
        op["durationMs"]["mean"] for op in operators
        if op["pipeline"] in ("detector", "landmark_fit")
        and op["name"] in ("Arithmetic", "Assignment")
    )
    snapshots = sum(groups[name]["mean"] for name in (
        "Producer snapshot", "Fit snapshot", "Mesh snapshot"
    ))
    tail_snapshot_overlap = groups["Fit snapshot"]["mean"] + groups["Mesh snapshot"]["mean"]
    # Union, not a sum that double-counts the fit/mesh snapshots in the tail.
    union = tail + copies + groups["Producer snapshot"]["mean"]

    graph_file = SOURCE / "FaceLandmarkerGraph.kt"
    runner_file = SOURCE / "FaceLandmarkerRunner.kt"
    session_file = SOURCE / "SpatialMLGraphSession.kt"
    graph = graph_file.read_text()
    runner = runner_file.read_text()
    session = session_file.read_text()
    raw = int(re.search(r"private val raw = session.global\(1, (\d+)\)", graph)[1])
    result = int(re.search(r"const val RESULT_SIZE = (\d+)", runner)[1])
    width = int(re.search(r"const val WIDTH = (\d+)", session)[1])
    height = int(re.search(r"const val HEIGHT = (\d+)", session)[1])
    anchors = sum(int(re.search(rf"val {name} = floats\((\d+), 16\)", graph)[1])
                  for name in ("fine", "coarse"))
    assert (raw, result, width, height, anchors) == (1434, 2994, 3248, 2464, 896)
    header_words = 64  # Proposed design envelope, not the current packet contract.
    payloads = {
        "fullCameraRgbU8": width * height * 3,
        "removedLogicalFullCameraFp32": width * height * 3 * 4,
        "oneCropRgbU8": 256 * 256 * 3,
        "oneNormalizedCropFp32": 256 * 256 * 3 * 4,
        "detectorOutputsFp32": anchors * (16 + 1) * 4,
        "rawLandmarksFp32": raw * 4,
        "currentFinalPacketFp32": result * 4,
        "proposedMetadataEnvelope": header_words * 4,
        "proposedRawLandmarksWithMetadata": (raw + header_words) * 4,
        "proposedRawLandmarksMetadataAndBlendshapes": (raw + header_words + 52) * 4,
        "proposedPoseSubsetWithMetadataAndDepthMean": (33 * 3 + header_words + 1) * 4,
        "proposedDetectorOutputsWithMetadata": (anchors * 17 + header_words) * 4,
        "proposedAppFeedbackEnvelope": 32 * 4,
    }
    source_paths = [benchmark, graph_file, runner_file, session_file]
    return {
        "status": "STATIC_DESIGN_ANALYSIS_PASS",
        "boundary": "Existing tracing-on matched eligible face means; no new runtime measurement or predicted speedup.",
        "variant": "rgb", "eligibleFaceChains": count,
        "operatorMeanMs": total, "operatorKinds": by_kind,
        "afterLandmarkBoundary": {
            "groups": tail_names, "existingWorkToMoveOrReplaceMs": tail,
            "existingPrefixOperatorMs": total - tail,
            "eligibility": "This tail includes internal SpatialML dependencies. Read back only final app results; retain required tracker state and service model inputs internally. The whole tail is not eligible for app transfer.",
            "replacementCosts": "Compact publication, completion, readback, app math/state, optional blendshape features/inference, and mesh upload must be measured.",
        },
        "diagnosticWork": {
            "cropCopiesMs": copies, "snapshotsMs": snapshots,
            "totalMs": copies + snapshots,
            "overlapWithAfterLandmarkTailMs": tail_snapshot_overlap,
            "unionWithAfterLandmarkTailMs": union,
            "retainedOldOperatorsAfterBothChangesMs": total - union,
            "caveat": "Arithmetic remainder only, not a valid retained-graph budget or frame-time forecast. Internal dependencies removed by this subtraction must remain or be replaced in SpatialML; other replacement work and scheduling are also excluded.",
        },
        "sameFrameTracedBudget": budget,
        "logicalPayloadBytes": payloads,
        "payloadEligibility": {
            "rule": "Compact size alone does not authorize intermediate readback; export final app outputs only.",
            "proposedDetectorOutputsWithMetadata": "Historical comparison size, not a valid app readback boundary for this face pipeline: detector outputs feed later SpatialML cropping.",
            "proposedAppFeedbackEnvelope": "Historical allowance from the withdrawn app tracker feedback proposal; service-dependent tracker state remains internal.",
        },
        "wrapperPayloadAccounting": {
            "twoFullRgbPreprocessInputs": 2 * payloads["fullCameraRgbU8"],
            "twoNormalizedOutputsPlusTwoTrainedModelInputs": 4 * payloads["oneNormalizedCropFp32"],
            "caveat": "Source-derived logical copy payloads; not physical CPU/GPU/NPU transfer bytes or measured copy time.",
        },
        "provenance": [
            {"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in source_paths
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.benchmark.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "status": result["status"], "eligibleFaceChains": result["eligibleFaceChains"],
        "operatorMeanMs": result["operatorMeanMs"],
        "operatorKinds": result["operatorKinds"],
        "afterLandmarkBoundary": result["afterLandmarkBoundary"],
        "diagnosticWork": result["diagnosticWork"],
        "logicalPayloadBytes": result["logicalPayloadBytes"],
    }, indent=2))


if __name__ == "__main__":
    main()
