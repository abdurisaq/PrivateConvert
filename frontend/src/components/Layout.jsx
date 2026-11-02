import { Outlet, Link } from 'react-router-dom';
import { Home, Upload, FileText, Workflow } from 'lucide-react';

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-900 text-gray-100">
      <aside className="w-64 bg-gray-800 shadow-xl">
        <div className="p-6 border-b border-gray-700">
          <h1 className="text-2xl font-bold text-purple-500">private-converter</h1>
          <p className="text-gray-400 text-sm">Local file conversion</p>
        </div>

        <nav className="mt-6">
          <Link
            to="/"
            className="flex items-center gap-3 px-6 py-3 rounded-lg hover:bg-gray-700 transition-colors"
          >
            <Home size={20} />
            <span>Dashboard</span>
          </Link>
          <Link
            to="/convert"
            className="flex items-center gap-3 px-6 py-3 rounded-lg hover:bg-gray-700 transition-colors"
          >
            <Upload size={20} />
            <span>Convert</span>
          </Link>
          <Link
            to="/pipelines"
            className="flex items-center gap-3 px-6 py-3 rounded-lg hover:bg-gray-700 transition-colors"
          >
            <Workflow size={20} />
            <span>File Operations</span>
          </Link>
          <Link
            to="/process"
            className="flex items-center gap-3 px-6 py-3 rounded-lg hover:bg-gray-700 transition-colors"
          >
            <FileText size={20} />
            <span>PDF Editor</span>
          </Link>
          <Link
            to="/jobs"
            className="flex items-center gap-3 px-6 py-3 rounded-lg hover:bg-gray-700 transition-colors"
          >
            <FileText size={20} />
            <span>Jobs</span>
          </Link>
        </nav>
      </aside>

      <main className="flex-1 overflow-auto p-6 bg-gray-900">
        <Outlet />
      </main>
    </div>
  );
}
