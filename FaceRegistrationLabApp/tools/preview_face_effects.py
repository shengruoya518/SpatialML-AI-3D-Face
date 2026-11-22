"""Preview exported production face-effect meshes without running the headset app.

This is a geometry preview with simple directional shading, not SDK render evidence.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np


def preview(source, output, effect, jaw_angle, fire):
    document = json.loads(source.read_text())
    prefix = {'cap': 'baseball-cap', 'dragon': 'dragon', 'helmet': 'scifi'}[effect]
    definitions = [mesh for mesh in document['meshes'] if mesh['name'].startswith(prefix)]
    fig = plt.figure(figsize=(8, 8), facecolor='#edf1f6')
    ax = fig.add_subplot(111, projection='3d', facecolor='#edf1f6')
    all_points = []
    all_faces = []
    all_colors = []
    light = np.array([-.35, .65, .68])
    light /= np.linalg.norm(light)
    for mesh in definitions:
        is_fire = 'flame' in mesh['name'] or 'fire' in mesh['name']
        if is_fire and not fire:
            continue
        vertices = np.array(mesh['vertices']).reshape(-1, 3)
        if mesh['jaw']:
            c, s = np.cos(jaw_angle), np.sin(jaw_angle)
            rotation = np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
            vertices = vertices @ rotation.T + [0, -.037, .037]
        if is_fire:
            vertices = vertices * [.52, .52, .57] + [0, -.043, .20]
        faces = vertices[np.array(mesh['indices']).reshape(-1, 3)]
        normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
        normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
        illumination = .50 + .50 * np.maximum(normals @ light, 0)
        color = np.array(mesh['color'])
        colors = np.tile(color, (len(faces), 1))
        colors[:, :3] *= illumination[:, None]
        # Matplotlib uses Z-up; production geometry uses Y-up and forward +Z.
        all_faces.append(faces[:, :, [0, 2, 1]])
        all_colors.append(colors)
        all_points.append(vertices[:, [0, 2, 1]])
    # Sort triangles across the whole assembly; per-mesh painter sorting hides facial details.
    ax.add_collection3d(Poly3DCollection(np.concatenate(all_faces), facecolors=np.concatenate(all_colors),
                                        edgecolors='none', zsort='average'))
    points = np.concatenate(all_points)
    lower, upper = points.min(axis=0), points.max(axis=0)
    center = (lower + upper) * .5
    half = max(upper - lower) * .62
    ax.set_xlim(center[0] - half, center[0] + half)
    ax.set_ylim(center[1] - half, center[1] + half)
    ax.set_zlim(center[2] - half, center[2] + half)
    ax.set_proj_type('ortho')
    ax.set_box_aspect((1, 1, 1), zoom=1.45)
    ax.view_init(elev=18, azim=65)
    ax.set_axis_off()
    title = {'cap': 'Baseball cap', 'helmet': 'Closed helmet · view from +Z',
             'dragon': 'Chinese dragon · jaw open' if jaw_angle else 'Chinese dragon · jaw closed'}[effect]
    if fire:
        title += ' · fire'
    fig.text(.5, .95, title, ha='center', fontsize=20, color='#17283e')
    fig.text(.5, .055, 'Production mesh geometry · front three-quarter view\nHost preview; headset materials and attachment fit need runtime validation',
             ha='center', fontsize=10, color='#526379')
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--effect', choices=('cap', 'dragon', 'helmet'), required=True)
    parser.add_argument('--jaw', type=float, default=0)
    parser.add_argument('--fire', action='store_true')
    args = parser.parse_args()
    preview(args.geometry, args.output, args.effect, args.jaw, args.fire)
