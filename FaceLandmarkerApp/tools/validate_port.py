"""Standalone asset, binding, handedness, and publication checks. Requires Python 3 and Node.js.

python3 FaceLandmarkerApp/tools/validate_port.py [--apk path/to/facelandmarker.apk]
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import zipfile

MODULE = Path(__file__).resolve().parents[1]
ASSETS = MODULE / "src/main/assets/SpatialML/face-landmarker"


def run_operator(process, script, tensors):
    process.stdin.write(json.dumps({"script": str(script), "tensors": tensors}) + "\n")
    process.stdin.flush()
    result = json.loads(process.stdout.readline())
    assert "error" not in result, result
    return result["tensors"]


def matrix(yaw, roll, scale, translation):
    c, s, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(roll), math.sin(roll)
    return [scale*c*cr, -scale*c*sr, scale*s, translation[0],
            scale*sr, scale*cr, 0, translation[1],
            -scale*s*cr, scale*s*sr, scale*c, translation[2], 0, 0, 0, 1]


def point(m, xyz):
    return [m[r*4+3] + sum(m[r*4+c]*xyz[c] for c in range(3)) for r in range(3)]


def check_assets():
    provenance = json.loads((ASSETS / "provenance.json").read_text())
    for name, entry in provenance["models"].items():
        data = (ASSETS / "model" / name).read_bytes()
        assert data[4:8] == b"TFL3", name
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], name
    geometry = json.loads((ASSETS / "data/face_geometry.json").read_text())
    assert len(geometry["canonical"]) == 468*4
    assert len(geometry["triangles"]) == 906*3
    assert all(0 <= i < 478 for i in geometry["triangles"])
    assert len(geometry["blendshapeIndices"]) == 146
    assert len(geometry["blendshapeNames"]) == 52
    assert sum(geometry["canonical"][i*4+3] > 0 for i in range(468)) == 33
    manifest = (MODULE / "src/main/AndroidManifest.xml").read_text()
    assert 'android:name="pico.spatial.stage.style" android:value="1"' in manifest
    print("PASS: model hashes, fixed topology, 33 weighted fit points, and Full Space passthrough Stage manifest")


def check_bindings():
    graph = (MODULE / "src/main/java/com/pico/spatial/ml/sample/facelandmarker/FaceLandmarkerGraph.kt").read_text()
    calls = list(re.finditer(r'script\(\s*"([\w]+)"', graph))
    for call in calls:
        start = graph.index("(", call.start())
        balance, end = 1, start+1
        while balance:
            balance += (graph[end] == "(") - (graph[end] == ")")
            end += 1
        aliases = set(re.findall(r'"(\w+)"\s+to\b', graph[start:end]))
        declared = set(re.findall(r'^var (\w+);', (ASSETS / "operators" / (call[1]+".js")).read_text(), re.M))
        assert aliases == declared, (call[1], "unbound", declared-aliases, "unused", aliases-declared)
    assert {call[1] for call in calls} == {p.stem for p in (ASSETS / "operators").glob("*.js")}
    print("PASS: all JavaScript operands and results are bound")


def check_coordinates():
    process = subprocess.Popen(["node", str(MODULE / "tools/run_operator.mjs")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    max_error = 0
    try:
        for frame in range(24):
            pose = matrix(frame*.07, frame*-.03, .5+frame*.03, [.3, -1.2, -75])
            world = matrix(frame*-.05, frame*.02, .75+frame*.01, [-.4, 1.6, -1.2])
            # A deformed 3D face, generated independently of either result packer.
            local_cm = [[math.sin(i*.19)*7, math.cos(i*.13)*9, math.sin(i*.11)*2] for i in range(478)]
            metric = [v for p in local_cm for v in point(pose, p)]
            tensors = {"command": [frame+1, frame/30, 1, 1], "validity": [1, .9], "roi": [1, .8, 512, 512, 256, 0],
                       "landmarks": [0]*1434, "metric": metric, "pose": pose, "worldPose": world,
                       "blendshapes": [i/52 for i in range(52)], "detectorInfo": [2, .8, 100], "diagnostics": [0]*32,
                       "leftCameraToXr": matrix(.2, -.1, 1, [.1, 1.5, 0]), "result": [0]*2994}
            stage = run_operator(process, ASSETS / "operators/pack_service_result.js", tensors)["result"]
            tensors["result"] = [0]*2978
            unity = run_operator(process, MODULE / "tools/reference/pack_unity_result.js", tensors)["result"]
            assert stage[0] == frame+1 and stage[1] == unity[1] == 1
            assert stage[2872:2924] == unity[2872:2924]
            for i, local in enumerate(local_cm):
                expected = point(world, [v*.01 for v in local])
                unity_world = point(unity[2924:2940], unity[1438+i*3:1441+i*3])
                unity_world[2] *= -1
                actual = stage[1438+i*3:1441+i*3]
                for a in range(3):
                    max_error = max(max_error, abs(actual[a]-expected[a]), abs(actual[a]-unity_world[a]))
            assert stage[2978:2994] == tensors["leftCameraToXr"]
        assert max_error < 1e-9, max_error
        tensors["validity"] = [0, 0]
        tensors["result"] = [123]*2994
        absent = run_operator(process, ASSETS / "operators/pack_service_result.js", tensors)["result"]
        assert absent[0] == 24 and absent[1] == 0 and all(v == 0 for v in absent[4:2940])
        tensors["validity"] = [1, .9]
        tensors["metric"][0] = "NaN"
        invalid = run_operator(process, ASSETS / "operators/pack_service_result.js", tensors)["result"]
        assert invalid[0] == 24 and all(v == 0 for v in invalid[1:])
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    print(f"PASS: 24 rotations/scales/deformations, Unity parity, capture pose, face loss and NaN rejection; max error {max_error:.3g} m")


def dex_classes(data):
    def uint(offset): return struct.unpack_from("<I", data, offset)[0]
    strings, types, count, classes = uint(60), uint(68), uint(96), uint(100)
    for i in range(count):
        string_index = uint(types + 4*uint(classes + 32*i))
        offset = uint(strings + 4*string_index)
        while data[offset] & 128: offset += 1
        offset += 1
        yield data[offset:data.index(0, offset)].decode()


def check_apk(path):
    with zipfile.ZipFile(path) as apk:
        for name in apk.namelist():
            if re.fullmatch(r"classes\d*\.dex", name):
                assert not any(c.startswith("Lcom/bytedance/pico/openmr/spatial/pack/") for c in dex_classes(apk.read(name))), "compile-only platform stubs packaged in APK"
        for name, entry in json.loads((ASSETS / "provenance.json").read_text())["models"].items():
            assert hashlib.sha256(apk.read("assets/SpatialML/face-landmarker/model/"+name)).hexdigest() == entry["sha256"]
    print("PASS: APK model hashes match and platform API stubs are excluded")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path)
    args = parser.parse_args()
    check_assets()
    check_bindings()
    check_coordinates()
    if args.apk: check_apk(args.apk)


if __name__ == "__main__": main()
