import { X, RotateCw, Crop, Edit2, Info } from "lucide-react";
import { PdfJsModalRenderer } from "./PdfJsModalRenderer";

export function EditPageModal({ page, file, onClose, onEditChange }) {
    if (!page || !file) return null;
    const currentRotation = page.rotation || 0;

    const handleRotate = () => {
        const newRotation = (currentRotation + 90) % 360;
        onEditChange(page.id, { rotation: newRotation });
    };

    const handleCropMarginChange = (event) => {
        const marginPercent = Number(event.target.value);
        const horizontalInset = page.widthPoints * marginPercent / 100;
        const verticalInset = page.heightPoints * marginPercent / 100;
        onEditChange(page.id, {
            cropMarginPercent: marginPercent,
            crop: marginPercent === 0 ? null : {
                x: page.originX + horizontalInset,
                y: page.originY + verticalInset,
                width: page.widthPoints - horizontalInset * 2,
                height: page.heightPoints - verticalInset * 2,
            },
        });
    };

    return (
        <div className="fixed inset-0 bg-black/90 z-[100] flex items-center justify-center p-4 backdrop-blur-sm">
            <div className="bg-gray-900 rounded-xl w-full max-w-5xl h-[90vh] flex flex-col border border-gray-700 shadow-2xl">
                <div className="p-4 border-b border-gray-800 flex justify-between items-center">
                    <h2 className="text-xl text-white flex items-center gap-2">
                        <Edit2 size={20} className="text-purple-400" /> Edit Page {page.pageIndex + 1}
                    </h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white p-2 hover:bg-gray-800 rounded-full"><X size={24} /></button>
                </div>
                <div className="flex-grow flex overflow-hidden">
                    {/* Sidebar */}
                    <div className="w-64 bg-gray-800/50 p-6 border-r border-gray-800 flex flex-col gap-4">
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-2">Transformations</h3>
                        <button onClick={handleRotate} className="flex items-center gap-3 p-4 bg-gray-700 hover:bg-purple-600 rounded-lg transition-all text-white shadow-lg">
                            <RotateCw size={20} /> <span className="font-medium">Rotate 90°</span>
                        </button>
                        <div className="rounded-lg bg-gray-700 p-4 text-white">
                            <div className="flex items-center justify-between">
                                <label htmlFor="crop-margin" className="flex items-center gap-2 font-medium">
                                    <Crop size={18} /> Crop margins
                                </label>
                                <span className="text-sm text-purple-300">{page.cropMarginPercent || 0}%</span>
                            </div>
                            <input
                                id="crop-margin"
                                type="range"
                                min="0"
                                max="40"
                                step="1"
                                value={page.cropMarginPercent || 0}
                                onChange={handleCropMarginChange}
                                className="mt-3 w-full accent-purple-500"
                            />
                            <p className="mt-2 text-xs text-gray-300">
                                Trim equally from each edge. Set to 0% to reset.
                            </p>
                        </div>
                        <div className="mt-auto p-4 bg-blue-900/20 border border-blue-500/30 rounded-lg">
                            <p className="text-xs text-blue-200 flex items-start gap-2">
                                <Info size={16} className="shrink-0 text-blue-300"/> Changes are saved to the recipe and applied on the server during the final merge.
                            </p>
                        </div>
                    </div>
                    {/* Renderer */}
                    <div className="flex-grow p-8 overflow-auto flex items-center justify-center bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]">
                         <PdfJsModalRenderer
                            fileUrl={file.url}
                            pageIndex={page.pageIndex}
                            rotation={currentRotation}
                            cropMarginPercent={page.cropMarginPercent || 0}
                        />
                    </div>
                </div>
                <div className="p-4 border-t border-gray-800 flex justify-end">
                    <button onClick={onClose} className="bg-white text-black hover:bg-gray-200 px-6 py-2 rounded-lg font-bold">Done</button>
                </div>
            </div>
        </div>
    );
}