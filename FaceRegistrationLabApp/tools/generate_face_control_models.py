"""Generate fused weightless CPU control models for the face pipeline.

The detector models replace decode_detection, prepare_roi, lab_camera,
lab_affine and lab_frame_snapshot without hiding persistent state.  The
tracking variant deliberately omits detector decoding so normal tracked frames
do not pay for 896-anchor post-processing.  A small GPU model handles the
fixed crop from a logical 336x256 view, using square 336x336 VST access to avoid
the shipped service's reversed non-square resize dimensions.

The landmark model is added below in the same generator so both stateful
boundaries share one explicit tensor ABI and one parity harness.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import tflite as fb

from generate_face_inline_geometry import InlineFitGraph
from generate_face_geometry import ASSETS
from generate_face_preprocessing import Graph


FLOAT_MAX = np.finfo(np.float32).max


class TensorOps:
    """Static-shape helpers shared by the detector and landmark graphs."""

    def input_tensor(self, name, shape, dtype=fb.TensorType.FLOAT32):
        tensor = self.tensor(name, shape, dtype)
        self.inputs.append(tensor)
        return tensor

    def input_flat(self, name, size, dtype=fb.TensorType.FLOAT32):
        return self.input_tensor(name, [1, 1, 1, size], dtype)

    def reshape(self, tensor, shape, name=None):
        target = self.tensor('shape_' + str(len(self.tensors)), [len(shape)], fb.TensorType.INT32, shape)
        return self.op('RESHAPE', [tensor, target], shape, name)

    def gather(self, tensor, indices, axis=3, name=None):
        ids = self.tensor('indices_' + str(len(self.tensors)), [len(indices)], fb.TensorType.INT32, indices)
        shape = self.tensors[tensor].shape.copy()
        shape[axis] = len(indices)
        return self.op(
            'GATHER',
            [tensor, ids],
            shape,
            name,
            {'axis': axis},
            dtype=self.tensors[tensor].dtype,
        )

    def dynamic_gather(self, tensor, index, axis, shape, name=None):
        index = self.reshape(index, [1])
        if self.tensors[index].dtype != fb.TensorType.INT32:
            index = self.op('CAST', [index], [1], dtype=fb.TensorType.INT32)
        return self.op('GATHER', [tensor, index], shape, name, {'axis': axis})

    def reduce(self, kind, tensor, axes, name=None):
        ids = self.tensor('reduce_axes_' + str(len(self.tensors)), [len(axes)], fb.TensorType.INT32, axes)
        shape = self.tensors[tensor].shape.copy()
        for axis in axes:
            shape[axis] = 1
        return self.op(kind, [tensor, ids], shape, name)

    def concat(self, tensors, axis=3, name=None):
        shape = self.tensors[tensors[0]].shape.copy()
        shape[axis] = sum(self.tensors[t].shape[axis] for t in tensors)
        return self.op('CONCATENATION', tensors, shape, name, {'axis': axis})

    def compare(self, kind, left, right):
        shape = np.broadcast_shapes(self.tensors[left].shape, self.tensors[right].shape)
        return self.op(kind, [left, right], shape, dtype=fb.TensorType.BOOL)

    def choose(self, condition, yes, no, name=None):
        shape = np.broadcast_shapes(self.tensors[condition].shape, self.tensors[yes].shape, self.tensors[no].shape)
        return self.op('SELECT_V2', [condition, yes, no], shape, name)

    def logical(self, kind, *values):
        shape = np.broadcast_shapes(*(self.tensors[v].shape for v in values))
        return self.op(kind, list(values), shape, dtype=fb.TensorType.BOOL)

    def finite(self, value):
        return self.compare('LESS_EQUAL', self.op('ABS', [value], self.tensors[value].shape), self.maximum_finite)

    def all_true(self, condition, axes):
        numeric = self.op('CAST', [condition], self.tensors[condition].shape)
        return self.compare('GREATER', self.reduce('REDUCE_MIN', numeric, axes), self.half)

    def any_true(self, condition, axes):
        numeric = self.op('CAST', [condition], self.tensors[condition].shape)
        return self.compare('GREATER', self.reduce('REDUCE_MAX', numeric, axes), self.half)

    def clip(self, value, lower, upper):
        return self.binary('MINIMUM', self.binary('MAXIMUM', value, lower), upper)

    def negate(self, value):
        return self.binary('SUB', self.zero, value)

    def square(self, value):
        return self.binary('MUL', value, value)

    def norm(self, values):
        total = self.square(values[0])
        for value in values[1:]:
            total = self.binary('ADD', total, self.square(value))
        return self.op('SQRT', [total], self.tensors[total].shape)

    def scalar_components(self, value):
        return [self.component(value, index) for index in range(self.tensors[value].shape[-1])]

    def first_index(self, condition, axis, count):
        shape = [1, 1, 1, 1]
        indices_shape = [1, 1, count, 1] if axis == 2 else [1, 1, 1, count]
        indices = self.tensor('ordered_indices_' + str(len(self.tensors)), indices_shape,
                              values=np.arange(count, dtype=np.float32).reshape(indices_shape))
        sentinel = self.constant('index_sentinel_' + str(len(self.tensors)), count)
        selected = self.choose(condition, indices, sentinel)
        return self.reduce('REDUCE_MIN', selected, [axis])


class ControlGraph(TensorOps, Graph):
    def __init__(self):
        super().__init__()
        self.zero = self.constant('zero', 0)
        self.one = self.constant('one', 1)
        self.half = self.constant('half', .5)
        self.maximum_finite = self.constant('maximum_finite', FLOAT_MAX)
        self.true = self.compare('GREATER', self.one, self.zero)
        self.false = self.compare('LESS', self.one, self.zero)


class LandmarkGraph(TensorOps, InlineFitGraph):
    def __init__(self, canonical):
        super().__init__(canonical)
        self.half = self.constant('half', .5)
        self.maximum_finite = self.constant('maximum_finite', FLOAT_MAX)
        self.true = self.compare('GREATER', self.one, self.zero)
        self.false = self.compare('LESS', self.one, self.zero)


def track_landmarks(g, raw_flat, presence, roi, settings, frame, intrinsics, state_tensor, fit_indices):
    raw = g.reshape(raw_flat, [1, 1, 478, 3])
    raw_xyz = [g.gather(raw, [axis], axis=3) for axis in range(3)]
    # Constant gather is used here; keep dynamic_gather reserved for scalar runtime indices.
    face_ids = g.tensor('face_point_indices', [468], fb.TensorType.INT32, range(468))
    face = g.op('GATHER', [raw, face_ids], [1, 1, 468, 3], options={'axis': 2})
    face_x = g.gather(face, [0], axis=3)
    face_y = g.gather(face, [1], axis=3)
    min_x = g.reduce('REDUCE_MIN', face_x, [2])
    max_x = g.reduce('REDUCE_MAX', face_x, [2])
    min_y = g.reduce('REDUCE_MIN', face_y, [2])
    max_y = g.reduce('REDUCE_MAX', face_y, [2])
    extent = g.binary('MAXIMUM', g.binary('SUB', max_x, min_x), g.binary('SUB', max_y, min_y))

    roi_parts = g.scalar_components(roi)
    settings_parts = g.scalar_components(settings)
    frame_parts = g.scalar_components(frame)
    state = g.scalar_components(state_tensor)
    intrinsics_flat = g.reshape(intrinsics, [1, 1, 1, 9])
    k = g.scalar_components(intrinsics_flat)
    probability = g.op('LOGISTIC', [g.component(presence, 0)], [1, 1, 1, 1])
    age = g.binary('ADD', g.binary('SUB', frame_parts[0], state[1]),
                   g.binary('SUB', frame_parts[1], state[2]))
    retained = g.logical('LOGICAL_AND', g.compare('GREATER', state[0], g.zero),
                         g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', age, g.zero),
                                   g.compare('LESS_EQUAL', age, settings_parts[6])))
    threshold = g.choose(retained, settings_parts[5], settings_parts[3])
    probability_good = g.logical('LOGICAL_AND', g.finite(probability),
                                 g.compare('GREATER_EQUAL', probability, threshold))
    roi_bad = g.logical('LOGICAL_OR', g.compare('LESS_EQUAL', roi_parts[0], g.zero),
                        g.logical('LOGICAL_NOT', probability_good))
    frame_bad = g.compare('LESS_EQUAL', frame_parts[3], g.zero)
    intrinsics_good = g.logical('LOGICAL_AND', g.all_true(g.finite(intrinsics_flat), [3]),
                                g.logical('LOGICAL_AND', g.compare('GREATER', k[0], g.zero),
                                          g.compare('GREATER', k[4], g.zero)))
    intrinsics_bad = g.logical('LOGICAL_NOT', intrinsics_good)
    raw_good = g.all_true(g.logical('LOGICAL_AND', g.finite(raw),
                                    g.compare('LESS_EQUAL', g.op('ABS', [raw], [1, 1, 478, 3]),
                                              g.constant('landmark_abs_limit', 512))), [2, 3])
    extent_good = g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', extent, g.constant('minimum_extent', 24)),
                            g.logical('LOGICAL_AND', g.compare('LESS_EQUAL', extent, g.constant('maximum_extent', 300)),
                                      g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', min_x, g.constant('minimum_crop_coordinate', -48)),
                                                g.logical('LOGICAL_AND', g.compare('LESS_EQUAL', max_x, g.constant('maximum_crop_coordinate_x', 304)),
                                                          g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', min_y, g.constant('minimum_crop_coordinate_y', -48)),
                                                                    g.compare('LESS_EQUAL', max_y, g.constant('maximum_crop_coordinate_y', 304)))))))
    raw_bad = g.logical('LOGICAL_NOT', g.logical('LOGICAL_AND', raw_good, extent_good))
    reason = g.choose(roi_bad, g.one, g.zero)
    reason = g.choose(frame_bad, g.constant('stale_reason', 3), reason)
    reason = g.choose(intrinsics_bad, g.constant('calibration_reason', 4), reason)
    reason = g.choose(raw_bad, g.constant('landmark_reason', 2), reason)
    valid = g.compare('EQUAL', reason, g.zero)
    validity = g.concat([g.op('CAST', [valid], [1, 1, 1, 1]),
                         g.choose(g.finite(probability), probability, g.zero)], name='tracked_validity')

    width, height, side = settings_parts[0], settings_parts[1], roi_parts[4]
    cosine = g.op('COS', [roi_parts[5]], [1, 1, 1, 1])
    sine = g.op('SIN', [roi_parts[5]], [1, 1, 1, 1])
    crop_x = g.binary('SUB', g.binary('DIV', raw_xyz[0], g.constant('landmark_crop_size_x', 256)), g.half)
    crop_y = g.binary('SUB', g.binary('DIV', raw_xyz[1], g.constant('landmark_crop_size_y', 256)), g.half)
    pixel_x = g.binary('ADD', roi_parts[2], g.binary('MUL', side,
                         g.binary('SUB', g.binary('MUL', cosine, crop_x), g.binary('MUL', sine, crop_y))))
    pixel_y = g.binary('ADD', roi_parts[3], g.binary('MUL', side,
                         g.binary('ADD', g.binary('MUL', sine, crop_x), g.binary('MUL', cosine, crop_y))))
    point_x = g.binary('DIV', pixel_x, width)
    point_y = g.binary('DIV', pixel_y, height)
    point_z = g.binary('MUL', g.binary('DIV', raw_xyz[2], g.constant('landmark_crop_size_z', 256)),
                       g.binary('DIV', side, width))
    points = g.concat([point_x, point_y, point_z], name='normalized_landmarks')
    selected = g.gather(points, fit_indices, axis=2)
    selected_xyz = [g.gather(selected, [axis], axis=3) for axis in range(3)]
    projected = g.concat([g.binary('DIV', g.binary('SUB', g.binary('MUL', selected_xyz[0], width), k[2]), k[0]),
                          g.binary('DIV', g.binary('SUB', k[5], g.binary('MUL', selected_xyz[1], height)), k[4]),
                          g.binary('DIV', g.binary('MUL', selected_xyz[2], width), k[0])], name='projected')
    projected = g.choose(valid, projected, g.zero, 'valid_projected')
    targets = g.concat([g.gather(projected, [0, 1], axis=3), g.negate(g.gather(projected, [2], axis=3))])
    targets = g.choose(valid, targets, g.points, 'first_targets')
    face_z_ids = g.tensor('face_z_indices', [468], fb.TensorType.INT32, range(468))
    face_z = g.op('GATHER', [point_z, face_z_ids], [1, 1, 468, 1], options={'axis': 2})
    depth = g.binary('DIV', g.reduce('SUM', g.binary('MUL', face_z, g.binary('DIV', width, k[0])), [2]),
                     g.constant('face_point_count', 468), 'depth')
    depth = g.choose(valid, depth, g.zero, 'depth_offset')

    center_x = g.binary('SUB', g.binary('MUL', g.binary('ADD', min_x, max_x), g.constant('bounds_scale', 1/512)), g.half)
    center_y = g.binary('SUB', g.binary('MUL', g.binary('ADD', min_y, max_y), g.constant('bounds_scale_y', 1/512)), g.half)
    next_x = g.binary('ADD', roi_parts[2], g.binary('MUL', side,
                       g.binary('SUB', g.binary('MUL', cosine, center_x), g.binary('MUL', sine, center_y))))
    next_y = g.binary('ADD', roi_parts[3], g.binary('MUL', side,
                       g.binary('ADD', g.binary('MUL', sine, center_x), g.binary('MUL', cosine, center_y))))
    next_side = g.clip(g.binary('MUL', g.binary('MUL', side, extent), g.constant('next_roi_scale', 1.5/256)),
                       g.constant('minimum_next_roi', 32), g.binary('MAXIMUM', width, height))
    eye_263 = g.dynamic_gather(points, g.constant('right_eye_index', 263), 2, [1, 1, 1, 3])
    eye_33 = g.dynamic_gather(points, g.constant('left_eye_index', 33), 2, [1, 1, 1, 3])
    right = g.scalar_components(eye_263)
    left = g.scalar_components(eye_33)
    eye_x = g.binary('MUL', g.binary('SUB', right[0], left[0]), width)
    eye_y = g.binary('MUL', g.binary('SUB', right[1], left[1]), height)
    measured = g.op('ATAN2', [eye_y, eye_x], [1, 1, 1, 1])
    roll_delta = g.binary('SUB', measured, roi_parts[5])
    wrapped = g.op('ATAN2', [g.op('SIN', [roll_delta], [1, 1, 1, 1]),
                             g.op('COS', [roll_delta], [1, 1, 1, 1])], [1, 1, 1, 1])
    roll = g.binary('ADD', roi_parts[5], g.clip(wrapped, g.constant('roll_step_min', -.2),
                                               g.constant('roll_step_max', .2)))
    roll = g.choose(g.compare('GREATER', g.norm([eye_x, eye_y]),
                              g.binary('MUL', next_side, g.constant('eye_separation_ratio', .18))),
                    roll, roi_parts[5])
    velocity_limit = g.binary('MUL', next_side, g.constant('velocity_limit_scale', 2))
    velocity_enabled = g.logical('LOGICAL_AND', retained, g.compare('GREATER_EQUAL', age, g.constant('velocity_dt_floor', .005)))

    def velocity(value, old, previous, name):
        measured_velocity = g.clip(g.binary('DIV', g.binary('SUB', value, old), age),
                                   g.negate(velocity_limit), velocity_limit)
        filtered = g.binary('MUL', g.binary('ADD', previous, measured_velocity), g.half, name)
        return g.choose(velocity_enabled, filtered, g.zero)

    next_state = list(state)
    next_state[16] = frame_parts[4]
    next_state[17] = reason
    frame_fresh = g.compare('GREATER', frame_parts[3], g.zero)
    next_state[13] = g.choose(frame_fresh, frame_parts[0], state[13])
    next_state[14] = g.choose(frame_fresh, frame_parts[1], state[14])
    next_state[18] = g.choose(frame_fresh, g.one, state[18])
    failure_count = g.binary('ADD', state[10], g.one)
    retry = g.logical('LOGICAL_AND', retained,
                      g.logical('LOGICAL_AND', g.compare('LESS_EQUAL', failure_count, g.one),
                                g.logical('LOGICAL_AND', g.compare('NOT_EQUAL', reason, g.constant('not_stale_reason', 3)),
                                          g.compare('NOT_EQUAL', reason, g.constant('not_calibration_reason', 4)))))
    failure_state = g.choose(retry, g.constant('local_retry_state', 2), g.zero)
    success_values = {
        0: g.one, 1: frame_parts[0], 2: frame_parts[1], 3: next_x, 4: next_y,
        5: next_side, 6: roll,
        7: velocity(next_x, state[3], state[7], 'velocity_x'),
        8: velocity(next_y, state[4], state[8], 'velocity_y'),
        9: velocity(next_side, state[5], state[9], 'velocity_side'),
        10: g.zero, 11: g.choose(retained, state[11], g.binary('ADD', state[11], g.one)),
        12: roi_parts[1], 15: probability,
    }
    failure_values = {0: failure_state, 10: failure_count}
    for index in range(24):
        success = success_values.get(index, next_state[index])
        failure = failure_values.get(index, next_state[index])
        next_state[index] = g.choose(valid, success, failure)
    return (projected, targets, depth, validity, g.concat(next_state, name='tracked_state'),
            points, raw, reason)


def inline_fit(g, first_targets, projected, depth, validity):
    targets = first_targets
    scales, stages = [], []
    for step in range(3):
        covariance, centers = g.covariance(targets)
        rotation = g.rotation(covariance)
        if step == 2:
            pose = g.solve_rotation(targets, centers, rotation, pose=True)
            break
        scale = g.solve_rotation(targets, centers, rotation)
        scales.append(scale)
        targets = g.unproject(projected, depth, g.one if step == 0 else scales[0], scale, validity)
        stages.append(targets)
    return scales[0], scales[1], stages[0], stages[1], pose


def pose_and_diagnostics(g, pose, validity, camera, command, settings, frame,
                         track_state_tensor, pose_state_tensor, projected, metric, roi, intrinsics):
    pose_flat = g.reshape(pose, [1, 1, 1, 16])
    pp = g.scalar_components(pose_flat)
    camera_flat = g.reshape(camera, [1, 1, 1, 16])
    command_parts = g.scalar_components(command)
    settings_parts = g.scalar_components(settings)
    frame_parts = g.scalar_components(frame)
    track = g.scalar_components(track_state_tensor)
    previous = g.scalar_components(pose_state_tensor)
    size_scale = g.choose(g.logical('LOGICAL_AND', g.finite(command_parts[2]),
                                    g.compare('GREATER', command_parts[2], g.zero)),
                          g.clip(command_parts[2], g.half, g.constant('maximum_size_scale', 1.5)), g.one)
    base_scale = g.norm([pp[0], pp[4], pp[8]])
    scale = g.binary('MUL', base_scale, size_scale)
    metric_parts = []
    for row in range(4):
        for column in range(4):
            value = pp[row * 4 + column]
            if row < 3:
                value = g.binary('MUL', value, size_scale)
                if column == 3:
                    value = g.binary('MUL', value, g.constant('centimeters_to_meters', .01))
            metric_parts.append(value)
    metric_matrix = g.reshape(g.concat(metric_parts), [1, 1, 4, 4])
    raw_matrix = g.op('BATCH_MATMUL', [camera, metric_matrix], [1, 1, 4, 4])
    raw_flat = g.reshape(raw_matrix, [1, 1, 1, 16])
    rp = g.scalar_components(raw_flat)
    good = g.logical('LOGICAL_AND', g.compare('GREATER', g.component(validity, 0), g.zero),
                     g.logical('LOGICAL_AND', g.all_true(g.finite(pose_flat), [3]),
                               g.all_true(g.finite(camera_flat), [3])))
    good = g.logical('LOGICAL_AND', good,
                     g.logical('LOGICAL_AND', g.compare('GREATER', base_scale, g.constant('minimum_pose_scale', .05)),
                               g.logical('LOGICAL_AND', g.compare('LESS', base_scale, g.constant('maximum_pose_scale', 20)),
                                         g.logical('LOGICAL_AND', g.compare('LESS', pp[11], g.constant('near_depth', -1)),
                                                   g.compare('GREATER', pp[11], g.constant('far_depth', -1000))))))
    raw_finite = g.all_true(g.finite(raw_flat), [3])
    raw_good = g.logical('LOGICAL_AND', good, raw_finite)
    r = [g.binary('DIV', rp[index], scale) for index in (0, 1, 2, 4, 5, 6, 8, 9, 10)]
    trace = g.binary('ADD', g.binary('ADD', r[0], r[4]), r[8])

    def sqrt4(value, name):
        return g.binary('MUL', g.constant(name, 2),
                        g.op('SQRT', [g.binary('MAXIMUM', value, g.zero)], [1, 1, 1, 1]))

    t0 = sqrt4(g.binary('ADD', trace, g.one), 'trace_scale')
    q0 = [g.binary('DIV', g.binary('SUB', r[7], r[5]), t0),
          g.binary('DIV', g.binary('SUB', r[2], r[6]), t0),
          g.binary('DIV', g.binary('SUB', r[3], r[1]), t0), g.binary('MUL', t0, g.constant('quarter_0', .25))]
    t1 = sqrt4(g.binary('SUB', g.binary('ADD', g.one, r[0]), g.binary('ADD', r[4], r[8])), 'x_scale')
    q1 = [g.binary('MUL', t1, g.constant('quarter_1', .25)), g.binary('DIV', g.binary('ADD', r[1], r[3]), t1),
          g.binary('DIV', g.binary('ADD', r[2], r[6]), t1), g.binary('DIV', g.binary('SUB', r[7], r[5]), t1)]
    t2 = sqrt4(g.binary('SUB', g.binary('ADD', g.one, r[4]), g.binary('ADD', r[0], r[8])), 'y_scale')
    q2 = [g.binary('DIV', g.binary('ADD', r[1], r[3]), t2), g.binary('MUL', t2, g.constant('quarter_2', .25)),
          g.binary('DIV', g.binary('ADD', r[5], r[7]), t2), g.binary('DIV', g.binary('SUB', r[2], r[6]), t2)]
    t3 = sqrt4(g.binary('SUB', g.binary('ADD', g.one, r[8]), g.binary('ADD', r[0], r[4])), 'z_scale')
    q3 = [g.binary('DIV', g.binary('ADD', r[2], r[6]), t3), g.binary('DIV', g.binary('ADD', r[5], r[7]), t3),
          g.binary('MUL', t3, g.constant('quarter_3', .25)), g.binary('DIV', g.binary('SUB', r[3], r[1]), t3)]
    trace_case = g.compare('GREATER', trace, g.zero)
    x_case = g.logical('LOGICAL_AND', g.compare('GREATER', r[0], r[4]), g.compare('GREATER', r[0], r[8]))
    y_case = g.compare('GREATER', r[4], r[8])
    q = [g.choose(trace_case, q0[index], g.choose(x_case, q1[index], g.choose(y_case, q2[index], q3[index])))
         for index in range(4)]
    q_norm = g.norm(q)
    q = [g.binary('DIV', value, q_norm) for value in q]
    p = [rp[3], rp[7], rp[11]]
    age = g.binary('ADD', g.binary('SUB', frame_parts[0], previous[0]),
                   g.binary('SUB', frame_parts[1], previous[1]))
    same_scale = g.compare('LESS', g.op('ABS', [g.binary('SUB', previous[19], size_scale)], [1, 1, 1, 1]),
                           g.constant('size_scale_epsilon', 1e-6))
    smooth = g.logical('LOGICAL_AND', g.compare('GREATER', settings_parts[4], g.zero),
                       g.logical('LOGICAL_AND', g.compare('GREATER', previous[2], g.zero),
                                 g.logical('LOGICAL_AND', g.compare('EQUAL', previous[3], track[11]),
                                           g.logical('LOGICAL_AND', g.compare('GREATER', age, g.zero),
                                                     g.logical('LOGICAL_AND', g.compare('LESS', age, g.half), same_scale)))))
    speed = g.norm([g.binary('DIV', g.binary('SUB', p[index], previous[12 + index]), age) for index in range(3)])
    dot = g.zero
    for index in range(4):
        dot = g.binary('ADD', dot, g.binary('MUL', q[index], previous[15 + index]))
    dot_abs = g.binary('MINIMUM', g.one, g.op('ABS', [dot], [1, 1, 1, 1]))
    acos = g.op('ATAN2', [g.op('SQRT', [g.binary('MAXIMUM', g.zero,
                                                  g.binary('SUB', g.one, g.square(dot_abs)))], [1, 1, 1, 1]),
                          dot_abs], [1, 1, 1, 1])
    angle_speed = g.binary('DIV', g.binary('MUL', g.constant('double_angle', 2), acos), age)
    two_pi = g.constant('two_pi', 2 * np.pi)
    alpha = g.binary('SUB', g.one, g.op('EXP', [g.negate(g.binary('MUL', two_pi,
                       g.binary('MUL', g.binary('ADD', g.constant('position_cutoff', 4),
                                                          g.binary('MUL', g.constant('position_speed_gain', 12), speed)), age)))], [1, 1, 1, 1]))
    beta = g.binary('SUB', g.one, g.op('EXP', [g.negate(g.binary('MUL', two_pi,
                      g.binary('MUL', g.binary('ADD', g.constant('angle_cutoff', 4),
                                                         g.binary('MUL', g.constant('angle_speed_gain', 3), angle_speed)), age)))], [1, 1, 1, 1]))
    filtered_p = [g.binary('ADD', previous[5 + index],
                           g.binary('MUL', alpha, g.binary('SUB', p[index], previous[5 + index]))) for index in range(3)]
    sign = g.choose(g.compare('LESS', sum_dot(g, q, previous[8:12]), g.zero), g.constant('negative_quaternion', -1), g.one)
    blended_q = [g.binary('ADD', previous[8 + index],
                          g.binary('MUL', beta, g.binary('SUB', g.binary('MUL', sign, q[index]), previous[8 + index])))
                 for index in range(4)]
    blended_norm = g.norm(blended_q)
    blended_q = [g.binary('DIV', value, blended_norm) for value in blended_q]
    scale_alpha = g.binary('SUB', g.one, g.op('EXP', [g.negate(g.binary('MUL',
                         g.binary('MUL', two_pi, g.constant('scale_cutoff', 5)), age))], [1, 1, 1, 1]))
    filtered_scale = g.op('EXP', [g.binary('ADD', g.op('LOG', [previous[4]], [1, 1, 1, 1]),
                              g.binary('MUL', scale_alpha, g.binary('SUB', g.op('LOG', [scale], [1, 1, 1, 1]),
                                                                  g.op('LOG', [previous[4]], [1, 1, 1, 1]))))], [1, 1, 1, 1])
    final_p = [g.choose(smooth, filtered_p[index], p[index]) for index in range(3)]
    final_q = [g.choose(smooth, blended_q[index], q[index]) for index in range(4)]
    final_scale = g.choose(smooth, filtered_scale, scale)
    filtered = quaternion_matrix(g, final_q, final_scale, final_p, 'filtered_world_pose')
    accepted = g.logical('LOGICAL_AND', good, g.all_true(g.finite(filtered), [2, 3]))
    identity = g.tensor('identity_pose', [1, 1, 4, 4], values=np.eye(4, dtype=np.float32))
    raw_world = g.choose(raw_good, raw_matrix, identity, 'raw_world_pose')

    next_track = list(track)
    failed_without_reason = g.logical('LOGICAL_AND', g.logical('LOGICAL_NOT', accepted),
                                      g.compare('EQUAL', track[17], g.zero))
    next_track[17] = g.choose(failed_without_reason, g.constant('pose_failure_reason', 5), track[17])
    next_track[0] = g.choose(failed_without_reason, g.zero, track[0])
    track_after_pose = g.concat(next_track, name='pose_track_state')
    held = g.logical('LOGICAL_AND', g.logical('LOGICAL_NOT', accepted),
                     g.logical('LOGICAL_AND', g.compare('GREATER', previous[2], g.zero),
                               g.logical('LOGICAL_AND', same_scale,
                                         g.logical('LOGICAL_AND', g.compare('GREATER', frame_parts[3], g.zero),
                                                   g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', age, g.zero),
                                                             g.logical('LOGICAL_AND', g.compare('LESS_EQUAL', age, settings_parts[8]),
                                                                       g.logical('LOGICAL_AND', g.compare('NOT_EQUAL', next_track[17], g.constant('held_stale_reason', 3)),
                                                                                 g.compare('NOT_EQUAL', next_track[17], g.constant('held_calibration_reason', 4)))))))))
    held_pose = quaternion_matrix(g, previous[8:12], previous[4], previous[5:8], 'held_world_pose')
    world = g.choose(accepted, filtered, g.choose(held, held_pose, identity), 'world_pose')
    status = g.choose(accepted, g.one, g.choose(held, g.constant('held_status', 2), g.zero), 'pose_status')
    validity_parts = g.scalar_components(validity)
    validity_after_pose = g.concat([g.choose(accepted, validity_parts[0], g.zero), validity_parts[1]], name='pose_validity')
    next_pose = list(previous)
    for index, value in {0: frame_parts[0], 1: frame_parts[1], 2: g.one, 3: next_track[11], 4: final_scale,
                         5: final_p[0], 6: final_p[1], 7: final_p[2],
                         8: final_q[0], 9: final_q[1], 10: final_q[2], 11: final_q[3],
                         12: p[0], 13: p[1], 14: p[2],
                         15: q[0], 16: q[1], 17: q[2], 18: q[3], 19: size_scale}.items():
        next_pose[index] = g.choose(accepted, value, next_pose[index])
    next_pose[2] = g.choose(g.logical('LOGICAL_OR', accepted, held), next_pose[2], g.zero)
    pose_state = g.concat(next_pose, name='next_pose_state')

    diagnostics, final_validity, final_track = registration_diagnostics(
        g, projected, metric, pose, validity_after_pose, roi, intrinsics, frame, command,
        track_after_pose, status)
    return (pose_state, final_track, final_validity, world, raw_world, status, diagnostics)


def sum_dot(g, left, right):
    result = g.zero
    for a, b in zip(left, right):
        result = g.binary('ADD', result, g.binary('MUL', a, b))
    return result


def quaternion_matrix(g, q, scale, position, name):
    x, y, z, w = q
    two = g.constant('quaternion_two_' + str(len(g.tensors)), 2)
    one = g.one
    values = [g.binary('MUL', g.binary('SUB', one, g.binary('MUL', two, g.binary('ADD', g.square(y), g.square(z)))), scale),
              g.binary('MUL', g.binary('MUL', two, g.binary('SUB', g.binary('MUL', x, y), g.binary('MUL', z, w))), scale),
              g.binary('MUL', g.binary('MUL', two, g.binary('ADD', g.binary('MUL', x, z), g.binary('MUL', y, w))), scale), position[0],
              g.binary('MUL', g.binary('MUL', two, g.binary('ADD', g.binary('MUL', x, y), g.binary('MUL', z, w))), scale),
              g.binary('MUL', g.binary('SUB', one, g.binary('MUL', two, g.binary('ADD', g.square(x), g.square(z)))), scale),
              g.binary('MUL', g.binary('MUL', two, g.binary('SUB', g.binary('MUL', y, z), g.binary('MUL', x, w))), scale), position[1],
              g.binary('MUL', g.binary('MUL', two, g.binary('SUB', g.binary('MUL', x, z), g.binary('MUL', y, w))), scale),
              g.binary('MUL', g.binary('MUL', two, g.binary('ADD', g.binary('MUL', y, z), g.binary('MUL', x, w))), scale),
              g.binary('MUL', g.binary('SUB', one, g.binary('MUL', two, g.binary('ADD', g.square(x), g.square(y)))), scale), position[2],
              g.zero, g.zero, g.zero, g.one]
    return g.reshape(g.concat(values), [1, 1, 4, 4], name)


def registration_diagnostics(g, projected, metric, pose, validity, roi, intrinsics,
                             frame, command, track_state, pose_status):
    p = [g.gather(projected, [axis], axis=3) for axis in range(3)]
    m = [g.gather(metric, [axis], axis=3) for axis in range(3)]
    k = g.scalar_components(g.reshape(intrinsics, [1, 1, 1, 9]))
    frame_parts = g.scalar_components(frame)
    command_parts = g.scalar_components(command)
    track = g.scalar_components(track_state)
    roi_parts = g.scalar_components(roi)
    validity_parts = g.scalar_components(validity)
    x = g.binary('ADD', k[2], g.binary('MUL', k[0], p[0]))
    y = g.binary('SUB', k[5], g.binary('MUL', k[4], p[1]))
    u = g.binary('ADD', k[2], g.binary('DIV', g.binary('MUL', k[0], m[0]), g.negate(m[2])))
    v = g.binary('SUB', k[5], g.binary('DIV', g.binary('MUL', k[4], m[1]), g.negate(m[2])))
    error = g.norm([g.binary('SUB', u, x), g.binary('SUB', v, y)])
    sum_error = g.reduce('SUM', g.square(error), [2])
    max_error = g.reduce('REDUCE_MAX', error, [2])
    min_x, max_x = g.reduce('REDUCE_MIN', x, [2]), g.reduce('REDUCE_MAX', x, [2])
    min_y, max_y = g.reduce('REDUCE_MIN', y, [2]), g.reduce('REDUCE_MAX', y, [2])
    min_u, max_u = g.reduce('REDUCE_MIN', u, [2]), g.reduce('REDUCE_MAX', u, [2])
    min_v, max_v = g.reduce('REDUCE_MIN', v, [2]), g.reduce('REDUCE_MAX', v, [2])
    width = g.binary('MAXIMUM', g.one, g.binary('SUB', max_x, min_x))
    height = g.binary('MAXIMUM', g.one, g.binary('SUB', max_y, min_y))
    rotation = g.op('SLICE', [pose,
        g.tensor('pose_rotation_begin', [4], fb.TensorType.INT32, [0, 0, 0, 0]),
        g.tensor('pose_rotation_size', [4], fb.TensorType.INT32, [1, 1, 3, 3])], [1, 1, 3, 3])
    translation = g.gather(g.reshape(pose, [1, 1, 1, 16]), [3, 7, 11])
    fitted = g.binary('ADD', g.op('BATCH_MATMUL', [g.points, rotation], [1, 1, 33, 3], options={'adj_y': True}), translation)
    fitted_xyz = [g.gather(fitted, [axis], axis=3) for axis in range(3)]
    fitted_x = g.binary('ADD', k[2], g.binary('DIV', g.binary('MUL', k[0], fitted_xyz[0]), g.negate(fitted_xyz[2])))
    fitted_y = g.binary('SUB', k[5], g.binary('DIV', g.binary('MUL', k[4], fitted_xyz[1]), g.negate(fitted_xyz[2])))
    fit_error = g.reduce('SUM', g.binary('ADD', g.square(g.binary('SUB', fitted_x, x)),
                                        g.square(g.binary('SUB', fitted_y, y))), [2])
    n = g.constant('diagnostic_count', 33)
    size_scale = g.choose(g.compare('GREATER', command_parts[2], g.zero),
                          g.clip(command_parts[2], g.half, g.constant('diagnostic_scale_max', 1.5)), g.one)
    pose_flat = g.reshape(pose, [1, 1, 1, 16])
    pose_parts = g.scalar_components(pose_flat)
    computed = {
        16: g.binary('DIV', g.op('SQRT', [g.binary('DIV', sum_error, n)], [1, 1, 1, 1]), width),
        17: g.binary('DIV', max_error, width), 18: g.binary('DIV', g.binary('SUB', max_u, min_u), width),
        19: g.binary('DIV', g.binary('SUB', max_v, min_v), height),
        20: g.binary('DIV', g.binary('SUB', g.binary('ADD', min_u, max_u), g.binary('ADD', min_x, max_x)),
                     g.binary('MUL', g.constant('double_width', 2), width)),
        21: g.binary('DIV', g.binary('SUB', g.binary('ADD', min_v, max_v), g.binary('ADD', min_y, max_y)),
                     g.binary('MUL', g.constant('double_height', 2), height)),
        22: g.binary('DIV', g.op('SQRT', [g.binary('DIV', fit_error, n)], [1, 1, 1, 1]), width),
        23: g.binary('MUL', g.norm([pose_parts[0], pose_parts[4], pose_parts[8]]), size_scale),
        24: g.binary('MUL', g.binary('MUL', g.negate(pose_parts[11]), g.constant('diagnostic_meters', .01)), size_scale),
        28: width, 29: height,
    }
    active = g.compare('GREATER', validity_parts[0], g.zero)
    values = [g.zero for _ in range(32)]
    values[0] = g.constant('diagnostic_version', 3)
    values[1:4] = frame_parts[:3]
    values[4] = track[0]; values[5] = frame_parts[4]; values[6] = track[17]; values[7] = track[11]
    values[8:12] = roi_parts[2:6]
    values[12:16] = [k[0], k[4], k[2], k[5]]
    values[25] = g.choose(g.compare('GREATER', track[0], g.zero), g.zero, g.one)
    values[26] = pose_status; values[27] = command_parts[2]
    values[30] = frame_parts[3]
    for index, value in computed.items():
        values[index] = g.choose(active, value, g.zero)
    diagnostics = g.concat(values, name='diagnostics')
    diagnostic_good = g.all_true(g.finite(diagnostics), [3])
    failed = g.logical('LOGICAL_AND', active, g.logical('LOGICAL_NOT', diagnostic_good))
    next_track = list(track)
    next_track[0] = g.choose(failed, g.zero, track[0])
    next_track[17] = g.choose(failed, g.constant('diagnostic_failure_reason', 5), track[17])
    values[6] = g.choose(failed, g.constant('diagnostic_reason_output', 5), values[6])
    values[25] = g.choose(failed, g.one, values[25])
    diagnostics = g.concat(values, name='final_diagnostics')
    final_validity = g.concat([g.choose(failed, g.zero, validity_parts[0]), validity_parts[1]], name='final_validity')
    return diagnostics, final_validity, g.concat(next_track, name='diagnostic_track_state')


def landmark_control(lab):
    geometry_path = ASSETS / 'data/face_geometry.json'
    canonical_all = np.asarray(json.loads(geometry_path.read_text())['canonical'], np.float32).reshape(468, 4)
    fit_indices = np.flatnonzero(canonical_all[:, 3] > 0).tolist()
    canonical = canonical_all[fit_indices]
    if len(canonical) != 33:
        raise ValueError('Landmark control ABI requires 33 canonical fit points')
    g = LandmarkGraph(canonical)
    raw = g.input_flat('raw_landmarks', 1434)
    presence = g.input_flat('presence_logit', 1)
    roi = g.input_flat('roi', 6)
    affine = g.input_tensor('affine', [1, 1, 2, 3])
    settings = g.input_flat('settings', 11)
    frame = g.input_flat('frame', 6)
    intrinsics = g.input_tensor('intrinsics', [1, 1, 3, 3])
    track_state = g.input_flat('track_state', 24)
    camera = g.input_tensor('left_camera_to_xr', [1, 1, 4, 4])
    command = g.input_flat('command', 4)
    pose_state = g.input_flat('pose_state', 24)
    producer_snapshot = g.input_flat('producer_snapshot', 66)
    projected, first_targets, depth, validity, tracked_state, points, raw_matrix, _ = track_landmarks(
        g, raw, presence, roi, settings, frame, intrinsics, track_state, fit_indices)
    first_scale, second_scale, second_targets, metric, pose = inline_fit(
        g, first_targets, projected, depth, validity)
    next_pose_state, next_track_state, final_validity, world_pose, raw_world_pose, pose_status, diagnostics = \
        pose_and_diagnostics(g, pose, validity, camera, command, settings, frame, tracked_state,
                             pose_state, projected, metric, roi, intrinsics)
    g.outputs = [next_track_state, final_validity, depth, first_scale, second_scale, pose,
                 next_pose_state, world_pose, raw_world_pose, pose_status, diagnostics]
    names = ['next_track_state', 'validity', 'depth_offset', 'first_scale', 'second_scale', 'pose',
             'next_pose_state', 'world_pose', 'raw_world_pose', 'pose_status', 'diagnostics']
    for tensor, name in zip(g.outputs, names):
        g.tensors[tensor].name = name
    if lab:
        snapshot = g.concat([command, frame, roi, g.reshape(affine, [1, 1, 1, 6]), raw,
                             g.reshape(projected, [1, 1, 1, 99]),
                             g.reshape(first_targets, [1, 1, 1, 99]),
                             g.reshape(second_targets, [1, 1, 1, 99]),
                             g.reshape(metric, [1, 1, 1, 99]),
                             g.reshape(pose, [1, 1, 1, 16]),
                             g.reshape(raw_world_pose, [1, 1, 1, 16]),
                             g.reshape(world_pose, [1, 1, 1, 16]),
                             first_scale, second_scale, depth,
                             g.reshape(intrinsics, [1, 1, 1, 9]),
                             g.reshape(camera, [1, 1, 1, 16]), g.zero, producer_snapshot],
                            name='fit_snapshot')
        g.outputs.append(snapshot)
    return g


def camera_intrinsics(g, service, transform, trial, mode):
    service_flat = g.reshape(service, [1, 1, 1, 9])
    service_values = g.scalar_components(service_flat)
    nonzero = g.false
    for value in service_values:
        nonzero = g.logical('LOGICAL_OR', nonzero, g.compare('NOT_EQUAL', value, g.zero))
    valid = g.logical('LOGICAL_AND', g.all_true(g.finite(service_flat), [3]),
                      g.logical('LOGICAL_AND', g.compare('GREATER', service_values[0], g.zero),
                                g.compare('GREATER', service_values[4], g.zero)))
    valid = g.logical('LOGICAL_AND', nonzero, valid)
    mode_value = g.component(mode, 0)
    mode_three = g.logical('LOGICAL_OR', g.compare('EQUAL', mode_value, g.constant('mode_three', 3)),
                           g.compare('EQUAL', mode_value, g.constant('mode_five', 5)))
    source = g.choose(mode_three, trial, service)
    transformed = g.op('BATCH_MATMUL', [transform, source], [1, 1, 3, 3])
    direct = g.logical('LOGICAL_OR', g.compare('EQUAL', mode_value, g.constant('mode_two', 2)),
                       g.compare('EQUAL', mode_value, g.constant('mode_four', 4)))
    selected = g.choose(direct, trial, transformed)
    return g.choose(valid, selected, g.binary('MUL', service, g.zero), 'intrinsics')


def compose_affine(g, affine, transform, name='sample_affine'):
    return g.op('BATCH_MATMUL', [affine, transform], [1, 1, 2, 3], name)


def timestamp_parts(g, timestamp):
    values = [g.op('CAST', [value], g.tensors[value].shape) for value in g.scalar_components(timestamp)]
    scale = g.constant('uint32_scale_' + str(len(g.tensors)), 4294967296.0)
    sec = g.binary('ADD', g.binary('MUL', values[0], scale), values[1])
    nanos = g.binary('ADD', g.binary('MUL', values[2], scale), values[3])
    fraction = g.binary('MUL', nanos, g.constant('nanoseconds_' + str(len(g.tensors)), 1e-9))
    return sec, fraction


def decode_detector(g, boxes_fine, boxes_coarse, scores_fine, scores_coarse,
                    settings, track_state, timestamp, detector_map):
    boxes = g.concat([boxes_fine, boxes_coarse], axis=2)
    scores = g.concat([scores_fine, scores_coarse], axis=2)
    raw_finite = g.finite(scores)
    safe_raw = g.choose(raw_finite, scores, g.constant('negative_score_sentinel', -FLOAT_MAX))
    best_raw = g.reduce('REDUCE_MAX', safe_raw, [2])
    has_raw = g.any_true(raw_finite, [2])
    best_raw = g.choose(has_raw, best_raw, g.zero)
    raw_winners = g.logical('LOGICAL_AND', raw_finite, g.compare('EQUAL', scores, best_raw))
    raw_index = g.first_index(raw_winners, 2, 896)
    raw_index = g.choose(has_raw, raw_index, g.constant('missing_anchor', -1))
    clipped_raw = g.clip(best_raw, g.constant('score_floor', -100), g.constant('score_ceiling', 100))
    raw_probability = g.op('LOGISTIC', [clipped_raw], [1, 1, 1, 1])
    raw_probability = g.choose(has_raw, raw_probability, g.zero)
    detector_info = g.concat([best_raw, raw_probability, raw_index], name='detector_info')

    score = g.op('LOGISTIC', [g.clip(scores, g.constant('candidate_floor', -100),
                                     g.constant('candidate_ceiling', 100))], [1, 1, 896, 1])
    anchor_x = np.r_[((np.arange(512)//2) % 16 + .5) * 16,
                     ((np.arange(384)//6) % 8 + .5) * 32]
    anchor_y = np.r_[((np.arange(512)//2) // 16 + .5) * 16,
                     ((np.arange(384)//6) // 8 + .5) * 32]
    ax = g.tensor('anchor_x', [1, 1, 896, 1], values=anchor_x)
    ay = g.tensor('anchor_y', [1, 1, 896, 1], values=anchor_y)
    box_parts = [g.gather(boxes, [index], axis=3) for index in range(16)]
    center_x = g.binary('ADD', box_parts[0], ax)
    center_y = g.binary('ADD', box_parts[1], ay)
    width, height = box_parts[2], box_parts[3]
    decoded_parts = [g.binary('SUB', center_x, g.binary('MUL', width, g.half)),
                     g.binary('SUB', center_y, g.binary('MUL', height, g.half)),
                     g.binary('ADD', center_x, g.binary('MUL', width, g.half)),
                     g.binary('ADD', center_y, g.binary('MUL', height, g.half))]
    for index in range(4, 16, 2):
        decoded_parts.extend([g.binary('ADD', box_parts[index], ax),
                              g.binary('ADD', box_parts[index + 1], ay)])
    decoded = g.concat(decoded_parts, name='decoded_boxes')

    threshold = g.component(settings, 2)
    # Candidate decode clamps +/-Infinity before sigmoid, matching JavaScript. Detector-info
    # ranking is stricter and ignores non-finite raw logits, so it uses raw_finite above.
    valid = g.logical('LOGICAL_AND', g.finite(score), g.compare('GREATER_EQUAL', score, threshold))
    valid = g.logical('LOGICAL_AND', valid, g.compare('GREATER', width, g.zero))
    valid = g.logical('LOGICAL_AND', valid, g.compare('GREATER', height, g.zero))
    valid = g.logical('LOGICAL_AND', valid, g.all_true(g.finite(decoded), [3]))

    mapping = g.scalar_components(detector_map)
    source_x = g.binary('ADD', g.binary('MUL', center_x, mapping[0]), mapping[2])
    source_y = g.binary('ADD', g.binary('MUL', center_y, mapping[1]), mapping[3])
    state = g.scalar_components(track_state)
    sec, fraction = timestamp_parts(g, timestamp)
    age = g.binary('ADD', g.binary('SUB', sec, state[1]), g.binary('SUB', fraction, state[2]))
    locked = g.logical('LOGICAL_AND', g.compare('GREATER', state[11], g.zero),
                       g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', age, g.zero),
                                 g.compare('LESS', age, g.component(settings, 10))))
    distance = g.binary('DIV', g.norm([g.binary('SUB', source_x, state[3]),
                                      g.binary('SUB', source_y, state[4])]),
                        g.binary('MAXIMUM', g.constant('minimum_identity_side', 32), state[5]))
    within_lock = g.logical('LOGICAL_OR', g.logical('LOGICAL_NOT', locked),
                            g.compare('LESS_EQUAL', distance, g.constant('identity_radius', .8)))
    valid = g.logical('LOGICAL_AND', valid, within_lock)
    penalty = g.choose(locked, g.binary('MUL', distance, g.constant('identity_penalty', .35)), g.zero)
    rank = g.choose(valid, g.binary('SUB', score, penalty), g.constant('rank_sentinel', -FLOAT_MAX))
    best_rank = g.reduce('REDUCE_MAX', rank, [2])
    present = g.any_true(valid, [2])
    winners = g.logical('LOGICAL_AND', valid, g.compare('EQUAL', rank, best_rank))
    best_index = g.first_index(winners, 2, 896)
    safe_best_index = g.choose(present, best_index, g.zero)
    best_decoded = g.dynamic_gather(decoded, safe_best_index, 2, [1, 1, 1, 16])
    best_score = g.dynamic_gather(score, safe_best_index, 2, [1, 1, 1, 1])
    best_parts = g.scalar_components(best_decoded)
    left = g.binary('MAXIMUM', decoded_parts[0], best_parts[0])
    top = g.binary('MAXIMUM', decoded_parts[1], best_parts[1])
    right = g.binary('MINIMUM', decoded_parts[2], best_parts[2])
    bottom = g.binary('MINIMUM', decoded_parts[3], best_parts[3])
    overlap = g.binary('MUL', g.binary('MAXIMUM', g.zero, g.binary('SUB', right, left)),
                       g.binary('MAXIMUM', g.zero, g.binary('SUB', bottom, top)))
    area = g.binary('MUL', g.binary('SUB', decoded_parts[2], decoded_parts[0]),
                    g.binary('SUB', decoded_parts[3], decoded_parts[1]))
    best_area = g.binary('MUL', g.binary('SUB', best_parts[2], best_parts[0]),
                         g.binary('SUB', best_parts[3], best_parts[1]))
    union = g.binary('SUB', g.binary('ADD', area, best_area), overlap)
    same = g.logical('LOGICAL_AND', valid,
                     g.compare('GREATER', g.binary('DIV', overlap, union), g.constant('suppression_iou', .3)))
    index_grid = g.tensor('candidate_index_grid', [1, 1, 896, 1], values=np.arange(896, dtype=np.float32))
    same = g.logical('LOGICAL_OR', same,
                     g.logical('LOGICAL_AND', present, g.compare('EQUAL', index_grid, safe_best_index)))
    weights = g.choose(same, score, g.zero)
    total = g.reduce('SUM', weights, [2])
    # SELECT invalid rows before multiplication: IEEE NaN * 0 is still NaN.
    weighted = g.binary('DIV', g.reduce('SUM', g.binary('MUL', g.choose(same, decoded, g.zero), weights), [2]), total)
    weighted_parts = g.scalar_components(weighted)
    detector_cx = g.binary('MUL', g.binary('ADD', weighted_parts[0], weighted_parts[2]), g.half)
    detector_cy = g.binary('MUL', g.binary('ADD', weighted_parts[1], weighted_parts[3]), g.half)
    face_x = g.binary('ADD', g.binary('MUL', detector_cx, mapping[0]), mapping[2])
    face_y = g.binary('ADD', g.binary('MUL', detector_cy, mapping[1]), mapping[3])
    face_side = g.binary('MUL', g.constant('roi_scale', 1.5),
                         g.binary('MAXIMUM',
                                  g.binary('MUL', g.binary('SUB', weighted_parts[2], weighted_parts[0]), mapping[0]),
                                  g.binary('MUL', g.binary('SUB', weighted_parts[3], weighted_parts[1]), mapping[1])))
    eye_dx = g.binary('MUL', g.binary('SUB', weighted_parts[6], weighted_parts[4]), mapping[0])
    eye_dy = g.binary('MUL', g.binary('SUB', weighted_parts[7], weighted_parts[5]), mapping[1])
    angle = g.op('ATAN2', [eye_dy, eye_dx], [1, 1, 1, 1])
    source_width, source_height = g.component(settings, 0), g.component(settings, 1)
    default_x = g.binary('MUL', source_width, g.half)
    default_y = g.binary('MUL', source_height, g.half)
    default_side = g.binary('MINIMUM', source_width, source_height)
    present_float = g.op('CAST', [present], [1, 1, 1, 1])
    roi = g.concat([present_float, g.choose(present, best_score, g.zero),
                    g.choose(present, face_x, default_x), g.choose(present, face_y, default_y),
                    g.choose(present, face_side, default_side), g.choose(present, angle, g.zero)], name='decoded_roi')
    return roi, detector_info


def prepare_roi(g, decoded_roi, settings, command, state_tensor, timestamp):
    state = g.scalar_components(state_tensor)
    sec, fraction = timestamp_parts(g, timestamp)
    dt = g.choose(g.compare('GREATER', state[18], g.zero),
                  g.binary('ADD', g.binary('SUB', sec, state[13]), g.binary('SUB', fraction, state[14])), g.zero)
    age = g.binary('ADD', g.binary('SUB', sec, state[1]), g.binary('SUB', fraction, state[2]))
    candidate_delta = g.binary('ADD', g.binary('SUB', sec, state[20]),
                               g.binary('SUB', fraction, state[21]))
    sane = g.logical('LOGICAL_AND', g.finite(g.binary('ADD', sec, fraction)),
                     g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', sec, g.zero),
                               g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', fraction, g.zero),
                                         g.compare('LESS', fraction, g.one))))
    continuous = g.logical('LOGICAL_AND', g.compare('GREATER', state[18], g.zero),
                           g.logical('LOGICAL_AND', g.compare('GREATER', dt, g.zero),
                                     g.compare('LESS_EQUAL', dt, g.constant('clock_horizon', 2))))
    rebase = g.logical('LOGICAL_AND', g.compare('GREATER', state[22], g.zero),
                       g.logical('LOGICAL_AND', g.compare('GREATER', candidate_delta, g.zero),
                                 g.compare('LESS_EQUAL', candidate_delta, g.constant('rebase_horizon', 2))))
    fresh = g.logical('LOGICAL_AND', sane, g.logical('LOGICAL_OR', continuous, rebase))
    candidate = g.logical('LOGICAL_AND', sane, g.logical('LOGICAL_NOT', fresh))
    next_state = list(state)
    next_state[20] = g.choose(candidate, sec, state[20])
    next_state[21] = g.choose(candidate, fraction, state[21])
    next_state[22] = g.choose(fresh, g.zero, g.choose(candidate, g.one, state[22]))
    reset_track = g.logical('LOGICAL_AND', fresh, g.logical('LOGICAL_NOT', continuous))
    next_state[0] = g.choose(reset_track, g.zero, state[0])

    frame = g.concat([sec, fraction, g.choose(continuous, dt, g.zero),
                      g.op('CAST', [fresh], [1, 1, 1, 1]),
                      g.choose(g.compare('GREATER', g.component(command, 3), g.zero), g.zero, g.one),
                      g.binary('MAXIMUM', g.zero, age)], name='frame')
    acquire = g.compare('GREATER', g.component(command, 3), g.zero)
    horizon = g.clip(age, g.zero, g.component(settings, 7))
    active = g.logical('LOGICAL_AND', g.compare('GREATER', next_state[0], g.zero),
                       g.logical('LOGICAL_AND', g.compare('GREATER_EQUAL', age, g.zero),
                                 g.compare('LESS_EQUAL', age, g.component(settings, 6))))
    predicted_present = g.logical('LOGICAL_AND', active, fresh)
    growth = g.choose(g.compare('EQUAL', next_state[0], g.constant('retry_state', 2)),
                      g.constant('retry_growth', 1.15), g.one)
    predicted = g.concat([g.op('CAST', [predicted_present], [1, 1, 1, 1]), next_state[12],
                          g.binary('ADD', next_state[3], g.binary('MUL', next_state[7], horizon)),
                          g.binary('ADD', next_state[4], g.binary('MUL', next_state[8], horizon)),
                          g.clip(g.binary('MUL', g.binary('ADD', next_state[5],
                                                        g.binary('MUL', next_state[9], horizon)), growth),
                                 g.constant('minimum_roi', 32),
                                 g.binary('MAXIMUM', g.component(settings, 0), g.component(settings, 1))),
                          next_state[6]])
    roi = g.choose(acquire, decoded_roi, predicted)
    roi_parts = g.scalar_components(roi)
    good_roi = g.logical('LOGICAL_AND', fresh,
                         g.logical('LOGICAL_AND', g.compare('GREATER', roi_parts[4], g.zero),
                                   g.all_true(g.finite(roi), [3])))
    fallback = [g.zero, roi_parts[1], g.binary('MUL', g.component(settings, 0), g.half),
                g.binary('MUL', g.component(settings, 1), g.half),
                g.binary('MINIMUM', g.component(settings, 0), g.component(settings, 1)), g.zero]
    roi = g.concat([g.choose(good_roi, roi_parts[index], fallback[index]) for index in range(6)], name='roi')
    rp = g.scalar_components(roi)
    cosine = g.op('COS', [rp[5]], [1, 1, 1, 1])
    sine = g.op('SIN', [rp[5]], [1, 1, 1, 1])
    scale = g.binary('DIV', g.constant('crop_size', 256), rp[4])
    a, b = g.binary('MUL', scale, cosine), g.binary('MUL', scale, sine)
    affine = g.concat([a, b, g.binary('SUB', g.constant('crop_center_x', 128),
                                                g.binary('ADD', g.binary('MUL', a, rp[2]), g.binary('MUL', b, rp[3]))),
                       g.negate(b), a, g.binary('ADD', g.constant('crop_center_y', 128),
                                               g.binary('SUB', g.binary('MUL', b, rp[2]), g.binary('MUL', a, rp[3])))],
                      name='affine')
    return roi, affine, frame, g.concat(next_state, name='next_track_state')


def detector_control(detection=True):
    g = ControlGraph()
    if detection:
        boxes_fine = g.input_tensor('boxes_fine', [1, 1, 512, 16])
        boxes_coarse = g.input_tensor('boxes_coarse', [1, 1, 384, 16])
        scores_fine = g.input_tensor('scores_fine', [1, 1, 512, 1])
        scores_coarse = g.input_tensor('scores_coarse', [1, 1, 384, 1])
    settings = g.input_flat('settings', 11)
    # SpatialML timestamps are one four-channel INT32 value. Preserve that ABI at the model
    # boundary, then cast the four words internally before reconstructing sec + nanoseconds.
    timestamp = g.input_flat('timestamp', 4, fb.TensorType.INT32)
    command = g.input_flat('command', 4)
    state = g.input_flat('track_state', 24)
    service = g.input_tensor('service_intrinsics', [1, 1, 3, 3])
    transform = g.input_tensor('image_transform', [1, 1, 3, 3])
    trial = g.input_tensor('trial_intrinsics', [1, 1, 3, 3])
    mode = g.input_flat('lab_mode', 1)
    camera = g.input_tensor('left_camera_to_xr', [1, 1, 4, 4])
    if detection:
        mapping = g.input_flat('detector_to_source', 4)
        decoded, detector_info = decode_detector(g, boxes_fine, boxes_coarse, scores_fine,
                                                  scores_coarse, settings, state, timestamp, mapping)
    else:
        decoded = g.concat([g.zero, g.zero, g.zero, g.zero, g.one, g.zero])
        detector_info = None
    roi, affine, frame, next_state = prepare_roi(g, decoded, settings, command, state, timestamp)
    intrinsics = camera_intrinsics(g, service, transform, trial, mode)
    affine_matrix = g.reshape(affine, [1, 1, 2, 3], 'affine')
    sample_affine = compose_affine(g, affine_matrix, transform)
    snapshot = g.concat([command, frame, roi, affine, g.reshape(intrinsics, [1, 1, 1, 9]),
                         g.reshape(service, [1, 1, 1, 9]), g.reshape(transform, [1, 1, 1, 9]),
                         g.reshape(camera, [1, 1, 1, 16]), mode], name='producer_snapshot')
    g.outputs = [intrinsics, roi, affine_matrix, sample_affine, frame, next_state, snapshot]
    if detection:
        g.outputs.insert(6, detector_info)
    return g


def compact_detector_preprocess():
    g = Graph()
    image = g.tensor('image', [1, 336, 336, 3], fb.TensorType.UINT8)
    g.inputs = [image]
    # Match nearest-neighbor 336x336 -> 336x256 rows. The device GPU compiler
    # rejects row GATHER, so use its native resize after a bounded square-image cast.
    floating = g.op('CAST', [image], [1, 336, 336, 3])
    resize_shape = g.tensor('detector_view_size', [2], fb.TensorType.INT32, [256, 336])
    resized = g.op('RESIZE_NEAREST_NEIGHBOR', [floating, resize_shape], [1, 256, 336, 3])
    begin = g.tensor('crop_begin', [4], fb.TensorType.INT32, [0, 0, 40, 0])
    size = g.tensor('crop_size', [4], fb.TensorType.INT32, [1, 256, 256, 3])
    crop = g.op('SLICE', [resized, begin, size], [1, 256, 256, 3])
    output = g.binary('DIV', crop, g.constant('byte_scale', 255), 'model_input')
    g.outputs = [output]
    return g


def completion_marker():
    g = Graph()
    command = g.tensor('command', [1, 1, 1, 4])
    g.inputs = [command]
    indices = g.tensor('sequence_index', [1], fb.TensorType.INT32, [0])
    g.outputs = [g.op('GATHER', [command, indices], [1, 1, 1, 1], 'sequence', {'axis': 3})]
    return g


def manifest_entry(name, graph, data, backend):
    def tensor_entry(index):
        tensor = graph.tensors[index]
        dtype = next(
            key
            for key in dir(fb.TensorType)
            if key.isupper() and getattr(fb.TensorType, key) == tensor.dtype
        )
        return dict(name=tensor.name, shape=tensor.shape, dtype=dtype)

    return dict(name=name, sha256=hashlib.sha256(data).hexdigest(), bytes=len(data),
                operators=len(graph.operators), operatorKinds=sorted(set(op[0] for op in graph.operators)),
                backend=backend,
                inputs=[tensor_entry(index) for index in graph.inputs],
                outputs=[tensor_entry(index) for index in graph.outputs])


def write_models(output):
    output.mkdir(parents=True, exist_ok=True)
    graphs = [('face_detector_control', detector_control(True), 'CPU'),
              ('face_roi_control', detector_control(False), 'CPU'),
              ('face_landmark_control', landmark_control(False), 'CPU'),
              ('face_landmark_control_lab', landmark_control(True), 'CPU'),
              ('detector_compact_preprocess_gpu', compact_detector_preprocess(), 'GPU'),
              ('face_completion_marker', completion_marker(), 'CPU')]
    manifest = []
    for name, graph, backend in graphs:
        data = graph.serialize(name + '; weightless; explicit state; ' + backend)
        (output / (name + '.tflite')).write_bytes(data)
        manifest.append(manifest_entry(name, graph, data, backend))
    (output / 'face_control_models.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ASSETS / 'model')
    args = parser.parse_args()
    print(json.dumps(write_models(args.output), indent=2))
