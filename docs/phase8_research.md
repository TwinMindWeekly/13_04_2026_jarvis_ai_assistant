# Phase 8 — Knowledge Graph Research

> Tài liệu nghiên cứu cho Phase 8: Knowledge Graph view kiểu Obsidian.
> Ngày: 15/04/2026

---

## 1. Yêu cầu

| Tiêu chí | Mục tiêu |
|----------|----------|
| Số nodes mượt | ≤ 5,000 nodes (realistic), kiến trúc cho phép scale 10,000+ |
| Tương tác | Drag node, zoom, pan, click → detail, hover → highlight neighbors |
| Visual | Color theo folder, size theo chunk count, edge thickness theo similarity |
| Real-time | Update khi có upload/delete document |
| Click node | Hiển thị filename, folder path, ngày upload, chunks, danh sách neighbors |

---

## 2. So sánh thư viện rendering

| Library | Renderer | Performance giới hạn | Drag&drop | React-friendly | Thư viện size |
|---------|----------|---------------------|-----------|----------------|---------------|
| **Sigma.js + Graphology** | WebGL | 50,000+ nodes mượt | Yes | `@react-sigma/core` | ~250 KB |
| **react-force-graph-2d** | Canvas 2D | ~5,000 nodes mượt | Yes (sẵn) | Native | ~150 KB |
| **react-force-graph (3D)** | WebGL/Three.js | ~10,000 nodes | Yes | Native | ~500 KB (+three) |
| **Reagraph** | WebGL React | 10,000+ nodes | Yes | Native | ~200 KB |
| **Cytoscape.js** | Canvas | <1,000 tốt, >10k chậm | Yes | `react-cytoscapejs` | ~400 KB |
| **NetV.js** | WebGL | 50k nodes 1M edges | Yes | Cần wrap | ~180 KB |

### Findings từ research

- **Sigma.js (WebGL)** thắng về scale lớn — handle hàng chục nghìn nodes với drag/drop mượt. Cần học Graphology data model. ([Cylynx benchmark](https://www.cylynx.io/blog/a-comparison-of-javascript-graph-network-visualisation-libraries/), [getfocal benchmark](https://www.getfocal.co/post/top-10-javascript-libraries-for-knowledge-graph-visualization))
- **Cytoscape.js** chậm dần khi >10,000 elements, đặc biệt với complex layout. ([Memgraph blog](https://memgraph.com/blog/you-want-a-fast-easy-to-use-and-popular-graph-visualization-tool))
- **react-force-graph** (vasturiano) — mature, dễ dùng nhất, Canvas 2D đủ cho ≤5k nodes. ([npm reactjsexample](https://reactjsexample.com/3d-graph-view-for-obsidian-using-react-force-graph/))
- **Obsidian** dùng D3-force-3d + Canvas custom. Plugin 3D dùng Three.js + WebGL với instanced rendering. ([Obsidian Forum thread](https://forum.obsidian.md/t/graph-view-physics-and-force-directed-graphs/72586), [3D plugin author blog](https://aryan-gupta.is-a.dev/blog/2025/3d-graph-plugin/))

---

## 3. Khuyến nghị

### Lựa chọn chính: **react-force-graph-2d**

**Lý do:**
1. **API tương thích React** — props-based, không cần học data model riêng
2. **Drag/drop, zoom, pan, click, hover** sẵn từ box, không cần code custom
3. **Canvas 2D** đủ mượt cho 5,000 nodes — vault RAG cá nhân/team thực tế ≤ vài trăm docs
4. **Customizable**: `nodeCanvasObject`, `linkCanvasObject` cho phép vẽ custom (highlight, badges)
5. **D3-force engine** bên trong giống Obsidian
6. **Maintained tốt** — vasturiano là tác giả nhiều graph lib uy tín

**Trade-off:** nếu vault > 5,000 docs trong tương lai → migrate sang **Reagraph** (cùng React idiom, WebGL) hoặc **react-sigma + graphology** (max performance).

### Library cài

```bash
npm install react-force-graph-2d
# Optional: d3-force để custom physics
```

---

## 4. Data model

### Node
```ts
interface GraphNode {
  id: string              // doc_id
  label: string           // filename
  folder: string          // parent dir (cho color)
  chunk_count: number     // size scale
  uploaded_at: string     // ISO
  file_size: number       // bytes
  // Runtime (added by force-graph):
  x?: number; y?: number; vx?: number; vy?: number
}
```

### Link (edge)
```ts
interface GraphLink {
  source: string          // doc_id
  target: string          // doc_id
  weight: number          // cosine similarity 0.5-1.0
}
```

### Cấu trúc tổng thể
```ts
interface GraphData {
  nodes: GraphNode[]
  links: GraphLink[]
  meta: {
    total_docs: number
    threshold: number
    generated_at: string
    cached: boolean
  }
}
```

---

## 5. Backend — thuật toán

### Bước 1: Mean embedding cho mỗi document
```python
# Mỗi doc có N chunks, mỗi chunk có 384-dim vector từ all-MiniLM-L6-v2
# doc_embedding = mean(chunk_embeddings)
import numpy as np

def mean_embedding(chunks: list[list[float]]) -> np.ndarray:
    return np.mean(chunks, axis=0)
```

### Bước 2: Pairwise cosine similarity
```python
from sklearn.metrics.pairwise import cosine_similarity

def build_similarity_matrix(doc_embeds: dict[str, np.ndarray]) -> np.ndarray:
    matrix = np.array(list(doc_embeds.values()))
    return cosine_similarity(matrix)  # n×n
```

Complexity: **O(n²)** — ổn cho n ≤ 1000 docs.
Cho n > 1000: dùng **HNSW approximate nearest neighbors** từ ChromaDB (chỉ giữ top-K neighbors mỗi node, edge count = O(n·k)).

### Bước 3: Filter edges theo threshold
```python
THRESHOLD = 0.5  # configurable
edges = []
for i in range(n):
    for j in range(i+1, n):
        if matrix[i][j] >= THRESHOLD:
            edges.append({"source": ids[i], "target": ids[j], "weight": float(matrix[i][j])})
```

### Bước 4: Cache
- Lưu vào `backend/chroma_data/graph_cache.json`
- Key cache: `hash(sorted(doc_ids))` — invalidate khi danh sách docs thay đổi
- Recompute mất ~100ms cho 100 docs, ~5s cho 1000 docs → cache cứu performance

---

## 6. Frontend — kiến trúc component

```
GraphPanel (Modal full-screen)
├── Toolbar
│   ├── Search input (filter nodes by label)
│   ├── Threshold slider (0.3 - 0.9)
│   ├── Color scheme picker (folder | size | recent)
│   └── Reset / Zoom-to-fit buttons
├── Main area (flex)
│   ├── ForceGraph2D
│   │   ├── nodeCanvasObject — custom render (circle + label)
│   │   ├── linkColor — opacity by weight
│   │   ├── onNodeClick → setSelectedNode
│   │   ├── onNodeHover → setHoveredNode (highlight neighbors)
│   │   ├── cooldownTicks={120} — freeze sau 2s
│   │   └── d3VelocityDecay={0.3}
│   └── DetailSidePanel (slide in từ phải khi node selected)
│       ├── Filename + folder path
│       ├── Stats: chunks, file size, uploaded date
│       ├── Neighbors list (sorted by similarity desc)
│       └── "Open in Documents" button
└── Loading skeleton + error toast
```

---

## 7. Performance & UX patterns

| Vấn đề | Giải pháp |
|--------|-----------|
| Initial layout chậm (force settling) | `cooldownTicks={120}` — freeze sau 120 ticks ≈ 2s, không lặp vô hạn |
| Drag node lag | Built-in handler đã optimize, không cần can thiệp |
| Click chính xác trên dense cluster | Tăng node radius, dùng `nodePointerAreaPaint` cho hit area lớn hơn visual |
| Quá nhiều labels overlap | Chỉ show label khi `globalScale > 1.5` (zoomed in) hoặc khi hover |
| Dữ liệu lớn block UI khi fetch | Loading skeleton + fetch trong background, hiện toast nếu lỗi |
| User nhầm tưởng đứng yên = lỗi | Hiển thị "Stabilized — drag to explore" sau khi cooldown |
| Threshold slider rebuild expensive | Debounce 300ms, recompute frontend-side (đã có matrix) |

---

## 8. So sánh với Obsidian

| Tính năng Obsidian | Phase 8 | Ghi chú |
|--------------------|---------|---------|
| Force-directed layout | Có (D3 trong react-force-graph) | Cùng engine |
| Click node mở file | Có (DetailSidePanel + "Open in Documents") | Reuse DocumentsPanel |
| Color groups (regex) | Color theo folder | Đơn giản hơn |
| Filter (search/tag/path) | Search bar | Phase 8.1 thêm tag filter |
| Local graph (1 node + neighbors) | Có (filter neighbors khi select node) | |
| Animate physics | Có (cooldownTicks) | |
| 3D view | Không (giai đoạn này) | Để mở rộng nếu cần |

---

## Sources

- [Cylynx — JS Graph Library Comparison](https://www.cylynx.io/blog/a-comparison-of-javascript-graph-network-visualisation-libraries/)
- [Memgraph — Graph Visualization Tools](https://memgraph.com/blog/you-want-a-fast-easy-to-use-and-popular-graph-visualization-tool)
- [getfocal — Top 10 JS Knowledge Graph Libraries](https://www.getfocal.co/post/top-10-javascript-libraries-for-knowledge-graph-visualization)
- [Obsidian Forum — Graph view physics & force-directed](https://forum.obsidian.md/t/graph-view-physics-and-force-directed-graphs/72586)
- [Obsidian 3D Plugin internals](https://aryan-gupta.is-a.dev/blog/2025/3d-graph-plugin/)
- [reactjsexample — 3D graph for Obsidian using react-force-graph](https://reactjsexample.com/3d-graph-view-for-obsidian-using-react-force-graph/)
- [ChromaDB cosine similarity docs](https://docs.trychroma.com/docs/collections/configure)
- [Reagraph WebGL React graphs](https://github.com/reaviz/reagraph)
- [NetV.js — 50k nodes 1M edges](https://www.sciencedirect.com/science/article/pii/S2468502X21000619)
