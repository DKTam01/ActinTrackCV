import unittest
from unittest import mock

import cv2
import numpy as np

from actintrack_app import video_processing as vp
from actintrack_app.video_processing import MediaLoadError


def _fake_cap(*, opened=True, count=5, read_results=None, read_error=None):
    cap = mock.MagicMock()
    cap.isOpened.return_value = opened
    cap.get.return_value = count
    if read_error is not None:
        cap.read.side_effect = read_error
    elif read_results is not None:
        cap.read.side_effect = read_results
    return cap


class LoadVideoFrameTest(unittest.TestCase):
    def test_decoder_cv2_error_becomes_media_load_error(self) -> None:
        cap = _fake_cap(count=5, read_error=cv2.error("decode failure"))
        with mock.patch.object(vp.cv2, "VideoCapture", return_value=cap):
            with self.assertRaises(MediaLoadError):
                vp.load_video_frame("clip.avi", 0)
        cap.release.assert_called()

    def test_empty_frame_becomes_media_load_error(self) -> None:
        cap = _fake_cap(count=5, read_results=[(True, np.zeros((0,), np.uint8))])
        with mock.patch.object(vp.cv2, "VideoCapture", return_value=cap):
            with self.assertRaises(MediaLoadError):
                vp.load_video_frame("clip.avi", 0)

    def test_unreadable_frame_becomes_media_load_error(self) -> None:
        cap = _fake_cap(count=5, read_results=[(False, None)])
        with mock.patch.object(vp.cv2, "VideoCapture", return_value=cap):
            with self.assertRaises(MediaLoadError):
                vp.load_video_frame("clip.avi", 0)

    def test_valid_frame_is_returned(self) -> None:
        frame = np.zeros((4, 4, 3), np.uint8)
        cap = _fake_cap(count=5, read_results=[(True, frame)])
        with mock.patch.object(vp.cv2, "VideoCapture", return_value=cap):
            out = vp.load_video_frame("clip.mp4", 0)
        self.assertIs(out, frame)


class FrameCountTest(unittest.TestCase):
    def test_decoder_cv2_error_becomes_media_load_error(self) -> None:
        cap = _fake_cap(count=0, read_error=cv2.error("read failure"))
        with mock.patch.object(vp.cv2, "VideoCapture", return_value=cap):
            with self.assertRaises(MediaLoadError):
                vp.get_video_frame_count("clip.avi")


class AssertVideoReadableTest(unittest.TestCase):
    def test_returns_count_when_frame_zero_decodes(self) -> None:
        frame = np.zeros((4, 4, 3), np.uint8)
        caps = [
            _fake_cap(count=5),
            _fake_cap(count=5, read_results=[(True, frame)]),
        ]
        with mock.patch.object(vp.cv2, "VideoCapture", side_effect=caps):
            self.assertEqual(vp.assert_video_readable("clip.mp4"), 5)

    def test_raises_when_frame_zero_unreadable(self) -> None:
        caps = [
            _fake_cap(count=5),
            _fake_cap(count=5, read_results=[(False, None)]),
        ]
        with mock.patch.object(vp.cv2, "VideoCapture", side_effect=caps):
            with self.assertRaises(MediaLoadError):
                vp.assert_video_readable("clip.avi")

    def test_raises_when_decoder_throws_cv2_error(self) -> None:
        caps = [
            _fake_cap(count=5),
            _fake_cap(count=5, read_error=cv2.error("decode failure")),
        ]
        with mock.patch.object(vp.cv2, "VideoCapture", side_effect=caps):
            with self.assertRaises(MediaLoadError):
                vp.assert_video_readable("clip.avi")


if __name__ == "__main__":
    unittest.main()
