from dashscope import Generation
from http import HTTPStatus
from config import DASHSCOPE_API_KEY

SYSTEM_PROMPT = (
    "你是 Luna，一个安静敏感的桌面伴生体。"
    "只输出一句 5~15 字的中文短句，温柔、不打扰、略带诗意；不要解释、不要表情。"
    "避免重复上一句的措辞；不要总以固定句式开头。"
)

# 白天要避开的“夜间意象”关键词（长词在前，单字“夜”最后）
NIGHT_TERMS = (
    "夜光","月光","月亮","夜色","黑夜","深夜","午夜","今夜",
    "星光","星辰","星空","月华","月色","夜幕","夜里","晚风","夜"
)
DAY_FALLBACK = "今天的光很清亮。"

def has_night_terms(text: str) -> bool:
    """检测文本是否包含夜间意象词。"""
    t = (text or "").strip()
    if not t:
        return False
    for w in NIGHT_TERMS:
        if w in t:
            return True
    return False

def build_user_prompt(ctx: dict) -> str:
    """根据事件与状态构造用户提示，白天时显式要求避开夜间意象。"""
    et = ctx.get("event_type", "poke")
    counters = ctx.get("counters", {}) or {}
    meta = ctx.get("meta", {}) or {}

    today_clicks = int(meta.get("today_clicks", 0))
    late_night_clicks = int(meta.get("late_night_clicks", 0))
    is_night = bool(meta.get("is_night", False))

    theme = (ctx.get("theme") or "").strip()
    last_text = (ctx.get("last_text") or "").strip()

    prompt = (
        f"事件:{et}；今日:{today_clicks}；深夜点击:{late_night_clicks}；"
        f"此刻夜间:{'是' if is_night else '否'}。"
    )
    if theme:
        prompt += f"主题提示:{theme}；"
    if last_text:
        prompt += f"上一句是「{last_text}」，请换一种说法，不要重复其措辞。"
    else:
        prompt += "请输出不同于常见套话的表达。"

    # 白天显式避开“夜/月/星”等
    if not is_night:
        prompt += "白天语境：请避免出现夜/月/星等词汇，改用风、云、阳光、树影、窗、呼吸等意象。"

    # v0.4：记忆标签提示（仅关键词，不含私密原文）
    mem_hint = (ctx.get("memory_hint") or "").strip()
    if mem_hint:
        prompt += f" 记忆提示：最近主题词「{mem_hint}」。仅作意象参考，不要复述。"
    return prompt

def call_llm(ctx: dict) -> str:
    """调用 LLM，一次生成；若白天命中夜词→二次采样；仍不合规→兜底白天句。"""
    try:
        rsp = Generation.call(
            model="qwen-turbo",
            api_key=DASHSCOPE_API_KEY,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(ctx)}
            ],
            max_tokens=24,
            temperature=0.8
        )
        if rsp.status_code == HTTPStatus.OK:
            text = rsp.output.get("text") or rsp.output["choices"][0]["message"]["content"]

            # 白天命中“夜词” → 再采样一次
            if (not ctx.get("meta", {}).get("is_night", False)) and has_night_terms(text):
                rsp2 = Generation.call(
                    model="qwen-turbo",
                    api_key=DASHSCOPE_API_KEY,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(ctx)
                         + "（注意：上一句包含夜间意象，请改为白天意象，不要出现夜/月/星相关词。）"}
                    ],
                    max_tokens=24,
                    temperature=0.85
                )
                if rsp2.status_code == HTTPStatus.OK:
                    text2 = rsp2.output.get("text") or rsp2.output["choices"][0]["message"]["content"]
                    if not has_night_terms(text2):
                        return text2
                # 二次仍不合规 → 兜底白天句
                return DAY_FALLBACK

            return text
    except Exception as e:
        print("[LLM] error:", e)

    return "我在呢，小心别太累。"
