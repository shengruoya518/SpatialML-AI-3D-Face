# Headset capture and timeout repair

The user requested two headset start controls and a capture flow without PC connection prompts, after run `3ae2cc9f` timed out. This is a bounded change to the existing Full Space Mixed Stage attachment, using the current 740×420 dp panel. It does not change the container, camera projection, candidate values or normal face-sample UI.

## Confirmed timeout cause

The retrieved session `2026-10-30T18-28-13.921371Z-a05649` timed out in SETTLE after 60.028 seconds, with zero exports. There were 137 completed frames in that interval, including 134 face-bearing frames; every face-bearing frame was rejected as not being on a new exposure.

The new guard had remembered a wall-clock fallback from frame 77: capture `1793384960.7078192` versus monotonic readback `3578.845314571`. That no-face, nonfresh frame advanced the guard's high-water mark. Subsequent valid sensor-clock exposures around 3800 seconds could never exceed it. Five fallback timestamps appear in the session. The existing stream liveness gate already excluded out-of-domain timestamps, but the newly added presentation guard did not.

The repair admits only capture timestamps within −0.1…2.0 seconds of monotonic readback into the guard's history. Invalid/fallback/NaN clocks are rejected without advancing that history. Legitimate no-face exposures are still remembered so a false-to-true face flag on the same exposure remains rejected. Replaying the failed journal's timestamp/freshness fields yields 107 advancing face candidates during SETTLE. This replay covers clocks only: the failed build did not record raw rejected geometry or head-motion measurements, so it cannot establish a new export time or full frame eligibility.

Evidence: `artifacts/facelandmarker/registration-lab/automatic-timeout-2026-10-30/`, including the retrieved journal, status, app logs and `timeout-analysis.json`. Headset files and recording are retained.

## Practical capture windows

The wearer reported that keeping both heads completely still was too difficult. The controller now requires three usable exposures over at least 0.8 seconds. It measures selected-marker steps between consecutive usable frames, with the existing 12 mm step limit, rather than accumulating all drift against the first frame. Larger steps or an unstable exposure restart that brief window. Small natural drift can continue during a phase.

HMD motion gating now uses the same ±50 ms camera-exposure window as the saved sample acceptance, with the existing history coverage, 1 cm and 1 degree limits. The former two-second HMD immobility window is removed. The independent save-time exposure check remains in force, along with the 0.9-second export freshness limit, distinct marker geometry, effective K/revision, native snapshot equality and exact scene/frame acknowledgement. Clean and marked scene dwell times remain two and three seconds; each phase retains its 60-second timeout.

Every `pipeline_frame` row now includes exposure motion coverage, metres, degrees and stability, in addition to clocks/freshness/rejection. This makes any next timeout attributable to a measured gate rather than a generic stillness message. Natural-motion host checks cover a slow head path that fails the old long hold but passes the exposure window, a sudden 2 cm step that remains rejected, and consecutive 10 mm marker drifts that permit capture.

## Headset UI and state contract

The timing/status panel adds two equal-width native `com.pico.spatial.ui.design.Button` controls in one row: **One check** and **Full trial**. Both invoke the same synchronized `FaceRegistrationLab.startAutomatic(single)` method as the existing commands. The first runs C once with three exports; the second runs seven candidates at four poses, with at most 84 exports. Both retain the 15-second countdown.

Controls disable during active capture, export locks, stopped camera, failed journal logging, unsupported ROM or insufficient session export capacity. Repeated starts remain rejected by the controller. Click errors and retry hints appear in the readable timing/status badge. If the camera stops, the hint asks the wearer to reopen the app. Ready, timed-out and completed states contain no PC/USB connection request. Completion asks the wearer to stop recording and says evidence is saved on the headset.

The enclosing `PicoTheme`, Stage attachment and bounded OCR background remain. Native Button slots inherit their component-owned colors and interaction/hover/haptic behavior. No custom design color, extra root background, material, border, icon or window is added. The patch uses the existing panel and state owner; the inherited generic architecture scanner limitations documented in VALIDATION.md are not declared fixed. Style verification must pass; headset layout and physical button input require separate device evidence.

## Wearer flow

1. Open SpatialML Face Calibration and put a face in view.
2. Start the headset system recorder in Spatial mode.
3. Press One check. Stay relaxed, with the face in view, through the countdown and clear/marked/clear phases.
4. At Capture complete, stop recording. The recording, exports and journal remain on the headset.
5. If it times out, stop that recording and use One check again after the next recorded issue is resolved. Closing/reopening the app restarts a stopped camera.

Full trial is available from the headset. The updated one-check recording must still be inspected before treating full-sweep data as accepted calibration evidence. This update makes capture controls and storage device-only; automatic fitting/application of a corrected calibration from recorded stereo footage is not implemented on the headset. Existing optional desktop diagnostics and retrieval remain available when requested.


## Final installed boundary

Installed APK SHA-256: `68ac56e426c560d8a944d159139bb695e3c0b6ce93dec8c904a7dcf7c3b41a0e` on PB311XHGKC220141G. Installed hash matches; PID 10968 supplied advancing frames 7/15/22 with effective C values. All 146 existing external app files and the private camera calibration were preserved; lease released. Both headset buttons, ready instructions and the natural-motion hint are visible without clipping in both captured views. Host regressions, final build/lint/format and style checks pass. Actual wearer tap and real-face clean/marked/clean exports remain the next acceptance step. Evidence: `automatic-timeout-2026-10-30/install/headset-ui-verification.json` and the installation manifest under the same artifact directory.
