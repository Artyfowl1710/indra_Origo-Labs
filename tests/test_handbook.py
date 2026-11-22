import unittest

from scripts.build_handbook import BOOK, rewrite


class HandbookTests(unittest.TestCase):
    def test_video_and_poster_use_the_published_media_directory(self):
        content = (
            '<video src="../media/indra-city.mp4" '
            'poster="../media/city-poster.webp"></video>'
        )

        self.assertEqual(
            rewrite(content, BOOK / "index.md"),
            '<video src="media/indra-city.mp4" '
            'poster="media/city-poster.webp"></video>',
        )
