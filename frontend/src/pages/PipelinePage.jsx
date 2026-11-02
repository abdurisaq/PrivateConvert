import { useMemo, useReducer, useState } from 'react';
import { Download, Play, Save, Trash2, Workflow } from 'lucide-react';
import toast from 'react-hot-toast';
import PipelineFiles from '../components/pipeline/PipelineFiles';
import PipelineStep from '../components/pipeline/PipelineStep';
import { defaultParams, estimateVideoState, filenameKind, secondsToTime } from '../utils/pipeline';
import { processingApi } from '../utils/api';
import { useJobPolling, usePipelineCatalog, useVideoMetadata } from '../hooks/usePipelineData';

const initialEditor = {
  selectedPipelineId: '', pipelineName: '', description: '', inputKind: '',
  steps: [], workflowMode: '', recording: false, isDragging: false,
};

async function withBusy(setBusy, errorMessage, action) {
  setBusy(true);
  try {
    await action();
  } catch (error) {
    toast.error(`${errorMessage}: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

function editorReducer(state, action) {
  switch (action.type) {
    case 'set': return { ...state, [action.key]: action.value };
    case 'addStep': return { ...state, steps: [...state.steps, action.step] };
    case 'updateParams': return {
      ...state,
      steps: state.steps.map((step, index) => index === action.index
        ? { ...step, params: { ...step.params, ...action.values } } : step),
    };
    case 'removeStep': return { ...state, steps: state.steps.filter((_, index) => index !== action.index) };
    case 'moveStep': {
      const target = action.index + action.direction;
      if (target < 0 || target >= state.steps.length) return state;
      const steps = [...state.steps];
      [steps[action.index], steps[target]] = [steps[target], steps[action.index]];
      return { ...state, steps };
    }
    case 'loadPipeline': return { ...state, ...action.value };
    default: return state;
  }
}

export default function PipelinePage() {
  const [editor, dispatch] = useReducer(editorReducer, initialEditor);
  const {
    selectedPipelineId, pipelineName, description, inputKind, steps,
    workflowMode, recording, isDragging,
  } = editor;
  const [files, setFiles] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [busy, setBusy] = useState(false);
  const { operations, savedPipelines, setSavedPipelines } = usePipelineCatalog();
  const { videoInfo, metadataLoading } = useVideoMetadata(files);
  useJobPolling(jobs, setJobs);
  const setEditor = (key, value) => dispatch({ type: 'set', key, value });

  const pipeline = useMemo(() => ({
    schema_version: 1,
    name: pipelineName,
    description,
    input_kind: files.length ? filenameKind(files[0].name) : inputKind || null,
    steps,
  }), [pipelineName, description, files, inputKind, steps]);

  const availableOperations = useMemo(() => {
    const kind = steps.length
      ? operations[steps[steps.length - 1].action]?.output_type
      : files.length ? filenameKind(files[0].name) : inputKind;
    return Object.entries(operations).filter(([, operation]) => (
      (!kind || operation.input_types.includes(kind))
      && operation.available !== false
    ));
  }, [files, inputKind, operations, steps]);

  const addStep = (event) => {
    const action = event.target.value;
    if (!action) return;
    const priorVideoState = estimateVideoState(files[0], videoInfo, steps);
    dispatch({ type: 'addStep', step: { action, params: defaultParams(action, videoInfo, priorVideoState) } });
    event.target.value = '';
  };

  const addFiles = (newFiles) => {
    const accepted = newFiles.filter((file) => ['image', 'pdf', 'video'].includes(filenameKind(file.name)));
    if (accepted.length !== newFiles.length) {
      toast.error('Some files were skipped. Supported inputs are images, PDFs, and videos.');
    }
    setFiles((current) => [...current, ...accepted]);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setEditor('isDragging', false);
    addFiles(Array.from(event.dataTransfer.files || []));
  };

  const updateParams = (index, values) => {
    dispatch({ type: 'updateParams', index, values });
  };

  const moveStep = (index, direction) => {
    dispatch({ type: 'moveStep', index, direction });
  };

  const loadPipeline = (pipelineId) => {
    const selected = savedPipelines.find((saved) => saved.id === pipelineId);
    if (!selected) {
      dispatch({ type: 'loadPipeline', value: initialEditor });
      return;
    }
    dispatch({ type: 'loadPipeline', value: {
      selectedPipelineId: pipelineId,
      pipelineName: selected.name,
      description: selected.description || '',
      inputKind: selected.input_kind || '',
      steps: selected.steps,
    } });
  };

  const save = async () => {
    await withBusy(setBusy, 'Could not save pipeline', async () => {
      const response = await processingApi.savePipeline(pipeline);
      setSavedPipelines((current) => [...current.filter((item) => item.id !== response.id && item.name !== response.name), response]);
      setEditor('selectedPipelineId', response.id);
      setEditor('recording', false);
      toast.success('Pipeline saved');
    });
  };

  const removeSaved = async () => {
    if (!selectedPipelineId) return;
    await withBusy(setBusy, 'Could not delete pipeline', async () => {
      await processingApi.deletePipeline(selectedPipelineId);
      setSavedPipelines((current) => current.filter((item) => item.id !== selectedPipelineId));
      setEditor('selectedPipelineId', '');
      toast.success('Saved pipeline deleted');
    });
  };

  const run = async (event) => {
    event.preventDefault();
    if (!files.length) return toast.error('Choose at least one input file');
    if (selectedKinds.length !== 1) return toast.error('Choose files of the same type for one operation pipeline');
    await withBusy(setBusy, 'Could not run pipeline', async () => {
      const { pipeline: validated } = await processingApi.validatePipeline(pipeline);
      const response = await processingApi.runPipeline(files, validated);
      setJobs(response.jobs.map((job) => ({ ...job, status: 'pending' })));
      toast.success(`Pipeline queued for ${response.jobs.length} file(s)`);
    });
  };

  const download = async (job) => {
    try {
      const blob = await processingApi.downloadResult(job.jobId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = job.output_filename || job.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      toast.error(`Could not download output: ${error.message}`);
    }
  };

  const canStartRecording = Boolean(pipelineName.trim());
  const selectedKinds = [...new Set(files.map((file) => filenameKind(file.name)))];

  return (
    <div className="mx-auto max-w-5xl space-y-6 text-gray-100">
      <header>
        <h1 className="flex items-center gap-3 text-3xl font-bold text-purple-300"><Workflow /> File operations</h1>
        <p className="mt-2 text-gray-400">Drop in a file to see its operations, process it now, or record a named pipeline to replay later.</p>
      </header>

      {!workflowMode ? (
        <section className="grid gap-4 md:grid-cols-2">
          <button type="button" onClick={() => setEditor('workflowMode', 'process')} className="rounded-xl border border-gray-700 bg-gray-800 p-6 text-left hover:border-purple-500">
            <Play className="mb-3 text-purple-300" />
            <h2 className="text-lg font-semibold">Process files</h2>
            <p className="mt-1 text-sm text-gray-400">Choose files and apply operations or a saved pipeline.</p>
          </button>
          <button type="button" onClick={() => setEditor('workflowMode', 'record')} className="rounded-xl border border-gray-700 bg-gray-800 p-6 text-left hover:border-purple-500">
            <Workflow className="mb-3 text-purple-300" />
            <h2 className="text-lg font-semibold">Record a pipeline</h2>
            <p className="mt-1 text-sm text-gray-400">Name a reusable workflow, then record the operations in order.</p>
          </button>
        </section>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="font-medium text-purple-200">{workflowMode === 'record' ? 'Record a reusable pipeline' : 'Process files'}</p>
            <button type="button" onClick={() => { setEditor('workflowMode', ''); setEditor('recording', false); }} className="text-sm text-gray-400 hover:text-white">Choose another mode</button>
          </div>

          {workflowMode === 'record' && (
            <section className="space-y-3 rounded-xl border border-purple-800 bg-purple-950/30 p-5">
              <label className="block text-sm text-purple-100">
                Name this recording before adding operations
                <input value={pipelineName} onChange={(event) => setEditor('pipelineName', event.target.value)} maxLength={100} placeholder="e.g. Social video export" className="mt-1 w-full rounded border border-gray-600 bg-gray-900 p-2 text-white" />
              </label>
              <button type="button" disabled={!canStartRecording || recording} onClick={() => setEditor('recording', true)} className="rounded bg-purple-600 px-4 py-2 font-semibold hover:bg-purple-500 disabled:opacity-50">
                {recording ? `Recording “${pipelineName}”` : 'Start recording steps'}
              </button>
            </section>
          )}

      <section className="space-y-4 rounded-xl border border-gray-700 bg-gray-800 p-6">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="text-sm text-gray-300">Select a saved pipeline
            <select value={selectedPipelineId} onChange={(event) => loadPipeline(event.target.value)} className="mt-1 w-full rounded border border-gray-600 bg-gray-900 p-2 text-white">
              <option value="">Build operations for this file</option>
              {savedPipelines.map((saved) => <option key={saved.id} value={saved.id}>{saved.name}</option>)}
            </select>
          </label>
          {workflowMode === 'process' && <label className="text-sm text-gray-300">Pipeline name (optional)
            <input value={pipelineName} onChange={(event) => setEditor('pipelineName', event.target.value)} maxLength={100} placeholder="Name to save this sequence" className="mt-1 w-full rounded border border-gray-600 bg-gray-900 p-2 text-white" />
          </label>}
        </div>

        <label
          onDragOver={(event) => { event.preventDefault(); setEditor('isDragging', true); }}
          onDragLeave={() => setEditor('isDragging', false)}
          onDrop={handleDrop}
          className={`block cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${isDragging ? 'border-purple-400 bg-purple-900/20' : 'border-gray-600 hover:border-purple-500'}`}
        >
          <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.gif,.mp4,.webm,.mkv,.mov,.avi" onChange={(event) => addFiles(Array.from(event.target.files || []))} className="hidden" />
          <Workflow className="mx-auto mb-2 text-purple-300" />
          <span className="font-medium">Drop files here or browse</span>
          <span className="mt-1 block text-sm text-gray-400">Images, PDFs, and video. Select one file type per run.</span>
        </label>

        <PipelineFiles
          files={files}
          onRemove={(index) => setFiles((current) => current.filter((_, fileIndex) => fileIndex !== index))}
        />
        {selectedKinds.length > 1 && <p className="text-sm text-amber-300">One pipeline runs on one file type. Remove files of other types to continue.</p>}

        <div className="space-y-3">
          {steps.map((step, index) => (
            <PipelineStep
              key={`${index}-${step.action}`}
              step={step}
              index={index}
              count={steps.length}
              operation={operations[step.action]}
              file={files[0]}
              videoInfo={videoInfo}
              steps={steps}
              onUpdate={updateParams}
              onMove={moveStep}
              onRemove={(stepIndex) => dispatch({ type: 'removeStep', index: stepIndex })}
            />
          ))}
        </div>

        <div className="flex flex-wrap gap-3">
          {files.length > 0 && (
            <select defaultValue="" onChange={addStep} disabled={(workflowMode === 'record' && !recording) || metadataLoading} className="rounded border border-gray-600 bg-gray-900 p-2 text-white disabled:opacity-50">
              <option value="" disabled>Add an operation…</option>
              {availableOperations.map(([action, operation]) => <option key={action} value={action}>{operation.label}</option>)}
            </select>
          )}
          {workflowMode === 'record' && recording && steps.length > 0 && <button type="button" disabled={busy} onClick={save} className="flex items-center gap-2 rounded bg-purple-600 px-4 py-2 hover:bg-purple-500 disabled:opacity-50"><Save size={17} /> Finish &amp; save recording</button>}
          {workflowMode === 'process' && pipelineName.trim() && steps.length > 0 && <button type="button" disabled={busy} onClick={save} className="flex items-center gap-2 rounded bg-gray-700 px-4 py-2 hover:bg-gray-600 disabled:opacity-50"><Save size={17} /> Save as pipeline</button>}
          {selectedPipelineId && <button type="button" onClick={removeSaved} className="flex items-center gap-2 rounded bg-red-900/50 px-4 py-2 text-red-200 hover:bg-red-900"><Trash2 size={17} /> Delete saved</button>}
        </div>
        {files.length > 0 && files[0] && <p className="text-sm text-gray-400">Available operations for {filenameKind(files[0].name)} files</p>}
        {metadataLoading && <p className="text-sm text-gray-400">Reading video duration and dimensions…</p>}
        {videoInfo && <p className="text-sm text-gray-400">Detected video: {videoInfo.width} × {videoInfo.height} · {secondsToTime(videoInfo.duration)} · {videoInfo.audio_bitrate ? `${Math.round(videoInfo.audio_bitrate / 1000)} kbps audio` : videoInfo.has_audio ? 'audio bitrate unavailable' : 'no audio track'}.</p>}
      </section>

      <form onSubmit={run} className="space-y-4 rounded-xl border border-gray-700 bg-gray-800 p-6">
        <p className="text-sm text-gray-400">{files.length} file(s) ready · {steps.length} operation(s) in sequence</p>
        <button type="submit" disabled={busy || !steps.length || !files.length || selectedKinds.length !== 1 || (workflowMode === 'record' && !recording)} className="flex items-center gap-2 rounded bg-purple-600 px-5 py-2.5 font-semibold hover:bg-purple-500 disabled:opacity-50"><Play size={18} /> {workflowMode === 'record' ? 'Run recorded pipeline' : 'Process files'}</button>
      </form>

      {jobs.length > 0 && (
        <section className="space-y-3 rounded-xl border border-gray-700 bg-gray-800 p-6">
          <h2 className="text-xl font-semibold">Batch results</h2>
          {jobs.map((job) => (
            <div key={job.jobId} className="flex flex-wrap items-center justify-between gap-3 rounded border border-gray-700 bg-gray-900 p-3">
              <div>
                <p className="font-medium">{job.filename}</p>
                <p className={`text-sm ${job.status === 'failed' ? 'text-red-300' : job.status === 'completed' ? 'text-green-300' : 'text-gray-400'}`}>{job.status}{job.error ? ` — ${job.error}` : ''}</p>
              </div>
              {job.status === 'completed' && <button type="button" onClick={() => download(job)} className="flex items-center gap-2 rounded bg-gray-700 px-3 py-2 hover:bg-gray-600"><Download size={17} /> Download</button>}
            </div>
          ))}
        </section>
      )}
        </>
      )}
    </div>
  );
}
