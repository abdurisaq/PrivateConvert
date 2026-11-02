import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react';
import { ParamInput, TrimControls } from './PipelineControls';
import { estimateVideoState, formatSize } from '../../utils/pipeline';

function visibleParams(step, operation) {
  return Object.entries(operation?.parameters || {}).filter(([name]) => {
    if (step.action === 'video.trim' && ['start_seconds', 'duration_seconds'].includes(name)) return false;
    if (step.action === 'video.mute_audio' && name === 'segments' && step.params.mute_all) return false;
    return !(step.action === 'image.convert' && name === 'quality'
      && !['jpg', 'webp'].includes(step.params.convert_to));
  });
}

export default function PipelineStep({
  step, index, count, operation, file, videoInfo, steps, onUpdate, onMove, onRemove,
}) {
  const priorVideoState = estimateVideoState(file, videoInfo, steps.slice(0, index));
  const projectedSize = formatSize(estimateVideoState(file, videoInfo, steps.slice(0, index + 1)).size);

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold text-purple-200">{index + 1}. {operation?.label || step.action}</h2>
        <div className="flex gap-1">
          <button type="button" disabled={index === 0} onClick={() => onMove(index, -1)} aria-label="Move step up" className="rounded p-1 text-gray-300 hover:bg-gray-700 disabled:opacity-30"><ArrowUp size={18} /></button>
          <button type="button" disabled={index === count - 1} onClick={() => onMove(index, 1)} aria-label="Move step down" className="rounded p-1 text-gray-300 hover:bg-gray-700 disabled:opacity-30"><ArrowDown size={18} /></button>
          <button type="button" onClick={() => onRemove(index)} aria-label="Remove step" className="rounded p-1 text-red-300 hover:bg-gray-700"><Trash2 size={18} /></button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {visibleParams(step, operation).map(([name, schema]) => (
          <ParamInput
            key={name}
            name={name}
            schema={{
              ...schema,
              ...(name === 'target_mb' ? { maximum: Math.max(schema.minimum, priorVideoState.size / 1024 ** 2) } : {}),
              ...(name === 'audio_kbps' ? { maximum: Math.max(schema.minimum, Math.min(schema.maximum, priorVideoState.audioKbps)) } : {}),
              ...(name === 'max_height' && priorVideoState.height ? { maximum: Math.max(schema.minimum, priorVideoState.height) } : {}),
            }}
            value={step.params[name]}
            withSlider={step.action.startsWith('video.') || (step.action === 'image.convert' && name === 'quality')}
            onChange={(value) => onUpdate(index, { [name]: value })}
          />
        ))}
        {step.action === 'video.trim' && (
          <TrimControls params={step.params} duration={videoInfo?.duration} onChange={(values) => onUpdate(index, values)} />
        )}
      </div>
      {['video.compress', 'video.compress_to_size'].includes(step.action) && (
        <p className="mt-3 text-sm text-purple-200">
          {step.action === 'video.compress_to_size'
            ? `Original: ${formatSize(file?.size || 0)} · after operations above: ${formatSize(priorVideoState.size)} · target output: ${formatSize((step.params.target_mb || 0) * 1024 ** 2)}`
            : `Predicted output: ${projectedSize} · rough estimate; video content affects results`}
        </p>
      )}
    </div>
  );
}
