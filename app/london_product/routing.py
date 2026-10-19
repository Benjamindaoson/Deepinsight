"""Fast, transparent intent router; it never acquires external data itself."""
import re

LOOKUP = re.compile(r'租金|空置|可租|成交|take.?up|rent|vacan|availab|leasing|利率|就业|通胀|interest|employment|inflation|规划|项目|事件|新闻|planning|event|news|supply|供应|来源|证据|source|evidence|epc|能效|esg', re.I)
ANALYSIS = re.compile(r'为什么|原因|风险|机会|分析|预测|展望|建议|解读|影响|趋势|变化|生成.*报告|写.*报告|why\b|risk|opportunit|forecast|outlook|analys|interpret|recommend|trend|\bchanges\b|what changed|generate.*report', re.I)
LOOKUP_VERB = re.compile(r'查看|显示|列出|查找|查询|多少|最新|比较|对比|数据|记录|状态|show|list|find|lookup|what is|latest|compare|data|record|status', re.I)


def request_action(question, has_context=False):
    """Classify explicit operations before model selection; ambiguity stays with the Agent."""
    if re.search(r'\baudit\b|\bverify\b.*(?:figures|claims|sources|evidence)|核查|审计', question, re.I):
        return 'evidence_audit'
    if re.search(r'\b(?:monitor|alert)\b',question,re.I) and re.search(r'\d+(?:\.\d+)?\s*%|threshold|exceeds',question,re.I):
        return 'monitor_rule'
    if re.search(r'\b(?:schedule|scheduled)\b|定时|调度', question, re.I) and re.search(r'create|set up|enable|daily|every|at \d|创建',question,re.I):
        return 'schedule_request'
    if re.search(r'\b(?:monitoring|monitor|job|scheduled run)\b|监测任务', question, re.I):
        return 'monitoring_status'
    if re.search(r'guaranteed|will certainly|certain.*20\d{2}|保证|确定.*20\d{2}',question,re.I):
        return 'future_uncertainty'
    if re.search(r'cake|recipe|football|weather|食谱|蛋糕',question,re.I):return 'out_of_domain'
    if re.search(r'private.*(?:email|contact)|tenant.*email',question,re.I):return 'private_contact'
    if re.search(r'\brents?\b|租金',question,re.I) and not re.search(r'prime|grade|face|effective|asking|achieved|trend|source|compare|report|briefing|20\d{2}|最新|\blatest\b',question,re.I):
        return 'clarification'
    if re.search(r'\b(?:new|prepare|generate|create|write|replacement)\b.*\b(?:report|briefing)\b|生成.*报告|新.*报告', question, re.I):
        return 'new_report'
    if has_context and re.search(r'how does that compare',question,re.I):return 'data_question'
    if has_context and re.search(r'what about|那.*呢',question,re.I):return 'follow_up'
    if re.search(r'previous (?:report|answer)|this source|pending review|what is missing|evidence (?:for|behind|supporting)|上一.*(?:报告|回答)',question,re.I):
        return 'follow_up'
    if not ANALYSIS.search(question) and LOOKUP.search(question) and re.search(r'what|show|which|latest|多少|最新|查看',question,re.I):
        return 'data_question'
    if has_context and re.search(r'\b(?:why|explain|what about|which source|what is the evidence)\b',question,re.I):
        return 'follow_up'
    return 'model_analysis'


def positive_metric_text(question):
    """Negated restrictions constrain scope; their keywords cannot add metrics."""
    return re.sub(r"\b(?:do not|don't|never)\s+(?:substitute|use|replace|include)\b[^.!?\n]*",'',question,flags=re.I)


def route_question(question: str) -> dict:
    """Use local snapshots for bounded lookups; reserve AI for interpretation.

    Unknown questions use the existing Agent, where retrieval and publication
    guards apply. A user-selected explicit mode bypasses this router.
    """
    if ANALYSIS.search(question):
        return dict(mode='agent', reason='interpretation_requested')
    if LOOKUP.search(question) or LOOKUP_VERB.search(question):
        return dict(mode='saved', reason='saved_data_lookup')
    return dict(mode='agent', reason='unclassified_question')
