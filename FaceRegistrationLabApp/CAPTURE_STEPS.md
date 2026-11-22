# Headset capture steps

For the updated measured-camera trial, use the shorter [A/D follow-up](TRIAL_CAPTURE_STEPS.md). This file describes the original full A/B/C capture plan; the current app also has D.

You can do the complete experiment with USB disconnected. The lab is already installed as **SpatialML Face Registration Lab**. Samples are saved on the headset; the development machine is needed only to install an updated app, retrieve the data, or run analysis.

## Before starting

1. Close the normal **SpatialML Face Landmarker** sample. Open **SpatialML Face Registration Lab** and allow Camera if asked.
2. Wait for **Ready** and advancing frame numbers. Start with **A: Service**, **Face front - 1 m**, and **Wireframe**. Size/depth is fixed at 1×.
3. Use one live person. Close or turn away any monitor showing a face photograph so detection stays on the person.
4. Start the headset's built-in screen recording. Include the real face, mesh and controls panel in the recording when possible.

The lab's on-screen buttons are **Next mode**, **Next step**, **Save sample**, **Wireframe / Solid / Hidden**, and **Show left camera / Show model crop**. Use those buttons with your normal headset pointing/selecting input. Unity's A/B/X/Y controller shortcuts are not used in this Kotlin lab.

## First pass: twelve face samples

For each row, keep the headset in the same position and save one sample in A, one in B, and one in C. Distances are approximate; measure them if convenient.

| Step shown in the lab | What the person does |
|---|---|
| Face front - 1 m | Face you from about 1 m away |
| Face looks left - 1 m | Turn their face about 30° toward your left, keeping their position fixed |
| Face looks right - 1 m | Turn their face about 30° toward your right, keeping their position fixed |
| Face front - 2 m | Face you from about 2 m away |

For each row:

1. Check that the step label matches the person's pose and the mode is **A: Service**.
2. Wait until landmarks and mesh are visible. Keep both headset and person still for two seconds.
3. Select **Save sample**. It waits one second; stay still until **Image captured** appears, then wait for **Saved NNN** before the next action.
4. Select **Next mode** once for **B: Aspect only**. Wait for Ready, settle, and save again.
5. Select **Next mode** once for **C: Renderer trial**. Wait for Ready, settle, and save again.
6. Select **Next mode** twice, through D, to return to A, then **Next step** for the next row.

If the status says **Head moved at exposure** or **Exposure history incomplete**, repeat that mode/pose sample. If it says **Save failed: No measured face**, wait for recovery and save again. Each successful face sample needs an actual detected face; a picture on a monitor is useful for a pipeline check but does not measure a real face's depth.

For at least one clearly offset frontal face, keep everyone stationary and cycle **Wireframe → Solid → Hidden → Wireframe** in the recording. Compare the nose, eye line, chin and cheeks. Then check the overlay with only your left eye open, and only your right eye open, keeping your head still. Say the mode and what you see aloud so the observation is in the recording, or write it down. The app does not automatically know which eye is open.

The first pass is 12 samples, plus any repeats. The camera/model preview refreshes less often than the mesh; the preview's frame number is shown. Saved data is matched within a sample, but a preview visible in a recording may be older than the live mesh.

## Second pass: sixteen checkerboard views

This is the independent camera measurement. It needs the [A4 checkerboard PDF](calibration/checkerboard-A4-20mm.pdf).

1. Print at **100% / Actual Size**, with Fit to Page disabled. Measure the printed ruler: it must be exactly 100 mm. Each square must be 20 mm; the board extent is 180×140 mm.
2. Mount the sheet flat on a rigid stationary surface near head height. Leave the board fixed for the whole set.
3. In the lab, choose **A: Service**, **Checkerboard calibration**, and **Show left camera**. No face is needed for this step.
4. Take the sixteen views below. Move the headset between views, then stop for two seconds, select Save, and remain still until Saved. Keep the entire checkerboard visible with a margin around it.

| Four views | Headset position |
|---|---|
| Frontal | Different distances, approximately 0.35–0.65 m |
| Across the image | Board toward left, right, upper and lower regions of the camera image |
| Yaw | About 15° and 25° to either side of the board |
| Pitch | About 15° and 25° above and below the board |

Vary position and tilt; avoid sixteen nearly identical centered views. At least 12 stable views with all corners detected are needed, and 16 are recommended. If the board moves or you recenter tracking, restart the lab and take a new complete board set. Do not combine board views across different app sessions.

## Finish and reconnect later

1. Stop the headset screen recording so the video is finalized.
2. Leave the saved lab data on the headset. You can disconnect USB throughout capture and reconnect later. Closing/restarting the lab preserves old samples and creates a new session for future captures.
3. Do not uninstall the lab, clear its app data, or delete its capture directory before retrieval. It holds up to 100 saved samples per session; restart for another session if needed.
4. Reconnect USB and tell me the recordings and lab captures are ready. I can pull and analyze them.

The lab stores samples under:

```text
/sdcard/Android/data/com.pico.spatial.ml.sample.facelandmarker.registrationlab/files/RegistrationLab/<session>/
```

Each completed sample has three camera/model images and `sample.json`. Directories ending in `.pending` are incomplete and should not be counted. Samples and headset system recordings are separate files; preserve both.

From the project root, data retrieval is:

```sh
bash FaceRegistrationLabApp/tools/registration_lab_device.sh pull
bash FaceRegistrationLabApp/tools/registration_lab_device.sh logs
```

The pull helper retrieves every stored lab session. The headset's system recordings are retrieved separately. For checkerboard analysis, select the single session containing the stationary-board set; instructions are in [README.md](README.md).

The lab collects evidence for a correction. It does not automatically calibrate or change the mesh's world position. The most useful return is the twelve live-face comparisons, one complete checkerboard session, and the accompanying system recording.
