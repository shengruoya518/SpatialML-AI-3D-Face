"""Bounded dynamic-output benchmark. Keeps all results local and restores debug/selection.

Requires idle lab, face in view, and no screen recording. It never starts calibration.
"""
import argparse,base64,hashlib,json,re,signal,subprocess,time
from pathlib import Path

MUX=Path.home()/'.trae/skills/devmux/scripts/devmux'
SERIAL='PB311XHGKC220141G'
PACKAGE='com.pico.spatial.ml.sample.facelandmarker.registrationlab'
PROP='debug.pico.spatialml.debug'

class Device:
    def __init__(self, root):
        self.root=root;self.data=root/'performance-data';self.data.mkdir(exist_ok=True)
    def adb(self,*args):
        r=subprocess.run([str(MUX),'adb','-s',SERIAL,*args],text=True,capture_output=True,timeout=50)
        if r.returncode: raise RuntimeError(r.stdout+r.stderr)
        return r.stdout
    def command(self,name,mask=None):
        args=['shell','am','broadcast','-a',PACKAGE+'.COMMAND','-p',PACKAGE,'--es','command',name]
        if mask is not None:args+=['--es','value',str(mask)]
        output=self.adb(*args)
        match=re.search(r'FACE_LAB_V1:([A-Za-z0-9+/=]+)',output)
        if not match:raise RuntimeError('Lab did not answer: '+output)
        status=json.loads(base64.b64decode(match[1]))
        if not status['accepted']:raise RuntimeError(status.get('error','Rejected'))
        return status
    def idle(self):
        s=self.command('status')
        if s['automatic']['active'] or (s['locked'] and not s['stopped']):raise RuntimeError('Calibration active')
        if not self.adb('shell','dumpsys','media_projection').strip().endswith('null'):raise RuntimeError('Recording active')
        return s
    def prop(self,value):
        self.adb('shell','setprop',PROP,value if value else "''")
        assert self.adb('shell','getprop',PROP).strip()==value
    def capture(self,label,seconds):
        path=self.data/(label+'.log')
        with path.open('wb') as out:
            p=subprocess.Popen([str(MUX),'adb','-s',SERIAL,'logcat','-T','1','-v','threadtime','-v','usec'],stdout=out,stderr=subprocess.STDOUT)
            try:
                try:p.wait(timeout=seconds)
                except subprocess.TimeoutExpired:p.send_signal(signal.SIGINT);p.wait(timeout=10)
                else:raise RuntimeError('Capture ended early')
            finally:
                if p.poll() is None:p.terminate();p.wait(timeout=10)
        return path
    def ready(self,mask,seconds=30):
        samples=[];seen=[];deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            s=self.idle();samples.append(s)
            (self.data/('ready-'+str(mask)+'.json')).write_text(json.dumps(samples,indent=2))
            if s['stopped']:raise RuntimeError(s['message'])
            if s.get('appliedOutputMask')==mask and s['hasFace'] and s['frameAgeSeconds']<1 and (not seen or s['frame']>seen[-1]):seen.append(s['frame'])
            else:seen=[]
            if len(seen)>=3:return s
            print('waiting mode',mask,'frame',s['frame'],'face',s['hasFace'],'applied',s.get('appliedOutputMask'),flush=True)
            time.sleep(2)
        raise RuntimeError('No sustained face-present output for mask '+str(mask))
    def snapshot(self,label):
        data={'status':self.idle()}
        for key,args in {'thermal':['dumpsys','thermalservice'],'battery':['dumpsys','battery'],'processes':['ps','-A'],'clock':['date','+%Y-%m-%dT%H:%M:%S%z'],'debug':['getprop',PROP]}.items():data[key]=self.adb('shell',*args)
        (self.data/(label+'.json')).write_text(json.dumps(data,indent=2))
        return data
    def window(self,label,mask,seconds,debug):
        self.command('outputs',mask);self.ready(mask);self.prop(debug)
        # Keep the first timed frame clear of the flag transition and remote probe.
        time.sleep(1)
        first=self.idle();start=time.monotonic();self.capture(label,seconds);last=self.idle()
        if last['stopped']:raise RuntimeError('Camera stopped in '+label)
        item=dict(label=label,mask=mask,debug=debug,startFrame=first['frame'],endFrame=last['frame'],
                  session=first['timeline']['session'],clientPid=int(self.adb('shell','pidof',PACKAGE).strip()),
                  elapsedHostSeconds=time.monotonic()-start,startStatus=first,endStatus=last,log=label+'.log')
        print(label,'frames',first['frame'],last['frame'],'face',first['hasFace'],last['hasFace'],flush=True)
        return item
    def pull_journal(self,session,label):
        self.adb('pull',f'/sdcard/Android/data/{PACKAGE}/files/RegistrationLab/{session}/timeline.jsonl',str(self.data/(label+'-timeline.jsonl')))

def measure(root,seconds,resume=False):
    d=Device(root);manifest=root/'dynamic-manifest.json'
    if manifest.exists() and not resume:raise RuntimeError('Existing results: use --resume to preserve and continue them')
    report=json.loads(manifest.read_text()) if manifest.exists() else {'windows':[]}
    if 'error' in report:report.setdefault('previousErrors',[]).append(report.pop('error'))
    report.update(debugRestored=False,leaseReleased=False)
    completed={w['label'] for w in report['windows']}
    original=None;selection=None
    subprocess.run([str(MUX),'acquire','-s',SERIAL,'--wait','15','--note','Measure dynamic face output combinations'],check=True)
    try:
        original=d.adb('shell','getprop',PROP).strip()
        first=d.snapshot('dynamic-resume-'+str(len(completed)) if completed else 'dynamic-before')
        selection=first['status']['requestedOutputMask']
        if any(w['session']!=first['status']['timeline']['session'] for w in report['windows']):
            raise RuntimeError('App session changed; start a new benchmark directory')
        # Forward/reverse order reduces ordering bias; all modes share the same warm session.
        for repeat,order in [('a',[7,1,4,2,5,3,6]),('b',[6,3,5,2,4,1,7])]:
            for mask in order:
                label=f'dynamic-{repeat}-mask{mask}'
                if label in completed:continue
                report['windows'].append(d.window(label,mask,seconds,'0'))
                (root/'dynamic-manifest.json').write_text(json.dumps(report,indent=2))
            d.snapshot('dynamic-after-'+repeat)
        # Types/lengths and no-submit behavior, before the separate tracing windows.
        d.command('outputs',0);time.sleep(2);a=d.command('status');time.sleep(3);b=d.command('status')
        assert a['requestedOutputMask']==b['requestedOutputMask']==0 and not a['stopped'] and not b['stopped']
        assert a['frame']==b['frame'],'All-off continued submitting'
        report['allOff']={'start':a['frame'],'end':b['frame'],'PASS':True}
        for mask in [1,4,7,2,5,3,6]:
            label=f'dynamic-trace-mask{mask}'
            if label in completed:continue
            report['windows'].append(d.window(label,mask,15,'1'))
            (root/'dynamic-manifest.json').write_text(json.dumps(report,indent=2))
        d.snapshot('dynamic-after-trace')
        d.pull_journal(first['status']['timeline']['session'],'dynamic')
    except Exception as error:
        report['error']=str(error);print('BENCHMARK ERROR',error,flush=True)
        try:d.pull_journal(d.command('status')['timeline']['session'],'dynamic')
        except Exception as pull_error:report['pullError']=str(pull_error)
        raise
    finally:
        try:
            if original is not None:d.prop(original);report['debugRestored']=True
            if selection is not None:d.command('outputs',selection)
        finally:
            report['leaseReleased']=subprocess.run([str(MUX),'release','-s',SERIAL]).returncode==0
            (root/'dynamic-manifest.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=20,choices=range(10,31))
    p.add_argument('--resume',action='store_true',help='Preserve completed windows and resume an interrupted run')
    a=p.parse_args();measure(a.output,a.seconds,a.resume)
