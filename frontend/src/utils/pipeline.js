export function currentAudioKbps(videoInfo) {
  return Math.max(32, Math.min(512, Math.round((videoInfo?.audio_bitrate || 128000) / 1000)));
}

export function estimateVideoState(file, videoInfo, steps = []) {
  const duration = videoInfo?.duration || 1;
  const state = {
    size: file?.size || 0,
    duration,
    width: videoInfo?.width || 0,
    height: videoInfo?.height || 0,
    audioKbps: currentAudioKbps(videoInfo),
    hasAudio: videoInfo?.has_audio !== false,
  };

  for (const { action, params } of steps) {
    const nextAudioKbps = params.audio_kbps || state.audioKbps;
    const inputAudioBytes = state.hasAudio ? state.audioKbps * 1000 * state.duration / 8 : 0;
    if (action === 'video.trim') {
      const nextDuration = Math.min(params.duration_seconds || state.duration, state.duration);
      const ratio = nextDuration / state.duration;
      const outputAudioBytes = state.hasAudio ? nextAudioKbps * 1000 * nextDuration / 8 : 0;
      state.size = Math.max(0, state.size - inputAudioBytes) * ratio + outputAudioBytes;
      state.duration = nextDuration;
    } else if (action === 'video.resize' && state.height) {
      const previousHeight = state.height;
      const nextHeight = Math.min(params.max_height || previousHeight, previousHeight);
      const outputAudioBytes = state.hasAudio ? nextAudioKbps * 1000 * state.duration / 8 : 0;
      state.size = Math.max(0, state.size - inputAudioBytes) * (nextHeight / previousHeight) ** 2 + outputAudioBytes;
      state.height = nextHeight;
      state.width = Math.round(state.width * nextHeight / previousHeight);
    } else if (action === 'video.compress') {
      const outputAudioBytes = state.hasAudio ? nextAudioKbps * 1000 * state.duration / 8 : 0;
      const videoBytes = Math.max(0, state.size - inputAudioBytes);
      state.size = videoBytes * 2 ** ((23 - (params.quality ?? 26)) / 6) + outputAudioBytes;
    } else if (action === 'video.compress_to_size') {
      state.size = (params.target_mb || 0) * 1024 ** 2;
    }
    state.audioKbps = nextAudioKbps;
  }
  return state;
}

export function defaultParams(action, videoInfo, priorVideoState) {
  const defaults = {
    'image.resize': { width: 1920, height: 1080, allow_upscale: false },
    'image.convert': { convert_to: 'png', quality: 85 },
    'image.rotate': { degrees: 90 },
    'image.crop': { x: 0, y: 0, width: 100, height: 100 },
    'pdf.pages': { pages: '1-' },
    'pdf.rotate': { degrees: 90, pages: '' },
    'video.compress': { quality: 26, preset: 'medium' },
    'video.resize': { max_height: videoInfo?.height || 720 },
    'video.trim': { start_seconds: 0, duration_seconds: videoInfo?.duration || 10 },
    'video.mute_audio': { mute_all: false, segments: '' },
  };
  if (!action.startsWith('video.')) return defaults[action] || {};
  if (action === 'video.extract_audio') return { convert_to: 'mp3' };

  const audioKbps = priorVideoState?.audioKbps || currentAudioKbps(videoInfo);
  return {
    convert_to: 'mp4',
    ...(action !== 'video.mute_audio' ? { audio_kbps: audioKbps } : {}),
    ...(action === 'video.compress_to_size' ? {
      target_mb: Math.max(0.5, Math.min(100000, (priorVideoState?.size || 0.5 * 1024 ** 2) / 1024 ** 2)),
    } : {}),
    ...(defaults[action] || {}),
  };
}

export function filenameKind(filename) {
  const extension = filename.toLowerCase().split('.').pop();
  if (extension === 'pdf') return 'pdf';
  if (['mp4', 'webm', 'mkv', 'mov', 'avi'].includes(extension)) return 'video';
  if (['mp3', 'wav', 'flac', 'ogg', 'aac', 'm4a', 'opus'].includes(extension)) return 'audio';
  if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tif', 'tiff', 'gif'].includes(extension)) return 'image';
  return 'unknown';
}

export function formatSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '—';
  return bytes >= 1024 ** 3
    ? `${(bytes / 1024 ** 3).toFixed(2)} GB`
    : `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export function secondsToTime(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
}
