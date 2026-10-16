import React, { useState, useEffect, useRef, useCallback } from "react";
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors, DragOverlay, defaultDropAnimationSideEffects } from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, rectSortingStrategy } from "@dnd-kit/sortable";
import * as pdfjs from "pdfjs-dist";
import { Upload, Trash2, Layers, Info } from "lucide-react";
import toast from "react-hot-toast";
import { v4 as uuidv4 } from "uuid";



import { SortablePage } from "../components/PageThumbnail/SortablePage";
import { DragOverlayContent } from "../components/PageThumbnail/DragOverlayContent";
import { EditPageModal } from "../components/EditPageModal/EditPageModal";
import { arrayMoveMultiple } from "../utils/pdfUtils";

import { processingApi } from '../utils/api';

// worker that needs to be specified for pdfjs, didnt work cuz didn't import properly
import worker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
pdfjs.GlobalWorkerOptions.workerSrc = worker;

const dropAnimation = {
    sideEffects: defaultDropAnimationSideEffects({ styles: { active: { opacity: '0.3' } } }),
};

export default function ProcessingPage({ initialPdfFile = null }) {
    const [files, setFiles] = useState({});
    const [pages, setPages] = useState([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [selectedPageIds, setSelectedPageIds] = useState([]);
    const [editingPageId, setEditingPageId] = useState(null);
    const [activeDragId, setActiveDragId] = useState(null);
    const [lastSelectedId, setLastSelectedId] = useState(null);
    const hasInitializedInitialFile = useRef(false);

    const pagesRef = useRef(pages);
    useEffect(() => { pagesRef.current = pages; }, [pages]);
    const filesRef = useRef(files);
    useEffect(() => { filesRef.current = files; }, [files]);

    const sensors = useSensors(
        useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
        useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
    );

    useEffect(() => {
        return () => {
            Object.values(filesRef.current).forEach(fileInfo => {
                if (fileInfo.url) URL.revokeObjectURL(fileInfo.url);
            });
        };
    }, []);

    const handleToggleSelection = useCallback((id, isShift, isCtrl) => {
        const pagesArray = pagesRef.current;
        setSelectedPageIds(prevIds => {
            if (isCtrl) {
                setLastSelectedId(id);
                return prevIds.includes(id) ? prevIds.filter(pid => pid !== id) : [...prevIds, id];
            } else if (isShift) {
                const anchorId = lastSelectedId || id;
                const clickedIndex = pagesArray.findIndex(p => p.id === id);
                const anchorIndex = pagesArray.findIndex(p => p.id === anchorId);
                if (clickedIndex === -1 || anchorIndex === -1) return prevIds;
                const [start, end] = [Math.min(clickedIndex, anchorIndex), Math.max(clickedIndex, anchorIndex)];
                return pagesArray.slice(start, end + 1).map(p => p.id);
            } else {
                setLastSelectedId(id);
                return prevIds.length === 1 && prevIds[0] === id ? prevIds : [id];
            }
        });
    }, [lastSelectedId]);

    const handleDragStart = useCallback((event) => {
        const { active } = event;
        setActiveDragId(active.id);
        if (!selectedPageIds.includes(active.id)) {
            setSelectedPageIds([active.id]);
            setLastSelectedId(active.id);
        }
    }, [selectedPageIds]);

    const handleDragEnd = useCallback((event) => {
        const { active, over } = event;
        setActiveDragId(null);
        if (!over || active.id === over.id) return;
        
        let idsToMove = [active.id];
        if (selectedPageIds.includes(active.id) && selectedPageIds.length > 0) {
             idsToMove = pages.filter(p => selectedPageIds.includes(p.id)).map(p => p.id);
        }

        setPages((items) => arrayMoveMultiple(items, idsToMove, active.id, over.id));
    }, [pages, selectedPageIds]);

    const processPdfFiles = async (selectedFiles) => {
        if (selectedFiles.length === 0) return;
        const uploadToast = toast.loading("Uploading and processing...");

        try {
          for (const selectedFile of selectedFiles) {
            if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
                throw new Error(`${selectedFile.name} is not a PDF file`);
            }
            const fileURL = URL.createObjectURL(selectedFile);
            try {
                const pdf = await pdfjs.getDocument({ data: await selectedFile.arrayBuffer() }).promise;
                const upload = await processingApi.uploadFile(selectedFile);
                const serverId = upload.fileId;
                const fileInfo = {
                    name: selectedFile.name,
                    url: fileURL,
                    serverFileId: serverId,
                };
                setFiles((current) => ({ ...current, [serverId]: fileInfo }));
                const addedPages = [];
                for (let i = 0; i < pdf.numPages; i++) {
                    const pdfPage = await pdf.getPage(i + 1);
                    const viewport = pdfPage.getViewport({ scale: 1 });
                    const [originX, originY] = pdfPage.view;
                    addedPages.push({
                        id: uuidv4(),
                        fileId: serverId,
                        pageIndex: i,
                        rotation: 0,
                        crop: null,
                        cropMarginPercent: 0,
                        originX,
                        originY,
                        widthPoints: viewport.width,
                        heightPoints: viewport.height,
                    });
                }
                setPages((current) => [...current, ...addedPages]);
            } catch (error) {
                URL.revokeObjectURL(fileURL);
                throw error;
            }
          }
          toast.success("Pages ready!");
        } catch (error) {
            toast.error(`Upload failed: ${error.message}`);
        } finally {
            toast.dismiss(uploadToast);
        }
    };

    const handleFileChange = async (e) => {
        const selectedFiles = Array.from(e.target.files || []).filter((f) => f.name.toLowerCase().endsWith(".pdf"));
        e.target.value = "";
        await processPdfFiles(selectedFiles);
    };

    useEffect(() => {
        if (initialPdfFile && !hasInitializedInitialFile.current) {
            hasInitializedInitialFile.current = true;
            setFiles({});
            setPages([]);
            setSelectedPageIds([]);
            setEditingPageId(null);
            processPdfFiles([initialPdfFile]);
        }
    }, [initialPdfFile]);

    const handleRemovePage = useCallback((id) => {
        setPages(prev => prev.filter(p => p.id !== id));
        setSelectedPageIds(prev => prev.filter(pid => pid !== id));
        if (id === lastSelectedId) setLastSelectedId(null);
    }, [lastSelectedId]);

    const handleDeleteSelected = useCallback(() => {
        setPages(prev => prev.filter(p => !selectedPageIds.includes(p.id)));
        setSelectedPageIds([]);
        setLastSelectedId(null);
    }, [selectedPageIds]);

    const handlePageEditChange = useCallback((id, data) => {
        setPages(prev => prev.map(p => p.id === id ? { ...p, ...data } : p));
    }, []);

    const clearWorkspace = () => {
        Object.values(filesRef.current).forEach((fileInfo) => {
            if (fileInfo.url) URL.revokeObjectURL(fileInfo.url);
        });
        setPages([]);
        setFiles({});
        setSelectedPageIds([]);
        setLastSelectedId(null);
    };

    const handleSubmit = async () => {
        if (pages.length === 0) return toast.error("No pages to process");
        setIsProcessing(true);

        try {
            const response = await processingApi.processPdf({
                outputFilename: "merged_document.pdf",
                pages: pages.map((page) => ({
                    sourceFileId: files[page.fileId].serverFileId,
                    sourcePageIndex: page.pageIndex,
                    transformations: { rotate: page.rotation, crop: page.crop },
                })),
            });

            if (!response.jobId) {
                throw new Error("The server did not return a PDF job ID");
            }

            let job;
            const deadline = Date.now() + 5 * 60 * 1000;
            do {
                await new Promise((resolve) => window.setTimeout(resolve, 1000));
                job = await processingApi.getStatus(response.jobId);
                if (job.status === "failed" || job.status === "cancelled") {
                    throw new Error(job.error_message || `PDF job ${job.status}`);
                }
            } while (job.status !== "completed" && Date.now() < deadline);

            if (job.status !== "completed") {
                throw new Error("PDF processing timed out. Check the Jobs page for status.");
            }

            const result = await processingApi.downloadResult(response.jobId);
            const downloadUrl = URL.createObjectURL(result);
            const link = document.createElement("a");
            link.href = downloadUrl;
            link.download = job.output_filename || "merged_document.pdf";
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
            toast.success("Your PDF is ready and downloading.");
        } catch (error) {
            toast.error(`Processing failed: ${error.message}`);
        } finally {
            setIsProcessing(false);
        }
    };

    const activeDragIds = activeDragId
        ? (selectedPageIds.includes(activeDragId) ? selectedPageIds : [activeDragId])
        : [];
    const editingPage = pages.find(p => p.id === editingPageId);

    return (
        <div className="min-h-screen bg-gray-950 text-gray-100 font-sans pb-20">
            <div className="max-w-7xl mx-auto p-6">
                
                <div className="flex justify-between items-end mb-8 border-b border-gray-800 pb-4">
                    <div>
                        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400">PDF Studio Pro</h1>
                        <p className="text-gray-400 text-sm mt-1">Upload, reorder, rotate, and export PDF pages</p>
                    </div>
                    {pages.length > 0 && (
                        <button onClick={clearWorkspace} className="text-red-400 hover:text-red-300 text-sm flex items-center gap-1">
                            <Trash2 size={14} /> Clear Workspace
                        </button>
                    )}
                </div>

                {pages.length > 0 && (
                    <div className="flex items-center gap-2 mb-4 p-3 bg-blue-900/20 border border-blue-800 rounded-lg text-sm text-blue-200">
                        <Info size={16} className="text-blue-400" />
                        <span>Hold <kbd className="bg-blue-800 px-2 py-0.5 rounded text-white font-mono text-xs shadow-sm">Ctrl/Cmd</kbd> to toggle, or <kbd className="bg-blue-800 px-2 py-0.5 rounded text-white font-mono text-xs shadow-sm">Shift</kbd> for range. Drag one to move the whole group.</span>
                    </div>
                )}

                {/* Grid */}
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
                    <SortableContext items={pages} strategy={rectSortingStrategy}>
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                            
                            <label className="border-2 border-dashed border-gray-800 rounded-lg flex flex-col items-center justify-center cursor-pointer hover:bg-gray-900 hover:border-purple-500 transition-all h-60 group">
                                <input type="file" multiple accept=".pdf" onChange={handleFileChange} className="hidden" />
                                <div className="bg-gray-800 group-hover:bg-gray-700 p-3 rounded-full mb-3 transition-colors">
                                    <Upload size={24} className="text-gray-400 group-hover:text-purple-400" />
                                </div>
                                <span className="text-xs text-gray-500 font-medium">Add PDF</span>
                            </label>

                            {pages.map((page) => (
                                <SortablePage
                                    key={page.id}
                                    id={page.id}
                                    page={page}
                                    file={files[page.fileId]}
                                    onRemove={handleRemovePage}
                                    isSelected={selectedPageIds.includes(page.id)}
                                    onToggleSelection={handleToggleSelection}
                                    onEnlarge={setEditingPageId}
                                />
                            ))}
                        </div>
                    </SortableContext>

                    <DragOverlay dropAnimation={dropAnimation}>
                        {activeDragId ? (
                            <DragOverlayContent ids={activeDragIds} pages={pages} files={files} />
                        ) : null}
                    </DragOverlay>
                </DndContext>

                {/*when empty */}
                {pages.length === 0 && (
                    <div className="text-center py-20">
                        <div className="inline-block p-6 bg-gray-900 rounded-full mb-4">
                            <Layers size={48} className="text-gray-700" />
                        </div>
                        <h3 className="text-xl font-semibold text-gray-300">Workspace is Empty</h3>
                        <p className="text-gray-500 max-w-sm mx-auto mt-2">Upload PDFs to start rearranging, rotating, and preparing your document structure.</p>
                    </div>
                )}
            </div>

            {/* bottom */}
            {pages.length > 0 && (
                <div className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 p-4 z-40 flex justify-between items-center px-8 shadow-[0_-10px_40px_rgba(0,0,0,0.5)]">
                    <div className="flex items-center gap-4">
                        <div className="text-sm text-gray-400">
                            <span className="text-white font-bold">{pages.length}</span> Pages • <span className="text-white font-bold">{Object.keys(files).length}</span> Files
                        </div>
                        {selectedPageIds.length > 0 && (
                            <button onClick={handleDeleteSelected} className="flex items-center gap-2 px-3 py-1 bg-red-900/30 text-red-400 border border-red-900/50 rounded-lg hover:bg-red-900/50 text-sm transition-colors font-medium">
                                <Trash2 size={16} /> Delete {selectedPageIds.length} Selected
                            </button>
                        )}
                    </div>
                    <button onClick={handleSubmit} disabled={isProcessing} className="bg-purple-600 hover:bg-purple-500 text-white px-8 py-2.5 rounded-lg font-bold shadow-lg shadow-purple-900/20 transition-all transform active:scale-95 flex items-center gap-2">
                        {isProcessing ? "Processing..." : "Export Final PDF"}
                    </button>
                </div>
            )}

            {/* edit modal */}
            {editingPageId && editingPage && (
                <EditPageModal
                    page={editingPage}
                    file={files[editingPage.fileId]}
                    onClose={() => setEditingPageId(null)}
                    onEditChange={handlePageEditChange}
                />
            )}
        </div>
    );
}