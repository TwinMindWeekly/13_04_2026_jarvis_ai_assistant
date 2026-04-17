# 🤖 Hướng Dẫn Xây Dựng AI Agent Có Khả Năng Tìm Kiếm Web Tự Động
> Tóm tắt từ bài viết gốc: [Data4AI - How to Build AI Agents with Autonomous Search](https://data4ai.com/blog/technical-how-tos/how-to-build-ai-agents-with-autonomous-search/)

---

## 1. Agentic Search là gì?

AI Agent với khả năng tìm kiếm **không chỉ đơn giản là chatbot tra cứu Google**.  
Nó có thể **tự suy luận → quyết định → hành động** qua nhiều bước mà không cần con người can thiệp.

Thay vì dựa vào dữ liệu huấn luyện cũ hoặc pipeline RAG tĩnh, agent có khả năng:

- Tự đặt câu truy vấn tìm kiếm phù hợp
- Chọn đúng công cụ/API (Tavily, SerpAPI, Brave, Bright Data...)
- Phân tích dữ liệu web thô từ kết quả
- Quyết định có cần tìm tiếp hay đã đủ thông tin
- Chuỗi hành động tiếp theo: tóm tắt, lưu file, kích hoạt cảnh báo...

---

## 2. Các Thành Phần Cốt Lõi

| Thành phần | Vai trò |
|---|---|
| **LLM (Não bộ)** | Hiểu prompt, lập kế hoạch, ra quyết định (Gemini, GPT-4o, Claude) |
| **Tool Calling System** | Cho phép LLM gọi công cụ bên ngoài (Search API, trình duyệt...) |
| **Memory / State** *(tuỳ chọn)* | Giúp agent nhớ ngữ cảnh qua các bước |
| **Orchestrator / Framework** | Quản lý luồng thực thi (LangGraph, CrewAI, AutoGen) |

---

## 3. Các Bước Xây Dựng Agent (Thực Hành)

> Stack sử dụng: **Gemini 2.0 Flash Lite + LangGraph + Tavily API**

### Bước 1 – Chọn LLM và Framework

```bash
pip install langgraph langchain-google-genai google-ai-generativelanguage==0.6.15
```

- **LLM**: Dùng `Gemini 2.0 Flash Lite` cho nhẹ, nhanh, rẻ.  
  Nếu cần reasoning phức tạp → dùng `GPT-4o` hoặc `Gemini Pro`.
- **Framework**: Dùng `LangGraph` để kiểm soát trạng thái và tool-calling tốt hơn LangChain cũ.

---

### Bước 2 – Tích hợp Search Tool (Tavily)

```python
from langchain_core.tools import tool
import requests

TAVILY_API_KEY = "your-tavily-api-key"

@tool
def search_tavily(query: str) -> str:
    """Search the web using Tavily and return summarized content."""
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": 5,
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json().get("answer", "No results found.")
```

> `@tool` decorator đăng ký hàm này để LLM có thể gọi trong quá trình suy luận.

---

### Bước 3 – Tạo Agent với LangGraph

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite",
    temperature=0.2,  # thấp = ổn định, ít ngẫu nhiên
)

tools = [search_tavily]
agent = create_react_agent(llm, tools)
```

> `create_react_agent()` tạo agent theo kiểu **ReAct** (Reasoning + Acting): suy nghĩ → hành động → quan sát → lặp lại.

---

### Bước 4 – Chạy thử Agent

```python
inputs = {
    "messages": [HumanMessage(content="Tìm tin tức mới nhất về các đối thủ của Nike như Adidas, New Balance và Under Armour trong tháng này.")]
}
result = agent.invoke(inputs)

print("🧠 Kết quả:")
for msg in result["messages"]:
    msg.pretty_print()
```

Agent sẽ tự động:
1. Phân tích yêu cầu
2. Gọi `search_tavily()` với truy vấn phù hợp
3. Nhận kết quả từ web
4. Trả về câu trả lời tổng hợp bằng ngôn ngữ tự nhiên

---

## 4. Bảng Chọn Công Cụ Theo Từng Giai Đoạn

### 🏗️ Orchestration (Framework)
| Tool | Điểm mạnh | Chi phí |
|---|---|---|
| **LangGraph** | Kiểm soát luồng theo bước, tốt cho logic rõ ràng | Miễn phí |
| **CrewAI** | Đa agent, phân vai (planner-executor) | Miễn phí |
| **AutoGen** | Vòng lặp chat đa agent | Miễn phí |

### 🧠 LLM
| Model | Điểm mạnh | Chi phí (~) |
|---|---|---|
| **GPT-4o** | Reasoning mạnh, hỗ trợ vision | $5–10/1M tokens |
| **Claude 3 Opus** | Reasoning tốt, nhiều lựa chọn | $15/1M tokens |
| **Gemini Flash** | Nhanh, rẻ, tốt cho task đơn giản | < $1/1M tokens |

### 🔍 Search API
| Tool | Điểm mạnh | Ghi chú |
|---|---|---|
| **Tavily** | Dễ tích hợp, trả về câu trả lời tóm tắt | Free tier + trả phí |
| **Brave Search API** | Không quảng cáo, JSON sạch + citation | ~$3/1000 queries |
| **SerpAPI** | Giả lập Google Search, trả SERP đầy đủ | $50/tháng+ |
| **Perplexity API** | Tóm tắt real-time có link nguồn | Tuỳ gói |

### 🌐 Browser Automation (nếu cần render JS)
| Tool | Dùng khi nào |
|---|---|
| **Browserbase** | Cần phiên trình duyệt đầy đủ, xử lý login |
| **Bright Data** | Cần proxy rotation, CAPTCHA solving |
| **ZenRows / Zyte** | Scraping phức tạp, JS rendering |

### 💾 Memory & RAG (nếu cần nhớ ngữ cảnh)
| Tool | Vai trò |
|---|---|
| **LlamaIndex** | Tích hợp RAG đơn giản |
| **Pinecone / Weaviate / Qdrant** | Vector DB lưu trữ bộ nhớ dài hạn |

---

## 5. Làm Agent Đáng Tin Cậy Hơn (Production-Ready)

| Thực hành | Mô tả |
|---|---|
| **Observability** | Dùng Langfuse hoặc Helicone để theo dõi từng bước quyết định |
| **Error Handling** | Xử lý timeout, API lỗi, retry logic |
| **Step Inspection** | LangGraph cho phép debug từng bước agent đã đi |
| **Guardrails** | Giới hạn số vòng lặp tìm kiếm tránh vòng lặp vô tận |
| **Prompt tuning** | Dựa vào log để cải thiện prompt theo thời gian |

---

## 6. Khi Nào Nên Dùng Loại Agent Nào?

```
Cần câu trả lời real-time / nhạy cảm về thời gian?
    → Agent với Search API (Tavily, Brave...)

Cần xử lý trang web có JavaScript, đăng nhập, CAPTCHA?
    → Agent với Browser Automation (Browserbase, Bright Data)

Cần nhớ ngữ cảnh nhiều phiên / tài liệu dài?
    → Thêm Memory + Vector DB (Pinecone, Qdrant)

Cần nhiều agent phối hợp (phân vai)?
    → CrewAI hoặc AutoGen
```

---

## 7. Tài Nguyên Thêm

- 📓 [Google Colab Notebook mẫu](https://colab.research.google.com/drive/1sk9UqEfY_Wx5EQnHEU6M69IF29CycFv8?usp=sharing)
- 📄 [Bài viết gốc Data4AI](https://data4ai.com/blog/technical-how-tos/how-to-build-ai-agents-with-autonomous-search/)
- 🔍 [So sánh 8 Search API tốt nhất](https://data4ai.com/blog/tool-comparisons/best-search-api-tools/)
- 🤖 [Đăng ký Tavily API](https://app.tavily.com/)
- 🏗️ [LangGraph Docs](https://www.langchain.com/langgraph)

---

*Tóm tắt bởi Claude · Nguồn: data4ai.com · Cập nhật: Tháng 4/2026*
