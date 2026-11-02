"""Validated file-operation pipelines for images, PDFs, and audio/video."""

import json
import math
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader, PdfWriter
from app.core.pipeline_catalog import (
    AUDIO_CODECS,
    AUDIO_EXTENSIONS,
    FORMAT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    OPERATIONS,
    VIDEO_EXTENSIONS,
)

_PIL_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".tif": "TIFF", ".tiff": "TIFF"}


class PipelineError(ValueError):
    """An invalid pipeline definition or a user-correctable operation failure."""


def _timestamp_seconds(value: str) -> float:
    parts = value.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError("Invalid timestamp")


def _mute_segments(value: str) -> list[tuple[float, float]]:
    segments = []
    for section in filter(None, (part.strip() for part in value.split(","))):
        match = re.fullmatch(r"([^-\s]+)\s*-\s*([^-\s]+)", section)
        if not match:
            raise PipelineError("Mute ranges must use start-end pairs such as 00:10-00:15")
        try:
            start, end = map(_timestamp_seconds, match.groups())
        except ValueError as exc:
            raise PipelineError(f"Invalid mute range '{section}'") from exc
        if not all(map(math.isfinite, (start, end))) or start < 0 or end <= start:
            raise PipelineError(f"Mute range '{section}' must end after it starts")
        segments.append((start, end))
    return segments


def file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    raise PipelineError(f"Unsupported pipeline input type: {suffix or 'no file extension'}")


def _coerce_param(action: str, name: str, value, expected: str):
    def integer(v):
        return not isinstance(v, bool) and isinstance(v, (int, float)) and int(v) == v

    def number(v):
        return not isinstance(v, bool) and isinstance(v, (int, float))

    coercers = {
        "integer": (integer, int),
        "number": (number, float),
        "boolean": (lambda v: isinstance(v, bool), lambda v: v),
        "string": (lambda v: isinstance(v, str), lambda v: v),
    }
    valid, convert = coercers[expected]
    if not valid(value):
        article = "an" if expected == "integer" else "a"
        raise PipelineError(f"{action}: '{name}' must be {article} {expected}")
    return convert(value)


def _check_constraints(action: str, name: str, value, spec: dict) -> None:
    if "minimum" in spec and value < spec["minimum"]:
        raise PipelineError(f"{action}: '{name}' must be at least {spec['minimum']}")
    if "maximum" in spec and value > spec["maximum"]:
        raise PipelineError(f"{action}: '{name}' must be at most {spec['maximum']}")
    if "enum" in spec and value not in spec["enum"]:
        raise PipelineError(f"{action}: '{name}' must be one of {spec['enum']}")


def _validate_cross_params(action: str, params: dict) -> None:
    if action == "image.resize" and not (params["width"] or params["height"]):
        raise PipelineError("image.resize requires a width, a height, or both")
    if action == "video.mute_audio" and not params["mute_all"] and not _mute_segments(params["segments"]):
        raise PipelineError("Select mute all or provide at least one mute range")


def _validate_params(action: str, params: dict) -> dict:
    schema = OPERATIONS[action]["parameters"]
    if action == "image.convert" and "format" in params and "convert_to" not in params:
        params = {**params, "convert_to": params["format"]}
        params.pop("format")
    unknown = set(params) - set(schema)
    if unknown:
        raise PipelineError(f"{action}: unknown parameter(s): {', '.join(sorted(unknown))}")

    normalized = {}
    for name, spec in schema.items():
        value = params.get(name, spec.get("default"))
        if value is None or value == "":
            if "default" not in spec:
                raise PipelineError(f"{action}: '{name}' is required")
        else:
            value = _coerce_param(action, name, value, spec["type"])
            _check_constraints(action, name, value, spec)
        normalized[name] = value
    _validate_cross_params(action, normalized)
    return normalized


def validate_pipeline(definition: dict, input_path: Path | None = None) -> dict:
    if not isinstance(definition, dict):
        raise PipelineError("Pipeline must be a JSON object")
    if definition.get("schema_version", 1) != 1:
        raise PipelineError("Unsupported pipeline schema version")
    steps = definition.get("steps")
    if not isinstance(steps, list) or not steps or len(steps) > 20:
        raise PipelineError("A pipeline must contain between 1 and 20 steps")
    current_kind = file_kind(input_path) if input_path else definition.get("input_kind")
    clean_steps = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict) or not isinstance(step.get("action"), str):
            raise PipelineError(f"Step {index} must specify an action")
        action = step["action"]
        operation = OPERATIONS.get(action)
        if operation is None:
            raise PipelineError(f"Step {index}: unknown action '{action}'")
        if current_kind and current_kind not in operation["input_types"]:
            raise PipelineError(
                f"Step {index}: '{action}' cannot follow a {current_kind} operation"
            )
        params = step.get("params", {})
        if not isinstance(params, dict):
            raise PipelineError(f"Step {index}: params must be an object")
        clean_steps.append({"action": action, "params": _validate_params(action, params)})
        current_kind = operation["output_type"]
    return {
        "schema_version": 1,
        "name": str(definition.get("name") or "Untitled pipeline").strip()[:100],
        "description": str(definition.get("description") or "").strip()[:500],
        "input_kind": file_kind(input_path) if input_path else definition.get("input_kind"),
        "steps": clean_steps,
    }


def output_extension(definition: dict, input_filename: str) -> str:
    final_step = definition["steps"][-1]
    operation = OPERATIONS[final_step["action"]]
    if "output_extension" in operation:
        return operation["output_extension"]
    if "extension_param" in operation:
        return FORMAT_EXTENSIONS[final_step["params"][operation["extension_param"]]]
    return Path(input_filename).suffix.lower()


def _page_range(section: str, page_count: int) -> list[int]:
    match = re.fullmatch(r"(\d*)\s*-\s*(\d*)", section)
    try:
        start, end = (
            (int(match.group(1) or 1), int(match.group(2) or page_count))
            if match else (int(section), int(section))
        )
    except ValueError as exc:
        raise PipelineError(f"Invalid page range '{section}'") from exc
    if not 1 <= start <= page_count or not 1 <= end <= page_count:
        raise PipelineError(f"Page range '{section}' is outside 1-{page_count}")
    direction = 1 if end >= start else -1
    return list(range(start - 1, end - 1 + direction, direction))


def _page_indexes(spec: str, page_count: int) -> list[int]:
    indexes = []
    for section in spec.split(","):
        if section.strip():
            indexes.extend(_page_range(section.strip(), page_count))
    if not indexes:
        raise PipelineError("Select at least one page")
    return indexes


def _next_path(workdir: Path, suffix: str) -> Path:
    return workdir / f"{uuid.uuid4().hex}{suffix}"


def _video_encoder_args(output_format: str, quality: int = 23, preset: str = "medium") -> list[str]:
    if output_format == "webm":
        cpu_used = {"ultrafast": "8", "fast": "6", "medium": "4", "slow": "1"}[preset]
        return [
            "-c:v", "libvpx-vp9",
            "-crf", str(quality),
            "-b:v", "0",
            "-deadline", "good",
            "-cpu-used", cpu_used,
        ]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(quality)]


def _run_ffmpeg(command: list[str], timeout: int = 3600):
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode(errors="replace")[-600:]
        raise PipelineError(f"Video encoding failed: {detail or exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise PipelineError(f"Video encoding timed out after {timeout} seconds") from exc


def _run_image_step(source: Path, workdir: Path, action: str, params: dict) -> Path:
    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).copy()
    except Exception as exc:
        raise PipelineError(f"Could not read image: {exc}") from exc

    suffix = source.suffix.lower()
    if action == "image.resize":
        width, height = params["width"], params["height"]
        width = width or image.width
        height = height or image.height
        scale = min(width / image.width, height / image.height)
        if not params["allow_upscale"]:
            scale = min(1, scale)
        image = image.resize(
            (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    elif action == "image.rotate":
        image = image.rotate(-params["degrees"], expand=True)
    elif action == "image.crop":
        x, y = params["x"], params["y"]
        right, bottom = x + params["width"], y + params["height"]
        if right > image.width or bottom > image.height:
            raise PipelineError("Crop rectangle extends beyond the image bounds")
        image = image.crop((x, y, right, bottom))
    elif action == "image.convert":
        suffix = FORMAT_EXTENSIONS[params["convert_to"]]

    target = _next_path(workdir, suffix)
    fmt = _PIL_FORMATS.get(suffix, suffix.lstrip(".").upper())
    save_options = {}
    if fmt == "JPEG":
        if image.mode not in ("RGB", "L"):
            background = Image.new("RGB", image.size, "white")
            if "A" in image.getbands():
                rgba = image.convert("RGBA")
                background.paste(rgba, mask=rgba.getchannel("A"))
            else:
                background.paste(image.convert("RGB"))
            image = background
        save_options = {"quality": params.get("quality", 85), "optimize": True}
    elif fmt == "WEBP":
        save_options = {"quality": params.get("quality", 85)}
    image.save(target, format=fmt, **save_options)
    return target


def _ffmpeg_base() -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise PipelineError("Video operations require ffmpeg on the server PATH")
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]


def _input_args(source: Path) -> list[str]:
    return ["-protocol_whitelist", "file,pipe", "-i", str(source)]


def _audio_args(output_format: str, audio_kbps: int | None = None) -> list[str]:
    args = list(AUDIO_CODECS[output_format])
    if audio_kbps is not None:
        args.extend(["-b:a", f"{audio_kbps}k"])
    return args


def _video_output(workdir: Path, output_format: str) -> Path:
    return _next_path(workdir, FORMAT_EXTENSIONS[output_format])


def _check_video_output(path: Path) -> Path:
    if not path.exists() or not path.stat().st_size:
        raise PipelineError("Video operation did not create an output file")
    return path


def _video_compress_to_size(source: Path, workdir: Path, params: dict) -> Path:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise PipelineError("Two-pass size compression requires ffprobe on the server PATH")
    output_format = params["convert_to"]
    output = _video_output(workdir, output_format)
    try:
        probe = subprocess.run(
            [
                ffprobe, "-v", "error", "-show_entries",
                "format=duration:stream=codec_type,height", "-of", "json",
                "-protocol_whitelist", "file,pipe", str(source),
            ],
            check=True, capture_output=True, text=True, timeout=60,
        )
        media = json.loads(probe.stdout)
        duration = max(float(media["format"]["duration"]), 0.1)
        streams = media.get("streams", [])
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        height = next((s.get("height") for s in streams if s.get("codec_type") == "video"), None)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise PipelineError(f"Could not inspect video for size compression: {exc}") from exc

    budget = params["target_mb"] * 1024**2 * 8 * 0.94
    video_bps = int(budget / duration - (params["audio_kbps"] * 1000 if has_audio else 0))
    if video_bps < 80_000:
        raise PipelineError("Target size is too small for this video's duration")
    cap = 360 if video_bps < 250_000 else 480 if video_bps < 600_000 else 720 if video_bps < 1_500_000 else None
    scale = ["-vf", f"scale=-2:{cap}"] if cap and (height or 0) > cap else []
    codec = (
        ["-c:v", "libvpx-vp9", "-deadline", "good", "-cpu-used", "4"]
        if output_format == "webm" else ["-c:v", "libx264", "-preset", "medium"]
    )
    passlog = str(workdir / f"pass-{uuid.uuid4().hex}")
    common = [
        *_input_args(source), *scale, *codec, "-pix_fmt", "yuv420p",
        "-b:v", str(video_bps), "-maxrate", str(int(video_bps * 1.2)),
        "-bufsize", str(video_bps * 2), "-passlogfile", passlog,
    ]
    try:
        _run_ffmpeg([*_ffmpeg_base(), *common, "-pass", "1", "-an", "-sn", "-dn", "-f", "null", os.devnull])
        audio = _audio_args(output_format, params["audio_kbps"]) if has_audio else ["-an"]
        faststart = ["-movflags", "+faststart"] if output_format == "mp4" else []
        _run_ffmpeg([*_ffmpeg_base(), *common, "-pass", "2", "-sn", "-dn", *audio, *faststart, str(output)])
    finally:
        for path in workdir.glob(f"{Path(passlog).name}*"):
            path.unlink(missing_ok=True)
    if output.stat().st_size > params["target_mb"] * 1024**2:
        output.unlink(missing_ok=True)
        raise PipelineError("Encoded file exceeded the requested target size")
    return output


def _video_mute_audio(source: Path, workdir: Path, params: dict) -> Path:
    output_format = params["convert_to"]
    output = _video_output(workdir, output_format)
    command = [*_ffmpeg_base(), *_input_args(source)]
    if params["mute_all"]:
        command.extend(["-an", *_video_encoder_args(output_format)])
    else:
        ranges = "+".join(
            f"between(t,{start:.3f},{end:.3f})"
            for start, end in _mute_segments(params["segments"])
        )
        command.extend(["-af", f"volume=0:enable='{ranges}'", *_audio_args(output_format), *_video_encoder_args(output_format)])
    command.extend(["-sn", "-dn", str(output)])
    _run_ffmpeg(command)
    return _check_video_output(output)


def _video_extract_audio(source: Path, workdir: Path, params: dict) -> Path:
    output = _video_output(workdir, params["convert_to"])
    _run_ffmpeg([*_ffmpeg_base(), *_input_args(source), "-vn", "-sn", "-dn", str(output)])
    return _check_video_output(output)


def _video_encode(source: Path, workdir: Path, action: str, params: dict) -> Path:
    output_format = params["convert_to"]
    output = _video_output(workdir, output_format)
    command = _ffmpeg_base()
    if action == "video.trim":
        command.extend(["-ss", str(params["start_seconds"])])
    command.extend(_input_args(source))
    if action == "video.trim":
        command.extend(["-t", str(params["duration_seconds"])])
    if action == "video.resize":
        command.extend(["-vf", f"scale=-2:'min({params['max_height']},ih)'"])
    command.extend([
        *_video_encoder_args(output_format, params.get("quality", 23), params.get("preset", "medium")),
        "-pix_fmt", "yuv420p", *_audio_args(output_format, params.get("audio_kbps", 128)),
        "-sn", "-dn", str(output),
    ])
    _run_ffmpeg(command)
    return _check_video_output(output)


def _video_convert(source: Path, workdir: Path, params: dict) -> Path:
    return _video_encode(source, workdir, "video.convert", params)


def _video_compress(source: Path, workdir: Path, params: dict) -> Path:
    return _video_encode(source, workdir, "video.compress", params)


def _video_trim(source: Path, workdir: Path, params: dict) -> Path:
    return _video_encode(source, workdir, "video.trim", params)


def _video_resize(source: Path, workdir: Path, params: dict) -> Path:
    return _video_encode(source, workdir, "video.resize", params)


_VIDEO_HANDLERS = {
    "video.compress_to_size": _video_compress_to_size,
    "video.mute_audio": _video_mute_audio,
    "video.extract_audio": _video_extract_audio,
    "video.convert": _video_convert,
    "video.compress": _video_compress,
    "video.trim": _video_trim,
    "video.resize": _video_resize,
}


def _run_video_step(source: Path, workdir: Path, action: str, params: dict) -> Path:
    try:
        return _VIDEO_HANDLERS[action](source, workdir, params)
    except KeyError as exc:
        raise PipelineError(f"Unsupported video operation: {action}") from exc


def _run_pdf_step(source: Path, workdir: Path, action: str, params: dict) -> Path:
    try:
        reader = PdfReader(source, strict=True)
        if reader.is_encrypted and not reader.decrypt(""):
            raise PipelineError("Password-protected PDFs are not supported")
        page_count = len(reader.pages)
        writer = PdfWriter()
        if action == "pdf.pages":
            indexes = _page_indexes(params["pages"], page_count)
            rotate_indexes = set()
        else:
            indexes = list(range(page_count))
            rotate_indexes = (
                set(_page_indexes(params["pages"], page_count))
                if params["pages"]
                else set(indexes)
            )
        for index in indexes:
            writer.add_page(reader.pages[index])
            if action == "pdf.rotate" and index in rotate_indexes:
                writer.pages[-1].rotate(params["degrees"])
        target = _next_path(workdir, ".pdf")
        with target.open("wb") as output:
            writer.write(output)
        return target
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"Could not process PDF: {exc}") from exc


_STEP_RUNNERS = {"image": _run_image_step, "video": _run_video_step, "pdf": _run_pdf_step}


def _run_step(source: Path, workdir: Path, action: str, params: dict) -> Path:
    try:
        runner = _STEP_RUNNERS[action.split(".", 1)[0]]
    except KeyError as exc:
        raise PipelineError(f"Unsupported operation: {action}") from exc
    return runner(source, workdir, action, params)


def run_pipeline(definition: dict, input_path: Path, output_path: Path, workdir: Path) -> Path:
    pipeline = validate_pipeline(definition, input_path)
    workdir.mkdir(parents=True, exist_ok=True)
    current_path = input_path
    try:
        for step in pipeline["steps"]:
            action, params = step["action"], step["params"]
            next_path = _run_step(current_path, workdir, action, params)
            if current_path != input_path:
                current_path.unlink(missing_ok=True)
            current_path = next_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(current_path), output_path)
        return output_path
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
