# JARVIS AI Assistant - Known Issues & Learnings

> Nhật ký sửa lỗi và bài học kinh nghiệm.
> File này là tài liệu VĨNH CỬU - không bao giờ xóa nội dung cũ.
> Cập nhật lần cuối: 15/04/2026 (Phase 8 — thêm entry start.bat paren bug + pip quiet bug)

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

### [15/04/2026] start.bat tự tắt khi double-click

- **Triệu chứng**: Người dùng nhấn `start.bat` thì cửa sổ cmd mở rồi tắt ngay, không thấy lỗi.
- **Nguyên nhân gốc**: Kết hợp `@echo off` + `%ERRORLEVEL%` trong nested `if` block khiến biến không expand đúng → script thoát sớm. Trên máy người dùng dùng Python launcher `py -3` thay vì `python` → branch detection thất bại.
- **Giải pháp**:
  - Thêm `setlocal EnableDelayedExpansion`, dùng `!ERRORLEVEL!` thay `%ERRORLEVEL%`.
  - Thêm label `:fail` với `pause` để giữ cửa sổ khi lỗi.
  - Ưu tiên `py -3` launcher (đã xác nhận máy người dùng có).
  - Quote port và path có spaces.
- **Testcase**: Manual smoke test — chạy `start.bat` lần đầu (chưa có venv) và lần thứ N (đã có venv).
- **Bài học**: Trên Windows, batch script với `if/else` lồng nhau bắt buộc dùng delayed expansion. Luôn để `pause` ở các nhánh lỗi để người dùng đọc được log.

### [15/04/2026] duckduckgo-search v8 — `AsyncDDGS` không tồn tại

- **Triệu chứng**: `ImportError: cannot import name 'AsyncDDGS' from 'duckduckgo_search'`.
- **Nguyên nhân gốc**: v8 đã loại bỏ class async, chỉ còn `DDGS` đồng bộ.
- **Giải pháp**: Dùng `DDGS()` đồng bộ + bọc trong `await asyncio.to_thread(...)`. Handle trường hợp `text()` trả `None` (rate limit) bằng cách trả `[]`.
- **Testcase**: `tests/tools/test_web_search.py` mock `DDGS().text` thay vì `AsyncDDGS`.
- **Bài học**: SDK upgrade major version có thể xoá API public — pin chính xác version trong `requirements.txt` cho production hoặc check changelog trước khi upgrade.

### [15/04/2026] Gemini model deprecation (2.0-flash → 2.5)

- **Triệu chứng**: `404 model not found: gemini-2.0-flash`.
- **Nguyên nhân gốc**: Google deprecate Gemini 2.0 series sau khi ra 2.5; project hardcode 2.0-flash trong default model list.
- **Giải pháp**: Cập nhật default models thành `gemini-2.5-flash` và `gemini-2.5-pro`. Cho phép người dùng nhập model name tự do trong Settings panel.
- **Testcase**: `/api/providers` test list models trả về 2.5 series.
- **Bài học**: Không hardcode model name vào code khi nhà cung cấp deprecate nhanh — kéo từ config hoặc cho phép user override.

### [15/04/2026] Voice STT echo loop với `continuous=true`

- **Triệu chứng**: Sau khi assistant trả lời, TTS phát qua loa → mic SpeechRecognition pick up → tạo message mới → lặp vô hạn. Người dùng thấy nhiều "Hàng này là thứ mấy" xuất hiện liên tiếp.
- **Nguyên nhân gốc**: `recognition.continuous = true` giữ mic active liên tục; khi TTS phát audio qua headphone/loa, mic ghi lại và tạo result mới.
- **Giải pháp**: `continuous = false` — recognition tự stop sau 1 final result. User phải click mic lại cho lượt sau. Đơn giản hoá `onend` handler chỉ set `isListening=false`.
- **Testcase**: Manual — bật mic, nói câu hỏi, chờ TTS trả lời, verify mic không tự bật lại.
- **Bài học**: Continuous voice mode chỉ an toàn khi có voice activity detection (VAD) hoặc echo cancellation hardware. Browser native không có → dùng push-to-talk (continuous=false).

### [15/04/2026] Gemini 2.5 thinking format leak vào UI

- **Triệu chứng**: Response hiển thị thô dạng `[{'type': 'text', 'text': 'Today is...', 'extras': {'signature': '...'}}]` thay vì plain text.
- **Nguyên nhân gốc**: Gemini 2.5 trả `message.content` dưới dạng list of dicts (text + thinking blocks) thay vì string. Backend dùng `str(content)` thẳng → in nguyên list ra UI.
- **Giải pháp**: Trong `run_agent` và `stream_agent` (`backend/app/agent/brain.py`), check `isinstance(content, list)` → loop, extract chỉ block `type=="text"`, join lại bằng `"\n".join(text_parts)`. Bỏ qua `thinking`, `signature`.
- **Testcase**: Manual verify — query simple ("What day is today?") + RAG query đều trả plain text, không có `[{...}]`.
- **Bài học**: Khi LangChain wrap multi-modal content, output có thể là list — luôn type-check trước khi serialize. Mỗi LLM provider có format thinking khác nhau; agent code phải normalize.

### [15/04/2026] Gemini safety filter chặn local computer control tools

- **Triệu chứng**: Khi đăng ký `desktop_control`, `app_launcher`, `file_manager` cho Gemini, model từ chối gọi tool với "I cannot perform actions on your local computer" ngay cả khi prompt đã engineer kỹ.
- **Nguyên nhân gốc**: Gemini 2.5 (cả flash và pro) có safety filter hardcoded cho category "tool that controls user's machine" — không có `safety_settings` nào bypass được.
- **Giải pháp**: Không có fix kỹ thuật. Document hạn chế trong README + technical_reference. Khuyến nghị OpenAI/Claude cho computer-use; Gemini chỉ cho web_search và rag_search.
- **Testcase**: N/A (limitation thuộc về provider).
- **Bài học**: Trước khi chọn LLM cho use case agent, test khả năng tool-calling thực tế chứ không chỉ dựa trên capability matrix nhà cung cấp công bố. Multi-provider factory cứu được tình huống này — switch sang provider khác là xong.

### [15/04/2026] PDF upload bị track vào git

- **Triệu chứng**: `git status` hiện file PDF lớn trong `backend/uploads/`.
- **Nguyên nhân gốc**: `.gitignore` ban đầu không có `backend/uploads/` và `backend/chroma_data/` — RAG runtime data bị track.
- **Giải pháp**: Thêm vào `.gitignore`: `backend/uploads/`, `backend/chroma_data/`, `chroma_data/`. `git rm --cached` cho các file đã track.
- **Testcase**: Sau upload mới, `git status` không hiển thị file mới.
- **Bài học**: Khi thêm tính năng có persistent local storage (uploads, vector DB, cache), update `.gitignore` ngay trong commit feature đó, không để sau.

### [15/04/2026] Vietnamese STT confuse "Jarvis" thành "chao với"

- **Triệu chứng**: Khi bật `lang=vi-VN` và nói "Jarvis", recognizer trả "chao với" (phonetic gần nhau).
- **Nguyên nhân gốc**: Web Speech API (Chrome) cho tiếng Việt không hỗ trợ wake word custom; phiên âm "Jarvis" không có trong từ vựng tiếng Việt.
- **Giải pháp**: Không có fix browser-side. Workaround: bỏ wake word, dùng push-to-talk (click mic). Document trong known_issues.
- **Testcase**: N/A.
- **Bài học**: Wake word detection trên browser native = không khả thi cho ngôn ngữ ngoài English. Nếu cần wake word cross-language → phải dùng Picovoice Porcupine hoặc Whisper cục bộ.

### [15/04/2026] Frontend hiện câu hỏi liên tục khi backend down

- **Triệu chứng**: Khi backend không chạy, người dùng gửi tin nhắn → frontend ECONNREFUSED → message của user vẫn append vào chat lặp đi lặp lại.
- **Nguyên nhân gốc**: `useAgent` không có retry control + không phân biệt error vs timeout, và `setMessages` push user message trước khi gọi API. Khi gọi fail, hook vẫn re-append.
- **Giải pháp** (Phase 7):
  - Push user message một lần duy nhất trước retry loop.
  - Retry 3 lần với exponential backoff (250 / 500 / 1000 ms).
  - Khi exhausted, hiển thị toast "Backend không phản hồi" thay vì spam chat.
  - WebSocket disconnect → auto-reconnect tối đa 5 lần rồi toast.
- **Testcase**: Manual — tắt backend, gửi message, verify chỉ thấy 1 user message + toast lỗi.
- **Bài học**: Mọi network call user-facing phải có retry + user feedback rõ ràng. Tách "submit message" và "send to API" làm 2 step idempotent.

### [15/04/2026] start.bat — `pip install --quiet` khiến người dùng tưởng script bị treo

- **Triệu chứng**: Chạy `start.bat` lần đầu tiên (chưa có venv packages), dừng ở `[2/6] Checking backend dependencies... Installing... this may take a few minutes` trong 10-30 phút không thấy tiến trình gì. Người dùng tưởng script đã đứng.
- **Nguyên nhân gốc**: Flag `--quiet` của pip tắt **toàn bộ output** (progress bar, tên package đang cài, URL đang tải). Requirements gồm `sentence-transformers` kéo theo `torch` (~2.5 GB), `chromadb`, `unstructured[pdf]`, `playwright`, v.v. — tổng ~3 GB phải download. Với `--quiet` thì màn hình đen im lặng cho tới khi xong hoặc fail.
- **Giải pháp**:
  - Bỏ `--quiet`, thay bằng `--progress-bar on --disable-pip-version-check` để hiện real-time progress bar của pip.
  - Thêm echo cảnh báo trước khi install: "~3 GB download, 10-30 min trên mạng chậm, do NOT close this window".
  - Sửa luôn `npm install --silent` → `npm install --progress=true` cho step [4/6] + thêm error check (trước không có).
- **Testcase**: Manual — xoá `backend/venv` và `frontend/node_modules`, chạy `start.bat`, verify thấy progress bar pip + npm.
- **Bài học**: Không dùng `--quiet` cho install command trong script người dùng chạy trực tiếp — silent UX làm người dùng tưởng hệ thống hỏng và Ctrl+C giữa chừng → corrupt venv. Luôn hiển thị progress cho operation dài > 5 giây.

### [15/04/2026] start.bat — ngoặc đơn trong `echo` phá block `if (...)`

- **Triệu chứng**: Sau khi sửa start.bat để hiển thị progress bar, người dùng double-click → cmd window tắt đột ngột, không kịp thấy lỗi.
- **Nguyên nhân gốc**: Bên trong block `if !ERRORLEVEL! neq 0 ( ... )`, Windows batch parser **chỉ đếm ngoặc đơn thô** — không phân biệt ngoặc trong string `echo`. Dòng `echo Installing... [first run downloads ~3 GB, can take 10-30 min on slow networks]` mà tôi viết ban đầu dùng `(...)` → parser gặp `)` đầu tiên (sau "networks") → **đóng block `if` sớm** → các lệnh còn lại (pip install, error check, echo Installed) chạy ngoài context `if`, hoặc gặp `)` thứ 2 làm syntax error → cmd thoát với `exit /b`.
- **Giải pháp**:
  - Đổi `(...)` → `[...]` trong mọi echo string nằm trong block `if`/`for`.
  - (Alternative: escape bằng `^(` `^)` — nhưng `[...]` sạch hơn.)
- **Testcase**: Manual — double-click `start.bat` trên máy chưa có venv, window phải chạy bình thường không tắt.
- **Bài học**: Trong Windows batch block (`if`, `for`, `( ... )`), các ký tự sau phải escape hoặc tránh trong string: `(` `)` `&` `|` `<` `>` `%` `!`. An toàn nhất là đọc script qua `cmd /V:ON /C "script.bat"` hoặc test `echo on` trước khi ship. Cạm bẫy này không được PowerShell/Bash cảnh báo — chỉ Windows cmd mới có.
