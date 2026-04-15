# Phase 8 — Knowledge Graph (Obsidian-style) — Tổng hợp

> **Trạng thái**: Đã merge vào `develop` ([PR #9](https://github.com/TwinMindWeekly/13_04_2026_jarvis_ai_assistant/pull/9))
> **Ngày hoàn thành**: 15/04/2026
> **Commit**: `e277198` (feat: implement Phase 8 — Knowledge Graph)

---

## 1. Mục tiêu

Hiển thị mối quan hệ giữa các tài liệu RAG dưới dạng đồ thị tương tác, tương tự Obsidian graph view. Yêu cầu cụ thể từ người dùng:

1. **Không lag** với hàng trăm – hàng ngàn node
2. **Hiệu ứng kéo thả mượt** như Obsidian
3. **Click vào node** biết file thuộc thư mục nào, các node liên kết

---

## 2. Nghiên cứu công nghệ

So sánh 5 thư viện render graph (chi tiết tại [`docs/phase8_research.md`](./docs/phase8_research.md)):

| Library | Renderer | Mượt tới | Drag/drop | React | Quyết định |
|---------|----------|----------|-----------|-------|------------|
| **react-force-graph-2d** | Canvas 2D + D3-force | ~5 000 nodes | Sẵn | Native | ⭐ **Chọn** |
| Reagraph | WebGL React | 10 000+ | Sẵn | Native | Dự phòng scale |
| Sigma.js + Graphology | WebGL | 50 000+ | Sẵn | qua `@react-sigma/core` | Max performance |
| Cytoscape.js | Canvas | < 1 000 tốt | Sẵn | Có wrapper | Không chọn |
| NetV.js | WebGL | 50k / 1M edges | Sẵn | Cần wrap | Không chọn |

**Lý do chọn `react-force-graph-2d`:**
- Cùng **D3-force engine** với Obsidian → hiệu ứng kéo thả y hệt
- API **React idiomatic** — props-based, không cần học data model riêng
- **Drag / zoom / pan / click / hover sẵn** từ box
- Canvas 2D đủ mượt cho **5 000 nodes** — vault RAG cá nhân/team thực tế chỉ vài trăm docs
- Tác giả vasturiano là maintainer uy tín trong graph visualization ecosystem
- **Migration path** sang Reagraph (WebGL) nếu sau này > 5 000 docs

**Nguồn tham khảo:**
- [Cylynx — JS Graph Library Comparison](https://www.cylynx.io/blog/a-comparison-of-javascript-graph-network-visualisation-libraries/)
- [Memgraph — Fast/Easy/Popular: Pick Two](https://memgraph.com/blog/you-want-a-fast-easy-to-use-and-popular-graph-visualization-tool)
- [getfocal — Top 10 JS Knowledge Graph Libraries](https://www.getfocal.co/post/top-10-javascript-libraries-for-knowledge-graph-visualization)
- [Obsidian Forum — Graph view physics](https://forum.obsidian.md/t/graph-view-physics-and-force-directed-graphs/72586)
- [ChromaDB cosine similarity docs](https://docs.trychroma.com/docs/collections/configure)

---

## 3. Kiến trúc

```
Frontend (React 19 + Vite 8)
├── GraphPanel          ← Modal full-screen với ForceGraph2D
├── GraphToolbar        ← search, threshold slider, zoom-to-fit, rebuild
├── GraphDetailPanel    ← side panel khi click node
├── GraphLegend         ← color map folders
└── useGraph (hook)     ← fetch + state + debounce

       │ HTTP GET/POST /api/graph/*
       ▼
Backend (FastAPI)
├── routers/graph.py    ← 3 endpoints
└── graph/
    ├── builder.py      ← compute graph từ ChromaDB
    └── cache.py        ← JSON file cache

       │
       ▼
ChromaDB (persistent)
└── Collection "jarvis_default"
    └── Chunks + embeddings (all-MiniLM-L6-v2, 384-dim)
```

---

## 4. Thuật toán build graph

```python
# app/graph/builder.py

# Bước 1: Load danh sách docs từ metadata index
docs = load_documents_index()  # JSON: [{id, filename, chunks_count, ...}]

# Bước 2: Fetch tất cả chunks + embeddings từ ChromaDB (1 lần gọi)
result = collection.get(include=["embeddings", "metadatas"])

# Bước 3: Group chunk embeddings theo doc_id
per_doc = {doc_id: [chunk_embedding, ...], ...}

# Bước 4: Mean embedding mỗi doc (384-dim vector đại diện cả doc)
doc_vectors = [np.mean(per_doc[d], axis=0) for d in doc_ids]

# Bước 5: Cosine pairwise
similarity = normalized_vectors @ normalized_vectors.T  # O(n²)

# Bước 6: Filter edges theo threshold (upper triangle)
edges = [(i, j, w) for i < j if similarity[i][j] >= threshold]
```

**Complexity**: O(n²) với n = số docs. Ổn cho n ≤ 1 000. Nếu scale > 1 000: dùng ChromaDB HNSW nearest-neighbor (top-K per doc) → O(n·k·log n).

**Cache**:
- Key = `md5(sorted(doc_ids) + threshold)`
- Lưu JSON file `backend/chroma_data/graph_cache.json`
- Invalidate tự động khi upload / delete document

---

## 5. API endpoints

| Endpoint | Method | Params | Mục đích |
|----------|--------|--------|----------|
| `/api/graph/data` | GET | `threshold=0.5`, `force=false` | Trả graph data (cache-first) |
| `/api/graph/stats` | GET | — | Chỉ counts (không compute) |
| `/api/graph/rebuild` | POST | `threshold=0.5` | Invalidate + recompute |

**Response mẫu `/api/graph/data`:**
```json
{
  "nodes": [
    {
      "id": "1fb44990-0598-4597-9e06-ac89822205f0",
      "label": "FullGuidetounderstandOdoo.pdf",
      "folder": "",
      "chunks_count": 19,
      "size_bytes": 378214,
      "uploaded_at": "2026-04-15T06:51:14",
      "file_ext": ".pdf"
    }
  ],
  "links": [
    { "source": "uuid1", "target": "uuid2", "weight": 0.82 }
  ],
  "meta": {
    "total_docs": 10,
    "total_links": 24,
    "threshold": 0.5,
    "generated_at": "2026-04-15T09:00:00+00:00",
    "cached": true
  }
}
```

---

## 6. Tương tác UI

| Hành động | Kết quả |
|-----------|---------|
| Mở Knowledge Graph | Click icon Network trong sidebar → modal full-screen mở |
| Drag node | Di chuyển tự do, spring-back tự nhiên (D3-force) |
| Zoom | Scroll wheel / pinch |
| Pan | Drag nền |
| Hover node | Node + neighbors có ring cam, edges nối đổi màu cam |
| Click node | Ring vàng; side panel phải hiện filename / folder / size / chunks / neighbors |
| Click neighbor trong side panel | Camera focus tới neighbor đó |
| Nhập search text | Node không match bị dim opacity 0.15 |
| Kéo threshold slider | Debounce 300ms → refetch edges |
| Nút "Fit" | `zoomToFit(400ms, padding=60px)` |
| Nút "Rebuild" | Invalidate cache + recompute |
| Click nền | Clear selection |
| Esc / close button | Đóng modal |

---

## 7. Tối ưu hiệu năng

| Vấn đề | Giải pháp |
|--------|-----------|
| Force simulation chạy mãi không dừng | `cooldownTicks={120}` → physics dừng sau ~2 s |
| Click chính xác trên cluster dày | `nodePointerAreaPaint` — hit area **lớn hơn visual** |
| Ngàn label đè lên nhau khi zoomed out | Label chỉ render khi `globalScale > 1.3` HOẶC node đang hover/select |
| Slider kéo nhanh → spam API | Debounce 300 ms trong `useGraph` hook |
| Layout lag khi fetch data lớn | Loading spinner overlay, canvas sẽ render khi data ready |
| Recompute mỗi request tốn 100ms-5s | JSON cache file, invalidate chỉ khi upload/delete |
| Empty state không rõ ràng | Message "Upload at least 2 documents to see the knowledge graph" |

---

## 8. Files mới / sửa

### Backend (6 files new, 2 modified)
```
backend/app/graph/
├── __init__.py             (new)  — public exports
├── builder.py              (new)  — compute graph algorithm
└── cache.py                (new)  — JSON cache layer

backend/app/models/graph_schemas.py  (new)  — Pydantic schemas
backend/app/routers/graph.py         (new)  — 3 endpoints
backend/tests/test_graph.py          (new)  — 12 unit tests

backend/app/main.py                  (modified) — register graph_router
backend/app/routers/documents.py     (modified) — invalidate cache hook
```

### Frontend (5 files new, 4 modified)
```
frontend/src/components/
├── GraphPanel.jsx          (new)  — main component
├── GraphToolbar.jsx        (new)  — toolbar
├── GraphDetailPanel.jsx    (new)  — side panel
└── GraphLegend.jsx         (new)  — legend

frontend/src/hooks/useGraph.js       (new)  — state + fetch
frontend/e2e/graph-panel.spec.js     (new)  — E2E test

frontend/src/App.jsx                 (modified) — wire GraphPanel
frontend/src/components/Sidebar.jsx  (modified) — thêm nav item
frontend/src/services/api.js         (modified) — graphAPI
frontend/src/i18n/{en,vi}.json       (modified) — 17 keys
```

### Docs (3 new, 2 modified)
```
docs/phase8_research.md               (new)
docs/phase8_implementation_plan.md    (new)
PHASE_8_SUMMARY.md                    (new, root)

README.md                             (modified) — thêm Knowledge Graph
docs/technical_reference.md           (modified) — 3 graph endpoints
task.md                               (modified) — Phase 8 marked done
```

---

## 9. Kiểm thử

**Backend**: 12 unit tests mới
- Cosine similarity helpers (identical / orthogonal / zero vector handling)
- Folder parsing
- Cache key determinism, roundtrip, miss-on-wrong-key
- Builder edge cases (empty / single doc)
- Stats count chunks

**Kết quả**: `pytest -q` → **139 passed in 8.86s** (127 cũ + 12 mới)

**E2E**: Playwright test mở graph panel, verify toolbar + canvas/empty state

**Build**: `npm run build` → 836 KB JS (266 KB gzipped) — OK

---

## 10. Acceptance criteria — trả lời yêu cầu ban đầu

| Yêu cầu | Giải pháp | Tình trạng |
|---------|-----------|------------|
| Không lag với hàng trăm – hàng ngàn node | Canvas 2D + cooldownTicks + label culling + debounce slider → mượt 5 000 nodes | Đạt |
| Hiệu ứng kéo thả mượt như Obsidian | react-force-graph-2d dùng cùng D3-force engine của Obsidian → pin-on-drag + spring-back giống hệt | Đạt |
| Click node biết file ở thư mục nào | GraphDetailPanel hiện folder path (từ `_folder_of` parser) | Đạt |
| Click node biết các liên kết | Neighbors list sorted theo similarity desc, click neighbor → camera focus | Đạt |

---

## 11. Out of scope (để lại cho tương lai)

- **3D view** (Three.js + WebGL) — Phase 8.2 nếu user yêu cầu
- **Manual links** (user vẽ edge tự định nghĩa) — Phase 8.3
- **Tags / categories filter** — Phase 8.1
- **Export graph as PNG / SVG** — Phase 8.1
- **Timeline scrubber** (xem graph ở các mốc thời gian) — Phase 8.4

---

## 12. Hệ quả / Bài học

**Mang sang project sau:**
- **react-force-graph-2d** là lựa chọn mặc định tốt cho graph visualization ≤ 5k nodes. API đơn giản, customizable, performance ổn.
- **Pattern "mean embedding per doc"**: cách đơn giản nhất để convert chunk-level embeddings → doc-level similarity. Có thể mất sắc thái với doc lớn — workaround: max-pooling hoặc TF-IDF rerank (deferred).
- **JSON cache cho expensive compute**: key = hash(inputs), invalidate on mutation hook. Áp dụng được cho bất kỳ O(n²) compute nào trong REST backend.
- **Debounce + force-refetch UX**: threshold slider debounce 300ms là đủ cho mắt người không thấy jank.

**Sai sót nhỏ (đã fix):**
- `datetime.utcnow()` deprecated trong Python 3.13 → chuyển `datetime.now(timezone.utc)` ngay trong commit Phase 8.

---

**Links:**
- [PR #9](https://github.com/TwinMindWeekly/13_04_2026_jarvis_ai_assistant/pull/9) — merged 2026-04-15
- [Research doc](./docs/phase8_research.md)
- [Implementation plan](./docs/phase8_implementation_plan.md)
- [Technical reference — graph endpoints](./docs/technical_reference.md#6-endpoints-knowledge-graph)
