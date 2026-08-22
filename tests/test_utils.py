import unittest

from app.utils import extract_json


class ExtractJsonTests(unittest.TestCase):
    def test_extracts_json_from_markdown_fence(self):
        text = '```json\n{"intent": ["general"]}\n```'
        self.assertEqual(extract_json(text), '{"intent": ["general"]}')

    def test_extracts_json_surrounded_by_explanation(self):
        text = '结果如下：{"confidence": 0.9}，请查收。'
        self.assertEqual(extract_json(text), '{"confidence": 0.9}')


if __name__ == "__main__":
    unittest.main()
