"""Build a PROVISIONAL data-review worksheet from unchanged raw model evidence.
Never impersonates a human sign-off or changes the frozen gold.
"""
import json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from london_data.extraction import ROOT
from london_data.documents import parse_document
from london_data.contracts import materialize
from london_data.validation import validate

directory=ROOT/'b1/evidence/evaluations/frozen-03'
gold=json.loads((directory/'gold-provisional.json').read_text(encoding='utf8'))
registry=json.loads((directory/'source-registry.json').read_text(encoding='utf8'))
rows=['# B1 事实复核工作表（待人工签收）','','执行者：Codex。最终审阅者：项目负责人本人（用户已指定）。状态：pending_review，不能作为人工金标准已签收的证明。',
      '数值来自本地官方快照；以下引用为逐字抽取定位和代码核对，尚未由项目负责人或指定人员签收。',
      '本表不改变 gold-provisional.json，不修正模型原始候选；租金缺少时间分母。','']
result={'status':'pending_review','original_gold_status':gold['status'],'reviewer':'project owner (user)','signed_at':None,'documents':[]}
for key,entry in registry['documents'].items():
    content=Path(entry['file']).read_bytes();sha=hashlib.sha256(content).hexdigest()
    assert sha==gold['documents'][key]['sha256']
    segs=parse_document(content,'application/pdf' if entry['file'].endswith('.pdf') else 'text/html')
    raw=json.loads((ROOT/'b1/evidence/extractions'/('eval-frozen-03-'+key+'-r1.json')).read_text(encoding='utf8'))
    facts=[validate(o,segs,registry['profile'].get('definitions'),registry['profile'],entry['period']) for o in materialize(raw['raw_output']).model_dump(mode='json')['observations']]
    result['documents'].append(dict(key=key,source=entry,sha256=sha,facts=facts))
    rows += ['## '+key,'',f"- 来源：{entry['url']}",f"- 本地原件：{entry['file']}",f'- SHA-256：{sha}',f"- 发布：{entry['published_at']}；季度：{entry['period']}；用途：{entry['role']}（执行后已暴露，不能再作为新版未见留出集）",'']
    for f in facts:
        rows += [f"### {f['metric']} / {f['geography']}",f"值：{f['value']}；单位：{f['unit']}；披露增量：{f['precision']}；状态：{f['status']}",f"定义：{f['definition']}；物业档次：{f['grade']}；统计方法标识：{f['method']}；期间基础：{f['basis']}",f"位置：{f['evidence']['segment_id']}，页 {f['evidence'].get('page')}，规范化文本偏移 {f['evidence'].get('offset')}",'> '+f['evidence']['quote'],f"校验说明：{f['validation_errors']}",'人工结论：待填写；审阅者：待填写；签收时间：待填写。','']
rows += ['## 出版物差异与禁止推断','','Q2 2026 官方叙述的 take-up 增长 26% 与披露的 2.5m→3.0m 不相等；代码只计算披露端点的 20%。空置率两个端点均为四舍五入后的 8.4%，不能复原文中所说 2bps 下降。','Q4 2024 HTML 和 PDF 端点披露精度不同，本评测绑定 PDF（9.71%、3.05m），不混用 HTML 舍入值。','City prime rent 不等同于 premium、平均成交租金或整个 Central London。£/sq ft 不能自动填入 year。']
(ROOT/'b1/docs/FACT_REVIEW.md').write_text('\n'.join(rows),encoding='utf8')
(ROOT/'b1/data/fact-review-provisional.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('Created provisional review worksheet for 12 opportunities; human review pending.')
