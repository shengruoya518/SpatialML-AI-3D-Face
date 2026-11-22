# Optional desktop calibration controls

Headset capture now starts with **One check** or **Full trial** in the app and runs without USB; see [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md). For optional numeric adjustment and diagnostics, open **http://127.0.0.1:47835** on this machine. The local server is running; refresh an already-open page to load the automatic controls. The approved freshness/marker/candidate update is installed on PB311XHGKC220141G with advancing startup camera frames and effective C values verified. The repeated one-sample check is next; see the latest [VALIDATION.md](VALIDATION.md) entry. Earlier live desktop status, start/cancel and restored-value readback results are retained below.

Keep USB connected and **SpatialML Face Calibration** open in the headset. The browser reads the current headset values on connection; opening the page does not reset or save them.

The new headset build adds pose/capture instructions to the [timing badge](TIMELINE_RECORDING.md); manual headset controls remain removed. Its matching timeline journal is saved automatically even with USB disconnected. The desktop and adb commands remain the control surface.

## Automatic capture

Follow [AUTOMATIC_CAPTURE_STEPS.md](AUTOMATIC_CAPTURE_STEPS.md), beginning with **Capture one check sample** after installation. Use the full sequence after that sample is inspected. Start the headset recorder in Spatial mode before pressing the button. Capture then runs on the headset without USB. Numeric edits and profile saving are disabled during the sequence; **Cancel sequence** remains available during export. Completion or cancellation restores starting working values without overwriting the saved profile. Older app versions disable automatic buttons and show an installation message.

## Adjust while watching the headset

1. Wait for **Headset connected**. Put a face in view so you can compare its mesh with passthrough.
2. Edit **fx**, **fy**, **cx** or **cy** with the mouse and keyboard. Type a number, drag its slider, or use its **− / +** buttons. Changes are sent automatically after a short pause in input. Enter finishes numeric input and sends pending edits.
3. The **Button & keyboard step** selector offers 0.5, 1, 5, 10 and 25 px. In a number field, Up/Down uses that step; Shift + Up/Down uses ten times the step. Sliders make coarse changes.
4. Check the readbacks under each control: **Headset** is the value accepted by the app; **Frame used** is the effective value read back from the latest processed camera frame. The top status confirms when the current values have reached the pipeline. This can take an adb exchange plus a frame; it is not a display-latency measurement.
5. Press **Save on headset** when you want to retain the current four values. Pending edits are sent first. Wait for **Calibration saved on this headset.** **Load saved** restores the last saved profile; **Reset to C** resets working values without overwriting the saved profile.

For the earlier small/high residual, the controlled adjustment directions are in [CALIBRATION_TUNING_STEPS.md](CALIBRATION_TUNING_STEPS.md). All inputs remain effective virtual-image pixels with the fixed C image transform. No physical correction constants have been accepted automatically.

The lower status panel shows whether a face was measured, the most recent frame, and any camera/profile status. Values can be saved with no face present. If the camera is stopped, edits are disabled and the reason is shown; saving the current values remains available. A fresh numeric readback does not by itself prove correct physical mesh overlap.

## Reconnect or restart

If USB is disconnected or another device session is busy, the page disables editing and reports the problem. It retries reading state; failed edits are not queued for later replay. After reconnection it reads the current headset values again. Keep one active editing page to avoid competing edits.

After saving, you may unplug USB and use the headset's saved calibration offline. The browser controls require the adb connection.

The server can be started again from the project root:

```sh
python3 FaceRegistrationLabApp/tools/calibration_desktop.py --open
```

Python 3 and the existing devmux/adb installation are sufficient; no web framework or Node installation is needed to run it. In a terminal, Ctrl+C stops the server. If port 47835 is already in use by this server, use the existing page. To run on another port, add `--port 47836`; the startup message gives the URL. The current agent-started background server's PID is recorded in `artifacts/facelandmarker/registration-lab/desktop-validation/server.pid`.

Saved profiles and camera samples remain in the app's existing storage. Retrieval commands are described in [CALIBRATION_TUNING_STEPS.md](CALIBRATION_TUNING_STEPS.md#retrieve-later).

## Implementation and validation

`tools/calibration_desktop.py` serves `tools/desktop/index.html` on loopback only. It accepts a fixed command set, validates numeric ranges, checks the page origin/token, and runs pinned devmux commands without shell interpolation. Each adb transaction uses its own short lease; a browser session does not reserve the headset continuously. It never automatically launches or restarts the app.

The app's existing Android-DUMP-protected receiver now returns a versioned base64 JSON result for ordered broadcasts. It reports requested values and revision separately from effective intrinsics, applied revision, frame age and face state. Invalid or locked commands return an explicit rejection. The existing frame-boundary updates, Stage rendering and profile persistence are retained.

Validation covers the actual Kotlin receiver/state/codec, HTTP input and origin guards, a real Chrome browser against a deterministic fake headset, and a live HTTP → devmux/adb → app → native-frame readback. The live probe changed fx from 1746.471313 to 1745.971313, observed it in frame 501, and restored 1746.471313. It did not save the test change. Browser tests cover number entry, keyboard steps, sliders, pending edits before Save, device-side value changes and disconnect/reconnect. Full evidence and remaining limits are in [VALIDATION.md](VALIDATION.md).
