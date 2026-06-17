import io
import math
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.config import settings


BBox = Dict[str, float]


@dataclass
class LayoutElement:
    page_number: int
    type: str
    text: str
    bbox: BBox
    source: str
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "type": self.type,
            "text": self.text,
            "bbox": self.bbox,
            "source": self.source,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class PageExtraction:
    page_number: int
    width: float
    height: float
    text: str = ""
    markdown: str = ""
    elements: List[LayoutElement] = field(default_factory=list)
    extraction_mode: str = "unknown"
    parser_chain: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "text": self.text,
            "markdown": self.markdown,
            "elements": [element.to_dict() for element in self.elements],
            "extraction_mode": self.extraction_mode,
            "parser_chain": self.parser_chain,
            "warnings": self.warnings,
            "char_count": len(self.text),
            "element_count": len(self.elements),
        }


class PDFExtractionService:
    """
    Layout-first document extraction pipeline.

    Native PDF content is read with LiteParse, then enriched with table-aware
    pdfplumber extraction. Pages with a weak or absent text layer are OCR'd with
    PaddleOCR and merged back into the same coordinate-preserving schema.
    """

    def __init__(self):
        self._paddle_ocr = None
        self._paddle_structure = None

    def extract_document(self, filename: str, content: bytes) -> Dict[str, Any]:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "pdf":
            return self._extract_pdf(filename, content)
        if ext in {"txt", "md", "csv", "html"}:
            return self._extract_text_file(filename, content, ext)
        raise ValueError(f"Unsupported document format: .{ext}")

    def _extract_text_file(self, filename: str, content: bytes, ext: str) -> Dict[str, Any]:
        text = content.decode("utf-8", errors="ignore")
        page = PageExtraction(
            page_number=1,
            width=0,
            height=0,
            text=text,
            markdown=text,
            extraction_mode="text",
            parser_chain=["raw-text"],
        )
        return self._build_document_result(
            filename=filename,
            file_type=ext,
            pages=[page],
            parser_chain=["raw-text"],
            warnings=[],
            markdown=text,
            profile="raw_text",
        )

    def _extract_pdf(self, filename: str, content: bytes) -> Dict[str, Any]:
        warnings: List[str] = []
        parser_chain: List[str] = []

        pages = self._extract_with_liteparse(content, warnings)
        if pages:
            parser_chain.append("liteparse")

        fallback_pages = self._extract_with_pdfplumber(content, warnings)
        if fallback_pages:
            parser_chain.append("pdfplumber")
            pages = self._merge_page_sets(pages, fallback_pages)

        if not pages:
            fallback_text = self._extract_with_pypdf(content, warnings)
            if fallback_text:
                parser_chain.append("pypdf")
                pages = [
                    PageExtraction(
                        page_number=1,
                        width=0,
                        height=0,
                        text=fallback_text,
                        markdown=fallback_text,
                        extraction_mode="digital_fallback",
                        parser_chain=["pypdf"],
                    )
                ]

        pages = self._ensure_page_slots(content, pages, warnings)
        page_numbers_for_ocr = self._select_pages_for_ocr(pages)

        if page_numbers_for_ocr:
            ocr_pages = self._extract_with_paddleocr(content, page_numbers_for_ocr, warnings)
            if ocr_pages:
                parser_chain.append("paddleocr")
                pages = self._merge_ocr_pages(pages, ocr_pages)

        structure_markdown = ""
        if settings.PDF_USE_PADDLE_STRUCTURE:
            structure_markdown = self._extract_with_paddle_structure(content, warnings)
            if structure_markdown:
                parser_chain.append("paddleocr-ppstructure")

        for page in pages:
            page.elements.sort(key=self._element_sort_key)
            page.text = page.text or self._elements_to_layout_text(page.elements, page.width)
            page.markdown = page.markdown or self._page_to_markdown(page)
            if not page.parser_chain:
                page.parser_chain = parser_chain

        markdown = structure_markdown or "\n\n".join(page.markdown for page in pages if page.markdown)
        profile = self._document_profile(pages)
        return self._build_document_result(
            filename=filename,
            file_type="pdf",
            pages=pages,
            parser_chain=parser_chain or ["unavailable"],
            warnings=warnings,
            markdown=markdown,
            profile=profile,
        )

    def _extract_with_liteparse(self, content: bytes, warnings: List[str]) -> List[PageExtraction]:
        try:
            from liteparse import LiteParse
        except Exception as exc:
            warnings.append(f"LiteParse unavailable: {exc}")
            return []

        try:
            parser = LiteParse(
                ocr_enabled=False,
                dpi=float(settings.PDF_RENDER_DPI),
                preserve_very_small_text=True,
                quiet=True,
                max_pages=settings.PDF_MAX_PAGES,
            )
            result = parser.parse(content)
        except Exception as exc:
            warnings.append(f"LiteParse extraction failed: {exc}")
            return []

        pages: List[PageExtraction] = []
        for parsed_page in getattr(result, "pages", []) or []:
            page_number = int(getattr(parsed_page, "page_num", len(pages) + 1))
            width = float(getattr(parsed_page, "width", 0) or 0)
            height = float(getattr(parsed_page, "height", 0) or 0)
            elements = []
            for item in getattr(parsed_page, "text_items", []) or []:
                text = str(getattr(item, "text", "") or "")
                if not text.strip():
                    continue
                x0 = float(getattr(item, "x", 0) or 0)
                top = float(getattr(item, "y", 0) or 0)
                item_width = float(getattr(item, "width", 0) or 0)
                item_height = float(getattr(item, "height", 0) or 0)
                elements.append(
                    LayoutElement(
                        page_number=page_number,
                        type="text",
                        text=text,
                        bbox={
                            "x0": x0,
                            "top": top,
                            "x1": x0 + item_width,
                            "bottom": top + item_height,
                        },
                        source="liteparse",
                        confidence=getattr(item, "confidence", None),
                        metadata={
                            "font_name": getattr(item, "font_name", None),
                            "font_size": getattr(item, "font_size", None),
                        },
                    )
                )

            text = str(getattr(parsed_page, "text", "") or "")
            page = PageExtraction(
                page_number=page_number,
                width=width,
                height=height,
                text=text or self._elements_to_layout_text(elements, width),
                markdown=text,
                elements=elements,
                extraction_mode="digital",
                parser_chain=["liteparse"],
            )
            pages.append(page)
        return pages

    def _extract_with_pdfplumber(self, content: bytes, warnings: List[str]) -> List[PageExtraction]:
        try:
            import pdfplumber
        except Exception as exc:
            warnings.append(f"pdfplumber unavailable: {exc}")
            return []

        pages: List[PageExtraction] = []
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for index, pdf_page in enumerate(pdf.pages, start=1):
                    words = pdf_page.extract_words(
                        keep_blank_chars=False,
                        use_text_flow=True,
                        x_tolerance=1,
                        y_tolerance=3,
                    )
                    elements = [
                        LayoutElement(
                            page_number=index,
                            type="text",
                            text=str(word.get("text", "")),
                            bbox={
                                "x0": float(word.get("x0", 0) or 0),
                                "top": float(word.get("top", 0) or 0),
                                "x1": float(word.get("x1", 0) or 0),
                                "bottom": float(word.get("bottom", 0) or 0),
                            },
                            source="pdfplumber",
                            metadata={
                                "upright": word.get("upright"),
                                "direction": word.get("direction"),
                            },
                        )
                        for word in words
                        if str(word.get("text", "")).strip()
                    ]

                    for table_index, table in enumerate(pdf_page.find_tables(), start=1):
                        table_data = table.extract() or []
                        table_text = self._table_to_markdown(table_data)
                        if not table_text.strip():
                            continue
                        x0, top, x1, bottom = table.bbox
                        elements.append(
                            LayoutElement(
                                page_number=index,
                                type="table",
                                text=table_text,
                                bbox={
                                    "x0": float(x0),
                                    "top": float(top),
                                    "x1": float(x1),
                                    "bottom": float(bottom),
                                },
                                source="pdfplumber",
                                metadata={
                                    "table_index": table_index,
                                    "rows": len(table_data),
                                    "columns": max((len(row) for row in table_data), default=0),
                                },
                            )
                        )

                    layout_text = self._elements_to_layout_text(elements, float(pdf_page.width or 0))
                    pages.append(
                        PageExtraction(
                            page_number=index,
                            width=float(pdf_page.width or 0),
                            height=float(pdf_page.height or 0),
                            text=layout_text,
                            markdown=self._elements_to_markdown(elements),
                            elements=elements,
                            extraction_mode="digital",
                            parser_chain=["pdfplumber"],
                        )
                    )
        except Exception as exc:
            warnings.append(f"pdfplumber extraction failed: {exc}")
            return []
        return pages

    def _extract_with_pypdf(self, content: bytes, warnings: List[str]) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
        except Exception as exc:
            warnings.append(f"pypdf fallback failed: {exc}")
            return ""

    def _extract_with_paddleocr(
        self,
        content: bytes,
        page_numbers: Sequence[int],
        warnings: List[str],
    ) -> List[PageExtraction]:
        try:
            rendered_pages = self._render_pdf_pages(content, page_numbers)
        except Exception as exc:
            warnings.append(f"PDF rendering for PaddleOCR failed: {exc}")
            return []

        try:
            ocr = self._get_paddle_ocr()
        except Exception as exc:
            warnings.append(f"PaddleOCR unavailable: {exc}")
            return []

        pages: List[PageExtraction] = []
        for rendered_page in rendered_pages:
            page_number = rendered_page["page_number"]
            try:
                raw_result = self._run_paddle_ocr(ocr, rendered_page["image"])
                elements = self._coerce_paddle_ocr_elements(
                    raw_result,
                    page_number=page_number,
                    image_width=float(rendered_page["image_width"]),
                    image_height=float(rendered_page["image_height"]),
                    page_width=float(rendered_page["page_width"]),
                    page_height=float(rendered_page["page_height"]),
                )
            except Exception as exc:
                warnings.append(f"PaddleOCR failed on page {page_number}: {exc}")
                continue

            text = self._elements_to_layout_text(elements, float(rendered_page["page_width"]))
            pages.append(
                PageExtraction(
                    page_number=page_number,
                    width=float(rendered_page["page_width"]),
                    height=float(rendered_page["page_height"]),
                    text=text,
                    markdown=self._elements_to_markdown(elements),
                    elements=elements,
                    extraction_mode="scanned_ocr",
                    parser_chain=["paddleocr"],
                )
            )
        return pages

    def _extract_with_paddle_structure(self, content: bytes, warnings: List[str]) -> str:
        try:
            structure = self._get_paddle_structure()
            with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_pdf:
                temp_pdf.write(content)
                temp_pdf.flush()
                result = structure.predict(temp_pdf.name)
        except Exception as exc:
            warnings.append(f"PP-StructureV3 extraction failed: {exc}")
            return ""

        markdown_pages = []
        for item in result or []:
            payload = self._object_to_dict(item)
            markdown = payload.get("markdown") or {}
            if isinstance(markdown, dict):
                page_text = markdown.get("text") or markdown.get("markdown_texts")
                if isinstance(page_text, list):
                    page_text = "\n\n".join(str(part) for part in page_text)
                if page_text:
                    markdown_pages.append(str(page_text))
        return "\n\n".join(markdown_pages)

    def _get_paddle_ocr(self):
        if self._paddle_ocr is not None:
            return self._paddle_ocr

        from paddleocr import PaddleOCR

        kwargs: Dict[str, Any] = {
            "lang": settings.PDF_OCR_LANG,
            "use_doc_orientation_classify": True,
            "use_doc_unwarping": True,
            "use_textline_orientation": True,
        }
        if settings.PDF_OCR_DEVICE:
            kwargs["device"] = settings.PDF_OCR_DEVICE
        if settings.PDF_OCR_ENGINE:
            kwargs["engine"] = settings.PDF_OCR_ENGINE

        try:
            self._paddle_ocr = PaddleOCR(**kwargs)
        except TypeError:
            legacy_kwargs: Dict[str, Any] = {
                "lang": settings.PDF_OCR_LANG,
                "use_angle_cls": True,
                "show_log": False,
            }
            self._paddle_ocr = PaddleOCR(**legacy_kwargs)
        return self._paddle_ocr

    def _get_paddle_structure(self):
        if self._paddle_structure is not None:
            return self._paddle_structure

        from paddleocr import PPStructureV3

        kwargs: Dict[str, Any] = {}
        if settings.PDF_OCR_DEVICE:
            kwargs["device"] = settings.PDF_OCR_DEVICE
        if settings.PDF_OCR_ENGINE:
            kwargs["engine"] = settings.PDF_OCR_ENGINE
        self._paddle_structure = PPStructureV3(**kwargs)
        return self._paddle_structure

    def _run_paddle_ocr(self, ocr: Any, image: Any) -> Any:
        if hasattr(ocr, "predict"):
            return ocr.predict(image)
        return ocr.ocr(image, cls=True)

    def _render_pdf_pages(self, content: bytes, page_numbers: Sequence[int]) -> List[Dict[str, Any]]:
        import fitz
        import numpy as np
        from PIL import Image

        pages: List[Dict[str, Any]] = []
        page_number_set = set(page_numbers)
        scale = settings.PDF_RENDER_DPI / 72.0
        matrix = fitz.Matrix(scale, scale)
        with fitz.open(stream=content, filetype="pdf") as document:
            for index, page in enumerate(document, start=1):
                if index not in page_number_set:
                    continue
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                image = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
                pages.append(
                    {
                        "page_number": index,
                        "page_width": float(page.rect.width),
                        "page_height": float(page.rect.height),
                        "image_width": image.width,
                        "image_height": image.height,
                        "image": np.array(image),
                    }
                )
        return pages

    def _coerce_paddle_ocr_elements(
        self,
        raw_result: Any,
        *,
        page_number: int,
        image_width: float,
        image_height: float,
        page_width: float,
        page_height: float,
    ) -> List[LayoutElement]:
        elements: List[LayoutElement] = []
        for payload in self._iter_ocr_payloads(raw_result):
            data = payload.get("res", payload)
            texts = data.get("rec_texts") or data.get("texts") or []
            scores = data.get("rec_scores") or data.get("scores") or []
            boxes = data.get("rec_boxes") or data.get("rec_polys") or data.get("dt_polys") or []

            for index, text in enumerate(texts):
                clean_text = str(text or "").strip()
                if not clean_text:
                    continue
                bbox = self._bbox_from_any_box(boxes[index] if index < len(boxes) else None)
                if not bbox:
                    bbox = {"x0": 0.0, "top": 0.0, "x1": page_width, "bottom": page_height}
                else:
                    bbox = self._scale_bbox(bbox, image_width, image_height, page_width, page_height)
                confidence = scores[index] if index < len(scores) else None
                elements.append(
                    LayoutElement(
                        page_number=page_number,
                        type="ocr_text",
                        text=clean_text,
                        bbox=bbox,
                        source="paddleocr",
                        confidence=self._safe_float(confidence),
                    )
                )

        if elements:
            return elements
        return self._coerce_legacy_paddle_elements(
            raw_result,
            page_number=page_number,
            image_width=image_width,
            image_height=image_height,
            page_width=page_width,
            page_height=page_height,
        )

    def _iter_ocr_payloads(self, raw_result: Any) -> Iterable[Dict[str, Any]]:
        if raw_result is None:
            return []
        if isinstance(raw_result, dict):
            return [raw_result]
        if not isinstance(raw_result, list):
            payload = self._object_to_dict(raw_result)
            return [payload] if payload else []

        payloads = []
        for item in raw_result:
            payload = self._object_to_dict(item)
            if payload:
                payloads.append(payload)
        return payloads

    def _coerce_legacy_paddle_elements(
        self,
        raw_result: Any,
        *,
        page_number: int,
        image_width: float,
        image_height: float,
        page_width: float,
        page_height: float,
    ) -> List[LayoutElement]:
        lines = raw_result
        if isinstance(raw_result, list) and len(raw_result) == 1 and isinstance(raw_result[0], list):
            lines = raw_result[0]

        elements: List[LayoutElement] = []
        if not isinstance(lines, list):
            return elements
        for line in lines:
            if not isinstance(line, (list, tuple)) or len(line) < 2:
                continue
            bbox = self._bbox_from_any_box(line[0])
            text_payload = line[1]
            text = ""
            confidence = None
            if isinstance(text_payload, (list, tuple)) and text_payload:
                text = str(text_payload[0] or "")
                confidence = text_payload[1] if len(text_payload) > 1 else None
            else:
                text = str(text_payload or "")
            if not text.strip() or not bbox:
                continue
            elements.append(
                LayoutElement(
                    page_number=page_number,
                    type="ocr_text",
                    text=text.strip(),
                    bbox=self._scale_bbox(bbox, image_width, image_height, page_width, page_height),
                    source="paddleocr",
                    confidence=self._safe_float(confidence),
                )
            )
        return elements

    def _object_to_dict(self, obj: Any) -> Dict[str, Any]:
        if isinstance(obj, dict):
            return obj
        json_attr = getattr(obj, "json", None)
        if isinstance(json_attr, dict):
            return json_attr
        if callable(json_attr):
            value = json_attr()
            if isinstance(value, dict):
                return value
        if hasattr(obj, "to_dict"):
            value = obj.to_dict()
            if isinstance(value, dict):
                return value
        return {}

    def _bbox_from_any_box(self, box: Any) -> Optional[BBox]:
        if box is None:
            return None
        if hasattr(box, "tolist"):
            box = box.tolist()
        if isinstance(box, dict):
            try:
                return {
                    "x0": float(box.get("x0", box.get("left", 0))),
                    "top": float(box.get("top", box.get("y0", 0))),
                    "x1": float(box.get("x1", box.get("right", 0))),
                    "bottom": float(box.get("bottom", box.get("y1", 0))),
                }
            except Exception:
                return None
        if not isinstance(box, (list, tuple)):
            return None
        if len(box) == 4 and all(isinstance(value, (int, float)) for value in box):
            x0, top, x1, bottom = box
            return {"x0": float(x0), "top": float(top), "x1": float(x1), "bottom": float(bottom)}
        points = []
        for point in box:
            if hasattr(point, "tolist"):
                point = point.tolist()
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((float(point[0]), float(point[1])))
        if not points:
            return None
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return {"x0": min(xs), "top": min(ys), "x1": max(xs), "bottom": max(ys)}

    def _scale_bbox(
        self,
        bbox: BBox,
        image_width: float,
        image_height: float,
        page_width: float,
        page_height: float,
    ) -> BBox:
        if image_width <= 0 or image_height <= 0:
            return bbox
        return {
            "x0": bbox["x0"] * page_width / image_width,
            "top": bbox["top"] * page_height / image_height,
            "x1": bbox["x1"] * page_width / image_width,
            "bottom": bbox["bottom"] * page_height / image_height,
        }

    def _merge_page_sets(
        self,
        primary_pages: List[PageExtraction],
        fallback_pages: List[PageExtraction],
    ) -> List[PageExtraction]:
        page_map = {page.page_number: page for page in primary_pages}
        for fallback in fallback_pages:
            existing = page_map.get(fallback.page_number)
            if existing is None:
                page_map[fallback.page_number] = fallback
                continue

            if len(fallback.text.strip()) > len(existing.text.strip()) * 1.25:
                fallback.parser_chain = self._merge_unique(existing.parser_chain + fallback.parser_chain)
                page_map[fallback.page_number] = fallback
                continue

            existing.parser_chain = self._merge_unique(existing.parser_chain + fallback.parser_chain)
            if not existing.width:
                existing.width = fallback.width
            if not existing.height:
                existing.height = fallback.height
            for element in fallback.elements:
                if element.type == "table":
                    existing.elements.append(element)
        return [page_map[number] for number in sorted(page_map)]

    def _merge_ocr_pages(
        self,
        pages: List[PageExtraction],
        ocr_pages: List[PageExtraction],
    ) -> List[PageExtraction]:
        page_map = {page.page_number: page for page in pages}
        for ocr_page in ocr_pages:
            existing = page_map.get(ocr_page.page_number)
            if existing is None:
                page_map[ocr_page.page_number] = ocr_page
                continue

            existing.parser_chain = self._merge_unique(existing.parser_chain + ocr_page.parser_chain)
            if self._page_has_usable_text(existing) and settings.PDF_EXTRACTION_STRATEGY != "hybrid":
                existing.extraction_mode = "hybrid_checked"
                continue

            if self._page_has_usable_text(existing):
                for element in ocr_page.elements:
                    if not self._is_duplicate_element(element, existing.elements):
                        existing.elements.append(element)
                existing.text = self._elements_to_layout_text(existing.elements, existing.width)
                existing.markdown = self._page_to_markdown(existing)
                existing.extraction_mode = "hybrid"
            else:
                page_map[ocr_page.page_number] = ocr_page
        return [page_map[number] for number in sorted(page_map)]

    def _ensure_page_slots(
        self,
        content: bytes,
        pages: List[PageExtraction],
        warnings: List[str],
    ) -> List[PageExtraction]:
        page_map = {page.page_number: page for page in pages}
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            total_pages = len(reader.pages)
        except Exception as exc:
            warnings.append(f"Unable to count PDF pages: {exc}")
            return pages

        for index in range(1, total_pages + 1):
            if index not in page_map:
                page_map[index] = PageExtraction(
                    page_number=index,
                    width=0,
                    height=0,
                    extraction_mode="pending_ocr",
                    parser_chain=[],
                )
        return [page_map[number] for number in sorted(page_map)]

    def _select_pages_for_ocr(self, pages: List[PageExtraction]) -> List[int]:
        strategy = settings.PDF_EXTRACTION_STRATEGY
        if strategy == "digital":
            return []
        if strategy == "ocr":
            return [page.page_number for page in pages]
        if strategy == "hybrid":
            return [page.page_number for page in pages]
        return [page.page_number for page in pages if not self._page_has_usable_text(page)]

    def _page_has_usable_text(self, page: PageExtraction) -> bool:
        text = page.text or self._elements_to_plain_text(page.elements)
        return len(text.strip()) >= settings.PDF_MIN_TEXT_CHARS_PER_PAGE

    def _document_profile(self, pages: List[PageExtraction]) -> str:
        modes = {page.extraction_mode for page in pages}
        if any(mode.startswith("scanned") for mode in modes) and any("digital" in mode for mode in modes):
            return "hybrid_pdf"
        if any(mode.startswith("scanned") for mode in modes):
            return "scanned_pdf"
        if any("hybrid" in mode for mode in modes):
            return "hybrid_pdf"
        return "digital_pdf"

    def _build_document_result(
        self,
        *,
        filename: str,
        file_type: str,
        pages: List[PageExtraction],
        parser_chain: List[str],
        warnings: List[str],
        markdown: str,
        profile: str,
    ) -> Dict[str, Any]:
        layout_text = "\n\n".join(self._format_page_text(page) for page in pages if page.text.strip())
        plain_text = layout_text or "\n\n".join(page.text for page in pages if page.text)
        elements_count = sum(len(page.elements) for page in pages)
        low_confidence_count = sum(
            1
            for page in pages
            for element in page.elements
            if element.confidence is not None and element.confidence < settings.PDF_OCR_MIN_CONFIDENCE
        )
        return {
            "filename": filename,
            "file_type": file_type,
            "text": plain_text,
            "layout_text": layout_text,
            "markdown": markdown or plain_text,
            "pages": [page.to_dict() for page in pages],
            "metadata": {
                "profile": profile,
                "page_count": len(pages),
                "parser_chain": self._merge_unique(parser_chain),
                "layout_preserved": True,
                "text_characters": len(plain_text),
                "element_count": elements_count,
                "low_confidence_ocr_elements": low_confidence_count,
            },
            "warnings": self._merge_unique(warnings),
        }

    def _format_page_text(self, page: PageExtraction) -> str:
        header = f"\n--- Page {page.page_number} ---\n"
        return f"{header}{page.text.strip()}"

    def _elements_to_plain_text(self, elements: Iterable[LayoutElement]) -> str:
        return " ".join(element.text for element in elements if element.text)

    def _elements_to_layout_text(self, elements: Iterable[LayoutElement], page_width: float) -> str:
        sorted_elements = sorted(
            [element for element in elements if element.text.strip() and element.type != "table"],
            key=self._element_sort_key,
        )
        if not sorted_elements:
            return ""

        line_height = self._median(
            [
                max(1.0, element.bbox["bottom"] - element.bbox["top"])
                for element in sorted_elements
                if element.bbox.get("bottom") is not None
            ]
        ) or 10.0
        y_tolerance = max(3.0, line_height * 0.6)
        char_width = max(3.5, (page_width or 612.0) / settings.PDF_LAYOUT_COLUMNS)

        lines: List[List[LayoutElement]] = []
        for element in sorted_elements:
            center_y = (element.bbox["top"] + element.bbox["bottom"]) / 2
            matched_line = None
            for line in lines:
                line_center = self._line_center_y(line)
                if abs(center_y - line_center) <= y_tolerance:
                    matched_line = line
                    break
            if matched_line is None:
                lines.append([element])
            else:
                matched_line.append(element)

        rendered_lines = []
        for line in lines:
            line.sort(key=lambda element: element.bbox["x0"])
            rendered = ""
            cursor = 0
            for element in line:
                target_col = max(0, int(element.bbox["x0"] / char_width))
                gap = max(1, target_col - cursor)
                if rendered:
                    rendered += " " * gap
                elif target_col > 0:
                    rendered += " " * min(target_col, settings.PDF_MAX_LEADING_SPACES)
                rendered += element.text
                cursor = target_col + len(element.text)
            rendered_lines.append(rendered.rstrip())

        table_blocks = [
            element.text
            for element in sorted(elements, key=self._element_sort_key)
            if element.type == "table" and element.text.strip()
        ]
        if table_blocks:
            return "\n".join(rendered_lines + [""] + table_blocks).strip()
        return "\n".join(rendered_lines).strip()

    def _elements_to_markdown(self, elements: Iterable[LayoutElement]) -> str:
        blocks = []
        for element in sorted(elements, key=self._element_sort_key):
            if element.type == "table":
                blocks.append(element.text)
            elif element.text.strip():
                blocks.append(element.text.strip())
        return "\n\n".join(blocks)

    def _page_to_markdown(self, page: PageExtraction) -> str:
        if page.markdown:
            return page.markdown
        return self._elements_to_markdown(page.elements) or page.text

    def _table_to_markdown(self, rows: List[List[Any]]) -> str:
        normalized_rows = [
            [str(cell or "").replace("\n", " ").strip() for cell in row]
            for row in rows
            if row and any(str(cell or "").strip() for cell in row)
        ]
        if not normalized_rows:
            return ""
        width = max(len(row) for row in normalized_rows)
        normalized_rows = [row + [""] * (width - len(row)) for row in normalized_rows]
        header = normalized_rows[0]
        separator = ["---"] * width
        body = normalized_rows[1:]
        return "\n".join(
            ["| " + " | ".join(header) + " |", "| " + " | ".join(separator) + " |"]
            + ["| " + " | ".join(row) + " |" for row in body]
        )

    def _is_duplicate_element(self, candidate: LayoutElement, existing: Iterable[LayoutElement]) -> bool:
        candidate_text = candidate.text.strip().lower()
        for element in existing:
            if element.text.strip().lower() != candidate_text:
                continue
            if self._bbox_overlap_ratio(candidate.bbox, element.bbox) > 0.65:
                return True
        return False

    def _bbox_overlap_ratio(self, left: BBox, right: BBox) -> float:
        x_overlap = max(0.0, min(left["x1"], right["x1"]) - max(left["x0"], right["x0"]))
        y_overlap = max(0.0, min(left["bottom"], right["bottom"]) - max(left["top"], right["top"]))
        intersection = x_overlap * y_overlap
        if intersection <= 0:
            return 0.0
        left_area = max(1.0, (left["x1"] - left["x0"]) * (left["bottom"] - left["top"]))
        right_area = max(1.0, (right["x1"] - right["x0"]) * (right["bottom"] - right["top"]))
        return intersection / min(left_area, right_area)

    def _element_sort_key(self, element: LayoutElement) -> Tuple[int, float, float, str]:
        return (
            element.page_number,
            round(float(element.bbox.get("top", 0)) / 4.0) * 4.0,
            float(element.bbox.get("x0", 0)),
            element.type,
        )

    def _line_center_y(self, line: Sequence[LayoutElement]) -> float:
        return sum((element.bbox["top"] + element.bbox["bottom"]) / 2 for element in line) / len(line)

    def _median(self, values: Sequence[float]) -> Optional[float]:
        if not values:
            return None
        sorted_values = sorted(value for value in values if not math.isnan(value))
        if not sorted_values:
            return None
        midpoint = len(sorted_values) // 2
        if len(sorted_values) % 2:
            return sorted_values[midpoint]
        return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except Exception:
            return None

    def _merge_unique(self, values: Iterable[str]) -> List[str]:
        merged = []
        for value in values:
            if value and value not in merged:
                merged.append(value)
        return merged


pdf_extraction_service = PDFExtractionService()
