import unittest
from generator import validate, plan, caption_layout, timestamp, SECONDS_PER_SCENE
from PIL import Image, ImageDraw


class InputTests(unittest.TestCase):
    def test_rejects_bad_input(self):
        for data in [None, {}, {'topic': 'ab'}, {'topic': 'valid', 'captions': ['x']*7},
                     {'topic': 'valid', 'theme': 'invalid'}, {'topic': 'valid', 'theme': []},
                     {'topic': 'valid', 'music': 'yes'}, {'topic': 'valid', 'captions': [' '*4]}]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                validate(data)

    def test_custom_captions_preserved(self):
        topic, captions, _, _ = validate({'topic': '  Morning habits  ', 'captions': [' Start small ']})
        self.assertEqual(plan(topic, captions), ['Morning habits', 'Start small'])

    def test_default_outline_is_bounded(self):
        self.assertEqual(len(plan('Morning habits', [])), 5)

    def test_video_clock_and_scene_duration(self):
        self.assertEqual(SECONDS_PER_SCENE, 4)
        self.assertEqual([timestamp(t) for t in (0, 4, 16, 28, 65)],
                         ['00:00', '00:04', '00:16', '00:28', '01:05'])

    def test_wide_captions_fit_safe_area(self):
        draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        for text in ['W'*180, 'A '*90, 'A short caption.', 'word\n'*30]:
            with self.subTest(text=text):
                wrapped, face = caption_layout(text)
                left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=face, spacing=12)
                self.assertLessEqual(right-left, 1128)
                self.assertLessEqual(bottom-top, 350)
                self.assertEqual(''.join(wrapped.split()), ''.join(text.split()))


if __name__ == '__main__':
    unittest.main()
