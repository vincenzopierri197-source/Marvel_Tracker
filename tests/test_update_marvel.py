import unittest

from scripts.update_marvel import extract_json, is_gemini_quota_error, normalize, slug


class UpdateMarvelTests(unittest.TestCase):

    def test_gemini_quota_error_is_detected(self):
        exc = RuntimeError('Gemini API HTTP 429: RESOURCE_EXHAUSTED - You exceeded your current quota')
        self.assertTrue(is_gemini_quota_error(exc))

    def test_other_errors_are_not_misclassified_as_quota(self):
        self.assertFalse(is_gemini_quota_error(RuntimeError("Groq API HTTP 429: rate limit")))

    def test_slug_normalizes_accents(self):
        self.assertEqual(slug("I Fantastici Quattro: Gli Inizi"), "i-fantastici-quattro-gli-inizi")

    def test_extract_json_plain_and_fenced(self):
        self.assertEqual(extract_json('{"researchUpdates":[]}'), {"researchUpdates": []})
        self.assertEqual(extract_json('```json\n{"sourceUpdates":[]}\n```'), {"sourceUpdates": []})

    def test_normalize_only_accepts_grounded_source_urls(self):
        data = {
            "orders": {"marvel": {"sections": [{"items": [{"title": "Iron Man"}]}]}},
            "sourceUpdates": [],
            "researchUpdates": [],
        }
        grounded = [{"title": "Marvel", "url": "https://www.marvel.com/news"}]
        ai = {
            "researchUpdates": [{
                "title": "Notizia test",
                "summary": "Test",
                "sources": [{"title": "Marvel", "url": "https://www.marvel.com/news"}],
            }],
            "sourceUpdates": [
                {"title": "Nuova serie", "type": "serie", "year": 2027, "source": "https://www.marvel.com/news"},
                {"title": "URL inventato", "type": "film", "year": 2027, "source": "https://fake.invalid/news"},
            ],
        }
        news, titles = normalize(data, ai, grounded)
        self.assertEqual(news, 1)
        self.assertEqual(titles, 1)
        self.assertEqual(len(data["sourceUpdates"]), 1)
        self.assertEqual(data["sourceUpdates"][0]["title"], "Nuova serie")


if __name__ == "__main__":
    unittest.main()
