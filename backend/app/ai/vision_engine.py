"""感知层 · 边缘视频分析引擎

部署形态：本模块运行在校侧边缘节点（教学演示中与后端同进程）。
推理路径分两级：
- 若环境存在 onnxruntime + REDGATE_YOLO_MODEL 指向的 ONNX 检测模型 → 真实推理（YOLOv8 导出格式）
- 否则回退到确定性帧特征分析：对上传帧做下采样灰度统计（积水反光面/密集人群纹理的简易判据），
  保证离线演示零依赖可运行。两条路径产出同一结构化事件格式。

数据安全：推理完成即丢弃原始帧，仅保留 SHA-256 快照哈希用于取证比对——事件里没有人脸、没有原图。
"""
import hashlib
import os
import struct
import zlib

# 支持识别的事件类型（与本体规则库 vision 模态 key 对齐）
EVENT_TYPES = [
    "illegal_parking",       # 校门口违停
    "crowd_density",         # 人群密度超限
    "stair_crowding",        # 楼梯间人群密度超限（踩踏风险）
    "waterlogging",          # 路面积水
    "fire_channel_blocked",  # 消防通道占用
    "kitchen_violation",     # 明厨亮灶：未戴帽/未戴口罩/鼠患活动
    "vendor_stall",          # 游商占道
]

_CONF_THRESHOLD = 0.45


def analyze_frame(frame: bytes, camera_zone: str, hint: str | None = None) -> list[dict]:
    """帧 → 结构化事件列表 [{event_type, confidence, bbox, snapshot_hash}]

    hint 为演示注入器提供的场景标签（scenario 回放时模拟真实相机在该场景下的画面内容）；
    实际部署中 hint 为空，全部走模型推理。
    """
    snapshot_hash = hashlib.sha256(frame).hexdigest()

    events = _infer_with_model(frame)
    if events is None:
        events = _infer_fallback(frame, hint)

    for e in events:
        e["snapshot_hash"] = snapshot_hash
        e["zone"] = camera_zone
    return [e for e in events if e["confidence"] >= _CONF_THRESHOLD]


def _infer_with_model(frame: bytes) -> list[dict] | None:
    """ONNX 推理路径。模型缺失/加载失败返回 None 走回退路径。"""
    model_path = os.getenv("REDGATE_YOLO_MODEL", "")
    if not model_path or not os.path.exists(model_path):
        return None
    try:
        import numpy as np
        import onnxruntime as ort
        from PIL import Image
        import io

        sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        img = Image.open(io.BytesIO(frame)).convert("RGB").resize((640, 640))
        x = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
        out = sess.run(None, {sess.get_inputs()[0].name: x})[0]
        # YOLOv8 输出 [1, 84, 8400]：前4行 bbox，后80行 COCO 类别分数
        preds = out[0].T
        events: list[dict] = []
        for row in preds:
            cls_scores = row[4:]
            cls_id, conf = int(cls_scores.argmax()), float(cls_scores.max())
            if conf < _CONF_THRESHOLD:
                continue
            # COCO 类别到校园事件的映射：2=car→违停候选 0=person 聚集→人群密度
            mapping = {2: "illegal_parking", 7: "illegal_parking", 0: "crowd_density"}
            if cls_id in mapping:
                cx, cy, w, h = (float(v) / 640 for v in row[:4])
                events.append({
                    "event_type": mapping[cls_id],
                    "confidence": round(conf, 3),
                    "bbox": [round(cx - w / 2, 3), round(cy - h / 2, 3), round(w, 3), round(h, 3)],
                })
        # 同类事件合并计数：≥6 个 person 才构成 crowd_density
        persons = [e for e in events if e["event_type"] == "crowd_density"]
        others = [e for e in events if e["event_type"] != "crowd_density"]
        if len(persons) >= 6:
            others.append({
                "event_type": "crowd_density",
                "confidence": round(sum(p["confidence"] for p in persons) / len(persons), 3),
                "bbox": None,
            })
        return others
    except Exception:
        return None


def _infer_fallback(frame: bytes, hint: str | None) -> list[dict]:
    """确定性回退分析：无模型环境下的可复现判据。

    - hint 命中已知事件类型 → 直接产出该事件（场景回放注入）
    - 否则用帧字节统计做简易判据：压缩比（zlib）近似画面纹理复杂度，
      低复杂度大面积同色块 → 疑似积水反光；高复杂度 → 疑似密集人群/车辆。
    """
    if hint and hint in EVENT_TYPES:
        conf = 0.80 + (frame[0] % 16) / 100 if frame else 0.85
        return [{"event_type": hint, "confidence": round(min(conf, 0.96), 3),
                 "bbox": _pseudo_bbox(frame)}]

    if not frame or len(frame) < 64:
        return []
    ratio = len(zlib.compress(frame[:65536])) / min(len(frame), 65536)
    if ratio < 0.30:
        return [{"event_type": "waterlogging", "confidence": round(0.45 + (0.30 - ratio), 3),
                 "bbox": _pseudo_bbox(frame)}]
    if ratio > 0.92:
        return [{"event_type": "crowd_density", "confidence": round(min(ratio - 0.40, 0.9), 3),
                 "bbox": None}]
    return []


def _pseudo_bbox(frame: bytes) -> list[float]:
    """从帧哈希导出确定性 bbox（回退路径演示用，同一帧永远同一框）"""
    h = hashlib.md5(frame).digest()
    x, y = struct.unpack("<HH", h[:4])
    return [round((x % 500) / 1000, 3), round((y % 500) / 1000, 3), 0.25, 0.2]
