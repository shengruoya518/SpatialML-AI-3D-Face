"""Known-camera board diagnostics including production marker atlas and failure boundaries."""
import argparse
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

import board_registration as board
import binocular_geometry as stereo
from validate_binocular_geometry import camera, render, rejected


def matrix(rotation, translation):
    value = np.eye(4)
    value[:3, :3] = Rotation.from_rotvec(rotation).as_matrix()
    value[:3, 3] = translation
    return value


def paint_board(image, projection, transform, spacing):
    canvas = image.copy()
    # One-square white margin around the full 9x7 pattern; inner origin is (0,0).
    for row in range(-2, 8):
        for col in range(-2, 10):
            points = np.array([[col,row,0], [col+1,row,0], [col+1,row+1,0], [col,row+1,0]], dtype=float)
            points[:, :2] *= spacing
            uv = stereo.apply(projection, stereo.apply(transform, points))
            color = 0 if -1 <= row < 6 and -1 <= col < 8 and (row+col)%2 == 0 else 255
            cv2.fillConvexPoly(canvas, np.rint(uv*16).astype(int), (color,)*3, cv2.LINE_AA, shift=4)
    return canvas


def validate(production, output):
    output.mkdir(parents=True, exist_ok=True)
    board_spec = dict(innerCorners=[8,6], fiveSquareHorizontalMm=100., fiveSquareVerticalMm=100.,
                      boardId='synthetic-20mm', orientationLabel='known synthetic origin')
    board.write_json(output/'board.json', board_spec)
    target = board.read_board(output/'board.json')
    xyz = board.object_points(target)
    k = np.array([[1150.,0,812.], [0,1040.,616.], [0,0,1.]])
    source_camera = k @ np.eye(4)[:3]
    optical = matrix([.01,-.02,.005], [-.035,.043,-.052])
    h = matrix([.15,-.25,.1], [1.,1.5,-.3])
    eyes = [camera(-.032), camera(.032,.003)]
    trials = []
    for depth in (.6,1.2,2.0):
        for roll in (-.26, 0, .26):
            head = matrix([.1,-.15,roll], [1,2,3])
            pose = matrix([.25,-.2,.08], [-.07,-.05,depth])
            uv = stereo.apply(source_camera, stereo.apply(pose,xyz))
            recovered = board.pose_candidates(uv,xyz,k,np.zeros(5))[0]['matrix']
            np.testing.assert_allclose(stereo.apply(recovered,xyz), stereo.apply(pose,xyz), atol=1e-8)
            observed = [stereo.apply(p,stereo.apply(optical@board.CV_TO_CAMERA@pose,xyz)) for p in eyes]
            _, _, errors = board.compare(xyz,recovered,head,optical,eyes,observed)
            assert max(e['rmsPixels'] for e in errors) < 1e-7
            wrong = optical.copy(); wrong[1,3] -= .04
            _, _, bad = board.compare(xyz,recovered,head,wrong,eyes,observed)
            assert min(e['rmsPixels'] for e in bad) > 20
            units = optical.copy(); units[:3,3] *= 100
            _, _, bad_units = board.compare(xyz,recovered,head,units,eyes,observed)
            assert max(e['rmsPixels'] for e in bad_units) > 100
            trials.append(dict(depth=depth,roll=roll,correctRms=errors[0]['rmsPixels'],down40Rms=bad[0]['rmsPixels']))
    refs = json.loads((production/'roll-projection-reference.json').read_text())
    atlas = cv2.imread(str(production/'projection-atlas.ppm'))
    pose = matrix([.25,-.2,.05],[-.07,-.05,1.2])
    source = paint_board(np.full((1232,1624,3),110,np.uint8),source_camera,pose,target['spacingMetresXY'])
    source_path = output/'source.ppm'; cv2.imwrite(str(source_path),source)
    physical = optical@board.CV_TO_CAMERA@pose
    images = [paint_board(render(refs,atlas,p),p,physical,target['spacingMetresXY']) for p in eyes]
    pair_path = output/'pair'; pair_path.mkdir(exist_ok=True)
    for i,image in enumerate(images): cv2.imwrite(str(pair_path/f'eye{i}.png'),image)
    board.write_json(pair_path/'pair.json', dict(viewIds=[0,1],pts=123,timeBase='1/30',synthetic=True,
        eyeSha256=[board.digest(pair_path/f'eye{i}.png') for i in (0,1)]))
    anchors = lambda uv: dict(origin=uv[0].tolist(),rowEnd=uv[7].tolist())
    identity = dict(source=anchors(stereo.apply(source_camera,stereo.apply(pose,xyz))),
        **{f'eye{i}':anchors(stereo.apply(p,stereo.apply(physical,xyz))) for i,p in enumerate(eyes)}, group='middle-level')
    board.write_json(output/'identity.json',identity)
    # Crop coordinates must be restored before physical identity and eye projection.
    # Use a translated image to catch accidental local-coordinate reporting.
    padded = cv2.copyMakeBorder(source, 37, 19, 83, 41, cv2.BORDER_CONSTANT, value=(110,)*3)
    shifted_identity = {key: (np.asarray(value)+[83,37]).tolist() for key,value in identity['source'].items()}
    cropped_points = board.detect(padded, shifted_identity, [83,37,83+1624,37+1232])
    np.testing.assert_allclose(cropped_points, board.detect(source,identity['source'])+[83,37], atol=1e-8)
    for roi in ([-1,0,10,10], [0,0,1625,1232], [10,10,10,20], [0,0,1.5,2], [0,0,float('nan'),2], [0,0,2]):
        rejected(lambda:board.detect(source,roi=roi))
    tag = dict(run='board-fixture',trial=1,pose=0,epoch=4,phase='MARKED',captureSequence=board.KINDS[0],poseLabel='middle-level')
    sample = dict(sequence=refs['sequence'],captureSeconds=100.,monotonicSecondsAtReadback=100.2,
        automatic=tag,poseCorrection=dict(id='current',enabled=False,cameraRayScale=1),sizeScale=1,
        headStableAtExposure=True,exposureHistoryCovered=True,mode=0,captureFrame=[100,0,.03,1,0,0],
        imageTransform=np.eye(3).ravel().tolist(),cameraToHead=optical.ravel().tolist(),
        headToStageAtCapture=h.ravel().tolist(),sourceStream=dict(fixture='known-pinhole'),fingerprint='synthetic',sourceWidth=1624,sourceHeight=1232,session='synthetic')
    board.write_json(output/'sample.json',sample)
    event = copy.deepcopy(refs)
    event.update(frame=sample['sequence'],captureSeconds=100.,uploadSeconds=100.25,automatic=tag,
        ownerRoundTripMaxMetres=1e-7,rigToStage=h.ravel().tolist(),cameraToHead=optical.ravel().tolist(),headToStageAtUpload=h.ravel().tolist())
    for marker in event['markers']:
        marker['stageCorners']=stereo.apply(h,np.array(marker['rigCorners']).reshape(4,3)).ravel().tolist()
    timeline=output/'timeline.jsonl'
    timeline.write_text(json.dumps(dict(event='projection_reference',details=event))+'\n')
    board.write_json(output/'camera.json',dict(coordinateSpace='saved-source-pixels',imageSize=[1624,1232],
        fingerprint='synthetic',sourceStream=sample['sourceStream'],board=target,cameraMatrix=k.tolist(),distortion=[0]*5,gatePassed=True,synthetic=True))
    args=SimpleNamespace(output=output/'observation',sample=output/'sample.json',board=output/'board.json',
        pair=pair_path,timeline=timeline,identity=output/'identity.json',camera=output/'camera.json')
    board.observe(args)
    result=json.loads((args.output/'observation.json').read_text())
    assert result['withinDiagnosticTarget'], result['eyes']
    for field,value in [('frame',-1),('captureSeconds',99.),('uploadSeconds',99.),('referenceLayout','original-v1'),('ownerRoundTripMaxMetres',.001)]:
        bad=copy.deepcopy(event);bad[field]=value
        rejected(lambda:board.reference_contract(sample,bad))
    bad=copy.deepcopy(event);bad['headToStageAtUpload'][3]+=.01
    rejected(lambda:board.reference_contract(sample,bad))
    for key,value in [('mode',4),('headStableAtExposure',False),('captureSeconds',1.)]:
        bad=copy.deepcopy(sample);bad[key]=value
        rejected(lambda:board.source_contract(bad))
    bad=copy.deepcopy(sample);bad['poseCorrection']['enabled']=True
    rejected(lambda:board.source_contract(bad))
    rejected(lambda:board.detect(np.zeros_like(source)))
    rejected(lambda:board.detect(source,dict(origin=[0,0],rowEnd=[1,1])))
    reflected=h.copy();reflected[:,0]*=-1
    rejected(lambda:board.rigid(reflected,'reflected'))
    # Unit/axis mistakes have large residuals even though source reprojection remains good.
    observed=[stereo.apply(p,stereo.apply(physical,xyz)) for p in eyes]
    _,_,axes=board.compare(xyz,pose,h,optical@board.CV_TO_CAMERA,eyes,observed)
    assert max(e['rmsPixels'] for e in axes)>50
    # Same-PTS provenance is mandatory; an altered eye image must fail before fitting.
    altered=images[0].copy();altered[0,0]=0;cv2.imwrite(str(pair_path/'eye0.png'),altered)
    rejected(lambda:board.observe(args))
    cv2.imwrite(str(pair_path/'eye0.png'),images[0])
    board.pilot(SimpleNamespace(sample=args.sample,timeline=timeline,pair=pair_path,output=output/'pilot'))
    # A real detector/calibrator round trip on sixteen separately rendered views.
    cal_session=output/'source-views';cal_session.mkdir(exist_ok=True)
    rng=np.random.default_rng(42)
    for i in range(16):
        child=cal_session/f'{i:02d}';child.mkdir(exist_ok=True)
        rotation=[-.4+.16*(i%5),-.35+.18*(i%4),-.12+.06*(i%5)]
        translation=[-.25+.10*(i%5),-.20+.09*(i%4),.75+.15*(i%5)]
        view=matrix(rotation,translation)
        im=paint_board(np.full_like(source,110),source_camera,view,target['spacingMetresXY'])
        cv2.imwrite(str(child/'source.ppm'),im)
        record=copy.deepcopy(sample)
        record['automatic'].update(captureSequence=board.KINDS[1],pose=i,board=dict(split='fit' if i<12 else 'validation'))
        record['captureSeconds']=100.+i;record['monotonicSecondsAtReadback']=100.2+i
        board.write_json(child/'sample.json',record)
    board.calibration(SimpleNamespace(session=cal_session,board=output/'board.json',output=output/'calibration',model='pinhole'))
    fitted=json.loads((output/'calibration/camera-profile.json').read_text())
    assert fitted['gatePassed']
    np.testing.assert_allclose(np.diag(fitted['cameraMatrix'])[:2],np.diag(k)[:2],rtol=.025)
    # Slight image noise near frontal makes the two planar solutions indistinguishable.
    frontal=matrix([0,0,0],[-.07,-.05,1.2])
    noisy=stereo.apply(source_camera,stereo.apply(frontal,xyz))+rng.normal(0,.08,(48,2))
    rejected(lambda:board.pose_candidates(noisy,xyz,k,np.zeros(5)))
    obs_path=args.output/'observation.json'
    rejected(lambda:board.summarize(SimpleNamespace(observations=[obs_path,obs_path],held_out=['middle-level'],output=output/'duplicate.json')))
    board.write_json(output/'validation.json',dict(status='PASS',exactPoses=trials,
        roiFullImageCoordinates='PASS', roiInvalidBoundsRejected=True,
        rasterizedBoardEyes=[e['rmsPixels'] for e in result['eyes']],
        boundary='Synthetic cameras and production marker atlas; no device or physical acceptance'))
    print('PASS: exact poses, head gauge, unit/axis/offset faults, rasterized board+references, identity, timestamp, motion and hash rejection')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();validate(args.production,args.output)
