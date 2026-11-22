"""Check the shipped reconstruction and raw-pose publication. Requires NumPy and Node.js."""

import json
import math
import subprocess
import sys

import numpy as np

sys.dont_write_bytecode = True
from validate_port import ASSETS, MODULE, matrix, run_operator


def main():
    geometry = json.loads((ASSETS / "data/face_geometry.json").read_text())
    canonical = np.array(geometry["canonical"], dtype=np.float32).reshape(468, 4)
    fit_indices = np.flatnonzero(canonical[:, 3] > 0)
    sparse = canonical[fit_indices]
    full = np.vstack((canonical, np.zeros((10, 4), dtype=np.float32)))
    width, height = 3248, 2464
    fx, fy, cx, cy = 2290., 2125., 1593., 1196.
    intrinsics = [fx, 0, cx, 0, fy, cy, 0, 0, 1]
    settings = [width, height, .25, .5, 1, .35, .45, .1, .25, 0, .75]
    process = subprocess.Popen(
        ["node", str(MODULE / "tools/run_operator.mjs")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )

    def op(name, **tensors):
        inputs = {k: np.asarray(v).reshape(-1).tolist() for k, v in tensors.items()}
        result = run_operator(process, ASSETS / "operators" / (name + ".js"), inputs)
        return {k: np.asarray(v, dtype=np.float32) for k, v in result.items()}

    def solve(source, targets):
        prepared = op("geometry_covariance", canonical=source, targets=targets,
                      covariance=np.zeros(9), centers=np.zeros(6))
        u, _, vt = np.linalg.svd(prepared["covariance"].reshape(3, 3))
        return op("geometry_solve", canonical=source, targets=targets,
                  centers=prepared["centers"], u=u, vt=vt, pose=np.zeros(16), scale=[0])

    def pixels(points):
        return np.column_stack((cx + fx * points[:, 0] / -points[:, 2],
                                cy - fy * points[:, 1] / -points[:, 2]))

    state = np.zeros(24)
    probe_state = np.zeros(24)
    errors = {"raw_reprojection_px": 0., "filtered_reprojection_px": 0.,
              "sparse_full_pose_difference": 0., "minimum_camera_relief_m": math.inf}
    try:
        for frame in range(40):
            # Independent nonplanar source face: translate, rotate and change scale smoothly.
            expected_pose = np.array(matrix(.45 * math.sin(frame * .17), .15 * math.sin(frame * .13),
                                            1 + .15 * math.sin(frame * .1),
                                            [5 * math.sin(frame * .2), -3, -70])).reshape(4, 4)
            source = full[:, :3] @ expected_pose[:3, :3].T + expected_pose[:3, 3]
            measured = pixels(source)
            depth = -source[:, 2]
            mean_depth = depth[:468].mean()
            landmarks = np.column_stack((measured[:, 0] / width, measured[:, 1] / height,
                                         (depth - mean_depth) / mean_depth * fx / width))
            projected = op("geometry_project", landmarks=landmarks, intrinsics=intrinsics,
                           settings=settings, canonical=full, validity=[1, 1],
                           projected=np.zeros(1434), targets=np.zeros(1434), depthOffset=[0])
            first = solve(sparse, projected["targets"].reshape(478, 3)[fit_indices])
            common = dict(projected=projected["projected"].reshape(478, 3)[fit_indices],
                          depthOffset=projected["depthOffset"], firstScale=first["scale"],
                          canonical=sparse, validity=[1, 1], targets=np.zeros((len(sparse), 3)))
            intermediate = op("geometry_unproject", secondScale=[1], **common)
            second = solve(sparse, intermediate["targets"])
            metric = op("geometry_unproject", projected=projected["projected"],
                        depthOffset=projected["depthOffset"], firstScale=first["scale"],
                        secondScale=second["scale"], canonical=full, validity=[1, 1],
                        targets=np.zeros(1434))["targets"].reshape(478, 3)
            sparse_fit = solve(sparse, metric[fit_indices])["pose"]
            full_fit = solve(full, metric)["pose"]
            errors["sparse_full_pose_difference"] = max(errors["sparse_full_pose_difference"],
                                                        float(np.max(np.abs(sparse_fit - full_fit))))
            errors["minimum_camera_relief_m"] = min(errors["minimum_camera_relief_m"],
                                                     float(np.ptp(metric[:468, 2]) * .01))
            camera = np.array(matrix(.06, -.03, 1, [-.026, .043, -.048]), dtype=np.float32).reshape(4, 4)
            tracker = np.zeros(24)
            tracker[11] = 1
            scale = .7 + .6 * frame / 39
            pose_output = op("face_pose", pose=sparse_fit, validity=[1, 1],
                             leftCameraToXr=camera, command=[frame + 1, frame / 30, scale, 1],
                             settings=settings, frame=[10, frame / 30, 1 / 30, 1, 0, 0],
                             trackState=tracker, poseState=state,
                             worldPose=np.zeros(16), rawWorldPose=np.zeros(16), poseStatus=[0])
            state = pose_output["poseState"]
            # Keep size fixed during this drift probe so the pose filter remains active.
            probe = op("face_pose", pose=sparse_fit, validity=[1, 1],
                       leftCameraToXr=camera, command=[frame + 1, frame / 30, 1, 1],
                       settings=settings, frame=[10, frame / 30, 1 / 30, 1, 0, 0],
                       trackState=tracker, poseState=probe_state,
                       worldPose=np.zeros(16), rawWorldPose=np.zeros(16), poseStatus=[0])
            probe_state = probe["poseState"]
            for kind, pose_name in (("raw", "rawWorldPose"), ("filtered", "worldPose")):
                result = op("pack_service_result", command=[frame + 1, frame / 30, 1, 1],
                            validity=[1, 1], roi=[1, .9, 1624, 1232, 600, 0], landmarks=landmarks,
                            metric=metric, pose=sparse_fit, worldPose=probe[pose_name],
                            blendshapes=np.zeros(52), detectorInfo=[1, .9, 0], diagnostics=np.zeros(32),
                            leftCameraToXr=camera, result=np.zeros(2994))["result"]
                assert result[1] == 1
                service_points = result[1438:2872].reshape(478, 3)
                inverse = np.linalg.inv(camera.astype(np.float64))
                camera_points = service_points @ inverse[:3, :3].T + inverse[:3, 3]
                error = np.linalg.norm(pixels(camera_points) - measured, axis=1).max()
                errors[kind + "_reprojection_px"] = max(errors[kind + "_reprojection_px"], float(error))
            # Physical size scales distance and relief together without changing image rays.
            raw = pose_output["rawWorldPose"].reshape(4, 4)
            raw_camera = np.linalg.inv(camera.astype(np.float64)) @ raw
            metric_pose = sparse_fit.reshape(4, 4).astype(np.float64)
            metric_pose[:3, 3] *= .01
            metric_pose[:3, :] *= scale
            assert np.max(np.abs(raw_camera - metric_pose)) < 2e-5
    finally:
        process.stdin.close()
        process.wait(timeout=10)
    assert errors["raw_reprojection_px"] < .02, errors
    assert errors["filtered_reprojection_px"] > 1, errors
    assert errors["sparse_full_pose_difference"] < 2e-4, errors
    assert errors["minimum_camera_relief_m"] > .02, errors
    print(json.dumps(errors, indent=2))
    print("PASS: float32 reconstruction, nonplanar relief, weighted sparse/full fit parity, optical size scaling, and 40-frame raw-pose reprojection")


if __name__ == "__main__":
    main()
