"""
权重校正工具 — 用标注数据校正效价/唤醒度权重。

方法:
    1. 收集N条标注样本: {E1..E12, K, 标注效价, 标注唤醒度}
    2. 计算每个E_i与标注效价/唤醒度的Pearson相关系数
    3. 用相关系数替换初始规则权重
    4. 无需训练模型，纯统计分析

参考: VCE专著中大量使用Pearson r作为参数关联性的度量(Table 1, 6-18)
"""

import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml
from dataclasses import dataclass


@dataclass
class CalibrationSample:
    """单条校准样本。"""
    e_params: Dict[str, float]   # E1-E12
    K: float                      # K值
    valence_label: float          # 标注效价 [0, 1]
    arousal_label: float          # 标注唤醒度 [0, 1]


def pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson相关系数。"""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mask = ~(np.isnan(x) | np.isnan(y))
    if mask.sum() < 3:
        return 0.0
    x_m = x[mask] - x[mask].mean()
    y_m = y[mask] - y[mask].mean()
    denom = np.sqrt((x_m**2).sum() * (y_m**2).sum())
    if denom < 1e-10:
        return 0.0
    return float((x_m * y_m).sum() / denom)


def pearson_correlation_matrix(
    samples: List[CalibrationSample],
) -> Dict[str, Dict[str, float]]:
    """
    计算每个E参数与效价、唤醒度的Pearson相关系数矩阵。

    Returns
    -------
    { 'aggression': {'valence': r, 'arousal': r}, ... }
    """
    n = len(samples)
    param_names = list(samples[0].e_params.keys())

    e_matrix = {}
    for p in param_names:
        e_matrix[p] = np.array([s.e_params[p] for s in samples])

    v_labels = np.array([s.valence_label for s in samples])
    a_labels = np.array([s.arousal_label for s in samples])

    result = {}
    for p in param_names:
        result[p] = {
            'valence': pearson_r(e_matrix[p], v_labels),
            'arousal': pearson_r(e_matrix[p], a_labels),
        }
    return result


def calibrate_weights(
    samples: List[CalibrationSample],
    weights_path: Path,
    output_path: Optional[Path] = None,
    blend_ratio: float = 0.5,
) -> Dict[str, Dict[str, float]]:
    """
    用标注数据校正权重并保存到YAML。

    校正策略:
        new_weight = blend_ratio × (Pearson r) + (1 - blend_ratio) × old_weight
        blend_ratio=0.5 表示新旧各半，保守校正。

    Parameters
    ----------
    samples : list
        校准样本列表。
    weights_path : Path
        原始权重YAML路径。
    output_path : Path, optional
        输出路径。None则覆盖原文件。
    blend_ratio : float
        新数据权重占比 [0, 1]。0=全用旧权重，1=全用Pearson r。

    Returns
    -------
    校正后的权重字典
    """
    # 加载旧权重
    with open(weights_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 计算Pearson r矩阵
    corr = pearson_correlation_matrix(samples)

    # 混合新旧权重
    new_valence = {}
    new_arousal = {}
    for param, r_dict in corr.items():
        old_v = config['weights']['valence'].get(param, 0.0)
        old_a = config['weights']['arousal'].get(param, 0.0)
        new_v = blend_ratio * r_dict['valence'] + (1 - blend_ratio) * old_v
        new_a = blend_ratio * r_dict['arousal'] + (1 - blend_ratio) * old_a
        new_valence[param] = round(new_v, 4)
        new_arousal[param] = round(new_a, 4)

    # 更新配置
    config['weights']['valence'] = new_valence
    config['weights']['arousal'] = new_arousal

    # 保存
    out = output_path or weights_path
    with open(out, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return {'valence': new_valence, 'arousal': new_arousal}
