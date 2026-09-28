import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.agent_service import AgentService

import asyncio

async def test_multiturn():
    service = AgentService()
    history = []
    
    turns = [
        "Tôi muốn làm thủ tục cấp sổ đỏ lần đầu",
        "Thế nộp ở đâu?",
        "Lệ phí bao nhiêu và thời hạn bao lâu?",
        "Cần chuẩn bị những giấy tờ gì?"
    ]
    
    print("=" * 60)
    print("RUNNING MULTI-TURN CONVERSATION & REASONING TEST")
    print("=" * 60)
    
    for i, user_msg in enumerate(turns, 1):
        print(f"\n--- [TURN {i}] USER: {user_msg} ---")
        
        # Test contextualize_query
        enriched_query, topic = service.contextualize_query(user_msg, history)
        print(f"-> Enriched Query: {enriched_query}")
        print(f"-> Extracted Topic: {topic}")
        
        # Generate Answer
        answer, sources = await service.generate_answer(user_msg, history=history, session_id="test_session_1")
        
        print(f"-> Answer Preview:\n{answer[:400]}...")
        print(f"-> Sources: {sources}")
        
        # Update history
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": answer})
        
    print("\n" + "=" * 60)
    print("TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_multiturn())
