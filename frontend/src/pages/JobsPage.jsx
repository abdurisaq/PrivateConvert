import { useState, useEffect } from 'react';
import { Download, Trash2, RefreshCw, CheckCircle, AlertCircle, Clock, Play } from 'lucide-react';
import { conversionApi } from '../utils/api';
import toast from 'react-hot-toast';
import { formatDistanceToNow } from 'date-fns';

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState('all');

  useEffect(() => {//change this later to only periodically poll while there are some jobs not in a terminal state
    
    fetchJobs();
    const interval = setInterval(fetchJobs, 3000); 
    return () => clearInterval(interval);
  }, [filter]);


  const fetchJobs = async () => {
    try {
      setLoading(true);
      const params = filter !== 'all' ? { status: filter } : {};
      const response = await conversionApi.listJobs(params);
      setJobs(response.results || []);
      // setJobs(response.data.results || []);
    } catch (error) {
      toast.error('Failed to fetch jobs');
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (jobId, filename) => {
    try {
      const response = await conversionApi.downloadResult(jobId);
      const blob = response instanceof Blob ? response : new Blob([response]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentElement.removeChild(link);
      toast.success('Download started');
    } catch (error) {
      toast.error('Failed to download file');
    }
  };

  const handleCancel = async (jobId) => {
    if (!confirm('Are you sure you want to cancel this job?')) return;

    try {
      await conversionApi.cancelJob(jobId);
      toast.success('Job cancelled');
      fetchJobs();
    } catch (error) {
      toast.error('Failed to cancel job');
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="text-green-600" size={20} />;
      case 'failed':
        return <AlertCircle className="text-red-600" size={20} />;
      case 'processing':
        return <Play className="text-blue-600" size={20} />;
      case 'pending':
        return <Clock className="text-yellow-600" size={20} />;
      default:
        return <Clock className="text-gray-600" size={20} />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-50 text-green-700 border-green-200';
      case 'failed':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'processing':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'pending':
        return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      default:
        return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  const filteredJobs = jobs.filter(job => {
    if (filter === 'all') return true;
    return job.status === filter;
  });

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Conversion Jobs</h1>
          <p className="text-gray-600 mt-2">Track and manage your file conversions</p>
        </div>
        <button
          onClick={fetchJobs}
          disabled={loading}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="mb-6 flex gap-2 flex-wrap">
        {['all', 'pending', 'processing', 'completed', 'failed'].map((status) => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === status
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {/* Jobs Table */}
      {loading && filteredJobs.length === 0 ? (
        <div className="card text-center">
          <p className="text-gray-600">Loading jobs...</p>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="card text-center">
          <p className="text-gray-600">No jobs found</p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredJobs.map((job) => (
            <div key={job.id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    {getStatusIcon(job.status)}
                    <div>
                      <h3 className="font-semibold text-gray-900">{job.input_filename}</h3>
                      <p className="text-sm text-gray-600">
                        {job.input_format.toUpperCase()} → {job.output_format.toUpperCase()}
                      </p>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  {job.status === 'processing' && (
                    <div className="mt-3 w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${job.progress || 0}%` }}
                      />
                    </div>
                  )}

                  {/* Status and Time */}
                  <div className="mt-3 flex flex-wrap gap-4 text-sm text-gray-600">
                    <span className={`px-3 py-1 rounded-full border ${getStatusColor(job.status)}`}>
                      {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                    </span>
                    <span>Created: {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}</span>
                    {job.completed_at && (
                      <span>Completed: {formatDistanceToNow(new Date(job.completed_at), { addSuffix: true })}</span>
                    )}
                  </div>

                  {/* Error Message */}
                  {job.error_message && (
                    <div className="mt-3 p-3 bg-red-50 rounded border border-red-200">
                      <p className="text-sm text-red-700">
                        <strong>Error:</strong> {job.error_message}
                      </p>
                    </div>
                  )}

                  {/* Progress Percentage */}
                  {job.progress && job.progress > 0 && (
                    <p className="text-sm text-gray-600 mt-2">Progress: {job.progress}%</p>
                  )}
                </div>

                {/* Actions */}
                <div className="ml-4 flex gap-2">
                  {job.status === 'completed' && (
                    <button
                      onClick={() => handleDownload(job.id, job.input_filename.split('.')[0] + '.' + job.output_format)}
                      className="btn-secondary flex items-center gap-1"
                      title="Download result"
                    >
                      <Download size={20} />
                    </button>
                  )}

                  {['pending', 'processing'].includes(job.status) && (
                    <button
                      onClick={() => handleCancel(job.id)}
                      className="btn-danger flex items-center gap-1"
                      title="Cancel job"
                    >
                      <Trash2 size={20} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredJobs.length === 0 && filter === 'all' && (
        <div className="card text-center py-12">
          <Clock size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-semibold text-gray-700 mb-2">No conversion jobs yet</h3>
          <p className="text-gray-600">
            Get started by uploading a file on the Convert page
          </p>
        </div>
      )}
    </div>
  );
}
