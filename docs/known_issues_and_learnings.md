# JARVIS AI Assistant - Known Issues & Learnings

> Nhật ký sửa lỗi và bài học kinh nghiệm.
> File này là tài liệu VĨNH CỬU - không bao giờ xóa nội dung cũ.
> Cập nhật lần cuối: 15/04/2026

---

## Quy ước ghi chép

Mỗi entry theo format:
```
### [Ngày] Tiêu đề ngắn gọn
- **Triệu chứng**: Mô tả lỗi/vấn đề
- **Nguyên nhân gốc**: Root cause
- **Giải pháp**: Cách fix
- **Testcase**: Test đã thêm để phòng ngừa regression
- **Bài học**: Rút ra bài học gì cho tương lai
```

---

## Bài học kế thừa từ dự án trước

### [15/04/2026] Kinh nghiệm từ 06_04_2026_multimodal_rag_ai

- **LLM Factory Pattern**: Đã kiểm chứng hoạt động tốt với 4 providers (OpenAI, Gemini, Claude, Ollama). Cần lưu ý: mỗi provider có format tool/function calling khác nhau → factory phải normalize.
- **ChromaDB per-collection isolation**: Mỗi conversation/project nên có collection riêng để tránh cross-contamination khi search.
- **Streaming SSE**: FastAPI SSE hoạt động tốt nhưng cần handle client disconnect gracefully (try/except GeneratorExit).
- **PyQt6 QThread vs FastAPI async**: Dự án này dùng FastAPI (async) thay vì PyQt6 (threads) → async/await là pattern chính, không dùng threading.

### [15/04/2026] Kinh nghiệm từ 06_04_2026_comic_translator

- **Provider rate limiting**: Groq có rate limit rất thấp (30 req/min). Cần retry logic với exponential backoff cho mọi provider.
- **Singleton cho heavy models**: OCR model (EasyOCR) load mất 5-10s → dùng singleton. Áp dụng tương tự: Playwright browser instance nên là singleton, không khởi tạo mới mỗi request.
- **[SKIP] protocol**: Khi LLM không thể xử lý (ảnh mờ, text không đọc được), trả về marker rõ ràng thay vì hallucinate. Áp dụng: agent nên trả về "Tôi không thể thực hiện yêu cầu này" thay vì cố gắng làm sai.

---

## Lỗi phát hiện trong quá trình phát triển

*(Chưa có - sẽ được cập nhật khi bắt đầu code)*
