import sys
sys.dont_write_bytecode = True
from pathlib import Path
import registration_lab as lab
import json
import cv2
import numpy as np
import argparse
parser=argparse.ArgumentParser(description='Synthetic rendered checkerboards validate detection, camera fit and Stage repeatability; no headset calibration.')
parser.add_argument('--output',type=Path,default=Path('artifacts/facelandmarker/registration-lab/board-validation'))
out=parser.parse_args().output
root = out / 'captures/stationary-board'
root.mkdir(parents=True, exist_ok=True)
K = np.array([[1032.8, 0, 811.75], [0, 1044.7, 615.75], [0, 0, 1.]])
board = np.full((1400,1800,3),255,np.uint8)
for row in range(7):
 for col in range(9):
  if (row+col)%2==0: board[row*200:(row+1)*200,col*200:(col+1)*200] = 0
outer = np.array([[-.02,-.02,0],[.16,-.02,0],[.16,.12,0],[-.02,.12,0]])
pixel = np.float32([[0,0],[1800,0],[1800,1400],[0,1400]])
E=np.eye(4);E[:3,3]=[-.026,.043,-.048]
worldBoard=np.eye(4);worldBoard[:3,3]=[.2,1.3,-.8]
for i in range(16):
 r=np.array([(-.35,-.12,.15,.4)[i%4],(-.4,-.15,.2,.38)[i//4],.06*(i%3)])
 t=np.array([-.12+.07*(i%4),-.12+.06*(i//4),.45+.06*(i%3)])
 xy,_=cv2.projectPoints(outer,r,t,K,np.zeros(5))
 image=cv2.warpPerspective(board,cv2.getPerspectiveTransform(pixel,xy.astype(np.float32)),(1624,1232),borderValue=(245,245,245))
 folder=root/f'{i+1:03}-mode0-step5';folder.mkdir(exist_ok=True)
 cv2.imwrite(str(folder/'source.ppm'),image)
 for name in ['detector','landmarker']: cv2.imwrite(str(folder/f'{name}.ppm'),np.full((256,256,3),60,np.uint8))
 camBoard=np.eye(4);camBoard[:3,:3]=cv2.Rodrigues(r)[0];camBoard[:3,3]=t
 worldCam=worldBoard@np.linalg.inv(lab.CV_TO_CAMERA@camBoard)
 head=worldCam@np.linalg.inv(E)
 result=np.zeros(2994);result[0]=i+1
 sample=dict(schema=2,mode=0,modeLabel='A: Service',step='Checkerboard calibration',sequence=i+1,
  sourceWidth=1624,sourceHeight=1232,nativeWidth=3248,nativeHeight=2464,sourceScale=.5,
  result=result.tolist(),stageResult=result.tolist(),captureFrame=[100,.01*i,.03,1,0,0],
  cameraIntrinsics=(np.diag([2,2,1])@K).ravel().tolist(),imageTransform=np.eye(3).ravel().tolist(),
  cropAffine=[1,0,0,0,1,0],modelLandmarks=[0]*1434,cameraToTracking=E.ravel().tolist(),cameraToHead=E.ravel().tolist(),
  headToStageAtCapture=head.ravel().tolist(),serviceToStage=head.ravel().tolist(),
  headStableDuringReadback=True,headMovementMetres=0,headMovementDegrees=0,stereoEnabled=False)
 (folder/'sample.json').write_text(json.dumps(sample))
lab.analyze(root,out/'analysis',True)
cal=json.loads((out/'analysis/report.json').read_text())['calibration']
assert cal['usable_views']==16,cal
assert cal['rms_saved_px']<.5,cal
assert np.max(np.abs(np.array(cal['k_saved'])-K))<2,cal
assert cal['stationary_board_world_repeatability']['position_rms_about_mean_metres']<.003,cal
print('PASS: rendered boards',cal['usable_views'],'RMS saved px',cal['rms_saved_px'],'world position RMS m',cal['stationary_board_world_repeatability']['position_rms_about_mean_metres'])
