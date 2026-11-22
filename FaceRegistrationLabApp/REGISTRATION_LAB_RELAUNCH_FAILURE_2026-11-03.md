# Registration lab relaunch failure — 2026-11-03

The latest lab APK can run after an OpenMR process reset and fail on a subsequent app-only
relaunch. The symptom is no face output and disabled pose, mesh, blendshape, One check and Full
trial controls. The current runner marks backend errors fatal; `stopped=true` then contributes to
the shared control lock.

## Device evidence

The affected APK is the compact-VST/fused-control build from `97a24dd`, SHA-256
`49037fedc23cf903375dbe093080cde24a46e0786b12df73d86c7289b82d2bec`, on Swan
`PB311XHGKC220141G`. The Spatial service is the original APK, SHA-256
`d7a9bdaca7d82b390ba5704a85170f4eaf1ee580fdbc85604cb94388fc94b61b`.

- Original reported failure: app PID `18230`, service PID `16966`, frame `0`, no readback,
  `locked=true`, `stopped=true`. The error is `SSMR backend exception: SecureMR encounters
  internal exception`.
- The saved log contains input-buffer allocation failures for clients `16990`, `18230`, then
  the controlled reproduction client `20043`, all in service PID `16966`.
- For client `20043`, the first compact detector preprocessing model delegates 3/3 nodes to
  `LITERT_CL`. OpenCL graph initialization starts, then the service reports
  `LiteRt create input buffer failed` and rejects `createModelOperator` with error code `256`.
- Stopping both face apps and both OpenMR packages, then launching the same APK, produces app
  PID `20249` and new Spatial service PID `20425`. Frames `16`, `55`, `96` advance successfully.
- Debugging was disabled and read back as `0`. Normal-permission frames `109`, `157`, `204`
  advance; a later status reaches frame `1093`, readback 6,332 bytes, `locked=false`,
  `stopped=false`, and **Ready for One check or Full trial**.

No face was available during these observations. They verify initialization, sustained camera
streaming and unlocked controls; face detection and calibration-export acceptance remain a
separate wearer check.

The comparison establishes failure associated with service reuse and recovery under a new service
process. It does not identify the exact LiteRT GPU cache, environment or teardown defect. Earlier
service analysis points to accelerator/environment reuse and delayed resource destruction, but
the current capture does not log the failing LiteRT status or buffer requirements.

Evidence: `artifacts/facelandmarker/registrationlab-disabled-20261103-1623/current-state.json`,
and `artifacts/facelandmarker/registrationlab-relaunch-diagnostic-20261103-1625/` containing
`diagnostic.json`, `full-logcat.txt` and `later-status.json`.

## Recovery

From the repository root, with recording and calibration stopped:

```sh
bash FaceRegistrationLabApp/tools/registration_lab_device.sh restart
```

The helper holds a devmux lease, checks for active recording/calibration, stops the two face clients
and the installed OpenMR service processes, then launches the lab. `install` now uses the same
process reset before replacing the app APK. Neither action replaces a service APK, clears data or
deletes saved calibration/evidence.

Leave the recovered app open while recording a One check. Standalone app relaunch remains subject
to this runtime limitation; a permanent service repair requires separate work and validation.
