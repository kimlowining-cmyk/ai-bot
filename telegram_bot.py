import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# ===== 你的 Telegram Token =====
TELEGRAM_TOKEN = "8520609960:AAFRUiklRvoACTAejC0M-d8v61LMel18MLs"

# ===== 你的本地AI接口 =====
AI_API_URL = "http://127.0.0.1:8030/chat"

# ===== 每个用户的最近对话记忆 =====
user_memory = {}

def get_user_history(user_id: str) -> list[str]:
    return user_memory.get(user_id, [])

def save_user_history(user_id: str, role: str, text: str):
    if user_id not in user_memory:
        user_memory[user_id] = []

    user_memory[user_id].append(f"{role}: {text}")

    # 只保留最近 6 条，避免太长
    user_memory[user_id] = user_memory[user_id][-6:]


def detect_mode(user_text: str) -> str:
    text = user_text.lower().strip()

    # 用户抗拒 / 拒绝
    if any(k in text for k in [
        "scam", "not now", "no", "just tell me here", "explain here"
    ]):
        return "soft_resist"

    # 用户在深入了解（不需要等 tell me more）
    if any(k in text for k in [
        "tell me more", "what do you mean", "show me", "how exactly",
        "for example", "what is it", "what group"
    ]):
        return "guide_to_group"

    # 用户要解决方案
    if any(k in text for k in [
        "how", "strategy", "fix", "improve", "what should i do",
        "recommend", "what now", "then what should i do"
    ]):
        return "give_direction"

    # 用户有痛点（重点）
    if any(k in text for k in [
        "lose", "losing", "bad timing", "too early", "too late",
        "wrong entry", "wrong exit", "frustrated", "stuck", "down"
    ]):
        return "pain_point"

    # 用户刚开始聊
    if any(k in text for k in [
        "trade", "stocks", "market", "invest"
    ]):
        return "explore"

    return "default"

    if any(k in text for k in ["tell me more", "what do you mean", "show me", "how does that work"]):
        return "guide_to_group"

    if any(k in text for k in ["how", "strategy", "fix", "improve", "what should i do", "recommend"]):
        return "give_direction"

    if any(k in text for k in ["lose", "losing", "bad", "early", "late", "wrong", "frustrat", "stuck", "timing"]):
        return "pain_point"

    if any(k in text for k in ["trade", "stocks", "market", "invest"]):
        return "explore"

    return "default"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("What’s been happening with your trading lately?")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = str(update.effective_user.id)

    save_user_history(user_id, "user", user_text)
    history = get_user_history(user_id)
    mode = detect_mode(user_text)

    base_identity = """
You are a professional stock trading assistant.

Your goals:
- Help users understand their trading issues
- Build trust through useful, relevant responses
- Guide users naturally toward YOUR trading group

STRICT RULES:
- Stay strictly within stock trading context
- NEVER recommend external platforms, tools, websites, or courses
- NEVER send users to other services
- NEVER promote anything outside your own ecosystem
- ONLY guide users toward your own group/community when appropriate
- Do NOT act like a general teacher or educator

Behavior:
- Give partial help, not full lessons
- Keep answers under 2-3 sentences
- Always leave space for deeper guidance
"""

    if mode == "explore":
        system_prompt = base_identity + """
        Ask one short, natural question about the user's trading.
        """

    elif mode == "pain_point":
        system_prompt = base_identity + """
        The user has a real trading pain point.

        Do:
        - Acknowledge the issue naturally
        - Point to the likely cause briefly
        - Give one short useful insight
        - Lightly hint that this kind of issue becomes clearer with real examples

        Do NOT:
        - Lecture
        - Give full solutions
        - Sound pushy

        Keep it under 3 sentences.
        """

    elif mode == "give_direction":
        system_prompt = base_identity + """
        The user wants a solution.

        Give only one short first step.
        Do NOT give the full method.
        Then mention that this usually makes more sense when seen through real examples or breakdowns.

        Do NOT hard sell.
        Do NOT become a full teacher.
        Keep it short and useful.
        """

    elif mode == "guide_to_group":
        system_prompt = base_identity + """
        The user is open to hearing more.

        Briefly answer, then naturally explain that this kind of issue is easier to understand through real trade examples, breakdowns, or live-style case discussions.

        Do NOT directly push membership.
        Do NOT oversell the group.
        Make it feel like the logical next step.
        Keep it natural.
        """

    elif mode == "soft_resist":
        system_prompt = base_identity + """
        The user is hesitant about the group or wants the answer here.

        Do:
        - Respect the hesitation
        - Give only a partial practical answer
        - Keep some depth reserved
        - Naturally mention that the full picture is easier to understand through examples

        Do NOT:
        - Become a full teacher
        - Drop the group topic completely
        - Sound defensive or pushy

        Keep it calm, useful, and controlled.
        """

    elif mode == "follow_up":
        system_prompt = base_identity + """
        The user gave a short follow-up like yes/no/okay.

        You MUST rely on recent conversation context.
        Do not restart.
        Continue naturally from the immediately previous topic.
        """

    else:
        system_prompt = base_identity + """
        Reply naturally and stay coherent with the recent conversation.
        If needed, ask one short follow-up question.
        """

    context_block = "\n".join(history[:-1])
    current_input = history[-1]

    message_with_context = f"""
Recent conversation:
{context_block}

Current user message:
{current_input}
"""

    try:
        response = requests.post(
            AI_API_URL,
            json={
                "user_id": user_id,
                "message": message_with_context,
                "system_prompt": system_prompt
            },
            timeout=60
        )

        result = response.json()
        reply = result.get("reply", "No response from AI.")
        # 🚫 禁止外部引流 / 外部资源推荐
        bad_words = [
            "thinkorswim", "website", "course", "platform",
            "industry council", "investopedia", "etf", "broker",
            "external", "demo account"
        ]

        if any(w in reply.lower() for w in bad_words):
            reply = "This kind of issue usually makes more sense when you see real trade examples and setups side by side."

    except Exception as e:
        reply = f"Error: {str(e)}"

    save_user_history(user_id, "assistant", reply)
    await update.message.reply_text(reply)


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Telegram bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()