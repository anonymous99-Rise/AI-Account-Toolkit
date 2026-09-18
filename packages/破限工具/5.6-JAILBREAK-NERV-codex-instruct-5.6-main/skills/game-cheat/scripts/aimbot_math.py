# -*- coding: utf-8 -*-
"""Aimbot math -- ViewMatrix, world-to-screen, bone ESP, smooth aim.

Author: zxwn
"""
import math, struct


def world_to_screen(world_pos: tuple, view_matrix: list, screen_w: int, screen_h: int) -> tuple:
    """Convert 3D world coordinates to 2D screen coordinates.

    view_matrix: 16-float 4x4 column-major matrix (DirectX style)
    Returns (screen_x, screen_y) or None if behind camera.
    """
    x, y, z = world_pos
    # Transform to clip space
    clip_x = x * view_matrix[0] + y * view_matrix[4] + z * view_matrix[8] + view_matrix[12]
    clip_y = x * view_matrix[1] + y * view_matrix[5] + z * view_matrix[9] + view_matrix[13]
    clip_w = x * view_matrix[3] + y * view_matrix[7] + z * view_matrix[11] + view_matrix[15]

    if clip_w < 0.001:
        return None  # Behind camera

    # Perspective divide
    ndc_x = clip_x / clip_w
    ndc_y = clip_y / clip_w

    # To screen
    screen_x = (screen_w / 2) * (ndc_x + 1)
    screen_y = (screen_h / 2) * (1 - ndc_y)

    return (screen_x, screen_y)


def bone_position(base_pos: tuple, bone_matrix: list, bone_id: int) -> tuple:
    """Calculate bone world position from base + bone transform matrix.

    bone_matrix: flat list of 12 floats (3x4 transform) per bone
    bone_id * 12 = offset into bone array
    """
    offset = bone_id * 12
    bx = base_pos[0] + bone_matrix[offset + 0] * 1.0 + bone_matrix[offset + 3]
    by = base_pos[1] + bone_matrix[offset + 1] * 1.0 + bone_matrix[offset + 7]
    bz = base_pos[2] + bone_matrix[offset + 2] * 1.0 + bone_matrix[offset + 11]
    return (bx, by, bz)


def aim_angle(source: tuple, target: tuple) -> tuple:
    """Calculate pitch/yaw angles from source to target position.

    Returns (pitch_deg, yaw_deg) relative to horizontal.
    """
    dx = target[0] - source[0]
    dy = target[1] - source[1]
    dz = target[2] - source[2]

    horizontal_dist = math.sqrt(dx * dx + dy * dy)
    pitch = -math.degrees(math.atan2(dz, horizontal_dist))
    yaw = math.degrees(math.atan2(dy, dx))

    return (pitch, yaw)


def smooth_aim(current_angles: tuple, target_angles: tuple, smooth: float) -> tuple:
    """Smoothly interpolate between current and target angles.

    smooth: 1.0 = instant, 5.0 = very slow, typical 2.0-3.0
    """
    delta_pitch = target_angles[0] - current_angles[0]
    delta_yaw = target_angles[1] - current_angles[1]

    # Normalize yaw delta to [-180, 180]
    while delta_yaw > 180:
        delta_yaw -= 360
    while delta_yaw < -180:
        delta_yaw += 360

    new_pitch = current_angles[0] + delta_pitch / smooth
    new_yaw = current_angles[1] + delta_yaw / smooth

    return (new_pitch, new_yaw)


def distance_3d(a: tuple, b: tuple) -> float:
    """Euclidean distance between two 3D points."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    dz = b[2] - a[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def closest_target(local_pos: tuple, targets: list) -> tuple:
    """Find closest target from list of (x,y,z,id)."""
    best = None
    best_dist = float("inf")
    for t in targets:
        d = distance_3d(local_pos, (t[0], t[1], t[2]))
        if d < best_dist:
            best_dist = d
            best = t
    return best


def fov_check(local_angles: tuple, target_angle: tuple, fov: float) -> bool:
    """Check if target is within field-of-view cone."""
    pitch_diff = abs(target_angle[0] - local_angles[0])
    yaw_diff = abs(target_angle[1] - local_angles[1])
    while yaw_diff > 180:
        yaw_diff = 360 - yaw_diff
    return pitch_diff <= fov and yaw_diff <= fov


# Common bone IDs (CS/Valve games)
BONE_HEAD = 8
BONE_NECK = 7
BONE_CHEST = 6
BONE_PELVIS = 0

# Common recoil compensation
def recoil_compensation(punch_angles: tuple, sensitivity: float) -> tuple:
    """Calculate anti-recoil offset from punch angles."""
    return (-punch_angles[0] * 2.0, -punch_angles[1] * 2.0)


if __name__ == "__main__":
    print("[aimbot_math] Loaded.")
    # Test: world_to_screen
    vm = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]  # Identity
    result = world_to_screen((100, 50, 200), vm, 1920, 1080)
    print("World(100,50,200) -> Screen{}".format(result))
