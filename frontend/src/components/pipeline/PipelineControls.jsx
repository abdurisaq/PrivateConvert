import { useState } from 'react';
import { secondsToTime } from '../../utils/pipeline';

export function ParamInput({ name, schema, value, onChange, withSlider = false }) {
  const labels = {
    convert_to: 'Convert to',
    quality: 'Quality',
    target_mb: 'Target size (MB)',
    audio_kbps: 'Audio bitrate (kbps)',
    mute_all: 'Mute the entire audio track',
    segments: 'Mute ranges (mm:ss-mm:ss, comma-separated)',
    max_height: 'Maximum height (pixels)',
    duration_seconds: 'Duration (seconds)',
    start_seconds: 'Start (seconds)',
    allow_upscale: 'Allow upscaling',
  };
  const label = labels[name] || name.replaceAll('_', ' ');
  if (schema.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 text-sm capitalize text-gray-300">
        <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} />
        {label}
      </label>
    );
  }
  if (schema.enum) {
    return (
      <Field label={label} help={schema.help}>
        <select
          value={value ?? ''}
          onChange={(event) => onChange(schema.type === 'integer' ? Number(event.target.value) : event.target.value)}
          className="mt-1 w-full rounded border border-gray-600 bg-gray-900 p-2 text-white"
        >
          {schema.enum.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      </Field>
    );
  }
  if (withSlider && ['integer', 'number'].includes(schema.type)) {
    const current = value === '' || value == null ? (schema.default ?? schema.minimum ?? 0) : value;
    const step = schema.type === 'integer' ? 1 : 0.1;
    const logarithmic = schema.minimum > 0 && schema.maximum / schema.minimum > 100;
    const sliderValue = logarithmic
      ? 1000 * Math.log(current / schema.minimum) / Math.log(schema.maximum / schema.minimum)
      : current;
    return (
      <Field label={label} help={schema.help}>
        <div className="mt-1 flex items-center gap-2">
          <input
            type="range"
            min={logarithmic ? 0 : schema.minimum ?? 0}
            max={logarithmic ? 1000 : schema.maximum ?? 100}
            step={logarithmic ? 1 : step}
            value={sliderValue}
            onChange={(event) => {
              const slider = Number(event.target.value);
              onChange(logarithmic
                ? schema.minimum * (schema.maximum / schema.minimum) ** (slider / 1000)
                : slider);
            }}
            className="min-w-0 flex-1 accent-purple-500"
          />
          <input
            type="number"
            min={schema.minimum}
            max={schema.maximum}
            step={step}
            value={value ?? ''}
            onChange={(event) => onChange(event.target.value === '' ? '' : Number(event.target.value))}
            className="w-24 rounded border border-gray-600 bg-gray-900 p-2 text-white"
          />
        </div>
      </Field>
    );
  }
  return (
    <Field label={label} help={schema.help}>
      <input
        type={['integer', 'number'].includes(schema.type) ? 'number' : 'text'}
        min={schema.minimum}
        max={schema.maximum}
        step={schema.type === 'number' ? 'any' : '1'}
        value={value ?? ''}
        placeholder={schema.example || (schema.default === null ? 'Optional' : '')}
        onChange={(event) => onChange(
          ['integer', 'number'].includes(schema.type) && event.target.value !== ''
            ? Number(event.target.value)
            : event.target.value,
        )}
        className="mt-1 w-full rounded border border-gray-600 bg-gray-900 p-2 text-white"
      />
    </Field>
  );
}

function Field({ label, help, children }) {
  return (
    <label className="block text-sm capitalize text-gray-300">
      {label}
      {help && <span className="ml-2 text-xs normal-case text-gray-500">{help}</span>}
      {children}
    </label>
  );
}

export function TrimControls({ params, duration, onChange }) {
  const [unit, setUnit] = useState('time');
  const total = duration || params.start_seconds + params.duration_seconds;
  const start = Math.min(params.start_seconds || 0, total);
  const end = Math.min(start + (params.duration_seconds || total), total);
  const percent = unit === 'percent';
  const scale = percent ? 100 / total : 1;
  const startValue = Math.round(start * scale);
  const endValue = Math.round(end * scale);
  const maximum = percent ? 100 : Math.max(1, Math.floor(total));
  const setStart = (value) => onChange({
    start_seconds: Math.min(value / scale, end - 0.1),
    duration_seconds: Math.max(0.1, end - value / scale),
  });
  const setEnd = (value) => onChange({
    duration_seconds: Math.max(0.1, Math.min(value / scale, total) - start),
  });

  return (
    <div className="space-y-3 sm:col-span-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-300">Trim range</span>
        <div className="flex gap-1 rounded bg-gray-900 p-1 text-xs">
          {['time', 'percent'].map((value) => (
            <button key={value} type="button" onClick={() => setUnit(value)} className={`rounded px-2 py-1 ${unit === value ? 'bg-purple-700 text-white' : 'text-gray-400'}`}>
              {value === 'time' ? 'Min:Sec' : 'Percent'}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          { label: 'Start', value: startValue, set: setStart },
          { label: 'End', value: endValue, set: setEnd },
        ].map(({ label, value, set }) => (
          <label key={label} className="text-sm capitalize text-gray-300">
            {label}
            <input type="range" min="0" max={maximum} value={value} onChange={(event) => set(Number(event.target.value))} className="mt-1 w-full accent-purple-500" />
            <input
              type={percent ? 'number' : 'text'}
              min={percent ? 0 : undefined}
              max={percent ? 100 : undefined}
              value={percent ? value : secondsToTime(value)}
              placeholder="mm:ss"
              onChange={(event) => {
                const parsed = percent ? Number(event.target.value) : timeToSeconds(event.target.value);
                if (Number.isFinite(parsed)) set(Math.max(0, Math.min(maximum, parsed)));
              }}
              className="mt-1 w-full rounded border border-gray-600 bg-gray-900 p-2 text-white"
            />
          </label>
        ))}
      </div>
      <p className="text-xs text-gray-500">Video duration: {secondsToTime(total)}</p>
    </div>
  );
}

function timeToSeconds(value) {
  const match = value.match(/^(\d+):([0-5]\d)$/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}
