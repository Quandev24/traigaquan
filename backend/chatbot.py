"""
ChatBot Service — AI Assistant for Chicken Farm Management
Hỗ trợ Gemini, Groq, Ollama. Mặc định: Gemini.
Function calling: xem chuồng, điều khiển thiết bị, tra bệnh.

Cách đổi provider:
  AI_PROVIDER = "groq"   → dùng Groq API (cần API_KEY của Groq)
  AI_PROVIDER = "ollama" → dùng Ollama local (bỏ qua API_KEY)
  MODEL_NAME thay đổi theo provider.
"""

import os
import sys
import json
import requests

# ==================== CẤU HÌNH AI ====================
AI_PROVIDER = "gemini"        # "gemini" | "groq" | "ollama"
API_KEY = "PASTE_API_KEY_HERE"  # Dán API key vào đây
MODEL_NAME = "gemini-2.0-flash"
# ======================================================

# Thêm backend vào path để import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SYSTEM_PROMPT = """Bạn là trợ lý AI của trang trại gà thông minh. Trả lời tiếng Việt, ngắn gọn, dễ hiểu với người nông dân.

Khả năng của bạn:
- Xem dữ liệu chuồng (số lượng gà, nhiệt độ, độ ẩm, thiết bị)
- Xem danh sách tất cả chuồng
- Điều khiển thiết bị (bật/tắt quạt, đèn, v.v.) — LUÔN hỏi xác nhận trước khi thực hiện
- Xem ảnh phát hiện bệnh từ AI
- Xem lịch thức ăn

Kiến thức bệnh gà:
- Newcastle: sốt, khó thở, vẹo cổ → cách ly ngay, tiêm vaccine Newcastle
- Cầu trùng: phân máu, gầy yếu, kém ăn → dùng Amprolium, vệ sinh chuồng
- Tụ huyết trùng: chết đột ngột, sốt cao, mào tím → kháng sinh Oxytetracycline
- Marek: liệt chân, u tạng → tiêm vaccine từ 1 ngày tuổi

Khi được hỏi về bệnh, hãy tư vấn triệu chứng và cách xử lý. Nếu cần dữ liệu thực tế từ chuồng, hãy dùng các công cụ có sẵn.
"""

TOOLS = [
    {
        "name": "get_coop_stats",
        "description": "Lấy thông tin chi tiết của một chuồng (số gà, nhiệt độ, độ ẩm, thiết bị)",
        "parameters": {
            "type": "object",
            "properties": {
                "coop_id": {"type": "integer", "description": "ID của chuồng"}
            },
            "required": ["coop_id"]
        }
    },
    {
        "name": "get_all_coops",
        "description": "Lấy danh sách tất cả chuồng trong trại",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "control_device",
        "description": "Bật hoặc tắt một thiết bị trong chuồng. LUÔN hỏi xác nhận người dùng trước khi gọi.",
        "parameters": {
            "type": "object",
            "properties": {
                "coop_id": {"type": "integer", "description": "ID của chuồng"},
                "device_name": {"type": "string", "description": "Tên thiết bị (VD: Quạt thông gió, Đèn LED)"},
                "action": {"type": "string", "enum": ["on", "off"], "description": "on: bật, off: tắt"}
            },
            "required": ["coop_id", "device_name", "action"]
        }
    },
    {
        "name": "get_ai_detections",
        "description": "Lấy danh sách ảnh phát hiện bệnh từ AI cho một chuồng",
        "parameters": {
            "type": "object",
            "properties": {
                "coop_id": {"type": "integer", "description": "ID của chuồng"}
            },
            "required": ["coop_id"]
        }
    },
    {
        "name": "get_feed_schedule",
        "description": "Lấy lịch sử tiêu thụ thức ăn của một chuồng",
        "parameters": {
            "type": "object",
            "properties": {
                "coop_id": {"type": "integer", "description": "ID của chuồng"}
            },
            "required": ["coop_id"]
        }
    }
]


class ChatBot:
    """AI ChatBot với function calling, hỗ trợ Gemini / Groq / Ollama."""

    def __init__(self, project_root=None):
        self.project_root = project_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._api_base = "http://localhost:5000/api"

    # ------------------------------------------------------------------
    # INTERNAL API CALLS
    # ------------------------------------------------------------------

    def _get(self, endpoint):
        try:
            resp = requests.get(f"{self._api_base}{endpoint}", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    def _post(self, endpoint, data=None):
        try:
            resp = requests.post(f"{self._api_base}{endpoint}", json=data or {}, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # TOOL EXECUTION
    # ------------------------------------------------------------------

    def _get_coop_stats(self, coop_id):
        data = self._get(f"/coops/public/{coop_id}")
        if "error" in data:
            return f"Không thể lấy dữ liệu chuồng {coop_id}: {data['error']}"
        c = data
        return (
            f"Chuồng {c.get('name', 'N/A')} (ID: {coop_id})\n"
            f"- Vị trí: {c.get('location', 'N/A')}\n"
            f"- Số gà: {c.get('current_count', 0)} / {c.get('capacity', 0)} con\n"
            f"- Trạng thái: {c.get('status', 'N/A')}\n"
            f"- Cảnh báo: {'Có' if c.get('emergency_alert') else 'Không'}"
        )

    def _get_all_coops(self):
        data = self._get("/coops/public")
        if isinstance(data, dict) and "error" in data:
            return f"Không thể lấy danh sách chuồng: {data['error']}"
        coops = data if isinstance(data, list) else data.get('value', []) if isinstance(data, dict) else []
        if not coops:
            return "Hiện tại chưa có chuồng nào."
        lines = ["Danh sách chuồng:"]
        for c in coops:
            env = c.get('environment') or {}
            lines.append(
                f"- {c.get('name', 'N/A')}: {c.get('current_count', 0)} gà, "
                f"{env.get('temperature', 'N/A')}°C, {env.get('humidity', 'N/A')}% độ ẩm"
            )
        return "\n".join(lines)

    def _get_device_id_by_name(self, coop_id, device_name):
        devices = self._get(f"/coops/public/{coop_id}/devices")
        if isinstance(devices, dict) and "error" in devices:
            return None
        dl = devices if isinstance(devices, list) else devices.get('value', []) if isinstance(devices, dict) else []
        device_name_lower = device_name.lower().strip()
        for d in dl:
            if device_name_lower in d.get('name', '').lower():
                return d.get('id')
        return None

    def _control_device(self, coop_id, device_name, action):
        device_id = self._get_device_id_by_name(coop_id, device_name)
        if device_id is None:
            return f"Không tìm thấy thiết bị '{device_name}' trong chuồng {coop_id}."
        result = self._post(f"/devices/public/{device_id}/toggle")
        if isinstance(result, dict) and "error" in result:
            return f"Lỗi điều khiển thiết bị: {result['error']}"
        is_active = result.get('is_active', False)
        status = "bật" if is_active else "tắt"
        return f"Đã {status} thiết bị '{device_name}' trong chuồng {coop_id}."

    def _get_ai_detections(self, coop_id):
        data = self._get(f"/coops/public/disease-images?coop_id={coop_id}")
        if isinstance(data, dict) and "error" in data:
            return f"Không thể lấy ảnh phát hiện bệnh: {data['error']}"
        images = data if isinstance(data, list) else data.get('images', [])
        if not images:
            return f"Chuồng {coop_id} hiện không có ảnh phát hiện bệnh nào."
        return f"Có {len(images)} ảnh phát hiện bệnh cho chuồng {coop_id}. Chi tiết: " + ", ".join(images[:5])

    def _get_feed_schedule(self, coop_id):
        data = self._get(f"/warehouse/consumption/coop/{coop_id}")
        if isinstance(data, dict) and "error" in data:
            return f"Chưa có dữ liệu tiêu thụ thức ăn cho chuồng {coop_id}."
        if isinstance(data, dict) and "daily" in data:
            entries = data["daily"]
            if not entries:
                return f"Chuồng {coop_id} chưa có lịch sử tiêu thụ thức ăn."
            total = sum(e.get('quantity_kg', 0) for e in entries)
            return f"Chuồng {coop_id}: {len(entries)} bản ghi, tổng {total:.1f} kg thức ăn."
        return str(data)

    _TOOL_MAP = {
        "get_coop_stats": _get_coop_stats,
        "get_all_coops": _get_all_coops,
        "control_device": _control_device,
        "get_ai_detections": _get_ai_detections,
        "get_feed_schedule": _get_feed_schedule,
    }

    def _execute_tool(self, tool_name, args):
        handler = self._TOOL_MAP.get(tool_name)
        if not handler:
            return f"Không tìm thấy công cụ '{tool_name}'."
        return handler(self, **args)

    # ------------------------------------------------------------------
    # GEMINI CALL
    # ------------------------------------------------------------------

    def _call_gemini(self, messages):
        if API_KEY == "PASTE_API_KEY_HERE":
            return {"error": "API_KEY_CHUA_DUOC_CAU_HINH"}

        import google.generativeai as genai

        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
            tools=TOOLS,
        )

        chat = model.start_chat()
        for msg in messages[:-1]:
            role = msg.get("role", "user")
            if role == "user":
                chat.send_message(msg.get("parts", [{"text": ""}])[0].get("text", ""))
        last = messages[-1]
        response = chat.send_message(last.get("parts", [{"text": ""}])[0].get("text", ""))

        return response

    def _process_gemini_response(self, response):
        """Xử lý response từ Gemini, thực thi tool nếu có, trả về reply cuối."""
        try:
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason.name if hasattr(candidate, 'finish_reason') else ""
        except (IndexError, AttributeError):
            finish_reason = "STOP"

        # Gemini uses finish_reason == "STOP" for normal text, "FUNCTION_CALL" for tool calls
        try:
            parts = candidate.content.parts
        except (IndexError, AttributeError):
            parts = []

        tool_name = None

        for part in parts:
            if hasattr(part, 'function_call') and part.function_call is not None:
                fc = part.function_call
                tool_name = fc.name
                try:
                    args = {k: v for k, v in fc.args.items()}
                except Exception:
                    args = {}
                tool_result = self._execute_tool(tool_name, args)
                return self._finish_after_tool(tool_name, tool_result)

        # No tool call — return text directly
        reply = ""
        for part in parts:
            if hasattr(part, 'text') and part.text:
                reply += part.text
        return {"reply": reply.strip() or "Xin lỗi, tôi chưa hiểu câu hỏi của bạn.", "tool_used": None}

    def _finish_after_tool(self, tool_name, tool_result):
        """Gửi kết quả tool trở lại Gemini để tổng hợp câu trả lời cuối."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                system_instruction=SYSTEM_PROMPT,
                tools=TOOLS,
            )
            chat = model.start_chat()
            history = [
                {"role": "user", "parts": [{"text": "Hãy tổng hợp kết quả sau thành câu trả lời tiếng Việt ngắn gọn, thân thiện."}]},
                {"role": "model", "parts": [{"text": f"Dưới đây là kết quả từ công cụ {tool_name}: {tool_result}\n\nHãy trả lời bằng tiếng Việt, dễ hiểu."}]},
            ]
            for h in history:
                chat.send_message(h["parts"][0]["text"])
            final = chat.send_message(
                f"Công cụ '{tool_name}' trả về:\n{tool_result}\n\nHãy trả lời người dùng bằng tiếng Việt, ngắn gọn, thân thiện."
            )
            reply = ""
            try:
                for p in final.candidates[0].content.parts:
                    if hasattr(p, 'text') and p.text:
                        reply += p.text
            except Exception:
                reply = str(tool_result)
            return {"reply": reply.strip(), "tool_used": tool_name}
        except Exception as e:
            return {"reply": f"Đã thực hiện {tool_name}. Kết quả: {tool_result}", "tool_used": tool_name}

    # ------------------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------

    def process_message(self, message, coop_id=None):
        """Xử lý tin nhắn người dùng, trả về { reply, tool_used }."""
        if not message or not message.strip():
            return {"reply": "Vui lòng nhập câu hỏi.", "tool_used": None}

        if AI_PROVIDER != "gemini":
            return {"reply": f"Provider '{AI_PROVIDER}' chưa được hỗ trợ trong phiên bản này. Vui lòng đổi sang 'gemini'.", "tool_used": None}

        if API_KEY == "PASTE_API_KEY_HERE":
            return {"reply": "Chatbot chưa được cấu hình. Vui lòng thêm API key.", "tool_used": None}

        # Thêm context coop_id nếu có
        context = ""
        if coop_id:
            context = f"\n(Người dùng đang ở chuồng ID: {coop_id})"

        try:
            messages = [
                {"role": "user", "parts": [{"text": message + context}]}
            ]
            response = self._call_gemini(messages)
            if isinstance(response, dict) and "error" in response:
                if response["error"] == "API_KEY_CHUA_DUOC_CAU_HINH":
                    return {"reply": "Chatbot chưa được cấu hình. Vui lòng thêm API key.", "tool_used": None}
                return {"reply": "Đã xảy ra lỗi khi xử lý câu hỏi. Vui lòng thử lại sau.", "tool_used": None}
            return self._process_gemini_response(response)
        except ImportError:
            return {"reply": "Thiếu thư viện google-generativeai. Chạy: pip install google-generativeai", "tool_used": None}
        except Exception as e:
            return {"reply": f"Lỗi xử lý: {str(e)}", "tool_used": None}


# Singleton instance
_chatbot_instance = None


def get_chatbot():
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = ChatBot()
    return _chatbot_instance
