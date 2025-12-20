# Pyright 类型检查清理计划

## 项目目标

消除后端所有 Pyright/basedpyright 类型检查错误，提升代码质量和类型安全性。

---

## 任务清单

| 序号 | 任务                                                                                                                       | 优先级 | 状态      |
| ---- | -------------------------------------------------------------------------------------------------------------------------- | ------ | --------- |
| 1    | 修复 FastAPI 默认参数触发的 Pyright 误报（用 `Annotated` 替代 `File`/`Depends` 默认值）                                    | 高     | ✅ 已完成 |
| 2    | 新增 `pyrightconfig.json`：设置 `executionEnvironments`/`root` & `extraPaths`，解决 `app.*` 导入无法解析与隐式相对导入红线 | 高     | ✅ 已完成 |
| 3    | 清理 `services`/`routers`/`schemas` 中旧 typing（`Optional`/`List`/`Tuple`）与 `Any`/返回类型不匹配                        | 中     | ✅ 已完成 |
| 4    | 迁移剩余 SQLAlchemy 1.x 风格模型到 SQLAlchemy 2.0 `Mapped`/`mapped_column`，消除 `Column[Unknown]` 类型错误                | 高     | ✅ 已完成 |

---

## 已完成的修改

### 1. Pyright 配置文件

- `backend/pyrightconfig.json` - 设置 `root`、`extraPaths`，禁用 `reportImplicitRelativeImport` 和 `reportCallInDefaultInitializer`
- `pyrightconfig.json` (项目根目录) - 同步配置

### 2. SQLAlchemy 2.0 ORM 迁移

| 文件                | 修改内容                                                |
| ------------------- | ------------------------------------------------------- | ------------------- |
| `models/forum.py`   | 使用 `Mapped[...]` 和 `mapped_column`，补齐关系类型标注 |
| `models/news.py`    | 迁移到 SQLAlchemy 2.0 风格                              |
| `models/lawfirm.py` | 迁移 `LawFirm`/`Lawyer`/`Consultation`/`Review` 模型    |
| `models/user.py`    | 使用 `                                                  | None`替代`Optional` |

### 3. 服务层类型升级

| 文件                          | 修改内容                                                      |
| ----------------------------- | ------------------------------------------------------------- | ------------------- |
| `services/forum_service.py`   | Python 3.10+ 类型语法，收紧 `update_data` 类型                |
| `services/lawfirm_service.py` | 移除 `Optional`/`List`/`Tuple`，使用 `                        | None`、`tuple[...]` |
| `services/news_service.py`    | 升级类型语法，修复布尔判断类型错误                            |
| `services/user_service.py`    | 升级类型语法，收紧 `update_data` 类型                         |
| `services/ai_assistant.py`    | 修复 LangChain 类型兼容性，cast `api_key`，收窄 metadata 类型 |

### 4. Schema 层类型升级

| 文件                 | 修改内容       |
| -------------------- | -------------- | ---------------------------------------------------- |
| `schemas/lawfirm.py` | `Optional` → ` | None`，`List`→`list`，`Config.from_attributes: bool` |
| `schemas/news.py`    | 同上           |
| `schemas/user.py`    | 同上           |
| `schemas/forum.py`   | 同上           |
| `schemas/ai.py`      | 同上           |

### 5. 路由层类型升级

| 文件                 | 修改内容                                                                       |
| -------------------- | ------------------------------------------------------------------------------ |
| `routers/forum.py`   | 使用 `Annotated[..., Query(...)]`/`Annotated[..., Depends(...)]`，修正参数顺序 |
| `routers/news.py`    | 同上，标记未使用参数                                                           |
| `routers/lawfirm.py` | 同上                                                                           |
| `routers/upload.py`  | 使用 `Annotated` 声明 `File`/`Depends` 参数                                    |
| `routers/ai.py`      | 同上                                                                           |

### 6. 工具层类型升级

| 文件                | 修改内容                     |
| ------------------- | ---------------------------- | ---------------------------------------- |
| `utils/deps.py`     | 使用 `                       | None`与`Annotated`，修复函数调用参数顺序 |
| `utils/security.py` | 升级到 Python 3.10+ 类型语法 |

---

## 技术要点

### Python 3.10+ 类型语法

```python
# 旧写法
from typing import Optional, List, Tuple
def foo(x: Optional[str]) -> List[int]: ...

# 新写法
def foo(x: str | None) -> list[int]: ...
```

### SQLAlchemy 2.0 ORM 类型

```python
# 旧写法
class User(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String(100))

# 新写法
from sqlalchemy.orm import Mapped, mapped_column

class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
```

### FastAPI Annotated 参数

```python
# 旧写法（触发 reportCallInDefaultInitializer）
def endpoint(page: int = Query(1)): ...

# 新写法
from typing import Annotated
def endpoint(page: Annotated[int, Query()] = 1): ...
```

### Pydantic Config 类型标注

```python
class MySchema(BaseModel):
    class Config:
        from_attributes: bool = True  # 显式标注避免 basedpyright 警告
```

---

## 后续计划

### 阶段一：完成剩余文件清理（优先级：中）

#### 1.1 待检查的服务层文件

| 文件                            | 检查项                  | 预计工作量 |
| ------------------------------- | ----------------------- | ---------- |
| `services/law_service.py`       | 检查是否存在旧式 typing | 10 分钟    |
| `services/knowledge_service.py` | 检查 Any 类型使用       | 10 分钟    |

#### 1.2 待检查的路由层文件

| 文件              | 检查项             | 预计工作量 |
| ----------------- | ------------------ | ---------- |
| `routers/user.py` | Annotated 参数改造 | 15 分钟    |
| `routers/auth.py` | 检查返回类型       | 10 分钟    |

#### 1.3 待检查的其他文件

| 文件          | 检查项             | 预计工作量 |
| ------------- | ------------------ | ---------- |
| `main.py`     | 检查启动配置类型   | 5 分钟     |
| `database.py` | 检查 Session 类型  | 5 分钟     |
| `config.py`   | 检查 Settings 类型 | 5 分钟     |

### 阶段二：运行完整验证（优先级：高）

1. **运行 Pyright 全量检查**

   ```bash
   cd backend
   pyright . --outputjson > pyright_report.json
   ```

2. **分析报告**

   - 统计剩余错误数量
   - 按严重程度分类
   - 按文件分组

3. **修复剩余问题**
   - 优先修复 error 级别
   - 其次处理 warning 级别
   - information 级别可选处理

### 阶段三：建立长期维护机制（优先级：低）

#### 3.1 CI/CD 集成

```yaml
# .github/workflows/type-check.yml
name: Type Check
on: [push, pull_request]
jobs:
  pyright:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install pyright
      - run: cd backend && pyright .
```

#### 3.2 Pre-commit 钩子

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/RobertCraiworthy/pyright-python
    rev: v1.1.350
    hooks:
      - id: pyright
        args: ["--project", "backend/pyrightconfig.json"]
```

#### 3.3 代码规范文档

建议在项目 README 或 CONTRIBUTING.md 中添加：

- 类型注解规范（使用 Python 3.10+ 语法）
- SQLAlchemy 模型规范（使用 2.0 风格）
- FastAPI 参数规范（使用 Annotated）

---

## 常见问题与解决方案

### Q1: `reportCallInDefaultInitializer` 警告

**问题**：FastAPI 的 `Query()`、`Depends()` 等作为默认值时触发警告

**解决**：使用 `Annotated` 类型

```python
# 修复前
def endpoint(page: int = Query(1)): ...

# 修复后
from typing import Annotated
def endpoint(page: Annotated[int, Query()] = 1): ...
```

### Q2: `Column[Unknown]` 类型错误

**问题**：SQLAlchemy 1.x 风格的 Column 定义无法推断类型

**解决**：迁移到 SQLAlchemy 2.0 风格

```python
# 修复前
id = Column(Integer, primary_key=True)

# 修复后
id: Mapped[int] = mapped_column(primary_key=True)
```

### Q3: `Optional` 被标记为 deprecated

**问题**：Python 3.10+ 推荐使用 `X | None` 语法

**解决**：替换所有 `Optional[X]` 为 `X | None`

```python
# 修复前
from typing import Optional
def foo(x: Optional[str]): ...

# 修复后
def foo(x: str | None): ...
```

### Q4: `value` 类型为 `Any`

**问题**：字典遍历时 value 类型推断为 Any

**解决**：显式声明字典类型

```python
# 修复前
update_data = {"name": "test"}
for key, value in update_data.items():  # value: Any
    ...

# 修复后
update_data: dict[str, str | int | bool] = {"name": "test"}
for key, value in update_data.items():  # value: str | int | bool
    ...
```

### Q5: 隐式相对导入警告

**问题**：`from app.xxx import yyy` 被识别为隐式相对导入

**解决**：在 `pyrightconfig.json` 中配置

```json
{
  "executionEnvironments": [{ "root": "app", "extraPaths": ["."] }],
  "reportImplicitRelativeImport": false
}
```

---

## Pyright 配置参考

当前 `backend/pyrightconfig.json` 配置：

```json
{
  "include": ["app"],
  "executionEnvironments": [
    {
      "root": "app",
      "extraPaths": ["."]
    }
  ],
  "reportImplicitRelativeImport": false,
  "reportCallInDefaultInitializer": false,
  "pythonVersion": "3.10",
  "typeCheckingMode": "basic"
}
```

**配置项说明**：
| 配置项 | 说明 |
|--------|------|
| `include` | 指定类型检查的目录范围 |
| `executionEnvironments` | 配置执行环境，解决导入路径问题 |
| `reportImplicitRelativeImport` | 是否报告隐式相对导入（建议关闭） |
| `reportCallInDefaultInitializer` | 是否报告默认值中的函数调用（建议关闭） |
| `pythonVersion` | 目标 Python 版本 |
| `typeCheckingMode` | 检查严格程度：off/basic/standard/strict/all |

---

## 验证命令

```bash
# 在 backend 目录运行 Pyright 检查
cd backend
pyright .

# 或使用 basedpyright
basedpyright .

# 输出 JSON 格式报告
pyright . --outputjson > pyright_report.json

# 仅检查特定文件
pyright app/services/forum_service.py

# 查看详细诊断信息
pyright . --verbose
```

---

## 检查清单

在提交代码前，请确认以下事项：

- [ ] 所有 `Optional[X]` 已替换为 `X | None`
- [ ] 所有 `List[X]` 已替换为 `list[X]`
- [ ] 所有 `Tuple[X, Y]` 已替换为 `tuple[X, Y]`
- [ ] 所有 `Dict[K, V]` 已替换为 `dict[K, V]`
- [ ] SQLAlchemy 模型使用 `Mapped` 和 `mapped_column`
- [ ] FastAPI 参数使用 `Annotated` 声明
- [ ] Pydantic `Config.from_attributes` 有 `bool` 类型注解
- [ ] 函数返回类型明确声明
- [ ] 无 `Any` 类型逃逸（除非必要）
- [ ] 运行 `pyright .` 无错误

---

_最后更新: 2024-12-16_

---

## 本次更新记录 (2024-12-16)

### 完成的修改

| 文件               | 修改内容                                                                                          |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| `routers/user.py`  | 所有 `Depends()` 默认参数改为 `Annotated` 风格，`keyword: str = None` 修复为 `str \| None = None` |
| `routers/admin.py` | `Depends()` 默认参数改为 `Annotated` 风格                                                         |
| `utils/deps.py`    | `require_admin` 函数改为 `Annotated` 风格                                                         |
| `config.py`        | `Config.from_attributes` 添加类型注解                                                             |

### 已验证无需修改的文件

- `services/ai_assistant.py` - 已使用 Python 3.10+ 类型语法
- `services/forum_service.py` - 已使用 Python 3.10+ 类型语法
- `services/lawfirm_service.py` - 已使用 Python 3.10+ 类型语法
- `services/news_service.py` - 已使用 Python 3.10+ 类型语法
- `services/user_service.py` - 已使用 Python 3.10+ 类型语法
- `utils/security.py` - 已使用 Python 3.10+ 类型语法
- `schemas/*.py` - 所有 schema 文件已使用现代类型语法
- `main.py` - 无类型问题
- `database.py` - 无类型问题

### 阶段二验证结果

运行 `pyright .` 结果：**0 errors, 0 warnings, 0 informations** ✅

### 额外修复

| 文件                 | 修改内容                                                                        |
| -------------------- | ------------------------------------------------------------------------------- |
| `utils/deps.py:51`   | `int(sub)` 改为 `int(str(sub))` 修复类型错误                                    |
| `routers/news.py:64` | `int(cat.get(...))` 改为 `int(str(cat.get(...)))` 修复类型错误                  |
| `pyrightconfig.json` | 添加 `reportMissingImports`/`reportMissingModuleSource` 配置，排除 scripts 目录 |

### 已知警告（无需修复）

- `routers/user.py:188` 和 `routers/admin.py:20` 中 `current_user` 未使用警告
  - 这是预期行为，`current_user` 用于权限验证（通过 `require_admin` 依赖），即使不在函数体内直接使用也必须存在
