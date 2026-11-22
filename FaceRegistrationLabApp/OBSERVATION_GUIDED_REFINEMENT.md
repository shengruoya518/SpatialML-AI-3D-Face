# Refinement from the latest wearer observations

The wearer reports that C remains close across view quadrants, but the mesh is slightly high, small and inside the physical face. The later clarification supersedes the initial apparent right/left difference: **the small/inward residual is similar in both turning directions**. There is no longer evidence here for a one-sided horizontal correction.

A read-only desktop status check during this discussion confirmed C values in both requested and applied state (fx/fy 1746.471313, cx 1623.5, cy 1231.5), revision 378, frame 4904, with a measured face. This establishes the baseline for the observations; it does not measure the actual registration error.

## First experiment: coupled focal reduction

A reconstructed face that is too distant can appear both small and inside the real face. In the shipped monocular canonical-face reconstruction, reducing fx and fy together largely retains metric face dimensions while reducing inferred distance. This is the first hypothesis to test after the symmetry clarification. It does not independently prove an error in physical camera intrinsics.

| Parameter | C | First trial |
|---|---:|---:|
| fx | 1746.471313 | 1711.54 |
| fy | 1746.471313 | 1711.54 |
| cx | 1623.5 | 1623.5 |
| cy | 1231.5 | 1231.5 |

The trial reduces both focal lengths by 2%. Approximately, this moves the estimate 2 cm closer at 1 m or 4 cm closer at 2 m, increasing apparent linear size by about 2% under a fixed eye view. Keep fx/fy linked numerically for this experiment; there is no reported horizontal-versus-vertical size mismatch requiring a changed aspect ratio. Keep cx unchanged because the correction removes the reported directional asymmetry.

A new float32 host replay of the earlier D far-frontal capture, holding landmarks and image affine fixed, changed median depth from 1.899714 m under C to 1.861401 m under this trial: **38.313 mm closer**. Camera-space width changed from 143.008 to 143.081 mm and height from 190.456 to 190.431 mm. Thus this control mainly changes distance in that capture. This is a counterfactual on an older capture, not a physical measurement of the current wearer observation.

Compare frontal and both turned poses after the focal change settles. If the inward/small residual improves but remains, a 3% reduction is fx=fy=1694.08. If surface depth becomes correct while the outline remains too small, stop using focal reduction to enlarge it: that would suggest a separate face-shape/scale issue requiring a scale about a face anchor at fixed depth. The existing optical-center sizeScale scales distance too and cannot supply that independent adjustment.

## Second experiment: height

After choosing the focal pair, lower cy while leaving cx and the chosen focal values unchanged. Start with cy=1211.5 (20 pixels below C). The approximate camera-space shift is:

`deltaY = depth / fy × deltaCy`

At C focal length this is about 11.45 mm downward per metre of distance. In the older 1.9 m replay it lowered the face center by 21.821 mm and changed median depth by only 1.176 mm. A 35-pixel decrease, cy=1196.5, is about 20.04 mm downward per metre; the replay center moved down 38.169 mm. Focal selection should precede this height adjustment because changing distance can also change apparent vertical placement.

At different distances, a principal-point correction produces approximately constant angular shift, whereas a physical camera/head translation produces a nearly constant metric shift. Near/far comparison can help distinguish them; a single qualitative view cannot.

Use eye corners, nose, lips and chin for comparisons. The landmark mesh does not include the entire head, hair or ears. Recheck off-center quadrants after the focal trial because focal changes also change off-axis rays.

The exact best values remain unmeasured. No parameters were changed or saved during this analysis. Numerical evidence and the shipped-operator replay are in `artifacts/facelandmarker/registration-lab/observation-refinement/`.
