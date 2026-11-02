import { Film, Image, Trash2, Workflow } from 'lucide-react';
import { filenameKind } from '../../utils/pipeline';

const ICONS = { video: Film, image: Image, pdf: Workflow };

export default function PipelineFiles({ files, onRemove }) {
  if (!files.length) return null;
  return (
    <div className="space-y-2">
      {files.map((file, index) => {
        const Icon = ICONS[filenameKind(file.name)] || Workflow;
        return (
          <div key={`${file.name}-${file.lastModified}-${index}`} className="flex items-center justify-between rounded bg-gray-900 px-3 py-2 text-sm">
            <span className="flex items-center gap-2"><Icon size={16} />{file.name}</span>
            <button type="button" onClick={() => onRemove(index)} aria-label={`Remove ${file.name}`} className="text-gray-400 hover:text-red-300"><Trash2 size={16} /></button>
          </div>
        );
      })}
    </div>
  );
}
