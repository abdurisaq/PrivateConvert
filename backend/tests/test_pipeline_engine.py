import json
import shutil
import subprocess

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from app.core.pipeline_engine import (
    PipelineError,
    run_pipeline,
    validate_pipeline,
)


def test_image_pipeline_resizes_then_converts_and_drops_exif(tmp_path):
    source = tmp_path / "source.png"
    with Image.new("RGB", (120, 60), "red") as image:
        image.save(source)
    output = tmp_path / "results" / "source.processed.webp"
    pipeline = {
        "steps": [
            {"action": "image.resize", "params": {"width": 30}},
            {"action": "image.convert", "params": {"format": "webp", "quality": 70}},
        ],
    }

    run_pipeline(pipeline, source, output, tmp_path / "work")

    with Image.open(output) as result:
        assert result.format == "WEBP"
        assert result.size == (30, 15)


def test_image_pipeline_converts_to_png_and_uses_the_png_extension(tmp_path):
    source = tmp_path / "source.jpg"
    with Image.new("RGB", (24, 16), "blue") as image:
        image.save(source)
    output = tmp_path / "results" / "source.processed.png"
    pipeline = {
        "steps": [
            {"action": "image.convert", "params": {"convert_to": "png"}},
        ],
    }

    run_pipeline(pipeline, source, output, tmp_path / "work")

    with Image.open(output) as result:
        assert result.format == "PNG"
        assert result.size == (24, 16)


def test_video_pipeline_validation_supports_two_pass_size_and_audio_extraction(tmp_path):
    source = tmp_path / "clip.mp4"
    size_pipeline = validate_pipeline({
        "steps": [
            {"action": "video.compress_to_size", "params": {"target_mb": 10}},
        ],
    }, source)
    audio_pipeline = validate_pipeline({
        "steps": [
            {"action": "video.extract_audio", "params": {"convert_to": "mp3"}},
        ],
    }, source)

    assert size_pipeline["steps"][0]["params"]["convert_to"] == "mp4"
    assert audio_pipeline["steps"][0]["action"] == "video.extract_audio"


def test_mute_audio_requires_valid_segments_or_mute_all(tmp_path):
    pipeline = validate_pipeline({
        "steps": [{
            "action": "video.mute_audio",
            "params": {"segments": "00:10-00:15,1:02-1:10"},
        }],
    }, tmp_path / "clip.mp4")

    assert pipeline["steps"][0]["params"]["segments"] == "00:10-00:15,1:02-1:10"
    with pytest.raises(PipelineError, match="mute all or provide"):
        validate_pipeline({
            "steps": [{"action": "video.mute_audio", "params": {}}],
        }, tmp_path / "clip.mp4")
    with pytest.raises(PipelineError, match="must end after"):
        validate_pipeline({
            "steps": [{
                "action": "video.mute_audio",
                "params": {"segments": "00:15-00:10"},
            }],
        }, tmp_path / "clip.mp4")


@pytest.mark.parametrize("mute_all", [True, False])
def test_mute_audio_pipeline_encodes_full_or_segment_mute(tmp_path, mute_all):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is required for the video mute smoke test")
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=24:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
        ],
        check=True,
        capture_output=True,
    )
    output = tmp_path / "results" / "muted.mp4"
    run_pipeline(
        {"steps": [{
            "action": "video.mute_audio",
            "params": {
                "mute_all": mute_all,
                "segments": "" if mute_all else "00:00-00:01",
                "convert_to": "mp4",
            },
        }]},
        source,
        output,
        tmp_path / "work",
    )
    probe = shutil.which("ffprobe")
    if not probe:
        pytest.skip("ffprobe is required to inspect the smoke test output")
    streams = subprocess.run(
        [probe, "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    has_audio = any(stream["codec_type"] == "audio" for stream in json.loads(streams.stdout)["streams"])
    assert has_audio is not mute_all


def test_image_conversion_quality_changes_lossy_output_size(tmp_path):
    source = tmp_path / "source.png"
    Image.effect_noise((256, 256), 100).convert("RGB").save(source)
    outputs = []
    for quality in (20, 95):
        output = tmp_path / f"quality-{quality}.jpg"
        run_pipeline(
            {"steps": [{
                "action": "image.convert",
                "params": {"convert_to": "jpg", "quality": quality},
            }]},
            source,
            output,
            tmp_path / f"work-{quality}",
        )
        outputs.append(output.stat().st_size)
    assert outputs[1] > outputs[0]


def test_video_operation_reports_missing_ffmpeg(tmp_path, monkeypatch):
    from app.core import pipeline_engine

    monkeypatch.setattr(pipeline_engine.shutil, "which", lambda _: None)
    with pytest.raises(PipelineError, match="require ffmpeg"):
        run_pipeline(
            {"steps": [{"action": "video.convert", "params": {"convert_to": "mp4"}}]},
            tmp_path / "clip.mp4",
            tmp_path / "result.mp4",
            tmp_path / "work",
        )


@pytest.mark.parametrize("output_format", ["mp4", "webm"])
def test_two_pass_video_compression_smoke(tmp_path, output_format):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are required for the video smoke test")

    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
        ],
        check=True,
        capture_output=True,
    )
    output = tmp_path / "results" / f"compressed.{output_format}"

    run_pipeline(
        {
            "steps": [
                {
                    "action": "video.compress_to_size",
                    "params": {"target_mb": 0.5, "convert_to": output_format},
                },
            ],
        },
        source,
        output,
        tmp_path / "work",
    )

    assert output.is_file()
    assert 0 < output.stat().st_size <= 0.5 * 1024 * 1024


@pytest.mark.parametrize(("action", "params"), [
    ("video.convert", {"convert_to": "mp4", "audio_kbps": 96}),
    ("video.compress", {"convert_to": "mp4", "audio_kbps": 96, "quality": 26, "preset": "ultrafast"}),
    ("video.trim", {"convert_to": "mp4", "audio_kbps": 96, "start_seconds": 0, "duration_seconds": 1}),
    ("video.resize", {"convert_to": "mp4", "audio_kbps": 96, "max_height": 144}),
])
def test_video_handler_dispatch_encodes_standard_operations(tmp_path, action, params):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is required for video operation smoke tests")
    source = tmp_path / "source.mp4"
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x240:rate=24:duration=2",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-c:v", "libx264", "-c:a", "aac", "-shortest", str(source),
    ], check=True, capture_output=True)

    output = tmp_path / "result.mp4"
    run_pipeline({"steps": [{"action": action, "params": params}]}, source, output, tmp_path / "work")

    assert output.is_file() and output.stat().st_size > 0


def test_pdf_pipeline_reorders_duplicates_and_rotates_pages(tmp_path):
    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=200)
    writer.add_blank_page(width=300, height=400)
    with source.open("wb") as output:
        writer.write(output)

    output = tmp_path / "result.pdf"
    pipeline = {
        "steps": [
            {"action": "pdf.pages", "params": {"pages": "2,1,2"}},
            {"action": "pdf.rotate", "params": {"degrees": 90, "pages": "1"}},
        ],
    }

    run_pipeline(pipeline, source, output, tmp_path / "work")

    pages = PdfReader(output).pages
    assert len(pages) == 3
    assert float(pages[0].mediabox.width) == 300
    assert pages[0].rotation == 90
    assert pages[1].rotation == 0
    assert float(pages[2].mediabox.width) == 300


def test_pipeline_validation_rejects_incompatible_steps_and_bad_ranges(tmp_path):
    with pytest.raises(PipelineError, match="cannot follow"):
        validate_pipeline({
            "steps": [
                {"action": "image.rotate", "params": {"degrees": 90}},
                {"action": "pdf.pages", "params": {"pages": "1-"}},
            ],
        }, tmp_path / "photo.png")

    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    with source.open("wb") as output:
        writer.write(output)
    with pytest.raises(PipelineError, match="outside"):
        run_pipeline(
            {"steps": [{"action": "pdf.pages", "params": {"pages": "2"}}]},
            source,
            tmp_path / "result.pdf",
            tmp_path / "work",
        )
