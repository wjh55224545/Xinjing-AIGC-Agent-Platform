"""
参数验证工具。

确保所有情绪参数输出在合理范围内，并提供质量检查功能。
"""

import numpy as np
from typing import Dict, List, Tuple
from ..utils.constants import (
    NORMAL_NORMS, NORMAL_SDS, CORRELATION_MATRIX,
    ALL_EMOTION_PARAMS, PARAM_NAMES_ZH,
)


def validate_parameter( name: str, value: float) -> Tuple[bool, str]:
    """
    验证单个参数的合理性。

    Checks:
    1. 在[0, 100]范围内 (E10可超过100%)
    2. 在M ± 3SD范围内 (统计合理性)

    Returns
    -------
    (is_valid, message) : Tuple[bool, str]
    """
    # 范围检查
    if name == 'neuroticism':
        if value < 0:
            return False, f"负值: {value:.2f}"
    else:
        if value < 0 or value > 100:
            return False, f"超出[0,100]范围: {value:.2f}"

    # 统计合理性 (M ± 3SD)
    if name in NORMAL_NORMS and name in NORMAL_SDS:
        M = NORMAL_NORMS[name]
        SD = NORMAL_SDS[name]
        lower = M - 3 * SD
        upper = M + 3 * SD

        if name == 'neuroticism':
            if value > upper * 1.5:
                return False, f"过高: {value:.2f} > {upper*1.5:.1f}"
        else:
            if value < max(0, lower) or value > upper:
                return True, f"偏离常模: {value:.2f} (常模 {M:.1f} ± {3*SD:.1f})"

    return True, "ok"


def validate_all(params: Dict[str, float]) -> Dict[str, List[str]]:
    """
    验证所有参数。

    Returns
    -------
    issues : dict
        {param_name: [issue_messages]}
    """
    issues = {}
    for name, value in params.items():
        is_valid, msg = validate_parameter(name, value)
        if not is_valid:
            issues[name] = [msg]
        elif msg != "ok":
            issues[name] = [msg]  # 警告但不阻塞

    return issues


def compute_correlation_matrix(
    results_list: List[Dict[str, float]],
) -> Dict[Tuple[str, str], float]:
    """
    从多个样本的结果计算参数间的Pearson相关系数矩阵。

    用于验证输出是否接近专著中的已知相关性。
    """
    n_samples = len(results_list)
    if n_samples < 3:
        return {}

    param_names = list(results_list[0].keys())
    corr_matrix = {}

    for i, p1 in enumerate(param_names):
        for j, p2 in enumerate(param_names):
            if i >= j:
                continue
            x = np.array([r[p1] for r in results_list])
            y = np.array([r[p2] for r in results_list])
            if np.std(x) > 0 and np.std(y) > 0:
                corr = float(np.corrcoef(x, y)[0, 1])
                if abs(corr) > 0.3:  # 仅记录显著相关
                    corr_matrix[(p1, p2)] = corr

    return corr_matrix


def compare_with_expected_correlations(
    observed: Dict[Tuple[str, str], float],
) -> Dict[str, float]:
    """
    比较观测到的相关性与专著中的预期值。

    Returns
    -------
    deviations : dict
        {(p1, p2): observed - expected}
    """
    deviations = {}
    for (p1, p2), expected in CORRELATION_MATRIX.items():
        if (p1, p2) in observed:
            deviations[f"{p1}_{p2}"] = observed[(p1, p2)] - expected
        else:
            deviations[f"{p1}_{p2}"] = float('nan')
    return deviations


def print_emotion_report(params: Dict[str, float]):
    """打印格式化的情绪参数报告 (中英文)。"""
    print("\n" + "=" * 60)
    print("情绪与心理生理参数报告")
    print("=" * 60)

    groups = [
        ("负性情绪", ['aggression', 'stress', 'tension', 'suspicious']),
        ("正性情绪", ['balance', 'charm', 'energy', 'self_regulation']),
        ("生理情绪", ['inhibition', 'neuroticism', 'depression', 'happiness']),
    ]

    for group_name, param_list in groups:
        print(f"\n--- {group_name} ---")
        for p in param_list:
            if p in params:
                name_zh = PARAM_NAMES_ZH.get(p, p)
                value = params[p]
                norm = NORMAL_NORMS.get(p, None)
                bar = _make_bar(value)
                norm_str = f" (常模: {norm:.1f})" if norm else ""
                print(f"  {name_zh:8s} [{p:18s}]: {value:6.1f}% {bar} {norm_str}")


def _make_bar(value: float, width: int = 20) -> str:
    """生成简易的ASCII进度条。"""
    filled = int(np.clip(value / 100.0, 0, 1) * width)
    return "█" * filled + "░" * (width - filled)
