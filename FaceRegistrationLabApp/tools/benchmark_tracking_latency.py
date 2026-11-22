"""Compare streaming policies in one APK; preserve calibration, recordings and service binaries.

This is a live headset command. --install performs a data-preserving APK replacement and
restarts the existing Spatial service process to avoid the documented GPU teardown fault.
No camera probes, tracing property changes, app-data clear or recording deletion occur.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import time

MUX = '/Users/bytedance/.trae/skills/devmux/scripts/devmux'
APP = 'com.pico.spatial.ml.sample.facelandmarker.registrationlab'
SERVICE = 'com.bytedance.pico.openmr.spatial'
ACTIVITY = 'com.pico.spatial.ml.sample.facelandmarker.platform.MainActivity'
FILES = f'/sdcard/Android/data/{APP}/files'


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (index - low)


def distribution(values):
    return None if not values else dict(n=len(values), median=statistics.median(values),
                                        p95=percentile(values, .95), mean=statistics.mean(values))


def summarize(rows, windows):
    packets = [r['details'] for r in rows if r.get('event') == 'pipeline_frame']
    applied = {r['details']['frame']: r['details'] for r in rows
               if r.get('event') == 'helmet_pose_applied' and r['details'].get('visible')}
    summaries = []
    for window in windows:
        candidates = [p for p in packets if window['start'] < p['readbackSeconds'] <= window['end']
                      and p.get('trackingPacing') == window['profile']]
        warm = candidates[5:]
        eligible = [p for p in warm if p.get('nativePacketFinite') and p.get('freshCameraFrame')
                    and not p.get('rejection') and not p.get('calibrationEvidence')
                    and 0 <= p['cameraAgeAtReadbackSeconds'] <= 2]
        groups = {}
        for label in ('tracking_face', 'acquisition_face', 'no_face'):
            selected = [p for p in eligible if
                        ('tracking_face' if p['hasFace'] and not p['detector'] else
                         'acquisition_face' if p['hasFace'] else 'no_face') == label]
            output = dict(frames=len(selected),
                          submitToReadbackMs=distribution([p['submitToReadbackSeconds'] * 1000 for p in selected]),
                          exposureToReadbackMs=distribution([p['cameraAgeAtReadbackSeconds'] * 1000 for p in selected]))
            joined = [(p, applied[p['frame']]) for p in selected if p['frame'] in applied]
            output['visibleUpdates'] = len(joined)
            output['exposureToPoseSetterMs'] = distribution([
                (a['appliedSeconds'] - p['captureSeconds']) * 1000 for p, a in joined])
            output['readbackToPoseSetterMs'] = distribution([
                (a['appliedSeconds'] - p['readbackSeconds']) * 1000 for p, a in joined])
            output['occlusionSdkUploadMs'] = distribution([
                a['occlusion']['sdkUploadMs'] for p, a in joined if 'occlusion' in a])
            groups[label] = output
        gaps = [(b['submitSeconds'] - a['readbackSeconds']) * 1000
                for a, b in zip(warm, warm[1:]) if b['frame'] == a['frame'] + 1]
        span = warm[-1]['readbackSeconds'] - warm[0]['readbackSeconds'] if len(warm) > 1 else 0
        summaries.append(dict(window, eligibleFrames=len(eligible), excludedFrames=len(warm)-len(eligible),
                              completionsPerSecond=(len(warm)-1)/span if span else None,
                              uniqueExposures=len({p['captureSeconds'] for p in eligible}),
                              interFrameGapMs=distribution(gaps), groups=groups))
    return dict(boundary='App result readback and entity transform setter return; no compositor presentation timing.',
                windows=summaries)


def main(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    report = dict(serial=args.serial, startedUtc=datetime.now(timezone.utc).isoformat(), windows=[])
    leased = False
    before = None
    session = None

    def run(argv, check=True, binary=False):
        p = subprocess.run(argv, capture_output=True, text=not binary, timeout=90)
        if check and p.returncode:
            raise RuntimeError(f'{argv}: {p.returncode}: {p.stdout!r} {p.stderr!r}')
        return p

    def adb(*argv, **kwargs):
        return run([MUX, 'adb', '-s', args.serial, *map(str, argv)], **kwargs)

    def shell(command, **kwargs):
        return adb('shell', command, **kwargs).stdout.strip()

    def write(name, value):
        (out/name).write_text(json.dumps(value, indent=2)+'\n')

    def apk(package):
        paths = shell('pm path '+package).splitlines()
        return {p.removeprefix('package:'): shell('sha256sum '+shlex.quote(p.removeprefix('package:'))).split()[0]
                for p in paths if p.startswith('package:')}

    def inventory(directory):
        raw = shell('find '+shlex.quote(directory)+' -type f -exec stat -c "%s|%n" {} \\;', check=False)
        return {line.split('|',1)[1]: int(line.split('|',1)[0]) for line in raw.splitlines() if '|' in line}

    def snapshot(label):
        private = {}
        for name in ('left-camera-to-head-v1.json', 'face-intrinsics-calibration-v1.json'):
            p = adb('exec-out', 'run-as', APP, 'cat', 'files/'+name, check=False, binary=True)
            if p.returncode == 0 and p.stdout.lstrip().startswith(b'{'):
                json.loads(p.stdout)
                private[name] = hashlib.sha256(p.stdout).hexdigest()
                (out/(label+'-'+name)).write_bytes(p.stdout)
            else:
                assert b'No such file' in p.stdout+p.stderr, 'Calibration snapshot failed'
                private[name] = None
        result = dict(privateCalibration=private, appFiles=inventory(FILES),
                      recordings=inventory('/sdcard/DCIM/ScreenRecording'))
        write(label+'.json', result)
        return result

    def latest_frames():
        raw = shell('tail -n 1200 '+shlex.quote(session+'/timeline.jsonl'))
        result = []
        for line in raw.splitlines():
            try:
                row = json.loads(line)
                if row.get('event') == 'pipeline_frame': result.append(row['details'])
            except json.JSONDecodeError:
                pass
        return result

    def command(profile):
        raw = adb('shell', 'am', 'broadcast', '--receiver-foreground', '-a', APP+'.COMMAND',
                  '-p', APP, '--es', 'command', 'latency', '--es', 'value', profile).stdout
        (out/('command-'+profile+'.txt')).write_text(raw)
        match = re.search(r'FACE_LAB_V1:([A-Za-z0-9+/=]+)', raw)
        if match:
            state = json.loads(base64.b64decode(match[1]))
            assert state.get('trackingPacing') == profile, state

    try:
        run([MUX,'acquire','-s',args.serial,'--wait','15','--note','Face tracking latency comparison'])
        leased = True
        assert shell('dumpsys media_projection').endswith('null'), 'Recording is active'
        bindings = shell('dumpsys activity services '+SERVICE)
        (out/'bindings-before.txt').write_text(bindings)
        assert all(APP+'/' in line for line in bindings.splitlines() if '* Client AppBindRecord' in line), 'Other Spatial client'
        report['fingerprint'] = shell('getprop ro.build.fingerprint')
        report['debugBefore'] = shell('getprop debug.pico.spatialml.debug')
        assert report['debugBefore'] != '1', 'Disable operator tracing before comparing policies'
        report['serviceApkBefore'] = apk(SERVICE)
        report['appApkBefore'] = apk(APP)
        before = snapshot('before')
        previous = shell(f'ls -td {FILES}/RegistrationLab/* | head -n 1')
        if previous:
            adb('pull', previous+'/timeline.jsonl', out/'previous-timeline.jsonl')
        old_pid = shell('pidof '+APP, check=False)
        if old_pid:
            (out/'previous-app-logcat.txt').write_text(adb('logcat','-d','--pid='+old_pid).stdout)
        if args.install:
            for i, (path, digest) in enumerate(report['appApkBefore'].items()):
                backup = out/f'previous-{i}.apk'
                adb('pull',path,backup)
                assert hashlib.sha256(backup.read_bytes()).hexdigest() == digest
            assert shell('dumpsys media_projection').endswith('null'), 'Recording started during preflight'
            shell('am force-stop '+APP)
            (out/'install.log').write_text(adb('install','-r',args.install).stdout)
            report['installedSha256'] = hashlib.sha256(args.install.read_bytes()).hexdigest()
            assert list(apk(APP).values()) == [report['installedSha256']]
            shell('am force-stop '+SERVICE)
            (out/'launch.log').write_text(shell(f'am start -W -n {APP}/{ACTIVITY}'))
        deadline = time.monotonic()+60
        while time.monotonic() < deadline:
            session = shell(f'ls -td {FILES}/RegistrationLab/* | head -n 1')
            frames = latest_frames()
            if frames and frames[-1].get('trackingPacing'): break
            time.sleep(2)
        else: raise RuntimeError('No live frames with pacing telemetry')
        report['session'] = session
        report['appPid'] = shell('pidof '+APP)
        report['servicePid'] = shell('pidof '+SERVICE)
        for profile in args.profiles:
            command(profile)
            deadline = time.monotonic()+20
            while time.monotonic() < deadline:
                frames = latest_frames()
                if frames and frames[-1].get('trackingPacing') == profile: break
                time.sleep(1)
            else: raise RuntimeError('Pacing command did not reach the running app: '+profile)
            start = frames[-1]['readbackSeconds']
            start_frame = frames[-1]['frame']
            for _ in range(args.seconds//5):
                time.sleep(5)
                frames = latest_frames()
                print(f"{profile}: frame={frames[-1]['frame']} face={frames[-1]['hasFace']} detector={frames[-1]['detector']}",flush=True)
                assert shell('pidof '+APP) == report['appPid'] and shell('pidof '+SERVICE) == report['servicePid'], 'Process changed'
            assert frames[-1]['frame'] > start_frame+5, 'Pipeline stopped'
            report['windows'].append(dict(profile=profile,start=start,end=frames[-1]['readbackSeconds']))
        report['status'] = 'CAPTURED'
    except Exception as error:
        report['status'] = 'FAILED'
        report['error'] = str(error)
        raise
    finally:
        try:
            if leased:
                if session:
                    try:
                        command('fast')
                    except Exception as error:
                        report['restorePolicyError'] = str(error)
                    adb('pull',session+'/timeline.jsonl',out/'timeline.jsonl')
                    data = (out/'timeline.jsonl').read_bytes()
                    digest = hashlib.sha256(data).hexdigest()
                    assert shell('head -c '+str(len(data))+' '+shlex.quote(session+'/timeline.jsonl')+' | sha256sum').split()[0] == digest
                    report['journalSha256'] = digest
                    rows = [json.loads(line) for line in data.decode().splitlines() if line]
                    write('summary.json',summarize(rows,report['windows']))
                if before:
                    after = snapshot('after')
                    report['calibrationPreserved'] = before['privateCalibration'] == after['privateCalibration']
                    report['missingOrShrunkAppFiles'] = [p for p,n in before['appFiles'].items() if after['appFiles'].get(p,-1)<n]
                    report['changedOrMissingRecordings'] = [p for p,n in before['recordings'].items() if after['recordings'].get(p)!=n]
                    assert report['calibrationPreserved'] and not report['missingOrShrunkAppFiles'] and not report['changedOrMissingRecordings']
                report['serviceApkAfter'] = apk(SERVICE)
                report['appApkAfter'] = apk(APP)
                report['debugAfter'] = shell('getprop debug.pico.spatialml.debug')
                assert report['serviceApkAfter'] == report['serviceApkBefore']
                assert report['debugAfter'] == report['debugBefore']
                for label, package in [('app',APP),('service',SERVICE)]:
                    pid = shell('pidof '+package,check=False)
                    if pid: (out/(label+'-logcat.txt')).write_text(adb('logcat','-d','--pid='+pid).stdout)
                (out/'crash-logcat.txt').write_text(adb('logcat','-d','-b','crash').stdout)
        except Exception as error:
            report['cleanupError'] = str(error)
            report['status'] = 'FAILED'
            raise
        finally:
            if leased: report['leaseReleased'] = run([MUX,'release','-s',args.serial],check=False).returncode == 0
            report['finishedUtc'] = datetime.now(timezone.utc).isoformat()
            write('manifest.json',report)
            print('Evidence: '+str(out),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial',default='PB311XHGKC220141G')
    parser.add_argument('--install',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seconds',type=int,choices=(15,20,30),default=20)
    parser.add_argument('--profiles',nargs='+',choices=('legacy','fast','eager'),default=['legacy','fast','eager','fast','legacy'])
    main(parser.parse_args())
