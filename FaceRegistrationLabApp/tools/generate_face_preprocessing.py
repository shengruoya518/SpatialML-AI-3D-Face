"""Generate deterministic weightless LiteRT GPU affine preprocessing models.

No TensorFlow conversion or trained weights. Resampler is the custom operation
explicitly registered by LiteRT's GPU runtime; CPU fallback is not supported.
The Float32 image variants are numerical/GPU host probes, never app assets.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import flatbuffers
import numpy as np
import tflite as fb


@dataclass
class Tensor:
    name: str
    shape: list
    dtype: int
    data: bytes = b''


class Graph:
    def __init__(self):
        self.tensors = []
        self.operators = []
        self.inputs = []
        self.outputs = []

    def tensor(self, name, shape, dtype=fb.TensorType.FLOAT32, values=None):
        data = b''
        if values is not None:
            typ = {fb.TensorType.FLOAT32:'<f4', fb.TensorType.INT32:'<i4'}[dtype]
            a = np.asarray(values, dtype=typ).reshape(shape)
            data = a.tobytes()
        self.tensors.append(Tensor(name, list(shape), dtype, data))
        return len(self.tensors)-1

    def constant(self, name, value):
        return self.tensor(name, [1,1,1,1], values=[value])

    def op(self, kind, inputs, shape, name=None, options=None, dtype=fb.TensorType.FLOAT32):
        # The GPU delegate rejects arithmetic nodes whose operands are both constants.
        # Fold these at generation time rather than leaving a CPU partition in the model.
        if inputs and all(self.tensors[i].data and self.tensors[i].dtype == fb.TensorType.FLOAT32 for i in inputs):
            arrays=[np.frombuffer(self.tensors[i].data,dtype='<f4').reshape(self.tensors[i].shape) for i in inputs]
            operation={'ADD':np.add,'SUB':np.subtract,'MUL':np.multiply,'DIV':np.divide,'FLOOR':np.floor}.get(kind)
            if operation is not None:
                value=operation(*arrays)
                return self.tensor(name or f'folded_{len(self.tensors)}',shape,values=value)
        output = self.tensor(name or f'{kind.lower()}_{len(self.operators)}', shape, dtype)
        self.operators.append((kind, list(inputs), [output], options or {}))
        return output

    def binary(self, kind, a, b, name=None):
        shape = np.broadcast_shapes(tuple(self.tensors[a].shape),tuple(self.tensors[b].shape))
        return self.op(kind,[a,b],shape,name)

    def component(self, affine, index):
        begin = self.tensor(f'begin_{index}', [4], fb.TensorType.INT32, [0,0,0,index])
        size = self.tensor(f'size_{index}', [4], fb.TensorType.INT32, [1,1,1,1])
        return self.op(
            'SLICE',
            [affine, begin, size],
            [1, 1, 1, 1],
            dtype=self.tensors[affine].dtype,
        )

    def serialize(self, description):
        builder=flatbuffers.Builder(4096)
        def ints(values):
            builder.StartVector(4,len(values),4)
            for v in reversed(values):builder.PrependInt32(int(v))
            return builder.EndVector()
        def refs(values):
            builder.StartVector(4,len(values),4)
            for v in reversed(values):builder.PrependUOffsetTRelative(v)
            return builder.EndVector()
        buffers=[]
        for data in [b'']+[t.data for t in self.tensors]:
            array=builder.CreateByteVector(data) if data else None
            fb.BufferStart(builder)
            if array is not None:fb.BufferAddData(builder,array)
            buffers.append(fb.BufferEnd(builder))
        tensors=[]
        for i,t in enumerate(self.tensors):
            name=builder.CreateString(t.name);shape=ints(t.shape)
            fb.TensorStart(builder);fb.TensorAddName(builder,name);fb.TensorAddShape(builder,shape)
            fb.TensorAddType(builder,t.dtype);fb.TensorAddBuffer(builder,i+1)
            tensors.append(fb.TensorEnd(builder))
        kinds=list(dict.fromkeys(o[0] for o in self.operators));codes=[]
        for kind in kinds:
            custom=builder.CreateString('Resampler') if kind=='RESAMPLER' else None
            code=fb.BuiltinOperator.CUSTOM if custom is not None else getattr(fb.BuiltinOperator,kind)
            fb.OperatorCodeStart(builder);fb.OperatorCodeAddBuiltinCode(builder,code)
            fb.OperatorCodeAddDeprecatedBuiltinCode(builder,min(code,127))
            fb.OperatorCodeAddVersion(builder,1)
            if custom is not None:fb.OperatorCodeAddCustomCode(builder,custom)
            codes.append(fb.OperatorCodeEnd(builder))
        operators=[]
        for kind,inputs,outputs,config in self.operators:
            option=0;option_type=0
            option_name={'ADD':'AddOptions','SUB':'SubOptions','MUL':'MulOptions','DIV':'DivOptions','CAST':'CastOptions','CONCATENATION':'ConcatenationOptions','SLICE':'SliceOptions','GATHER':'GatherOptions','SUM':'ReducerOptions','REDUCE_MIN':'ReducerOptions','REDUCE_MAX':'ReducerOptions','RESHAPE':'ReshapeOptions','MAXIMUM':'MaximumMinimumOptions','MINIMUM':'MaximumMinimumOptions','BATCH_MATMUL':'BatchMatMulOptions'}.get(kind)
            if kind=='RESIZE_NEAREST_NEIGHBOR':option_name='ResizeNearestNeighborOptions'
            if option_name:
                getattr(fb,option_name+'Start')(builder)
                if kind=='RESIZE_NEAREST_NEIGHBOR':
                    fb.ResizeNearestNeighborOptionsAddAlignCorners(builder,False)
                    fb.ResizeNearestNeighborOptionsAddHalfPixelCenters(builder,False)
                if kind=='CAST':
                    fb.CastOptionsAddInDataType(builder,self.tensors[inputs[0]].dtype)
                    fb.CastOptionsAddOutDataType(builder,self.tensors[outputs[0]].dtype)
                if kind=='CONCATENATION':fb.ConcatenationOptionsAddAxis(builder,config.get('axis',3))
                if kind=='GATHER':fb.GatherOptionsAddAxis(builder,config.get('axis',3))
                if kind in ('SUM','REDUCE_MIN','REDUCE_MAX'):fb.ReducerOptionsAddKeepDims(builder,True)
                if kind=='BATCH_MATMUL':
                    fb.BatchMatMulOptionsAddAdjX(builder,config.get('adj_x',False))
                    fb.BatchMatMulOptionsAddAdjY(builder,config.get('adj_y',False))
                option=getattr(fb,option_name+'End')(builder)
                option_type=getattr(fb.BuiltinOptions,option_name)
            iv=ints(inputs);ov=ints(outputs)
            fb.OperatorStart(builder);fb.OperatorAddOpcodeIndex(builder,kinds.index(kind))
            fb.OperatorAddInputs(builder,iv);fb.OperatorAddOutputs(builder,ov)
            if option:
                fb.OperatorAddBuiltinOptionsType(builder,option_type);fb.OperatorAddBuiltinOptions(builder,option)
            operators.append(fb.OperatorEnd(builder))
        tv=refs(tensors);ov=refs(operators);iv=ints(self.inputs);outv=ints(self.outputs)
        name=builder.CreateString('main')
        fb.SubGraphStart(builder);fb.SubGraphAddTensors(builder,tv);fb.SubGraphAddOperators(builder,ov)
        fb.SubGraphAddInputs(builder,iv);fb.SubGraphAddOutputs(builder,outv);fb.SubGraphAddName(builder,name)
        subgraph=fb.SubGraphEnd(builder)
        maps=[]
        for indexes in [self.inputs,self.outputs]:
            entries=[]
            for index in indexes:
                name=builder.CreateString(self.tensors[index].name)
                fb.TensorMapStart(builder);fb.TensorMapAddName(builder,name);fb.TensorMapAddTensorIndex(builder,index)
                entries.append(fb.TensorMapEnd(builder))
            maps.append(refs(entries))
        name=builder.CreateString('serving_default')
        fb.SignatureDefStart(builder);fb.SignatureDefAddInputs(builder,maps[0]);fb.SignatureDefAddOutputs(builder,maps[1]);fb.SignatureDefAddSignatureKey(builder,name)
        signature=fb.SignatureDefEnd(builder)
        cv=refs(codes);sv=refs([subgraph]);bv=refs(buffers);sigv=refs([signature]);desc=builder.CreateString(description)
        fb.ModelStart(builder);fb.ModelAddVersion(builder,3);fb.ModelAddOperatorCodes(builder,cv);fb.ModelAddSubgraphs(builder,sv);fb.ModelAddBuffers(builder,bv);fb.ModelAddDescription(builder,desc);fb.ModelAddSignatureDefs(builder,sigv)
        model=fb.ModelEnd(builder);builder.Finish(model,file_identifier=b'TFL3')
        return bytes(builder.Output())


def make_model(detector, width, height, size=256, float_image=False, sample_bytes=False):
    g=Graph()
    image=g.tensor('image',[1,height,width,3],fb.TensorType.FLOAT32 if float_image else fb.TensorType.UINT8)
    affine=g.tensor('affine',[1,1,1,6]);g.inputs=[image,affine]
    # Resampler's Read<float> converts sampled byte values. The byte-sampling variant
    # avoids explicitly materializing a full-resolution floating-point camera image.
    cast=image if float_image or sample_bytes else g.op('CAST',[image],[1,height,width,3])
    a=g.component(affine,0);tx=g.component(affine,2);e=g.component(affine,4);ty=g.component(affine,5)
    zero=g.constant('zero',0);half=g.constant('half',.5)
    inv32=g.constant('inverse_interpolation_scale',1/32);thirtytwo=g.constant('interpolation_scale',32)
    fixed_scale=g.constant('affine_fraction_scale',1024)
    interpolation_bias=g.constant('affine_interpolation_bias',16)
    def neg(x):return g.binary('SUB',zero,x)
    if detector:
        one=g.constant('one',1)
        inverse=[g.binary('DIV',one,a),zero,g.binary('DIV',neg(tx),a),zero,g.binary('DIV',one,e),g.binary('DIV',neg(ty),e)]
    else:
        b=g.component(affine,1);d=g.component(affine,3)
        determinant=g.binary('SUB',g.binary('MUL',a,e),g.binary('MUL',b,d))
        inverse=[g.binary('DIV',e,determinant),g.binary('DIV',neg(b),determinant),
                 g.binary('DIV',g.binary('SUB',g.binary('MUL',b,ty),g.binary('MUL',e,tx)),determinant),
                 g.binary('DIV',neg(d),determinant),g.binary('DIV',a,determinant),
                 g.binary('DIV',g.binary('SUB',g.binary('MUL',d,tx),g.binary('MUL',a,ty)),determinant)]
    gx=g.tensor('destination_x',[1,1,size,1],values=np.arange(size))
    gy=g.tensor('destination_y',[1,size,1,1],values=np.arange(size))
    def round_nearest(x):return g.op('FLOOR',[g.binary('ADD',x,half)],g.tensors[x].shape)
    coords=[]
    for i in [0,3]:
        # Split integer/fraction before 1/32 quantization. Multiplying full-resolution
        # coordinates by 1024 overflows FP16 GPU intermediates. Full precision remains
        # required for subpixel calibration parity on the 3248x2464 source.
        components=[g.binary('MUL',inverse[i],gx),g.binary('ADD',g.binary('MUL',inverse[i+1],gy),inverse[i+2])]
        wholes=[];fractions=[]
        for value in components:
            whole=g.op('FLOOR',[value],g.tensors[value].shape)
            wholes.append(whole)
            fractions.append(round_nearest(g.binary('MUL',g.binary('SUB',value,whole),fixed_scale)))
        whole=g.binary('ADD',*wholes)
        fractional_sum=g.binary('ADD',g.binary('ADD',*fractions),interpolation_bias)
        quantized=g.op('FLOOR',[g.binary('DIV',fractional_sum,thirtytwo)],[1,size,size,1])
        coords.append(g.binary('ADD',whole,g.binary('MUL',quantized,inv32)))
    warp=g.op('CONCATENATION',coords,[1,size,size,2])
    pixels=g.op('RESAMPLER',[cast,warp],[1,size,size,3])
    crop=g.op('FLOOR',[g.binary('ADD',pixels,half)],[1,size,size,3],'crop')
    normal=g.binary('DIV',crop,g.constant('byte_scale',255),'model_input')
    # Export one terminal output. Some LiteRT GPU versions do not materialize an
    # intermediate tensor which is also requested as a second signature output.
    g.outputs=[normal]
    return g


def write_models(output, probes=None, sample_bytes=False):
    output.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for detector in [True,False]:
        name=('detector' if detector else 'landmark')+('_preprocess_rgb_gpu' if sample_bytes else '_preprocess_gpu')
        g=make_model(detector,3248,2464,sample_bytes=sample_bytes)
        path=output/(name+'.tflite');data=g.serialize(name+'; weightless; GPU Resampler; affine is source-to-crop; RGB; OpenCV-style 1/32 sampling')
        path.write_bytes(data)
        manifest.append({'name':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'operators':[o[0] for o in g.operators],'inputImage':[1,2464,3248,3],'inputImageType':'uint8','affine':[1,1,1,6],'outputs':{'model_input':[1,256,256,3]},'exportCrop':'round(model_input*255) converted to uint8 by lab-only native operators','target':'GPU','requiresCustomOp':'Resampler','requiresFullPrecisionForCalibration':True,'detectorAxisAlignedOnly':detector,**({'samplingOrder':'uint8 source directly into Resampler; floating-point conversion on selected reads; crop rounding and normalization after sampling','fullFrameCast':False} if sample_bytes else {})})
        if probes:
            probes.mkdir(parents=True,exist_ok=True)
            for floating in [False,True]:
                fixture=make_model(detector,64,48,32,floating,sample_bytes)
                (probes/(name+('_float' if floating else '_byte')+'.tflite')).write_bytes(fixture.serialize(name+' host probe'))
    (output/('preprocessing_rgb_models.json' if sample_bytes else 'preprocessing_models.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def write_tile_model(output):
    """Write only the retained-frame landmark tile model; never replace full-frame assets."""
    output.mkdir(parents=True,exist_ok=True)
    name='landmark_preprocess_tile_rgb_gpu'
    g=make_model(False,768,768,sample_bytes=True)
    data=g.serialize(name+'; weightless; GPU Resampler; 768x768 retained VST tile; affine is tile-to-crop; RGB; OpenCV-style 1/32 sampling')
    path=output/(name+'.tflite');path.write_bytes(data)
    manifest=[{'name':name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'operators':[o[0] for o in g.operators],'inputImage':[1,768,768,3],'inputImageType':'uint8','affine':[1,1,1,6],'outputs':{'model_input':[1,256,256,3]},'exportCrop':'round(model_input*255) converted to uint8 by lab-only native operators','target':'GPU','requiresCustomOp':'Resampler','samplingOrder':'uint8 retained-frame tile directly into Resampler; floating-point conversion on selected reads; crop rounding and normalization after sampling','fullFrameCast':False,'fullFrameGraphTensor':False,'sourceTileBytes':768*768*3}]
    (output/'landmark_tile_preprocessing_rgb_model.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'FaceLandmarkerApp/src/main/assets/SpatialML/face-landmarker/model')
    p.add_argument('--probes',type=Path)
    p.add_argument('--sample-bytes',action='store_true',help='Generate separate RGB-first models without a full-frame CAST')
    p.add_argument('--tile-only',action='store_true',help='Write only the retained-frame 768x768 landmark model')
    args=p.parse_args()
    print(json.dumps(write_tile_model(args.output) if args.tile_only else write_models(args.output,args.probes,args.sample_bytes),indent=2))
