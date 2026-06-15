"""
Chat Routes - AI ChatBot API

Module này cung cấp endpoint để giao tiếp với AI ChatBot:
- POST /api/chat - Gửi tin nhắn, nhận phản hồi từ AI
"""

from flask import Blueprint, request, jsonify
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('', methods=['POST'])
def chat():
    """
    Xử lý tin nhắn từ ChatBot.
    Body: { "message": str, "coop_id": int | null }
    Response: { "reply": str, "tool_used": str | null }
    """
    data = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    coop_id = data.get('coop_id')

    if not message:
        return jsonify({"reply": "Vui lòng nhập câu hỏi.", "tool_used": None}), 400

    try:
        from chatbot import get_chatbot
        chatbot = get_chatbot()
        result = chatbot.process_message(message, coop_id=coop_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"reply": f"Lỗi máy chủ: {str(e)}", "tool_used": None}), 500
