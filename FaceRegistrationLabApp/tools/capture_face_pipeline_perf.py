"""Capture trace-off / operator-trace / trace-off windows on the pinned headset.

Requires the lab already running, idle, and a face kept in view. Does not start a
calibration run, reinstall, clear logs/data, restart a service, or change camera K.
Enabling debug.pico.spatialml.debug enables device-wide service logging AND readback
permission bypass. Its original value is restored in finally before releasing devmux.
"""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import signal
import subprocess
import time

PACKAGE = 'com.pico.spatial.ml.sample.facelandmarker.registrationlab'
PROPERTY = 'debug.pico.spatialml.debug'


def capture(root, serial, seconds, mux):
    root.mkdir(parents=True, exist_ok=False)
    report = {'serial':serial, 'package':PACKAGE, 'secondsPerWindow':seconds, 'windows':[],
              'propertyRestored':False, 'leaseReleased':False}
    command = [str(mux), 'adb', '-s', serial]
    def run(args, check=True):
        result = subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=40)
        if check and result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result
    def adb(*args, check=True):
        return run(command+list(args),check)
    def status():
        result=adb('shell','am','broadcast','-a',PACKAGE+'.COMMAND','-p',PACKAGE,'--es','command','status')
        token=re.search(r'FACE_LAB_V1:([A-Za-z0-9+/=]+)',result.stdout)
        if not token: raise RuntimeError('Open the lab on the headset before profiling')
        state=json.loads(base64.b64decode(token[1]))
        if state['stopped']: raise RuntimeError('Camera is stopped; recover the app before profiling')
        if state['automatic']['active'] or state['locked']: raise RuntimeError('Calibration capture is active; finish it before profiling')
        return state
    def set_property(value):
        # adb shell reconstructs an argument string; an empty original value needs literal quoting.
        adb('shell','setprop',PROPERTY,value if value else "''")
        actual=adb('shell','getprop',PROPERTY).stdout.strip()
        if actual!=value: raise RuntimeError('Debug property readback mismatch')
    def metadata(label):
        state=status()
        data={'status':state,'hostUtc':datetime.now(timezone.utc).isoformat()}
        for name,args in {'clock':['date','+%Y-%m-%dT%H:%M:%S%z'],
                          'fingerprint':['getprop','ro.build.fingerprint'],
                          'processes':['ps','-A'],'battery':['dumpsys','battery'],
                          'thermal':['dumpsys','thermalservice'],
                          'debug':['getprop',PROPERTY]}.items():
            r=adb('shell',*args,check=False);data[name]=r.stdout+r.stderr
        apk=adb('shell','pm','path',PACKAGE).stdout.strip().removeprefix('package:')
        data['installedApkPath']=apk
        data['installedApkSha256']=adb('shell','sha256sum',apk).stdout.split()[0]
        (root/(label+'.json')).write_text(json.dumps(data,indent=2)+'\n')
        return state
    original=None
    acquired=False
    try:
        run([str(mux),'acquire','-s',serial,'--wait','15','--note','Bounded face pipeline performance profiling'])
        acquired=True
        original=adb('shell','getprop',PROPERTY).stdout.strip()
        report['originalDebugProperty']=original
        before=metadata('before')
        report['timelineSession']=before['timeline']['session']
        report['clientPid']=adb('shell','pidof',PACKAGE).stdout.strip()
        for label,value in [('baseline_before','0'),('operators','1'),('baseline_after','0')]:
            set_property(value)
            first=status()
            file=root/(label+'.log')
            start=time.monotonic()
            with file.open('wb') as stream:
                process=subprocess.Popen(command+['logcat','-T','1','-v','threadtime','-v','usec'],stdout=stream,stderr=subprocess.STDOUT)
                try:
                    try: process.wait(timeout=seconds)
                    except subprocess.TimeoutExpired:
                        process.send_signal(signal.SIGINT)
                        process.wait(timeout=10)
                    else: raise RuntimeError('Log capture ended before its bounded window')
                finally:
                    if process.poll() is None:
                        process.terminate();process.wait(timeout=10)
            last=status()
            report['windows'].append({'label':label,'startFrame':first['frame'],'endFrame':last['frame'],
                                     'elapsedHostSeconds':time.monotonic()-start,'startFace':first['hasFace'],
                                     'endFace':last['hasFace'],'log':file.name,'sha256':hashlib.file_digest(file.open('rb'),'sha256').hexdigest()})
            print(label,first['frame'],last['frame'],flush=True)
        after=metadata('after')
        remote=f'/sdcard/Android/data/{PACKAGE}/files/RegistrationLab/'+after['timeline']['session']+'/timeline.jsonl'
        adb('pull',remote,str(root/'timeline.jsonl'))
    finally:
        try:
            if acquired and original is not None:
                set_property(original);report['propertyRestored']=True
        finally:
            if acquired: report['leaseReleased']=run([str(mux),'release','-s',serial],False).returncode==0
            (root/'capture-manifest.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--serial',default='PB311XHGKC220141G')
    parser.add_argument('--seconds',type=int,default=30,choices=range(10,61))
    parser.add_argument('--devmux',type=Path,default=Path.home()/'.trae/skills/devmux/scripts/devmux')
    args=parser.parse_args()
    capture(args.output,args.serial,args.seconds,args.devmux)
