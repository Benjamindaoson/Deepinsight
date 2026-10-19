"""Read-only Skill package inspection. No imports from the model or data runtime."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

SKILLS_ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ('Capabilities','Input','Workflow','Quick Start','Output','Examples',
            'Safety Mechanisms','Dependencies','Runtime Integration')


def inspect_registry(root: Path = SKILLS_ROOT) -> dict:
    """Validate documents and relative links without executing their contents."""
    skills = []
    seen = set()
    for path in sorted(root.glob('*/SKILL.md')):
        text = path.read_text(encoding='utf-8')
        issues = []
        metadata = {}
        parts = text.split('---\n',2)
        if not text.startswith('---\n') or len(parts) != 3:
            issues.append('missing or incomplete YAML frontmatter')
        else:
            for line in parts[1].splitlines():
                if ':' in line:
                    key,value = line.split(':',1)
                    metadata[key.strip()] = value.strip().strip('"\'')
        name = metadata.get('name','')
        description = metadata.get('description','')
        if name != path.parent.name or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
            issues.append('name must match the Skill directory in kebab-case')
        if name in seen:issues.append('duplicate name')
        seen.add(name)
        if not description:issues.append('missing description')
        if not any(trigger in description for trigger in ('Use when','Triggered when')):
            issues.append('description lacks explicit trigger conditions')
        if len(description)>1024:issues.append('description exceeds 1024 characters')
        for title in REQUIRED:
            if '\n## '+title+'\n' not in text:issues.append('missing section: '+title)
        reference=path.parent/'references/runtime-contract.md'
        if not reference.is_file():
            issues.append('missing Agno-loadable reference: references/runtime-contract.md')
        else:
            master=root/'references/runtime-contract.md'
            if master.is_file():
                expected=master.read_text(encoding='utf-8').replace('](../../london_product/','](../../../london_product/')
                if reference.read_text(encoding='utf-8')!=expected:
                    issues.append('Skill-local runtime reference is out of sync with shared source')
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
            if re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'):continue
            local=target.split('#',1)[0]
            if local and not (path.parent/local).is_file():issues.append('missing local reference: '+target)
        for example in re.findall(r'```json\s*\n(.*?)\n```',text,re.S):
            try:json.loads(example)
            except json.JSONDecodeError:issues.append('invalid JSON example')
        skills.append(dict(name=name,description=description,file=path.relative_to(root).as_posix(),issues=issues))
    return dict(valid=bool(skills) and not any(x['issues'] for x in skills),count=len(skills),skills=skills)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('list',help='List names, descriptions and file locations as JSON')
    commands.add_parser('check',help='Check authoring contracts, local links and JSON examples')
    show=commands.add_parser('show',help='Print one existing Skill without executing it')
    show.add_argument('name')
    args=parser.parse_args(argv)
    result=inspect_registry()
    if args.command=='show':
        skill=next((item for item in result['skills'] if item['name']==args.name),None)
        if skill is None:
            print('Unknown Skill: '+args.name,file=sys.stderr);return 2
        print((SKILLS_ROOT/skill['file']).read_text(encoding='utf-8'));return 0
    if args.command=='list':
        result=dict(count=result['count'],skills=[{k:v for k,v in x.items() if k!='issues'} for x in result['skills']])
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if args.command=='list' or result['valid'] else 1


if __name__=='__main__':
    # Keep Chinese descriptions usable in ordinary Windows terminals.
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
