import React, { useEffect, useRef } from "react";
import pdfjs from "../../utils/pdfjs";

export const PdfJsModalRenderer = ({ fileUrl, pageIndex, rotation, cropMarginPercent = 0 }) => {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas || !fileUrl) return;

        let pdfDocument = null;
        let page = null;
        let destroyed = false;

        const renderPage = async () => {
            try {
                pdfDocument = await pdfjs.getDocument({ url: fileUrl }).promise;
                page = await pdfDocument.getPage(pageIndex + 1);
                if(destroyed) return;

                const viewport1x = page.getViewport({ scale: 1 });
                // Target width/height for display in modal
                const scale = Math.min(600 / viewport1x.width, 800 / viewport1x.height);
                const viewport = page.getViewport({ scale, rotation });

                const context = canvas.getContext('2d');
                canvas.height = viewport.height;
                canvas.width = viewport.width;

                await page.render({ canvasContext: context, viewport }).promise;
            } catch (error) {
                console.error("Failed to render PDF page", error);
            }
        };
        renderPage();
        return () => { destroyed = true; if(page) page.cleanup(); };
    }, [fileUrl, pageIndex, rotation]);

    return (
        <div className="relative inline-flex">
            <canvas ref={canvasRef} className="shadow-2xl border border-gray-700" />
            {cropMarginPercent > 0 && (
                <>
                    <div className="pointer-events-none absolute inset-x-0 top-0 bg-black/60" style={{ height: `${cropMarginPercent}%` }} />
                    <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-black/60" style={{ height: `${cropMarginPercent}%` }} />
                    <div className="pointer-events-none absolute left-0 bg-black/60" style={{ top: `${cropMarginPercent}%`, bottom: `${cropMarginPercent}%`, width: `${cropMarginPercent}%` }} />
                    <div className="pointer-events-none absolute right-0 bg-black/60" style={{ top: `${cropMarginPercent}%`, bottom: `${cropMarginPercent}%`, width: `${cropMarginPercent}%` }} />
                    <div className="pointer-events-none absolute border-2 border-purple-400" style={{ inset: `${cropMarginPercent}%` }} />
                </>
            )}
        </div>
    );
};