# 发布到 PyPI 指南

## 前置准备

### 1. 注册 PyPI 账号
访问 https://pypi.org/account/register/ 注册账号

### 2. 启用双重认证（2FA）
- PyPI 要求发布包时必须启用 2FA
- 在账号设置中配置 2FA

### 3. 创建 API Token
1. 访问 https://pypi.org/manage/account/token/
2. 创建新的 API token
3. 选择 "Entire account" 范围（用于发布）
4. **重要**：复制并保存 token，只显示一次！

## 构建包

```bash
# 安装构建工具
uv pip install build

# 构建包
uv run python -m build

# 检查生成的文件
ls dist/
```

应该看到：
- `weather_mcp-0.1.0-py3-none-any.whl`
- `weather_mcp-0.1.0.tar.gz`

## 测试包（推荐）

### 1. 发布到 TestPyPI 先测试

```bash
# 安装 twine
uv pip install twine

# 发布到 TestPyPI
uv run twine upload --repository testpypi dist/*

# 从 TestPyPI 测试安装
pip install --index-url https://test.pypi.org/simple/ weather-mcp
```

### 2. 本地测试安装

```bash
# 从构建的 wheel 文件安装
pip install dist/weather_mcp-0.1.0-py3-none-any.whl

# 测试命令
weather-mcp --help

# 或使用 uvx 测试
uvx --from dist/weather_mcp-0.1.0-py3-none-any.whl weather-mcp
```

## 发布到正式 PyPI

### 方法 1：使用 Twine（推荐）

```bash
# 设置 API Token（或使用环境变量）
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=你的API_TOKEN

# 或者使用 ~/.pypirc 文件
cat > ~/.pypirc << EOF
[pypi]
username = __token__
password = 你的API_TOKEN
EOF

# 发布
uv run twine upload dist/*
```

### 方法 2：使用 uv 直接发布

```bash
# 设置环境变量
export UV_PUBLISH_TOKEN=pypi-你的API_TOKEN
# 或 Windows PowerShell
$env:UV_PUBLISH_TOKEN="pypi-你的API_TOKEN"

# 发布
uv publish
```

## 发布后验证

### 1. 访问 PyPI 页面
https://pypi.org/project/weather-mcp/

### 2. 测试安装

```bash
# 清理缓存
pip cache purge

# 安装
pip install weather-mcp

# 运行
weather-mcp
```

### 3. 测试 uvx

```bash
# 在新终端测试
uvx weather-mcp
```

## 更新版本

### 1. 修改版本号
编辑 `pyproject.toml`：
```toml
version = "0.2.0"  # 新版本
```

### 2. 重新构建和发布
```bash
# 清理旧的构建文件
rm -rf dist/ build/ *.egg-info

# 重新构建
uv run python -m build

# 重新发布
uv run twine upload dist/*
```

## 常见问题

### Q: 提示包名已存在
A: 包名在 PyPI 上是全局唯一的。如果 `weather-mcp` 已被占用，需要修改 `pyproject.toml` 中的 `name` 字段。

### Q: 上传失败
A: 检查：
- API Token 是否正确
- 版本号是否已存在（不能重复上传相同版本）
- 网络连接是否正常

### Q: 如何删除已发布的版本？
A: PyPI **不允许**删除已发布的版本，只能发布新版本修复问题。

## 发布检查清单

- [ ] 已注册 PyPI 账号并启用 2FA
- [ ] 已创建 API Token
- [ ] pyproject.toml 中的版本号正确
- [ ] README.md 更新了使用说明
- [ ] 本地测试构建成功
- [ ] （可选）在 TestPyPI 测试过
- [ ] 构建文件是最新的
- [ ] Git 已提交并推送

## 成功发布后的使用方式

用户现在可以通过以下方式使用：

### 1. uvx 直接运行（推荐，无需安装）
```bash
uvx weather-mcp
```

### 2. pip 安装后运行
```bash
pip install weather-mcp
weather-mcp
```

### 3. Claude Desktop 配置
```json
{
  "mcpServers": {
    "weather": {
      "command": "weather-mcp"
    }
  }
}
```

## 下一步

发布成功后，你可以：
1. 在 ModelScope MCP 广场创建服务（使用 GitHub 链接）
2. 在社交媒体分享你的包
3. 添加 badge 到 README：
```markdown
[![PyPI version](https://badge.fury.io/py/weather-mcp.svg)](https://badge.fury.io/py/weather-mcp)
```
