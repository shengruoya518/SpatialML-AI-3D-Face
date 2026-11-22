"""Measure original/split/inline/original fitting with identical output selection.

Requires idle lab and a sustained face; preserves the original APK, calibration,
recordings, debug flag and output selection. Never starts a calibration capture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import time

from measure_face_outputs import Device, MUX, PACKAGE, SERIAL


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(root, split, inline, seconds):
    root.mkdir(parents=True, exist_ok=False)
    d=Device(root)
    manifest={'windows':[], 'originalRestored':False, 'debugRestored':False, 'leaseReleased':False,
              'settings':{'preprocessing':'native', 'outputMask':7, 'seconds':seconds, 'serial':SERIAL, 'package':PACKAGE}}
    original=root/'original.apk'
    original_debug=None;selection=None;replaced=False
    def save():
        (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    def snapshot(label):
        s=d.snapshot(label)
        path=d.adb('shell','pm','path',PACKAGE).strip().removeprefix('package:')
        s['apkSha256']=d.adb('shell','sha256sum',path).split()[0]
        (d.data/(label+'.json')).write_text(json.dumps(s,indent=2)+'\n')
        return s
    def files(label):
        data=d.adb('shell','find',f'/sdcard/Android/data/{PACKAGE}/files','-type','f','-exec','stat','-c','"%s|%n"','{}','\\;')
        (d.data/('files-'+label+'.txt')).write_text(data)
        return {p:int(s) for s,p in (line.split('|',1) for line in data.splitlines())}
    def install(apk,label):
        d.idle()
        with (d.data/(label+'-startup.log')).open('wb') as stream:
            process=subprocess.Popen([str(MUX),'adb','-s',SERIAL,'logcat','-T','1','-v','threadtime','-v','usec'],stdout=stream,stderr=subprocess.STDOUT)
            try:
                d.adb('shell','am','force-stop',PACKAGE);time.sleep(2)
                (d.data/(label+'-install.txt')).write_text(d.adb('install','-r',str(apk)))
                d.adb('shell','am','start','-n',PACKAGE+'/com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity')
                deadline=time.monotonic()+55;seen=[]
                while time.monotonic()<deadline:
                    try:s=d.idle()
                    except RuntimeError as error:
                        if 'Lab did not answer' in str(error):time.sleep(2);continue
                        raise
                    print(label,'frame',s['frame'],'face',s['hasFace'],'stopped',s['stopped'],flush=True)
                    if s['stopped']:raise RuntimeError(s['message'])
                    if s['frame']>=10 and (not seen or s['frame']>seen[-1]):seen.append(s['frame'])
                    else:seen=[]
                    if len(seen)>=3:break
                    time.sleep(2)
                else:raise RuntimeError('Startup did not supply advancing frames')
                d.command('outputs',7)
                state=snapshot(label)
                assert state['apkSha256']==digest(apk)
                return state
            finally:
                if process.poll() is None:process.send_signal(signal.SIGINT);process.wait(timeout=10)
    def window(label,debug,variant):
        item=d.window(label,7,seconds,debug);item['variant']=variant
        manifest['windows'].append(item);save()
        d.pull_journal(item['session'],label)
    subprocess.run([str(MUX),'acquire','-s',SERIAL,'--wait','15','--note','Original/split/inline face geometry benchmark'],check=True)
    # Preserve clock anchors emitted between bounded windows/readiness probes.
    # A 20 s window can otherwise miss every-100-frame app status logging.
    session_stream=None;session_log=None
    try:
        session_stream=(d.data/'session-continuous.log').open('wb')
        session_log=subprocess.Popen([str(MUX),'adb','-s',SERIAL,'logcat','-T','1','-v','threadtime','-v','usec'],stdout=session_stream,stderr=subprocess.STDOUT)
        original_debug=d.adb('shell','getprop','debug.pico.spatialml.debug').strip()
        initial=d.idle();selection=initial['requestedOutputMask']
        d.command('outputs',7);d.ready(7,seconds=30)
        path=d.adb('shell','pm','path',PACKAGE).strip().removeprefix('package:')
        d.adb('pull',path,str(original))
        manifest['before']=snapshot('before');assert manifest['before']['apkSha256']==digest(original)
        manifest['apkSha256']={name:digest(path) for name,path in [('original',original),('split',split),('inline',inline)]}
        manifest['privateCalibrationBefore']=d.adb('shell','run-as',PACKAGE,'sha256sum','files/left-camera-to-head-v1.json').strip()
        before_files=files('before');save()
        window('original-before','0','original');window('original-trace','1','original')
        for label,apk in [('split',split),('inline',inline)]:
            d.prop('1');replaced=True;install(apk,label)
            window(label+'-before','0',label);window(label+'-trace','1',label);window(label+'-after','0',label)
        d.prop('0');install(original,'restored');manifest['originalRestored']=True
        window('original-after','0','original')
    except Exception as error:
        manifest['error']=str(error);print('BENCHMARK ERROR',error,flush=True)
    finally:
        restoration_errors=[]
        try:
            if replaced and not manifest['originalRestored']:
                try:install(original,'restore-recovery');manifest['originalRestored']=True
                except Exception as error:restoration_errors.append('APK restore: '+str(error))
            if original_debug is not None:
                try:d.prop(original_debug);manifest['debugRestored']=True
                except Exception as error:restoration_errors.append('Debug restore: '+str(error))
            if selection is not None:
                try:d.command('outputs',selection)
                except Exception as error:restoration_errors.append('Selection restore: '+str(error))
            if replaced:
                try:
                    manifest['final']=snapshot('final')
                    manifest['privateCalibrationAfter']=d.adb('shell','run-as',PACKAGE,'sha256sum','files/left-camera-to-head-v1.json').strip()
                    manifest['privateCalibrationPreserved']=manifest['privateCalibrationBefore']==manifest['privateCalibrationAfter']
                    after_files=files('after')
                    manifest['existingExternalFilesPreserved']=all(p in after_files and after_files[p]>=size for p,size in before_files.items())
                    manifest['existingExternalFileCount']=len(before_files)
                except Exception as error:restoration_errors.append('Preservation check: '+str(error))
        finally:
            manifest['restorationErrors']=restoration_errors
            try:
                if session_log is not None and session_log.poll() is None:
                    session_log.send_signal(signal.SIGINT)
                    try:session_log.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        session_log.kill();session_log.wait(timeout=5)
                        restoration_errors.append('Log capture did not exit on interrupt')
            finally:
                if session_stream is not None:session_stream.close()
                manifest['leaseReleased']=subprocess.run([str(MUX),'release','-s',SERIAL]).returncode==0
                save()
    print(root,flush=True)
    return 1 if manifest.get('error') or manifest['restorationErrors'] else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--split-apk',type=Path,required=True)
    parser.add_argument('--inline-apk',type=Path,required=True)
    parser.add_argument('--seconds',type=int,default=20,choices=range(15,31))
    args=parser.parse_args()
    if not args.split_apk.is_file() or not args.inline_apk.is_file():parser.error('Both candidate APKs must exist')
    raise SystemExit(measure(args.output,args.split_apk,args.inline_apk,args.seconds))
