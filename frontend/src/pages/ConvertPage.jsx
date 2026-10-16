import { useEffect, useState } from 'react';
import { Upload, FileUp, AlertCircle } from 'lucide-react';
import { conversionApi } from '../utils/api';
import toast from 'react-hot-toast';
import ProcessingPage from './ProcessingPage';

const normalizeFormat = (value) => value?.toLowerCase()?.replace(/^|\./g, '');

export default function ConvertPage() {
  const [file, setFile] = useState(null);
  const [inputFormat, setInputFormat] = useState('');
  const [outputFormat, setOutputFormat] = useState('');
  const [formats, setFormats] = useState({});
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchFormats();
  }, []);

  useEffect(() => {
    if (!inputFormat || Object.keys(formats).length === 0) {
      return;
    }

    const availableCategories = getCategoriesForFormat(inputFormat);
    if (availableCategories.length > 0) {
      setSelectedCategory((current) =>
        availableCategories.includes(current) ? current : availableCategories[0]
      );
    } else if (categories.length > 0) {
      setSelectedCategory((current) => current || categories[0]);
    }
  }, [inputFormat, formats, categories]);

  const fetchFormats = async () => {
    try {
      setLoading(true);
      const response = await conversionApi.getFormats();
      setFormats(response || {});
      const categoryKeys = Object.keys(response || {});
      setCategories(categoryKeys);
      if (categoryKeys.length > 0) {
        setSelectedCategory(categoryKeys[0]);
      }
    } catch (error) {
      toast.error('Failed to load supported formats');
    } finally {
      setLoading(false);
    }
  };

  const getCategoriesForFormat = (format) => {
    const normalized = normalizeFormat(format);
    return Object.entries(formats)
      .filter(([, data]) =>
        Array.isArray(data.input) && data.input.some((item) => normalizeFormat(item) === normalized)
      )
      .map(([category]) => category);
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) {
      return;
    }

    const ext = selectedFile.name.split('.').pop().toLowerCase();
    setFile(selectedFile);
    setInputFormat(ext);
    setOutputFormat('');
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    const droppedFile = e.dataTransfer.files?.[0];
    if (!droppedFile) {
      return;
    }

    const ext = droppedFile.name.split('.').pop().toLowerCase();
    setFile(droppedFile);
    setInputFormat(ext);
    setOutputFormat('');
  };

  const handleClear = () => {
    setFile(null);
    setInputFormat('');
    setOutputFormat('');
    setSelectedCategory(categories[0] || '');
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
      fileInput.value = '';
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return toast.error('Please select a file');
    if (!inputFormat) return toast.error('Please specify input format');
    if (!outputFormat) return toast.error('Please specify output format');

    setUploading(true);
    try {
      await conversionApi.upload(file, inputFormat, outputFormat);
      toast.success('File uploaded! Check your jobs page for status.');
      handleClear();
    } catch (error) {
      const message = error.response?.data?.error || 'Upload failed';
      toast.error(message);
    } finally {
      setUploading(false);
    }
  };

  const isPdf = normalizeFormat(inputFormat) === 'pdf';
  const matchingCategories = inputFormat ? getCategoriesForFormat(inputFormat) : categories;
  const outputFormats = selectedCategory ? formats[selectedCategory]?.output || [] : [];
  const isFormatSupported = matchingCategories.length > 0;

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="p-8 bg-gray-800 rounded-lg shadow text-center text-gray-300">
          Loading supported formats...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-purple-400">Upload once, get smarter options</h1>
        <p className="text-gray-400 mt-2">
          Upload your file and receive tailored options. PDFs open the manipulation studio, other files show available conversions.
        </p>
      </div>

      <div className="p-6 bg-gray-800 rounded-lg shadow mb-6">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">Upload a file</h2>
        <div
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          className="border-2 border-dashed border-gray-700 rounded-lg p-10 text-center hover:border-purple-500 transition-colors cursor-pointer"
        >
          <input
            id="fileInput"
            type="file"
            onChange={handleFileChange}
            className="hidden"
            disabled={uploading}
          />
          <label htmlFor="fileInput" className="cursor-pointer">
            <Upload className="mx-auto mb-3 text-purple-400" size={36} />
            <p className="text-gray-300 font-medium text-lg">
              {file ? file.name : 'Drop a file here, or click to browse'}
            </p>
            <p className="text-gray-500 text-sm mt-1">
              {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : 'PDFs open the editor. Other files show available conversions.'}
            </p>
          </label>
        </div>

        {file && (
          <div className="mt-4 p-4 bg-green-700/20 rounded-lg border border-green-500 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm text-green-100 font-medium">{file.name}</p>
              <p className="text-xs text-green-200">Type: {inputFormat.toUpperCase()}</p>
            </div>
            <button
              type="button"
              onClick={handleClear}
              className="text-purple-300 hover:text-purple-100 text-sm"
            >
              Change file
            </button>
          </div>
        )}
      </div>

      {file ? (
        isPdf ? (
          <div className="space-y-6">
            <div className="p-6 bg-gray-800 rounded-lg shadow">
              <h2 className="text-xl font-semibold text-gray-100 mb-2">PDF Manipulation Studio</h2>
              <p className="text-gray-400">
                Your PDF has been detected. Reorder pages, apply transforms, and export your final document.
              </p>
            </div>
            <ProcessingPage initialPdfFile={file} />
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="p-6 bg-gray-800 rounded-lg shadow">
              <h2 className="text-lg font-semibold text-gray-100 mb-4">Available conversions</h2>
              {isFormatSupported ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {matchingCategories.map((category) => (
                    <button
                      type="button"
                      key={category}
                      onClick={() => setSelectedCategory(category)}
                      className={`p-3 rounded-lg border-2 text-sm font-medium transition-colors w-full ${
                        selectedCategory === category
                          ? 'border-purple-500 bg-purple-700 text-gray-100'
                          : 'border-gray-700 bg-gray-900 text-gray-300 hover:border-purple-500 hover:bg-gray-700'
                      }`}
                    >
                      {category.charAt(0).toUpperCase() + category.slice(1)}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No supported conversions were found for this file type.</p>
              )}
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              <div className="p-6 bg-gray-800 rounded-lg shadow">
                <h2 className="text-lg font-semibold text-gray-100 mb-4">From Format</h2>
                <input
                  type="text"
                  readOnly
                  value={inputFormat.toUpperCase()}
                  className="w-full p-3 rounded bg-gray-900 text-gray-300 border border-gray-700"
                />
              </div>

              <div className="p-6 bg-gray-800 rounded-lg shadow">
                <h2 className="text-lg font-semibold text-gray-100 mb-4">To Format</h2>
                <select
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value)}
                  className="w-full p-3 rounded bg-gray-900 text-gray-300 border border-gray-700"
                  disabled={!isFormatSupported}
                >
                  <option value="">Select output format</option>
                  {outputFormats.map((fmt) => (
                    <option key={fmt} value={fmt}>
                      {fmt.toUpperCase()}
                    </option>
                  ))}
                </select>
                {!isFormatSupported && (
                  <div className="mt-3 p-3 bg-yellow-700/20 rounded border border-yellow-500 flex gap-2">
                    <AlertCircle size={16} className="text-yellow-400 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-yellow-300">This file type is not supported for conversion yet.</p>
                  </div>
                )}
              </div>
            </div>

            <button
              type="submit"
              disabled={uploading || !outputFormat || !isFormatSupported}
              className="w-full flex items-center justify-center gap-2 p-3 font-semibold text-gray-100 rounded-lg bg-purple-700 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {uploading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <FileUp size={20} />
                  Convert File
                </>
              )}
            </button>
          </form>
        )
      ) : (
        <div className="p-6 bg-gray-800 rounded-lg shadow text-center text-gray-400">
          Select a file above to see the right workflow for your file type.
        </div>
      )}

      <div className="mt-8 p-6 bg-gray-800 rounded-lg shadow border border-gray-700">
        <h3 className="font-semibold text-gray-100 mb-2">How it works</h3>
        <ol className="text-sm text-gray-400 space-y-1 list-decimal list-inside">
          <li>Upload a file using the unified workflow.</li>
          <li>If it is a PDF, the editor will switch to PDF page-level controls.</li>
          <li>For any other supported file type, choose a target format and convert.</li>
          <li>Visit the jobs page to check status and download results.</li>
        </ol>
      </div>
    </div>
  );
}
