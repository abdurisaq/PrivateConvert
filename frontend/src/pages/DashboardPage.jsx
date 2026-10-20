import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FileUp, Zap, Clock, CheckCircle, Wand2 } from 'lucide-react';
import { conversionApi } from '../utils/api';

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [recentJobs, setRecentJobs] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const jobsResponse = await conversionApi.listJobs();
      const allJobs = jobsResponse?.results || [];

      const completed = allJobs.filter(j => j.status === 'completed').length;
      const processing = allJobs.filter(j => j.status === 'processing').length;
      const pending = allJobs.filter(j => j.status === 'pending').length;
      const failed = allJobs.filter(j => j.status === 'failed').length;

      setStats({ totalJobs: allJobs.length, completed, processing, pending, failed });
      setRecentJobs(allJobs.slice(0, 5));
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-purple-400">Private Converter</h1>
        <p className="text-gray-400 mt-2">Manage your file conversions</p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <div className="card bg-gray-800 text-gray-100">
          <p className="text-gray-400 text-sm">Total Jobs</p>
          <p className="text-3xl font-bold mt-2">{stats?.totalJobs || 0}</p>
        </div>
        <div className="card bg-gray-800 border-l-4 border-blue-500 text-gray-100">
          <p className="text-gray-400 text-sm">Processing</p>
          <p className="text-3xl font-bold text-blue-400 mt-2">{stats?.processing || 0}</p>
        </div>
        <div className="card bg-gray-800 border-l-4 border-yellow-500 text-gray-100">
          <p className="text-gray-400 text-sm">Pending</p>
          <p className="text-3xl font-bold text-yellow-400 mt-2">{stats?.pending || 0}</p>
        </div>
        <div className="card bg-gray-800 border-l-4 border-green-500 text-gray-100">
          <p className="text-gray-400 text-sm">Completed</p>
          <p className="text-3xl font-bold text-green-400 mt-2">{stats?.completed || 0}</p>
        </div>
        <div className="card bg-gray-800 border-l-4 border-red-500 text-gray-100">
          <p className="text-gray-400 text-sm">Failed</p>
          <p className="text-3xl font-bold text-red-400 mt-2">{stats?.failed || 0}</p>
        </div>
      </div>

      {/* Main Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">

        {/* Convert */}
        <Link className="card hover:shadow-lg transition-shadow cursor-pointer bg-gray-800 text-gray-100" to="/convert">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-700 rounded-lg">
              <FileUp size={32} />
            </div>
            <div>
              <h3 className="font-semibold text-gray-100">Convert a File</h3>
              <p className="text-gray-400 text-sm">Upload and convert your files</p>
            </div>
          </div>
        </Link>

        {/* Process */}
        <Link className="card hover:shadow-lg transition-shadow cursor-pointer bg-gray-800 text-gray-100" to="/process">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-amber-700 rounded-lg">
              <Wand2 size={32} />
            </div>
            <div>
              <h3 className="font-semibold text-gray-100">Process a File</h3>
              <p className="text-gray-400 text-sm">Trim, crop, merge, compress & more</p>
            </div>
          </div>
        </Link>

        {/* Jobs */}
        <Link className="card hover:shadow-lg transition-shadow cursor-pointer bg-gray-800 text-gray-100" to="/jobs">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-700 rounded-lg">
              <Zap size={32} />
            </div>
            <div>
              <h3 className="font-semibold text-gray-100">View Jobs</h3>
              <p className="text-gray-400 text-sm">Check status and download results</p>
            </div>
          </div>
        </Link>

      </div>

      {/* Recent Jobs */}
      <div className="card bg-gray-800 text-gray-100">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold">Recent Jobs</h2>
          <Link to="/jobs" className="text-purple-400 hover:text-purple-500 text-sm font-semibold">
            View all →
          </Link>
        </div>

        {loading ? (
          <p className="text-gray-400">Loading...</p>
        ) : recentJobs.length === 0 ? (
          <div className="text-center py-8">
            <Clock size={32} className="mx-auto text-gray-500 mb-2" />
            <p className="text-gray-400">No jobs yet. Start converting files!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {recentJobs.map((job) => (
              <div key={job.id} className="flex items-center justify-between p-3 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors">
                <div className="flex-1">
                  <p className="font-medium">{job.input_filename}</p>
                  <p className="text-sm text-gray-400">
                    {job.input_format.toUpperCase()} → {job.output_format.toUpperCase()}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${
                      job.status === 'completed'
                        ? 'bg-green-600 text-gray-100'
                        : job.status === 'processing'
                        ? 'bg-blue-600 text-gray-100'
                        : job.status === 'failed'
                        ? 'bg-red-600 text-gray-100'
                        : 'bg-yellow-600 text-gray-100'
                    }`}
                  >
                    {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
                  </span>
                  {job.status === 'completed' && (
                    <CheckCircle className="text-green-400" size={20} />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="mt-8 p-6 bg-gradient-to-r from-purple-800 to-indigo-900 rounded-lg border border-gray-700 text-gray-100">
        <h3 className="font-semibold mb-2">Supported Formats</h3>
        <p className="text-gray-300 text-sm">
          private-converter supports conversions for audio, video, images, documents, eBooks, PDFs, and archives.
          Check the Convert page for all available format combinations.
        </p>
      </div>
    </div>
  );
}
