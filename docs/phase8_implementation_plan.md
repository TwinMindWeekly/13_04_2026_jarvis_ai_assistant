# Phase 8 — Implementation Plan: Knowledge Graph

> Kế hoạch triển khai chi tiết. Đã research → xem [phase8_research.md](./phase8_research.md).
> Trạng thái: **Đề xuất** — chờ approve.

---

## Mục tiêu

Knowledge Graph view kiểu Obsidian:
- Hiển thị mọi document đã upload thành node, kết nối theo similarity
- Drag/zoom/pan/click mượt với hàng trăm-hàng ngàn nodes
- Click node → biết file thuộc folder nào, các neighbor
- Cập nhật real-time khi upload/delete

## Lựa chọn công nghệ

- **Frontend renderer**: `react-force-graph-2d` (Canvas 2D + D3-force)
- **Backend graph builder**: numpy + sklearn cosine_similarity (compute) + JSON cache file
- **Data source**: ChromaDB collection "documents" (đã có từ Phase 6) + metadata index

## Cấu trúc thư mục mới

```
backend/
  app/
    graph/
      __init__.py
      builder.py            # Build + cache graph data
      cache.py              # Cache invalidation logic
    routers/
      graph.py              # /api/graph/* endpoints
    models/
      graph_schemas.py      # Pydantic GraphData, GraphNode, GraphLink
  tests/
    test_graph_builder.py
    test_graph_router.py

frontend/
  src/
    components/
      GraphPanel.jsx        # Modal full-screen graph view
      GraphToolbar.jsx      # Search + threshold + buttons
      GraphDetailPanel.jsx  # Side panel cho node selected
      GraphLegend.jsx       # Color legend theo folder
    hooks/
      useGraph.js           # Fetch + manage selected/hovered state
    services/
      api.js                # Thêm graphAPI
  e2e/
    graph-panel.spec.js
```

## 8 bước triển khai

### Step 1 — Backend graph builder (`app/graph/builder.py`)

```python
async def build_document_graph(threshold: float = 0.5) -> GraphData:
    # 1. Lấy tất cả docs từ metadata index
    docs = load_documents_index()
    if len(docs) < 2:
        return GraphData(nodes=[...], links=[])

    # 2. Lấy chunks + embeddings từ ChromaDB
    chunks_per_doc = {doc_id: chroma.get(where={"doc_id": doc_id}) for doc_id in docs}

    # 3. Mean embedding mỗi doc
    doc_embeds = {doc_id: np.mean(embeds, axis=0) for ...}

    # 4. Cosine pairwise (sklearn)
    matrix = cosine_similarity(np.array(list(doc_embeds.values())))

    # 5. Filter edges theo threshold
    links = [{"source": ids[i], "target": ids[j], "weight": float(matrix[i][j])}
             for i in range(n) for j in range(i+1, n) if matrix[i][j] >= threshold]

    # 6. Build nodes với metadata
    nodes = [{"id": doc_id, "label": doc.filename, "folder": doc.folder, ...} for doc in docs]

    return GraphData(nodes=nodes, links=links, meta={...})
```

### Step 2 — Cache layer (`app/graph/cache.py`)

```python
CACHE_PATH = Path(settings.chroma_persist_dir) / "graph_cache.json"

def cache_key(doc_ids: list[str], threshold: float) -> str:
    return hashlib.md5(f"{sorted(doc_ids)}-{threshold}".encode()).hexdigest()

def load_cache(key: str) -> GraphData | None: ...
def save_cache(key: str, data: GraphData) -> None: ...
def invalidate_cache() -> None:
    CACHE_PATH.unlink(missing_ok=True)
```

### Step 3 — Router (`app/routers/graph.py`)

```python
@router.get("/data", response_model=GraphData)
async def get_graph(threshold: float = 0.5):
    docs = load_documents_index()
    key = cache_key(list(docs.keys()), threshold)
    cached = load_cache(key)
    if cached:
        return cached
    data = await build_document_graph(threshold)
    save_cache(key, data)
    return data

@router.get("/stats")
async def get_stats(): ...

@router.post("/rebuild")
async def rebuild(threshold: float = 0.5):
    invalidate_cache()
    return await build_document_graph(threshold)
```

### Step 4 — Cache invalidation hook (`app/routers/documents.py` patch)

```python
# Trong handler upload + delete:
from app.graph.cache import invalidate_cache
invalidate_cache()
```

### Step 5 — Frontend GraphPanel

```jsx
import ForceGraph2D from 'react-force-graph-2d'

function GraphPanel({ isOpen, onClose }) {
  const { data, loading, error, threshold, setThreshold } = useGraph()
  const [selected, setSelected] = useState(null)
  const [hovered, setHovered] = useState(null)

  const nodeColor = (node) => folderColorMap[node.folder]
  const nodeSize = (node) => Math.sqrt(node.chunk_count) * 2

  return (
    <Modal show={isOpen} onHide={onClose} fullscreen>
      <GraphToolbar threshold={threshold} onThresholdChange={setThreshold} />
      <div style={{ display: 'flex', height: '100%' }}>
        <ForceGraph2D
          graphData={data}
          nodeColor={nodeColor}
          nodeVal={nodeSize}
          linkWidth={(link) => link.weight * 3}
          linkColor={(link) =>
            hovered && (link.source.id === hovered.id || link.target.id === hovered.id)
              ? '#ffaa00' : 'rgba(255,255,255,0.2)'}
          onNodeClick={setSelected}
          onNodeHover={setHovered}
          cooldownTicks={120}
          d3VelocityDecay={0.3}
        />
        {selected && <GraphDetailPanel node={selected} onClose={() => setSelected(null)} />}
      </div>
    </Modal>
  )
}
```

### Step 6 — Detail side panel

- Hiển thị: filename, folder path, file size, uploaded date, chunks count
- "Neighbors" list — sort theo similarity desc, click → focus camera
- Button "View in Documents" — đóng GraphPanel, mở DocumentsPanel scroll tới doc

### Step 7 — Performance tuning

- `cooldownTicks={120}` — physics dừng sau 2s
- `nodeRelSize` + `nodePointerAreaPaint` cho hit area lớn hơn
- Search bar filter: dim nodes không match (giảm opacity 0.2)
- Threshold slider debounce 300ms
- Color legend ở góc dưới
- Loading skeleton centered

### Step 8 — Tests + docs

**Backend:**
- `test_graph_builder.py`:
  - Empty docs → empty graph
  - 2 similar docs → 1 edge với weight đúng
  - Threshold filter
  - Cache hit/miss

**Frontend (E2E):**
- `graph-panel.spec.js`: open panel → see canvas element

**Docs:**
- README: thêm "Knowledge Graph" vào features list
- technical_reference: section mới mô tả graph endpoints + algorithm
- known_issues: log nếu phát sinh
- task.md: mark Phase 8 done

## Dependencies

```bash
# Backend
pip install scikit-learn  # có thể đã có sẵn từ sentence-transformers

# Frontend
npm install react-force-graph-2d
```

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| O(n²) compute chậm khi >1000 docs | Cache file JSON; fallback dùng ChromaDB HNSW top-K |
| Canvas lag với >5000 nodes | Document trade-off; chuẩn bị migration path sang Reagraph (WebGL) |
| Empty vault → graph trống không UX | Empty state "Upload documents to see the graph" |
| Threshold quá cao → graph rời rạc | Default 0.5, slider 0.3-0.9, hiển thị edge count realtime |
| Mean embedding mất sắc thái doc lớn | Nếu cần: dùng max-pool hoặc TF-IDF rerank — Phase 8.1 |

## Out of scope (deferred)

- 3D view (Three.js) — Phase 8.2 nếu user yêu cầu
- Manual links (user vẽ edge tự định nghĩa) — Phase 8.3
- Tags / categories filter — Phase 8.1
- Export graph as PNG/SVG — Phase 8.1

## Acceptance criteria

- [ ] Upload 5+ documents → mở graph panel → thấy nodes + edges
- [ ] Drag node → di chuyển mượt
- [ ] Click node → side panel hiện tên file + folder + neighbors
- [ ] Hover node → connected edges đổi màu
- [ ] Threshold slider thay đổi → edges hiện/ẩn realtime
- [ ] Upload doc mới → cache invalidate → graph rebuild
- [ ] Tests pass; docs updated; PR review OK
