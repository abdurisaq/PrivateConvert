import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { filenameKind } from '../utils/pipeline';
import { processingApi } from '../utils/api';

const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

export function usePipelineCatalog() {
  const [operations, setOperations] = useState({});
  const [savedPipelines, setSavedPipelines] = useState([]);
  useEffect(() => {
    Promise.all([processingApi.getPipelineOperations(), processingApi.listPipelines()])
      .then(([catalog, saved]) => {
        setOperations(catalog.operations || {});
        setSavedPipelines(saved.results || []);
      })
      .catch((error) => toast.error(`Could not load pipelines: ${error.message}`));
  }, []);
  return { operations, savedPipelines, setSavedPipelines };
}

export function useVideoMetadata(files) {
  const [result, setResult] = useState({ file: null, info: null, error: null, done: false });
  const file = files.find((item) => filenameKind(item.name) === 'video');
  useEffect(() => {
    if (!file) return undefined;
    let active = true;
    processingApi.getVideoInfo(file)
      .then((info) => active && setResult({ file, info, error: null, done: true }))
      .catch((error) => {
        if (active) setResult({ file, info: null, error, done: true });
      });
    return () => { active = false; };
  }, [file]);
  useEffect(() => {
    if (result.error) toast.error(`Could not inspect video: ${result.error.message}`);
  }, [result.error]);
  return {
    videoInfo: result.file === file ? result.info : null,
    metadataLoading: Boolean(file) && (result.file !== file || !result.done),
  };
}

export function useJobPolling(jobs, setJobs) {
  useEffect(() => {
    if (!jobs.some((job) => !TERMINAL.has(job.status))) return undefined;
    const timer = window.setInterval(async () => {
      try {
        setJobs(await Promise.all(jobs.map(async (job) => {
          if (TERMINAL.has(job.status)) return job;
          const status = await processingApi.getStatus(job.jobId);
          return { ...job, status: status.status, error: status.error_message, output_filename: status.output_filename };
        })));
      } catch (error) {
        toast.error(`Could not refresh pipeline jobs: ${error.message}`);
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [jobs, setJobs]);
}
