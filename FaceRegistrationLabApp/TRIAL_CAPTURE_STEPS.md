# Measured camera trial: short follow-up

Current adjustable-intrinsics build: [CALIBRATION_TUNING_STEPS.md](CALIBRATION_TUNING_STEPS.md). It starts from C or saved Custom values; the historical trials below remain evidence, not accepted correction constants.

The first follow-up has been retrieved and analyzed in [TRIAL_RESULTS_2026-10-28.md](TRIAL_RESULTS_2026-10-28.md). The newer 09:42 recording and wearer assessment now favor C over D; see [MODE_C_REFINEMENT_FINDINGS.md](MODE_C_REFINEMENT_FINDINGS.md). The A/D repeat is superseded. Establish successful saving and prepare a C refinement trial before requesting more captures. The rows below preserve the original procedure; the three returned boards already provide independent fixed-candidate validation.

Use this procedure after the updated **SpatialML Face Registration Lab** is installed. It adds **D: Measured trial**, using the camera candidate from your earlier checkerboard captures. The candidate is experimental. This pass compares A with D and saves the intermediate geometry needed to investigate the intermittent native mismatch.

Keep the verified lab session open for this pass. Immediate forced restarts can still disturb the service camera on this ROM. You can unplug USB after installation and launch. Saves stay in the app's local storage. Keep the app installed and leave its data and recordings intact for retrieval.

## Face comparison: six accepted exposures

Before recording, confirm that frame numbers advance and the panel says **Ready**. If it says **Stopped** or a camera error, reconnect the headset for recovery before collecting calibration data. Start one screen recording. Keep **Wireframe** selected. Use **Show left camera** briefly to check that the full face is visible, then choose the model crop if preferred. The lab starts at **A: Service**, **Face front - 1 m**.

Have the person stay in the same place for each A/D pair. Keep your head steady while pressing **Save sample** and during the one-second countdown. Wait until **Image captured. You may move; exporting…** before moving. Wait for **Saved … Exposure accepted** before changing mode or step. If it says **repeat**, redo that same mode/pose. The status shows saved, exposure-accepted and repeat counts.

| Comparison | Step label | Save sequence |
|---|---|---|
| Frontal, about 1 m | Face front - 1 m | Save A; press Next mode three times to D; save D |
| Person turns toward your left, about 1 m | Face looks left - 1 m | From D, Next mode once returns to A; Next step once; save A; Next mode three times; save D |
| Frontal, about 2 m | Face front - 2 m | From D, Next mode once returns to A; Next step twice skips the right-facing step; save A; Next mode three times; save D |

Allow **Ready** and two advancing frames after each mode change. For each saved view, briefly compare the mesh in each eye by closing the other eye, then return to both eyes. Say in the recording whether D shifts the mesh left/right/up/down or changes its apparent depth, and whether the effect differs by eye. You can also send those observations as text afterward.

Aim for **6 new exposure-accepted samples**. If the panel already counts a diagnostic save, note the starting accepted count and increase it by six; that earlier save is outside your recording. You do not need to repeat B/C or the full earlier face sequence. Exposure acceptance checks headset movement and head-history coverage; it does not certify face stillness, mesh correctness or precise physical alignment.

## Checkerboard: four new views

Keep the printed board flat and stationary on the whiteboard. From D, press **Next mode** once for A and **Next step** once from the far-frontal step to **Checkerboard calibration**. Select **Hidden** and **Show left camera**.

Save four views with the complete board visible and readable:

1. A nearer view with the board toward the left side of the source image.
2. A nearer view with the board toward the right side.
3. A higher or lower viewpoint with a noticeable vertical tilt.
4. A farther, roughly frontal view.

Move between views; settle before each save. Use the same **Image captured** and **Exposure accepted** cues. Finish with **10 new exposure-accepted samples** in this session (six face and four board, added to the starting count), then stop the recording.

These four board views test the existing candidate on new images. They are not a complete new calibration set. The analyzer compares fixed measured K against service K per view; a full camera/Stage calibration still requires at least 12 stable board views in one stationary-board session.

Afterward, reconnect the headset and tell me the capture is finished. I will retrieve the local JSON/images and recording, compare A/D, replay the intermediate fit and mesh tensors, and check the camera candidate against the new board views.
