"""Prepare a standalone candidate USDA for managed Editor import; never edit a managed scene.

The supplied Sentinel GLB remains unchanged. Remove its disconnected neck skirt and
clip remaining shell/faceplate triangles at the canonical chin, preserving materials
and the original forehead hinge. Requires numpy and usd-core.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt


SOURCE_SHA = "7a0c46a03d56d866abe8be4be06ea31d5953b5cdb21d16a424f2fc13116210db"
CHIN_Y = .175
HEAD_CENTER = np.array([0, .26875, .00625])
HINGE = np.array([0, 2.7200000286102295, .03999999910593033]) * .125


def prepare(source: Path, output: Path):
    assert output.suffix == '.usda' and '/res3d/' not in str(output.resolve())
    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA, 'Reinspect a changed source model'
    length = struct.unpack_from('<I', raw, 12)[0]
    gltf = json.loads(raw[20:20 + length])
    binary = raw[28 + length:]

    def accessor(index):
        a = gltf['accessors'][index]
        view = gltf['bufferViews'][a['bufferView']]
        assert 'byteStride' not in view and 'sparse' not in a
        dtype = {5126: '<f4', 5125: '<u4', 5123: '<u2'}[a['componentType']]
        channels = {'VEC3': 3, 'VEC2': 2, 'VEC4': 4, 'SCALAR': 1}[a['type']]
        return np.frombuffer(binary, dtype=dtype, count=a['count'] * channels,
                             offset=view.get('byteOffset', 0) + a.get('byteOffset', 0)).reshape(-1, channels).astype(float)

    def components(vertices, triangles):
        _, weld = np.unique(np.round(vertices, 5), axis=0, return_inverse=True)
        parents = list(range(int(weld.max()) + 1))

        def find(x):
            while parents[x] != x:
                parents[x] = parents[parents[x]]
                x = parents[x]
            return x

        for a, b, c in weld[triangles]:
            parents[find(b)] = find(a)
            parents[find(c)] = find(a)
        groups = {}
        for face, triangle in enumerate(triangles):
            groups.setdefault(find(weld[triangle[0]]), []).append(face)
        return groups.values()

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError('Use a new candidate path; imported candidates are immutable')
    stage = Usd.Stage.CreateNew(str(output))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, '/SentinelHelmet')
    stage.SetDefaultPrim(root.GetPrim())
    root.GetPrim().SetCustomDataByKey('headCenterMeters', Gf.Vec3d(*HEAD_CENTER))
    hinge = UsdGeom.Xform.Define(stage, '/SentinelHelmet/FaceplateHinge')
    hinge.AddTranslateOp().Set(Gf.Vec3d(*HINGE))
    hinge.AddOrientOp().Set(Gf.Quatf(1, 0, 0, 0))
    UsdGeom.Xform.Define(stage, '/SentinelHelmet/FaceplateHinge/FaceplateMobileMesh')
    UsdGeom.Xform.Define(stage, '/SentinelHelmet/ShellMobileMesh')
    materials = []
    for i, definition in enumerate(gltf['materials']):
        pbr = definition['pbrMetallicRoughness']
        assert not any('Texture' in k for k in pbr), 'This source has constant materials'
        material = UsdShade.Material.Define(stage, f'/SentinelHelmet/Materials/M{i}')
        shader = UsdShade.Shader.Define(stage, f'{material.GetPath()}/Surface')
        shader.CreateIdAttr('UsdPreviewSurface')
        shader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*pbr.get('baseColorFactor', [1]*4)[:3]))
        shader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(pbr.get('metallicFactor', 1))
        shader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(pbr.get('roughnessFactor', 1))
        emission = np.array(definition.get('emissiveFactor', [0, 0, 0]), dtype=float)
        emission *= definition.get('extensions', {}).get('KHR_materials_emissive_strength', {}).get('emissiveStrength', 1)
        shader.CreateInput('emissiveColor', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*emission))
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), 'surface')
        materials.append(material)

    stats = {'sourceSha256': SOURCE_SHA, 'chinY': CHIN_Y, 'headCenter': HEAD_CENTER.tolist(),
             'hingePosition': HINGE.tolist(), 'removedNeckComponents': 0, 'sourceTriangles': 0, 'outputTriangles': 0}
    all_positions = []
    for mesh_index, mesh in enumerate(gltf['meshes']):
        for part, primitive in enumerate(mesh['primitives']):
            pos = accessor(primitive['attributes']['POSITION'])
            normals = accessor(primitive['attributes']['NORMAL'])
            faces = accessor(primitive['indices']).astype(int).reshape(-1, 3)
            stats['sourceTriangles'] += len(faces)
            if mesh_index == 0:
                world = pos * .125
            else:
                # Original ShellMobileMesh rotation is -90 degrees about Z, then translation.
                world = np.c_[pos[:, 1] - 1.1699999570846558,
                              2.8543503284454346 - pos[:, 0], pos[:, 2] - .09435028582811356] * .125
                normals = np.c_[normals[:, 1], -normals[:, 0], normals[:, 2]]
                kept = []
                for group in components(pos, faces):
                    points = world[faces[group]].reshape(-1, 3)
                    low, high = points.min(0), points.max(0)
                    outside_shell = high[0] - low[0] > .29 or min(abs(low[0]), abs(high[0])) > .145
                    if high[1] <= .26 and outside_shell:
                        stats['removedNeckComponents'] += 1
                    else:
                        kept.extend(group)
                faces = faces[kept]
            emitted = []
            for face in faces:
                polygon = [np.r_[world[v], normals[v]] for v in face]
                clipped = []
                previous = polygon[-1]
                for vertex in polygon:
                    inside, previous_inside = vertex[1] >= CHIN_Y, previous[1] >= CHIN_Y
                    if inside != previous_inside:
                        t = (CHIN_Y - previous[1]) / (vertex[1] - previous[1])
                        clipped.append(previous + t * (vertex - previous))
                    if inside:
                        clipped.append(vertex)
                    previous = vertex
                for i in range(1, len(clipped) - 1):
                    tri = np.array([clipped[0], clipped[i], clipped[i + 1]])
                    if np.linalg.norm(np.cross(tri[1, :3] - tri[0, :3], tri[2, :3] - tri[0, :3])) > 1e-12:
                        emitted.extend(tri)
            if not emitted:
                continue
            vertices = np.array(emitted)
            all_positions.append(vertices[:, :3].copy())
            if mesh_index == 0:
                vertices[:, :3] -= HINGE
            vertices[:, 3:] /= np.maximum(np.linalg.norm(vertices[:, 3:], axis=1, keepdims=True), 1e-12)
            parent = '/SentinelHelmet/FaceplateHinge/FaceplateMobileMesh' if mesh_index == 0 else '/SentinelHelmet/ShellMobileMesh'
            surface = UsdGeom.Mesh.Define(stage, f'{parent}/Part{part}')
            surface.CreateSubdivisionSchemeAttr('none')
            surface.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(vertices[:, :3].astype(np.float32)))
            surface.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(vertices[:, 3:].astype(np.float32)))
            surface.SetNormalsInterpolation('vertex')
            surface.CreateFaceVertexCountsAttr([3] * (len(vertices) // 3))
            surface.CreateFaceVertexIndicesAttr(list(range(len(vertices))))
            surface.CreateExtentAttr([Gf.Vec3f(*vertices[:, :3].min(0)), Gf.Vec3f(*vertices[:, :3].max(0))])
            UsdShade.MaterialBindingAPI.Apply(surface.GetPrim()).Bind(materials[primitive['material']])
            stats['outputTriangles'] += len(vertices) // 3
    points = np.concatenate(all_positions)
    assert points[:, 1].min() >= CHIN_Y - 1e-9
    assert stats['removedNeckComponents'] >= 6
    assert stats['outputTriangles'] < stats['sourceTriangles']
    stats['bounds'] = [points.min(0).tolist(), points.max(0).tolist()]
    stage.GetRootLayer().Save()
    stats['candidateSha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.json').write_text(json.dumps(stats, indent=2) + '\n')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.output)
