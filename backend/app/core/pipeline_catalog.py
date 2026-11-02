"""Supported file operations and their API validation schemas."""

IMAGE_FORMATS = ("jpg", "png", "webp", "bmp", "tiff")
VIDEO_FORMATS = ("mp4", "webm", "mkv", "mov", "avi")
VIDEO_EXTENSIONS = {f".{fmt}" for fmt in VIDEO_FORMATS}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".gif"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".opus"}
FORMAT_EXTENSIONS = {
    **{fmt: f".{fmt}" for fmt in (*IMAGE_FORMATS, *VIDEO_FORMATS)},
    **{fmt: f".{fmt}" for fmt in ("mp3", "wav", "flac", "ogg")},
}
AUDIO_CODECS = {
    "mp4": ["-c:a", "aac"],
    "webm": ["-c:a", "libopus"],
    "mkv": ["-c:a", "aac"],
    "mov": ["-c:a", "aac"],
    "avi": ["-c:a", "libmp3lame"],
}

_VIDEO_FORMAT = {"type": "string", "enum": list(VIDEO_FORMATS), "default": "mp4"}
_AUDIO_BITRATE = {"type": "integer", "minimum": 32, "maximum": 512, "default": 128}
_VIDEO_OUTPUT = {"convert_to": _VIDEO_FORMAT, "audio_kbps": _AUDIO_BITRATE}


def _operation(
    label: str,
    kind: str,
    parameters: dict,
    requires: tuple[str, ...] = (),
    output_type: str | None = None,
) -> dict:
    operation = {
        "label": label,
        "input_types": [kind],
        "output_type": output_type or kind,
        "parameters": parameters,
    }
    if requires:
        operation["requires"] = list(requires)
    return operation


OPERATIONS = {
    "image.resize": _operation("Resize image", "image", {
        "width": {"type": "integer", "minimum": 1, "maximum": 20000, "default": None},
        "height": {"type": "integer", "minimum": 1, "maximum": 20000, "default": None},
        "allow_upscale": {"type": "boolean", "default": False},
    }),
    "image.convert": {
        **_operation("Convert to…", "image", {
            "convert_to": {"type": "string", "enum": list(IMAGE_FORMATS)},
            "quality": {
                "type": "integer", "minimum": 1, "maximum": 100, "default": 85,
                "help": "For JPG and WebP only; higher means better quality and larger files.",
            },
        }),
        "extension_param": "convert_to",
    },
    "image.rotate": _operation("Rotate image", "image", {
        "degrees": {"type": "integer", "enum": [90, 180, 270]},
    }),
    "image.crop": _operation("Crop image", "image", {
        "x": {"type": "integer", "minimum": 0},
        "y": {"type": "integer", "minimum": 0},
        "width": {"type": "integer", "minimum": 1},
        "height": {"type": "integer", "minimum": 1},
    }),
    "pdf.pages": {
        **_operation("Extract, reorder, or duplicate PDF pages", "pdf", {
            "pages": {"type": "string", "example": "3,1,2 or 1-3,7"},
        }),
        "output_extension": ".pdf",
    },
    "pdf.rotate": {
        **_operation("Rotate PDF pages", "pdf", {
            "degrees": {"type": "integer", "enum": [90, 180, 270]},
            "pages": {"type": "string", "default": "", "example": "1,3-5 (empty means all)"},
        }),
        "output_extension": ".pdf",
    },
    "video.convert": {
        **_operation("Convert video to…", "video", _VIDEO_OUTPUT, ("ffmpeg",)),
        "extension_param": "convert_to",
    },
    "video.compress": {
        **_operation("Compress video", "video", {
            "quality": {"type": "integer", "minimum": 18, "maximum": 35, "default": 26, "help": "Higher means smaller file"},
            "preset": {"type": "string", "enum": ["ultrafast", "fast", "medium", "slow"], "default": "medium"},
            **_VIDEO_OUTPUT,
        }, ("ffmpeg",)),
        "extension_param": "convert_to",
    },
    "video.compress_to_size": {
        **_operation("Compress to a size (2-pass)", "video", {
            "target_mb": {"type": "number", "minimum": 0.5, "maximum": 100000, "default": 25},
            "audio_kbps": {**_AUDIO_BITRATE, "default": 96},
            "convert_to": {"type": "string", "enum": ["mp4", "webm"], "default": "mp4"},
        }, ("ffmpeg", "ffprobe")),
        "extension_param": "convert_to",
    },
    "video.resize": {
        **_operation("Resize video", "video", {
            "max_height": {"type": "integer", "minimum": 144, "maximum": 4320, "default": 720},
            **_VIDEO_OUTPUT,
        }, ("ffmpeg",)),
        "extension_param": "convert_to",
    },
    "video.trim": {
        **_operation("Trim video", "video", {
            "start_seconds": {"type": "number", "minimum": 0, "default": 0},
            "duration_seconds": {"type": "number", "minimum": 0.1, "default": 10},
            **_VIDEO_OUTPUT,
        }, ("ffmpeg",)),
        "extension_param": "convert_to",
    },
    "video.mute_audio": {
        **_operation("Mute audio", "video", {
            "mute_all": {"type": "boolean", "default": False},
            "segments": {"type": "string", "default": "", "example": "00:10-00:15,00:30-00:35"},
            "convert_to": _VIDEO_FORMAT,
        }, ("ffmpeg",)),
        "extension_param": "convert_to",
    },
    "video.extract_audio": {
        **_operation("Extract audio to…", "video", {
            "convert_to": {"type": "string", "enum": ["mp3", "wav", "flac", "ogg"], "default": "mp3"},
        }, ("ffmpeg",), "audio"),
        "extension_param": "convert_to",
    },
}
