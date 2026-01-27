"""
Lumina Studio - Mesh Generation Strategies
网格生成策略模块 - 统一管理不同建模模式的3D网格生成
"""

from abc import ABC, abstractmethod
import numpy as np
import cv2
import trimesh
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

# Woodblock模式依赖检查
try:
    from skimage import color, segmentation
    from skimage.measure import regionprops
    try:
        from skimage import graph
    except ImportError:
        from skimage.future import graph
    WOODBLOCK_AVAILABLE = True
except Exception as e:
    WOODBLOCK_AVAILABLE = False
    print(f"[MESH_GENERATORS] scikit-image not available: {e}")


class BaseMesher(ABC):
    """网格生成器抽象基类"""
    
    @abstractmethod
    def generate_mesh(self, voxel_matrix, mat_id, height_px):
        """
        生成指定材质的3D网格
        
        Args:
            voxel_matrix: (Z, H, W) 体素矩阵
            mat_id: 材质ID (0-3)
            height_px: 图像高度(像素)
        
        Returns:
            trimesh.Trimesh or None
        """
        pass


class VoxelMesher(BaseMesher):
    """
    像素模式网格生成器
    生成方块风格的体素网格
    """
    
    def generate_mesh(self, voxel_matrix, mat_id, height_px):
        """生成像素模式网格 (Legacy Voxel Mode)"""
        vertices, faces = [], []
        shrink = 0.05
        
        for z in range(voxel_matrix.shape[0]):
            z_bottom, z_top = z, z + 1
            mask = (voxel_matrix[z] == mat_id)
            if not np.any(mask):
                continue
            
            for y in range(height_px):
                world_y = (height_px - 1 - y)
                row = mask[y]
                padded = np.pad(row, (1, 1), mode='constant')
                diff = np.diff(padded.astype(int))
                starts, ends = np.where(diff == 1)[0], np.where(diff == -1)[0]
                
                for start, end in zip(starts, ends):
                    x0, x1 = start + shrink, end - shrink
                    y0, y1 = world_y + shrink, world_y + 1 - shrink
                    
                    base_idx = len(vertices)
                    vertices.extend([
                        [x0, y0, z_bottom], [x1, y0, z_bottom], 
                        [x1, y1, z_bottom], [x0, y1, z_bottom],
                        [x0, y0, z_top], [x1, y0, z_top], 
                        [x1, y1, z_top], [x0, y1, z_top]
                    ])
                    cube_faces = [
                        [0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
                        [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                        [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]
                    ]
                    faces.extend([[v + base_idx for v in f] for f in cube_faces])
        
        if not vertices:
            return None
        
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        mesh.merge_vertices()
        mesh.update_faces(mesh.unique_faces())
        return mesh


class VectorMesher(BaseMesher):
    """
    矢量模式网格生成器
    使用OpenCV轮廓提取生成平滑曲线
    """
    
    def generate_mesh(self, voxel_matrix, mat_id, height_px):
        """生成矢量模式网格 (Smooth Vector Mode)"""
        # 垂直层合并 (RLE压缩)
        layer_groups = self._merge_layers(voxel_matrix, mat_id)
        
        print(f"[VECTOR] Mat ID {mat_id}: Merged {voxel_matrix.shape[0]} layers → {len(layer_groups)} groups")
        
        all_meshes = []
        
        for start_z, end_z, mask in layer_groups:
            num_layers = end_z - start_z + 1
            z_height = float(num_layers)
            
            print(f"[VECTOR] Processing z={start_z}-{end_z} (height={z_height})")
            
            # 形态学清理
            mask_uint8 = (mask.astype(np.uint8) * 255)
            kernel = np.ones((3, 3), np.uint8)
            mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel, iterations=1)
            mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel, iterations=1)
            
            # 轮廓提取
            contours, hierarchy = cv2.findContours(
                mask_uint8, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )
            
            if len(contours) == 0:
                continue
            
            print(f"[VECTOR] Found {len(contours)} contours")
            
            # 处理轮廓
            polygons = self._process_contours(contours, hierarchy, height_px)
            
            # 布尔运算合并
            merged = self._merge_polygons(polygons)
            
            # 挤出为3D
            meshes = self._extrude_polygons(merged, z_height, start_z)
            all_meshes.extend(meshes)
        
        if not all_meshes:
            return None
        
        combined = trimesh.util.concatenate(all_meshes)
        combined.process()
        
        print(f"[VECTOR] Mat {mat_id}: {len(combined.vertices)} vertices, {len(combined.faces)} faces")
        
        return combined

    
    def _merge_layers(self, voxel_matrix, mat_id):
        """合并相同的垂直层 (RLE压缩)"""
        layer_groups = []
        prev_mask = None
        start_z = 0
        
        for z in range(voxel_matrix.shape[0]):
            curr_mask = (voxel_matrix[z] == mat_id)
            
            if not np.any(curr_mask):
                if prev_mask is not None and np.any(prev_mask):
                    layer_groups.append((start_z, z - 1, prev_mask))
                    prev_mask = None
                continue
            
            if prev_mask is None:
                start_z = z
                prev_mask = curr_mask.copy()
            elif np.array_equal(curr_mask, prev_mask):
                pass  # 继续当前组
            else:
                layer_groups.append((start_z, z - 1, prev_mask))
                start_z = z
                prev_mask = curr_mask.copy()
        
        if prev_mask is not None and np.any(prev_mask):
            layer_groups.append((start_z, voxel_matrix.shape[0] - 1, prev_mask))
        
        return layer_groups
    
    def _process_contours(self, contours, hierarchy, height_px):
        """处理轮廓并转换为多边形"""
        polygons = []
        
        for idx, contour in enumerate(contours):
            contour_area = cv2.contourArea(contour)
            if contour_area < 4.0:
                continue
            
            # 多边形近似
            epsilon = 0.1
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) < 3:
                continue
            
            # 转换坐标
            points_2d = []
            for point in approx[:, 0, :]:
                x, y = point
                world_y = (height_px - 1 - y)
                points_2d.append([float(x), float(world_y)])
            
            try:
                poly = Polygon(points_2d)
                
                if not poly.is_valid:
                    poly = poly.buffer(0)
                
                if poly.is_valid and poly.area > 0.01:
                    poly = poly.buffer(6.0)
                    
                    # 判断是否为孔洞
                    is_hole = False
                    if hierarchy is not None and hierarchy[0][idx][3] != -1:
                        is_hole = True
                    
                    polygons.append((poly, is_hole))
            
            except Exception as e:
                print(f"[VECTOR] Warning: Polygon creation failed: {e}")
                continue
        
        return polygons
    
    def _merge_polygons(self, polygons):
        """使用布尔运算合并多边形"""
        outer_polys = [p for p, is_hole in polygons if not is_hole]
        hole_polys = [p for p, is_hole in polygons if is_hole]
        
        if len(outer_polys) == 0:
            return []
        
        # 合并外轮廓
        if len(outer_polys) > 1:
            merged = unary_union(outer_polys)
        else:
            merged = outer_polys[0]
        
        # 减去孔洞
        for hole in hole_polys:
            merged = merged.difference(hole)
        
        # 转换为列表
        if isinstance(merged, Polygon):
            return [merged]
        elif isinstance(merged, MultiPolygon):
            return list(merged.geoms)
        else:
            return []
    
    def _extrude_polygons(self, polygons, z_height, start_z):
        """挤出多边形为3D网格"""
        meshes = []
        
        for poly in polygons:
            if poly.area < 0.01:
                continue
            
            try:
                mesh = trimesh.creation.extrude_polygon(poly, height=z_height)
                mesh.apply_translation([0, 0, start_z])
                meshes.append(mesh)
            except Exception as e:
                print(f"[VECTOR] Warning: Extrusion failed: {e}")
                continue
        
        return meshes


class WoodblockMesher(BaseMesher):
    """
    版画模式网格生成器
    使用SLIC超像素和细节保护技术
    """
    
    def __init__(self):
        if not WOODBLOCK_AVAILABLE:
            print("[WOODBLOCK] scikit-image not available, will fallback to Vector mode")
        self.fallback_mesher = VectorMesher()
    
    def generate_mesh(self, voxel_matrix, mat_id, height_px):
        """生成版画模式网格 (Woodblock Detail-Optimized Mode)"""
        if not WOODBLOCK_AVAILABLE:
            print("[WOODBLOCK] Falling back to Vector mode")
            return self.fallback_mesher.generate_mesh(voxel_matrix, mat_id, height_px)
        
        print(f"[WOODBLOCK] Processing material ID {mat_id}...")
        
        # 垂直层合并
        layer_groups = self._merge_layers(voxel_matrix, mat_id)
        
        print(f"[WOODBLOCK] Mat {mat_id}: Merged {voxel_matrix.shape[0]} layers → {len(layer_groups)} groups")
        
        all_meshes = []
        
        for group_idx, (start_z, end_z, mask) in enumerate(layer_groups):
            z_height = float(end_z - start_z + 1)
            
            print(f"[WOODBLOCK] Group {group_idx+1}/{len(layer_groups)}: z={start_z}-{end_z}")
            
            # 形态学清理
            mask_uint8 = (mask.astype(np.uint8) * 255)
            kernel = np.ones((3, 3), np.uint8)
            mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel, iterations=1)
            mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel, iterations=1)
            
            # 轮廓提取
            contours, hierarchy = cv2.findContours(
                mask_uint8, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )
            
            if len(contours) == 0:
                continue
            
            print(f"[WOODBLOCK] Found {len(contours)} contours")
            
            # 智能轮廓处理
            polygons = self._process_contours_with_rescue(contours, hierarchy, height_px)
            
            # 布尔运算合并
            merged = self._merge_polygons(polygons)
            
            # 挤出为3D
            meshes = self._extrude_polygons(merged, z_height, start_z)
            all_meshes.extend(meshes)
        
        if not all_meshes:
            return None
        
        combined = trimesh.util.concatenate(all_meshes)
        combined.process()
        
        print(f"[WOODBLOCK] Mat {mat_id}: {len(combined.vertices)} vertices, {len(combined.faces)} faces")
        
        return combined

    
    def _merge_layers(self, voxel_matrix, mat_id):
        """合并相同的垂直层 (与VectorMesher相同)"""
        layer_groups = []
        prev_mask = None
        start_z = 0
        
        for z in range(voxel_matrix.shape[0]):
            curr_mask = (voxel_matrix[z] == mat_id)
            
            if not np.any(curr_mask):
                if prev_mask is not None and np.any(prev_mask):
                    layer_groups.append((start_z, z - 1, prev_mask))
                    prev_mask = None
                continue
            
            if prev_mask is None:
                start_z = z
                prev_mask = curr_mask.copy()
            elif np.array_equal(curr_mask, prev_mask):
                pass
            else:
                layer_groups.append((start_z, z - 1, prev_mask))
                start_z = z
                prev_mask = curr_mask.copy()
        
        if prev_mask is not None and np.any(prev_mask):
            layer_groups.append((start_z, voxel_matrix.shape[0] - 1, prev_mask))
        
        return layer_groups
    
    def _process_contours_with_rescue(self, contours, hierarchy, height_px):
        """
        智能轮廓处理与几何修复
        版画模式特有的细节保护逻辑
        """
        polygons = []
        min_feature_px = 4.0
        
        for idx, contour in enumerate(contours):
            contour_area = cv2.contourArea(contour)
            
            if contour_area < min_feature_px:
                continue
            
            # 多边形近似
            epsilon = 0.1
            approx = cv2.approxPolyDP(contour, epsilon, True)
            
            if len(approx) < 3:
                continue
            
            # 转换坐标
            points_2d = []
            for point in approx[:, 0, :]:
                x, y = point
                world_y = (height_px - 1 - y)
                points_2d.append([float(x), float(world_y)])
            
            try:
                poly = Polygon(points_2d)
                
                if not poly.is_valid:
                    poly = poly.buffer(0)
                
                if not poly.is_valid or poly.area < 0.01:
                    continue
                
                # 细节保护：检测细小特征
                test_shrink = poly.buffer(-min_feature_px / 2.0)
                
                if test_shrink.is_empty or test_shrink.area < 0.01:
                    # 细小特征救援
                    rescue_distance = min_feature_px / 2.0 + 0.5
                    poly = poly.buffer(
                        distance=rescue_distance,
                        join_style=2,  # Mitre保持尖角
                        mitre_limit=5.0
                    )
                    print(f"[WOODBLOCK] Rescued thin feature: area={contour_area:.1f}px²")
                else:
                    # 正常特征：轻微扩展
                    poly = poly.buffer(
                        distance=0.5,
                        join_style=2,
                        mitre_limit=5.0
                    )
                
                # 判断是否为孔洞
                is_hole = False
                if hierarchy is not None and hierarchy[0][idx][3] != -1:
                    is_hole = True
                
                polygons.append((poly, is_hole))
            
            except Exception as e:
                print(f"[WOODBLOCK] Warning: Polygon creation failed: {e}")
                continue
        
        return polygons
    
    def _merge_polygons(self, polygons):
        """布尔运算合并多边形 (与VectorMesher相同)"""
        outer_polys = [p for p, is_hole in polygons if not is_hole]
        hole_polys = [p for p, is_hole in polygons if is_hole]
        
        if len(outer_polys) == 0:
            return []
        
        if len(outer_polys) > 1:
            merged = unary_union(outer_polys)
        else:
            merged = outer_polys[0]
        
        for hole in hole_polys:
            merged = merged.difference(hole)
        
        if isinstance(merged, Polygon):
            return [merged]
        elif isinstance(merged, MultiPolygon):
            return list(merged.geoms)
        else:
            return []
    
    def _extrude_polygons(self, polygons, z_height, start_z):
        """挤出多边形为3D网格 (与VectorMesher相同)"""
        meshes = []
        
        for poly in polygons:
            if poly.area < 0.01:
                continue
            
            try:
                mesh = trimesh.creation.extrude_polygon(poly, height=z_height)
                mesh.apply_translation([0, 0, start_z])
                meshes.append(mesh)
            except Exception as e:
                print(f"[WOODBLOCK] Warning: Extrusion failed: {e}")
                continue
        
        return meshes


# ========== 工厂方法 ==========

def get_mesher(mode_name):
    """
    根据模式名称返回对应的Mesher实例
    
    Args:
        mode_name: 模式名称 ("vector", "woodblock", "voxel")
    
    Returns:
        BaseMesher实例
    """
    mode_str = str(mode_name).lower()
    
    if "woodblock" in mode_str or "版画" in mode_str:
        return WoodblockMesher()
    elif "vector" in mode_str or "矢量" in mode_str:
        return VectorMesher()
    else:
        return VoxelMesher()
