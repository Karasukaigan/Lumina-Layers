"""
Lumina Studio - Geometry Utilities
几何工具模块 - 纯函数式几何计算工具
"""

import numpy as np
import trimesh


def create_keychain_loop(width_mm, length_mm, hole_dia_mm, thickness_mm, 
                         attach_x_mm, attach_y_mm):
    """
    创建钥匙扣挂孔网格
    
    这是一个纯函数，生成带孔洞的矩形+半圆挂孔几何体
    
    Args:
        width_mm: 挂孔宽度(毫米)
        length_mm: 挂孔长度(毫米)
        hole_dia_mm: 孔洞直径(毫米)
        thickness_mm: 挂孔厚度(毫米)
        attach_x_mm: 附着点X坐标(毫米)
        attach_y_mm: 附着点Y坐标(毫米)
    
    Returns:
        trimesh.Trimesh: 挂孔网格对象
    """
    print(f"[GEOMETRY] Creating keychain loop: w={width_mm}, l={length_mm}, "
          f"hole={hole_dia_mm}, thick={thickness_mm}, pos=({attach_x_mm}, {attach_y_mm})")
    
    # 计算几何参数
    half_w = width_mm / 2
    circle_radius = half_w
    hole_radius = min(hole_dia_mm / 2, circle_radius * 0.8)
    rect_height = max(0.2, length_mm - circle_radius)
    circle_center_y = rect_height
    
    # 生成外轮廓点
    n_arc = 32
    outer_pts = []
    
    # 矩形底部
    outer_pts.append((-half_w, 0))
    outer_pts.append((half_w, 0))
    outer_pts.append((half_w, rect_height))
    
    # 半圆顶部
    for i in range(1, n_arc):
        angle = np.pi * i / n_arc
        x = circle_radius * np.cos(angle)
        y = circle_center_y + circle_radius * np.sin(angle)
        outer_pts.append((x, y))
    
    # 矩形左边
    outer_pts.append((-half_w, rect_height))
    
    outer_pts = np.array(outer_pts)
    n_outer = len(outer_pts)
    
    # 生成孔洞点
    n_hole = 32
    hole_pts = []
    for i in range(n_hole):
        angle = 2 * np.pi * i / n_hole
        x = hole_radius * np.cos(angle)
        y = circle_center_y + hole_radius * np.sin(angle)
        hole_pts.append((x, y))
    hole_pts = np.array(hole_pts)
    n_hole_pts = len(hole_pts)
    
    # 构建3D顶点
    vertices = []
    faces = []
    
    # 底面外轮廓
    for pt in outer_pts:
        vertices.append([pt[0], pt[1], 0])
    
    # 底面孔洞
    for pt in hole_pts:
        vertices.append([pt[0], pt[1], 0])
    
    # 顶面外轮廓
    for pt in outer_pts:
        vertices.append([pt[0], pt[1], thickness_mm])
    
    # 顶面孔洞
    for pt in hole_pts:
        vertices.append([pt[0], pt[1], thickness_mm])
    
    # 索引定义
    bottom_outer_start = 0
    bottom_hole_start = n_outer
    top_outer_start = n_outer + n_hole_pts
    top_hole_start = n_outer + n_hole_pts + n_outer
    
    # 外轮廓侧面
    for i in range(n_outer):
        i_next = (i + 1) % n_outer
        bi = bottom_outer_start + i
        bi_next = bottom_outer_start + i_next
        ti = top_outer_start + i
        ti_next = top_outer_start + i_next
        faces.append([bi, bi_next, ti_next])
        faces.append([bi, ti_next, ti])
    
    # 孔洞侧面
    for i in range(n_hole_pts):
        i_next = (i + 1) % n_hole_pts
        bi = bottom_hole_start + i
        bi_next = bottom_hole_start + i_next
        ti = top_hole_start + i
        ti_next = top_hole_start + i_next
        faces.append([bi, ti, ti_next])
        faces.append([bi, ti_next, bi_next])
    
    # 连接外轮廓和孔洞 (顶面和底面)
    vertices_arr = np.array(vertices)
    
    bottom_outer_idx = list(range(bottom_outer_start, bottom_outer_start + n_outer))
    bottom_hole_idx = list(range(bottom_hole_start, bottom_hole_start + n_hole_pts))
    bottom_faces = _connect_rings(bottom_outer_idx, bottom_hole_idx, vertices_arr, is_top=False)
    faces.extend(bottom_faces)
    
    top_outer_idx = list(range(top_outer_start, top_outer_start + n_outer))
    top_hole_idx = list(range(top_hole_start, top_hole_start + n_hole_pts))
    top_faces = _connect_rings(top_outer_idx, top_hole_idx, vertices_arr, is_top=True)
    faces.extend(top_faces)
    
    # 应用位置偏移
    vertices_arr = np.array(vertices)
    vertices_arr[:, 0] += attach_x_mm
    vertices_arr[:, 1] += attach_y_mm
    
    # 创建网格
    mesh = trimesh.Trimesh(vertices=vertices_arr, faces=np.array(faces))
    mesh.fix_normals()
    
    print(f"[GEOMETRY] Loop mesh created: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")
    
    return mesh


def _connect_rings(outer_indices, hole_indices, vertices_arr, is_top=True):
    """
    连接外环和内环的辅助函数
    使用贪心算法生成三角面片
    
    Args:
        outer_indices: 外环顶点索引列表
        hole_indices: 内环顶点索引列表
        vertices_arr: 顶点数组
        is_top: 是否为顶面
    
    Returns:
        list: 面片索引列表
    """
    ring_faces = []
    n_o = len(outer_indices)
    n_h = len(hole_indices)
    
    oi = 0  # 外环指针
    hi = 0  # 内环指针
    
    def get_2d(idx):
        """获取顶点的2D坐标"""
        return np.array([vertices_arr[idx][0], vertices_arr[idx][1]])
    
    total_steps = n_o + n_h
    for _ in range(total_steps):
        o_curr = outer_indices[oi % n_o]
        o_next = outer_indices[(oi + 1) % n_o]
        h_curr = hole_indices[hi % n_h]
        h_next = hole_indices[(hi + 1) % n_h]
        
        # 计算距离决定连接方向
        dist_o = np.linalg.norm(get_2d(o_next) - get_2d(h_curr))
        dist_h = np.linalg.norm(get_2d(o_curr) - get_2d(h_next))
        
        if oi >= n_o:
            # 外环已完成，只连接内环
            if is_top:
                ring_faces.append([o_curr, h_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, h_next])
            hi += 1
        elif hi >= n_h:
            # 内环已完成，只连接外环
            if is_top:
                ring_faces.append([o_curr, o_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, o_next])
            oi += 1
        elif dist_o < dist_h:
            # 连接外环下一个点
            if is_top:
                ring_faces.append([o_curr, o_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, o_next])
            oi += 1
        else:
            # 连接内环下一个点
            if is_top:
                ring_faces.append([o_curr, h_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, h_next])
            hi += 1
    
    return ring_faces
