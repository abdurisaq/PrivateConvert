import asyncio

from fastapi.responses import FileResponse

from app import app as application


def test_module_worker_assets_use_javascript_mime_type(tmp_path, monkeypatch):
    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (assets_dir / "pdf.worker.mjs").write_text("export {};", encoding="utf-8")
    monkeypatch.setattr(application, "frontend_dir", static_dir)

    response = asyncio.run(application.serve_frontend("assets/pdf.worker.mjs"))

    assert isinstance(response, FileResponse)
    assert response.media_type == "text/javascript"
