"""测试 extract_json — 各种格式的 JSON 提取"""

from app.domain.agent.base import extract_json


class TestExtractJson:

    def test_pure_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown_block(self):
        result = extract_json('```json\n{"name": "test"}\n```')
        assert result == {"name": "test"}

    def test_json_with_text_before_after(self):
        result = extract_json('一些文字 {"a": 1} 更多文字')
        assert result == {"a": 1}

    def test_nested_json(self):
        result = extract_json('{"data": {"values": [1, 2, 3]}}')
        assert result == {"data": {"values": [1, 2, 3]}}

    def test_array_json(self):
        result = extract_json('[1, 2, {"k": "v"}]')
        assert result == [1, 2, {"k": "v"}]

    def test_invalid_raises(self):
        try:
            extract_json("not json at all")
            assert False, "应该抛出异常"
        except ValueError:
            pass
