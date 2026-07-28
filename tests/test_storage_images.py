import numpy as np

from carma.storage.images import clear_images, save_hit_images


def test_saves_both_images_and_returns_filenames(tmp_path):
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    crop = np.zeros((10, 10, 3), dtype=np.uint8)
    images_dir = tmp_path / "images"

    frame_filename, crop_filename = save_hit_images(frame, crop, str(images_dir))

    assert (images_dir / frame_filename).is_file()
    assert (images_dir / crop_filename).is_file()
    assert frame_filename.endswith("_frame.jpg")
    assert crop_filename.endswith("_crop.jpg")


def test_creates_images_dir_if_missing(tmp_path):
    images_dir = tmp_path / "nested" / "images"
    frame = np.zeros((5, 5, 3), dtype=np.uint8)

    save_hit_images(frame, frame, str(images_dir))

    assert images_dir.is_dir()


def test_filenames_are_unique_across_calls(tmp_path):
    frame = np.zeros((5, 5, 3), dtype=np.uint8)
    images_dir = tmp_path / "images"

    first = save_hit_images(frame, frame, str(images_dir))
    second = save_hit_images(frame, frame, str(images_dir))

    assert first != second


def test_clear_images_removes_all_files(tmp_path):
    frame = np.zeros((5, 5, 3), dtype=np.uint8)
    images_dir = tmp_path / "images"
    save_hit_images(frame, frame, str(images_dir))
    save_hit_images(frame, frame, str(images_dir))
    assert len(list(images_dir.iterdir())) == 4

    clear_images(str(images_dir))

    assert list(images_dir.iterdir()) == []
    assert images_dir.is_dir()  # directory itself stays


def test_clear_images_on_missing_dir_does_not_raise(tmp_path):
    clear_images(str(tmp_path / "does-not-exist"))  # must not raise
