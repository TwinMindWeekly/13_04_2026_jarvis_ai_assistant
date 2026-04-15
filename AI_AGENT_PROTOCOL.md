# MASTER AI AGENT PROTOCOL
*(Universal Enterprise Guidelines)*

Tài liệu này đóng vai trò là "Bộ Hiến Pháp" (Master Guidelines) định hình cách thức làm việc giữa AI Agent và User cho **Bất kỳ Dự án Phát triển Hệ thống nào**. 
Mục tiêu tối thượng là đảm bảo chất lượng kỹ thuật, tính minh bạch, khả năng bảo trì và cấu hình kiến trúc mở rộng theo tiêu chuẩn doanh nghiệp.
Mọi AI Agent đi vào dự án bắt buộc phải tuân theo các quy định dưới đây.

---

## 1. Quy tắc Khởi tạo Dự án & Đặt tên
Khi được yêu cầu khởi tạo một dự án mới, AI Agent phải thực hiện việc định nghĩa tên theo cấu trúc:
- **Cấu trúc Tên Project/Repository**: `DD_MM_YYYY_tên_dự_án`
- **Ví dụ**: `06_04_2026_multimodal_rag_ai`
- **Giải thích**: Phần ngày tháng (`DD_MM_YYYY`) **luôn luôn** là ngày thứ Hai (bắt đầu của tuần đó) theo chuẩn giờ Việt Nam. Định dạng ngày tháng phải sử dụng dấu gạch dưới `_`.
- **Git Remote**: Mỗi dự án quy hoạch đẩy lên kho lưu trữ tương ứng tại GitHub: `https://github.com/TwinMindWeekly/...`

---

## 2. Quy chuẩn Tài liệu (Documentation)
Mọi project đều phải có đủ bộ tài liệu tiêu chuẩn ngay từ đầu. AI Agent KHÔNG ĐƯỢC phép code bất kỳ logic nào nếu chưa khởi tạo các file này:
1. `README.md`: Giới thiệu dự án, công nghệ sử dụng, và cách chạy dự án (How to run).
2. `task.md`: Bảng quản lý tiến độ chia thành các Phase rõ ràng (VD: `[ ]` Chưa làm, `[x]` Đã xong).
3. `implementation_plan.md`: Đề xuất chi tiết giải pháp kỹ thuật trước khi làm.
4. `docs/`: Thư mục chứa tài liệu tham khảo kỹ thuật, sơ đồ hệ thống, v.v.

---

## 3. Luồng làm việc chuẩn của AI Agent (Workflow Protocol)
Để xử lý các task hiệu quả, AI Agent phải trải qua vòng lặp sau:

### Bước 1: Tiếp nhận & Phân tích (Breakdown)
- Khi User đưa ra ý tưởng, AI phải phân rã (break down) mục tiêu dự án thành các **Phases** (Giai đoạn) và **Tasks** (Nhiệm vụ nhỏ) với sự phân tách logic.
- Ghi toàn bộ kết quả phân rã vào file `task.md`.

### Bước 2: Đề xuất Kế hoạch (Implementation Plan)
- Thay vì lao vào Code ngay lập tức dẫn đến hỏng cấu trúc, AI Agent **phải viết lộ trình kỹ thuật** vào `implementation_plan.md` cho Phase/Task chuẩn bị làm.
- Cấu trúc plan phải nêu rõ: File nào được tạo mới, file nào bị xóa, luồng dữ liệu chạy ra sao, thư viện gì được dùng.

### Bước 3: Chờ Phê Duyệt (Ask for Approval) 
- Phải dừng lại và hỏi ý kiến User: *"Kế hoạch này đã đúng ý bạn chưa? Tôi có thể tiến hành code không?"*. **NẾU USER CHƯA DUYỆT, TUYỆT ĐỐI KHÔNG SỬA ĐỔI SOURCE CODE.**
- Chủ động đặt câu hỏi cho User nếu có bất kỳ điểm mù (blind-spots) hoặc sự mâu thuẫn nào trong requirement thay vì tự ý giả định.

### Bước 4: Thực thi (Execute) & Cập nhật Context
- Sau khi được duyệt, AI tiến hành sinh code. Làm xong bước nào, chủ động mở file `task.md` đánh dấu `[x]` vào bước nấy.
- Luôn giữ `task.md` được cập nhật up-to-date như một cuốn nhật ký tiến độ dự án.

---

## 4. Đặc tả Code & Thiết kế
- **Ngôn ngữ phản hồi**: Trả lời User và viết comment trong Plan bằng Tiếng Việt (trừ khi User yêu cầu khác). Comment trong file source code có thể dùng Tiếng Anh để đảm bảo tính chuyên nghiệp quốc tế.
- **Tính trọn vẹn**: Cố gắng giải bài toán bằng cách tiếp cận sạch nhất (Clean Code), Modular (chia nhỏ module) thay vì nhồi nhét vào một file duy nhất. 
- **Thiết kế UI/UX**: Luôn ưu tiên các chuẩn thiết kế hiện đại, tránh việc tạo ra các giao diện làm qua loa.
- **Đồng bộ Tài liệu (Documentation Synchronization)**: MỖI KHI sửa đổi, thêm mới, hoặc xóa bỏ một tính năng nào đó trong mã nguồn, AI Agent có trách nhiệm BẮT BUỘC phải tự động cập nhật sự thay đổi đó vào các file tài liệu liên quan (như `README.md`, `docs/technical_reference.md`, `docs/project_scope_and_tech.md`). Không bao giờ được để code đi trước tài liệu.

---

## 5. Quy chuẩn Quản lý Mã nguồn (Enterprise Git Workflow)
Để đảm bảo các dự án rẽ nhánh và tích hợp mượt mà, AI Agent và User tuân theo chiến lược phân nhánh doanh nghiệp (ví dụ chuẩn Git Flow hoặc GitHub Flow):
- **Cấu trúc phân nhánh (Branching Scheme):**
  - `main` / `master`: Mã nguồn đưa vào triển khai (Production-ready). Trạng thái luôn hoạt động không có lỗi. Code không ĐƯỢC CHÉP THẲNG vào đây.
  - `develop`: Mã nguồn ở trạng thái thử nghiệm tích hợp tính năng. Đây là nơi code được tập trung trước khi đóng phiên bản (release).
  - `feature/<tên_tính_năng>` (VD: `feature/auth-system`): Nhánh sinh ra từ `develop` để làm tính năng độc lập. Xong sẽ có Pull Request về lại `develop`.
  - `hotfix/<tên_lỗi>` (VD: `hotfix/memory-leak`): Nhánh rẽ thẳng từ `main` nhằm cấp cứu những lỗi nghiêm trọng trên Production và vá lập tức.
- **Quy tắc Commit Message (Conventional Commits):**
  - **Dạng thức**: `loại(chủ-đề): thông điệp ngắn gọn`
  - Các tiền tố cho phép:
    - `feat:` (thêm tính năng mới).
    - `fix:` (vá lỗi).
    - `refactor:` (sửa đổi kiến trúc code, không thêm tính năng mới).
    - `docs:` (cập nhật file README, tài liệu).
    - `chore:` (các công việc dọn dẹp, update thư viện...).
- **Quy tắc Gộp mã (Pull Request):**
  - Trước khi sáp nhập tính năng mới (merge nhánh `feature` vào `develop` hoặc `main`), bắt buộc tạo một Pull Request, đính kèm giải thích sự thay đổi và thông báo cho User (Code Owner) để review.

---

## 6. Quy trình Phát triển Phần mềm Chuẩn Doanh nghiệp (Enterprise SDLC)
Để một dự án được phát triển dài hạn mà không bị "trôi mất phương hướng", dễ dàng bảo trì và mở rộng, AI Agent phải đi theo mô hình Vòng đời Phát triển Phần mềm (System Development Life Cycle) gắt gao:
1. **Thu thập và Phân tích Yêu cầu (Requirements Gathering):** Khảo sát 100% mục tiêu của User trước khi đề xuất giải pháp. Nếu User yêu cầu mập mờ, AI phải hỏi lại để làm sáng tỏ.
2. **Thiết kế Hệ thống (System Design):** Mọi dự án phải có file thiết kế (`docs/technical_reference.md` hoặc thiết kế DB Schema, API Endpoints) trước khi viết code lõi. Định hình rõ mô hình (VD: MVC, Clean Architecture).
3. **Phân rã & Lập kế hoạch (Task breakdown & Planning):** Tạo file `task.md` chia nhỏ Phase/Task. Duyệt `implementation_plan.md` cho từng Phase.
4. **Viết Code & Review (Implementation):** Tuân thủ DRY (Don't Repeat Yourself) và SOLID principles. Luôn phải thông qua bước Pull Request như đã nêu ở mục 5.
5. **Kiểm thử (Testing):** Khuyến khích viết Unit Test cho những module logic quan trọng (như bóc tách file, gọi API bên thứ 3) trước khi đưa lên Production.
6. **Phiên bản hóa & Bảo trì (Versioning & Maintenance):** Gắn thẻ phiên bản (Tags) như `v1.0.0`, `v1.1.0` theo nguyên tắc Semantic Versioning để dễ dàng truy vết và rollback khi xảy ra lỗi.

---

## 7. Quy trình Học hỏi & Ghi nhận Lỗi (Continuous Learning & Bug Tracking)
Mọi AI Agent đi sau không được lặp lại sai lầm của AI đi trước. Do đó, phải xây dựng cơ chế học hỏi liên tục khi xảy ra lỗi (Bug Learning Loop):
1. **Ghi nhận Lỗi (Knowledge Artifacts)**: Khi phát hiện và vá thành công mạng lưới lỗi (đặc biệt là lỗi cấu hình/logic do chênh lệch phiên bản), AI Agent BẮT BUỘC chép lại thông tin đó vào `docs/known_issues_and_learnings.md` (Nhật ký sửa lỗi hệ thống). Nhật ký này mang tính vĩnh cửu.
2. **Tạo Testcase Phòng ngừa**: Đi đôi với việc vá lỗi `fix: ...`, AI phải tự động đánh giá và khởi tạo các kịch bản kiểm thử (Testcase / Unit Test) để bao phủ lỗi đó, đảm bảo 100% code tương lai không làm Regression (hỏng lại lỗi cũ).
3. **Truy vấn Ngữ cảnh (Context Recall)**: Ở những đoạn tính năng tiềm ẩn rủi ro từng bị hỏng trong quá khứ, AI Agent có trách nhiệm chủ động quét ngược lại file `known_issues_and_learnings.md` để tự nhắc nhở bản thân về "vết xe đổ" và các mẹo (tricks) cài đặt độc thù của dự án.

---

## 8. Quy chuẩn Rà soát Mã Nguồn (Code Review & Quality Assurance)
Bất cứ khi nào viết, chỉnh sửa hoặc tích hợp code mới, AI Agent bắt buộc phải bật "Chế độ Rà Soát Kép" (Dual-Pass Review Mode) tự kiểm tra lại thành phẩm trước khi Push hoặc kết thúc lượt (Turn):
1. **Truy quét Edge Cases & Lỗi Cú pháp (Syntax Errors):** Không để lọt các lỗi hiển nhiên như dư/thiếu dấu phẩy, thẻ XML, hoặc lỗi import thư viện. Rà soát lại logic cho mọi ngoại lệ (null params, HTTP timeouts).
2. **Rò rỉ Bộ nhớ & Tối ưu (Memory Leaks & Starvation):** 
   - Backend: Cực kỳ thận trọng với các biến DB toàn cục, Database Sessions trong BackgroundTasks/Threads, con trỏ file chưa đóng hoặc GPU RAM khi chạy Embedding models local. Đảm bảo mọi kết nối/context đều có hàm `finally: obj.close()` hoặc dùng `with`.
   - Frontend: Rà quét các hook `useEffect` rỗng (thiếu dependency array) hoặc lắng nghe sự kiện (EventListeners), Websocket không có hàm dọn dẹp (`return () => clearInterval()`) khi component unmount.
3. **Log & Cảnh báo an toàn (Safe Fallbacks):** Mã nguồn luôn đi kèm với try-except bắt các Exception chí mạng để không sập toàn bộ Cụm Dịch vụ.

> **Xác nhận Hệ thống:** Nếu bạn là một AI Agent đính kèm vào bất kỳ repository nào chứa file này, hãy đọc file này và thiết lập hệ tư duy (System Prompt Context) tại lượt trò chuyện đầu tiên để đảm bảo mọi Request tiếp theo của bạn đều tuân thủ kiến trúc gắt gao này.
