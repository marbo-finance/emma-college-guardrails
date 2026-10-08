import json
import os
import tempfile
import unittest

from emma_college import access
from emma_college.access import ProfileFileError, profile_from_dict


def _write(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return path


class TestPupilProfileFile(unittest.TestCase):
    def tearDown(self):
        for k in [k for k in access.PROFILES if k.startswith("t-")]:
            del access.PROFILES[k]

    def test_valid_profile_combines_and_overrides(self):
        p = profile_from_dict({"name": "t-a", "label": "Groupe A", "base": ["lecture_vocale", "une_etape_a_la_fois"],
                               "overrides": {"max_sentence_words": 10}})
        self.assertEqual(p.max_sentence_words, 10)
        self.assertEqual(p.max_steps_per_reply, 1)
        self.assertTrue(p.spoken_math)

    def test_diagnosis_like_label_is_refused(self):
        for bad in ("dyslexie", "Élève TDAH", "autisme léger", "student with ADHD", "handicap visuel"):
            with self.assertRaises(ProfileFileError, msg=bad):
                profile_from_dict({"name": "t-b", "label": bad, "base": []})

    def test_unknown_fields_and_keys_are_refused(self):
        with self.assertRaises(ProfileFileError):
            profile_from_dict({"name": "t-c", "label": "x", "diagnosis": "none"})
        with self.assertRaises(ProfileFileError):
            profile_from_dict({"name": "t-c", "label": "x", "overrides": {"colour": 1}})
        with self.assertRaises(ProfileFileError):
            profile_from_dict({"name": "t-c", "label": "x", "base": ["nope"]})

    def test_cannot_shadow_builtin_or_bad_numbers(self):
        with self.assertRaises(ProfileFileError):
            profile_from_dict({"name": "default", "label": "x"})
        with self.assertRaises(ProfileFileError):
            profile_from_dict({"name": "t-d", "label": "x", "overrides": {"max_sentence_words": 999}})
        with self.assertRaises(ProfileFileError):
            profile_from_dict({"name": "t-d", "label": "x", "overrides": {"spoken_math": 1}})

    def test_file_registers_profiles_usable_by_harness(self):
        path = _write({"schema": access.SCHEMA, "profiles": [
            {"name": "t-e", "label": "Texte court", "base": ["texte_aere"], "overrides": {"max_sentence_words": 6}}]})
        try:
            access.load_profiles_file(path)
        finally:
            os.unlink(path)
        from emma_college.harness import Harness
        r = Harness(profile="t-e").check("a", "Cette phrase est vraiment trop longue pour cet élève.",
                                         {"statement": "", "answer": "x=5"})
        self.assertTrue(any(getattr(f, "code", "") == "LONG_SENTENCE" for f in r.findings))

    def test_wrong_schema_is_refused(self):
        path = _write({"schema": "other", "profiles": []})
        try:
            with self.assertRaises(ProfileFileError):
                access.load_profiles_file(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
