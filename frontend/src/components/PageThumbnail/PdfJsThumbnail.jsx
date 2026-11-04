import React, { useEffect, useRef } from "react";
import pdfjs from "../../utils/pdfjs";

const PdfJsThumbnail = React.memo(({ fileUrl, pageIndex, rotation, width = 180, isDragging, isOverlay }) => {
    const canvasRef = useRef(null);

    useEffect(() => {
        if (isDragging && !isOverlay) return;

        const canvas = canvasRef.current;
        if (!canvas || !fileUrl) return;

        let destroyed = false;
        let pdfDocument = null;
        let page = null;

        const renderPage = async () => {
            try {
                pdfDocument = await pdfjs.getDocument({ url: fileUrl }).promise;
                page = await pdfDocument.getPage(pageIndex + 1);
                if (destroyed) return;

                const scale = width / page.getViewport({ scale: 1 }).width;
                const viewport = page.getViewport({ scale });
                const context = canvas.getContext('2d');

                canvas.height = viewport.height;
                canvas.width = viewport.width;

                await page.render({ canvasContext: context, viewport: viewport }).promise;
            } catch (error) {
                if (!destroyed) console.error("Failed to render PDF thumbnail", error);
            }
        };

        renderPage();

        return () => {
            destroyed = true;
            if (page) page.cleanup();
            if (pdfDocument) pdfDocument.destroy().catch(() => {});
        };
    }, [fileUrl, pageIndex, width, isDragging, rotation, isOverlay]);

    if (isDragging && !isOverlay) {
        return (
            <div className="flex items-center justify-center w-full h-full bg-gray-800/50 rounded-lg">
                <div className="text-xs text-gray-500 font-medium">Moving...</div>
            </div>
        );
    }

    return (
        <div className="flex items-center justify-center w-full h-full p-2 overflow-hidden">
            <canvas
                ref={canvasRef}
                className="shadow-sm max-w-full max-h-full transition-transform duration-200"
                style={{ transform: `rotate(${rotation || 0}deg)` }}
            />
        </div>
    );
});

export default PdfJsThumbnail;