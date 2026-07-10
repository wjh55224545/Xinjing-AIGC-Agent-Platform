"""
平台适配器测试
===============

测试国产算力平台适配层的各项功能。
"""

import os
import pytest
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestPlatformAdapter:
    """平台适配器测试"""

    def test_list_platforms(self):
        """测试列出所有平台"""
        from backend.llm.platform_adapter import PlatformAdapter

        platforms = PlatformAdapter.list_platforms()
        assert len(platforms) >= 4
        platform_ids = [p["id"] for p in platforms]
        assert "gitee_ai" in platform_ids
        assert "deepseek" in platform_ids
        assert "local" in platform_ids

    def test_platform_is_domestic(self):
        """测试所有平台标记为国产"""
        from backend.llm.platform_adapter import PlatformAdapter

        platforms = PlatformAdapter.list_platforms()
        for p in platforms:
            assert p["is_domestic"] is True, f"{p['id']} 未标记为国产平台"

    def test_gitee_ai_config(self):
        """测试Gitee.AI平台配置"""
        from backend.llm.platform_adapter import PLATFORM_CONFIGS

        config = PLATFORM_CONFIGS["gitee_ai"]
        assert config["name"] == "Gitee.AI (沐曦GPU)"
        assert "沐曦" in config["provider"]
        assert "gitee.ai" in config["base_url"]
        assert config["is_domestic"] is True

    def test_platform_info_structure(self):
        """测试平台信息数据结构"""
        from backend.llm.platform_adapter import PlatformAdapter

        platforms = PlatformAdapter.list_platforms()
        required_fields = ["id", "name", "description", "is_domestic", "provider", "default_model"]
        for p in platforms:
            for field in required_fields:
                assert field in p, f"{p['id']} 缺少字段 {field}"

    def test_get_platform_adapter_cache(self):
        """测试平台适配器缓存"""
        from backend.llm.platform_adapter import get_platform_adapter

        adapter1 = get_platform_adapter(platform="gitee_ai")
        adapter2 = get_platform_adapter(platform="gitee_ai")
        assert adapter1 is adapter2  # 缓存命中

    def test_adapter_platform_info(self):
        """测试适配器平台信息"""
        from backend.llm.platform_adapter import PlatformAdapter

        adapter = PlatformAdapter(platform="gitee_ai")
        info = adapter.get_platform_info()
        assert info["platform"] == "gitee_ai"
        assert "沐曦" in info["gpu_vendor"]
        assert info["is_domestic"] is True


class TestPlatformEnum:
    """平台枚举测试"""

    def test_platform_values(self):
        """测试平台枚举值"""
        from backend.llm.platform_adapter import Platform

        assert Platform.GITEE_AI.value == "gitee_ai"
        assert Platform.DEEPSEEK.value == "deepseek"
        assert Platform.LOCAL.value == "local"
        assert Platform.CUSTOM.value == "custom"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
