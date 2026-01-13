# 文档互链审计报告（Docs Link Audit）

日期：2026-01-13

## 1. 目的

确保“权威入口文档”之间互链无断链，避免新任务入口/归档入口变化造成引用失效。

本次重点覆盖：

- `README.md`
- `docs/README.md`
- `docs/核心文档清单/*`
- `docs/TECH_SPEC.md`
- `docs/DATABASE.md`

## 2. 范围与方法

### 2.1 扫描范围

- 扫描仓库内 `*.md` 的相对链接（Markdown 格式：`[text](relative/path.md)`）。
- 排除目录：
  - `node_modules/`
  - `.venv/`
  - `.git/`
  - `dist/`、`build/`

### 2.2 扫描规则

- 忽略：
  - 以 `http(s)://` 开头的外链
  - `mailto:`
  - 仅锚点 `#...`
  - 以 `/` 开头的站点绝对路径（运行时路由，不属于仓库文件）

## 3. 扫描结论

- 结果：**0 处断链**（在排除 `node_modules/.venv` 后）。

> 说明：若包含依赖包自带 README（`node_modules`、`.venv`），会出现大量“包内相对链接在本仓库不存在”的误报，不纳入项目文档质量口径。

## 4. 任务入口与归档入口

- 当前任务入口：`TASKS.md` → `TASKS_NEXT.md`
- 历史任务快照：`docs/_archive/TASKS_2026-01-13.md`

---

## 附：复现命令（Windows）

```powershell
py -c "import os,re,sys
root=r'c:\\Users\\10256\\Desktop\\百姓助手'
exclude={'node_modules','.venv','.git','dist','build','__pycache__'}
md=[]
for dp,ds,fs in os.walk(root):
  ds[:]=[d for d in ds if d not in exclude]
  for f in fs:
    if f.lower().endswith('.md'):
      md.append(os.path.join(dp,f))
link_re=re.compile(r'\[[^\]]*\]\(([^)]+)\)')
problems=[]
for p in md:
  try: txt=open(p,'r',encoding='utf-8').read()
  except UnicodeDecodeError:
    txt=open(p,'r',encoding='utf-8-sig').read()
  for m in link_re.finditer(txt):
    u=m.group(1).strip()
    if not u or u.startswith('#') or u.startswith('mailto:') or re.match(r'^[a-zA-Z]+://',u):
      continue
    u=u.split('#',1)[0].strip()
    if not u or re.match(r'^[a-zA-Z]+://',u):
      continue
    if u.startswith('<') and u.endswith('>'):
      u=u[1:-1]
    u=u.replace('\\','/')
    if u.startswith('/'):
      continue
    ap=os.path.normpath(os.path.join(os.path.dirname(p),u))
    if not os.path.exists(ap):
      problems.append((p,u))
print('checked',len(md),'md files (excluding node_modules/.venv)')
print('broken_links',len(problems))
for p,u in problems[:200]:
  rel=os.path.relpath(p,root)
  print(rel,'->',u)
sys.exit(2 if problems else 0)"
```
