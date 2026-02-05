# MCP：从玩具到工具的关键升级

> 这篇文章写给“正在把 MCP 服务端从 demo 变成可上线服务”的你。结论先放在前面：SSE 在 MCP 里能跑，但它会把连接管理、网关适配、扩展性问题放大；Streamable HTTP 把交互收敛回标准 HTTP 语义，同时保留流式能力，更适合作为长期默认方案。

本文不空谈：下面所有现象都能在本仓库复现（以 `exercise/fastmcp_sse.py` 为例），并附上我在本机实际跑出来的命令输出。

## 先问三个问题

1) 为什么我只是开了几个 MCP 客户端，本机 `8000` 端口的连接数就蹭蹭上涨？  
2) 为什么 SSE 的 MCP 往往是“两段式”：先连 `/sse`，再拿到一个 `/messages?session_id=...` 去发消息？  
3) 为什么这套东西在本地没问题，一上网关/负载均衡就开始出现各种超时、断流、重连风暴？

把这三个问题讲清楚，你就会自然理解：为什么社区会推动从 SSE 迁移到 Streamable HTTP。

## 1) MCP 里的 SSE：不是“一个端点”，而是一套会话拼装

典型 SSE 形态的 MCP 交互大致是：

- 客户端 `GET /sse` 建立长连接，用来接收服务端推送的消息（包括心跳、事件、工具调用结果等）。
- 服务端会返回一个“消息投递入口”，常见是带 `session_id` 的 `/messages` URL。
- 客户端后续发请求（例如 tool call）时，走 `POST /messages?session_id=...`。

直觉上看很合理：**推送走 SSE，提交走 POST**。  
但工程上，这相当于你把“一个 RPC 会话”拆成了两条通道、两段语义。

### 案例 1：FastMCP 的 SSE 握手会返回 `endpoint + session_id`

先看服务端代码（就是你正在用的例子）：

```py
from mcp.server.fastmcp import FastMCP

app = FastMCP("WeatherMCP")

@app.tool()
def get_weather(city: str) -> dict:
    return {"city": city, "temp": 25}

if __name__ == "__main__":
    app.run(transport="sse")
```

启动后，用 `curl` 连 SSE：

```powershell
curl.exe -N -H "Accept: text/event-stream" "http://127.0.0.1:8000/sse" --max-time 2
```

我本机的实际输出是（关键点：`/messages/?session_id=...`）：

```text
event: endpoint
data: /messages/?session_id=02a92b6b7c294357a9c5c8446fa4a624
```

这就是“两段式”的由来：**SSE 这条连接主要用来“收”；而“发请求”通常要去另一个带会话标识的 endpoint。**

## 2) SSE 在 MCP 场景的核心问题：连接与语义被放大

### 2.1 长连接会线性吃资源，而且你很难“忽略它”

SSE 是“一客户端一长连接”。你多开几个客户端，本机就能观察到连接数增长。

在 Windows 上你可以用这条命令确认（以端口 `8000` 为例）：

```powershell
Get-NetTCPConnection |
  Where-Object { $_.LocalPort -eq 8000 -or $_.RemotePort -eq 8000 } |
  Format-Table -AutoSize
```

注意：有些 Windows 环境下 `Get-NetTCPConnection` 可能会报“拒绝访问”（权限限制）。不想折腾就直接用 `netstat`，效果一样直观。

你会看到一排排 `Established`。这不是“噪音”，而是实打实的资源占用：socket、文件句柄、连接追踪表项、负载均衡连接槽位……

一旦你进入生产环境，这些问题会迅速具象化：

- 连接空闲超时怎么设？是网关断，还是服务端断，还是客户端断？
- 服务端重启时客户端会不会同时重连（重连风暴）？
- 实例扩容/缩容时，长连接如何迁移？如何优雅下线？

### 案例 2：多开几个 SSE 客户端，`ESTABLISHED` 就线性增长

下面这个现象特别“有手感”：你每多连一个 SSE 客户端，就多一条 TCP 长连接。

我在本机用 3 个客户端连接同一个 `:8000` SSE 服务后，执行：

```powershell
netstat -ano | findstr "8000"
```

得到（节选）：

```text
TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       36272
TCP    127.0.0.1:8000         127.0.0.1:57985        ESTABLISHED     36272
TCP    127.0.0.1:8000         127.0.0.1:57995        ESTABLISHED     36272
TCP    127.0.0.1:8000         127.0.0.1:57997        ESTABLISHED     36272
TCP    127.0.0.1:57985        127.0.0.1:8000         ESTABLISHED     15620
TCP    127.0.0.1:57995        127.0.0.1:8000         ESTABLISHED     15620
TCP    127.0.0.1:57997        127.0.0.1:8000         ESTABLISHED     20044
```

读法也很简单：

- `LISTENING 36272` 是服务端进程 PID（FastMCP/uvicorn）。
- 每个客户端都会对应一对 `ESTABLISHED`（服务端视角 + 客户端视角）。

当你把客户端数量从 3 提到 30、300 时，SSE 这套模型的压力点就不再是“业务逻辑”，而是连接数本身。

### 2.2 “两段式端点”让鉴权、网关、观测都变复杂

SSE + messages endpoint 的组合，通常意味着：

- 鉴权要做两次（`/sse` 一次、`/messages` 一次），token 过期处理也要考虑两条链路。
- 日志/Trace 会被切碎：推送流量不再是一个个请求，而是“一条持续不断的连接”；你想还原一次完整交互会更费劲。
- 网关策略更难统一：有的网关对 `text/event-stream` 需要额外配置（缓冲、超时、最大连接数、HTTP/2 兼容等）。

### 2.3 SSE 是“服务端单向推送”，但 MCP 是“会话式双向交互”

SSE 的本质是：服务端 -> 客户端的单向事件流。  
而 MCP 的本质更像“会话式 RPC”：客户端发起请求，服务端返回结果，有时还需要流式输出。

你当然可以用 SSE 拼装出双向能力（靠第二条 `/messages` 请求通道），但你也因此引入更多状态：`session_id`、endpoint 发现、心跳、重连与一致性……

## 3) Streamable HTTP：把“会话交互”收敛回标准 HTTP

Streamable HTTP 可以用一句话理解：

> 用标准 HTTP 的请求/响应来承载 MCP 的会话交互，并允许响应体以流式方式逐步返回。

它解决的不是“能不能流”，而是“把会话语义放回 HTTP 生态里”：

- 对网关友好：还是 HTTP 请求；鉴权、限流、日志、追踪都有成熟方案。
- 对扩展友好：扩的是吞吐（并发请求/耗时/资源），而不是“连接容器”的承载上限。
- 对实现友好：客户端与服务端更接近一个统一的 RPC 入口，减少两段式端点与额外状态。

如果你想先建立直觉，你仓库里的 `exercise/streamable.py` 就是一个最小“可流式 HTTP”示例：`POST` 进来一个请求，`StreamingResponse` 边产出边返回。

### 对照阅读：Higress 的压测数据（为什么“连接数”会成为 SSE 的硬上限）

如果你希望看到更“工程化”的对比（不仅是本机 `netstat` 这种直觉证据），我建议读一下 Higress 在 2025-04-25 发布的这篇文章（链接放在代码块里，方便复制）：

```text
https://higress.cn/blog/higress-gvr7dx_awbbpb_vt50nsm76qkpi78w/
```

里面有三块信息，跟你写 MCP 服务端时遇到的问题高度对应：

1) **HTTP+SSE 的三类问题**：需要维护大量长连接、消息只能走 SSE 带来额外复杂度、很多网络基础设施（比如企业防火墙/网关）会终止超时长连接，导致不稳定。  
2) **Streamable HTTP 的关键改进**：移除专门的 `/sse` 端点，把通信收敛到统一端点；服务端可以按需选择“普通 HTTP 响应”或“流式返回”；引入 session 机制用于状态管理与恢复。  
3) **并发压测现象**（他们用 Python 程序模拟并发访问）：在 1000 并发场景里，SSE 方案的连接无法复用，会带来 TCP 连接数突增；而 Streamable HTTP 可以复用连接，连接数峰值维持在较低数量级，同时整体执行时间更短。并且当并发数逼近进程/系统最大连接数限制（文章提到 Linux 默认 1024 的典型上限）时，SSE 方案会出现成功率快速下降的情况。

这组数据的意义在于：你本地看到的“每个客户端一条长连接”，在高并发下会直接变成一个可测量、可复现的稳定性与成功率问题，而不仅是“资源用多一点”。

### 规范变更：PR #206（用 Streamable HTTP 替代 HTTP+SSE 的方向）

如果你想知道“这件事在 MCP 规范层面到底怎么改”，直接看这个 PR（链接放代码块里，方便复制）：

```text
https://github.com/modelcontextprotocol/modelcontextprotocol/pull/206
```

它的 TL;DR 很值得服务端作者逐条对照理解（我按工程语言转述一下）：

1) **移除专门的 `/sse` 端点**：不再要求你必须提供一个“永远挂着的推送通道”。  
2) **客户端 -> 服务端消息收敛到 `/message`（或类似）**：请求统一入口，少掉“两段式”拆分。  
3) **按需升级为 SSE**：并不是禁止 SSE，而是把 SSE 变成“当需要流式通知/结果时的一种响应形态”。  
4) **会话 ID 可选**：服务端可以完全无状态；需要状态时再建立 session，并让客户端在每次请求里带回。  
5) **客户端也可以用 GET 建立 SSE 流**：例如对 `/message` 发一个空的 GET 来初始化 SSE 流（用于接收通知/请求）。

另外 PR 还专门解释了“为什么现在不把 WebSocket 作为默认远程传输”：核心是希望保留 **RPC-like 的轻量调用**（避免每次都要维护 WS 连接的运维成本），同时考虑到 **浏览器环境头部/鉴权能力** 与 **HTTP 方法升级限制** 等现实约束。

### 官方列出的优点（Benefits）：为什么这不是“为了换而换”

PR #206 里官方把优势写得很直白，我按“服务端落地”的视角解释一下每条意味着什么：

1) **Stateless servers are now possible**：你可以做一个完全无状态的 MCP 服务端——每个请求来了就算、算完就回，不需要维持一个高可用的长连接推送通道。  
   - 对应到你本文的案例：SSE 的“每客户端一条长连接”天然逼着你管连接生命周期；Streamable HTTP 允许你把很多场景退化成“普通 HTTP 请求”。  

2) **Plain HTTP implementation**：不要求 SSE 也能实现 MCP——你用任何能处理 HTTP 的服务（甚至不支持 `text/event-stream` 的环境）都能跑起来。  
   - 这对“把 MCP 接进现有后端”很关键：你不必为 SSE 单独改造框架、代理、超时与缓冲策略。  

3) **Infrastructure compatibility**：它就是 HTTP，所以天然更兼容中间件与基础设施（鉴权、WAF、限流、审计、日志、Tracing 等）。  
   - 你遇到的很多“上了网关就怪起来”的问题，本质是基础设施对长连接/流式的默认行为差异；把默认形态收敛到 HTTP，会少掉大量隐性坑。  

4) **Backwards compatibility**：这是对当前传输的增量演进，而不是推倒重来。  
   - 对服务端作者意味着：你可以分阶段迁移（先兼容旧客户端，再逐步切到新形态），不需要一次性“大断代”。  

5) **Flexible upgrade path**：需要流式时再升级成 SSE，用 SSE 来承载“流式响应/通知/请求”；不需要时就用普通 HTTP。  
   - 也就是说，SSE 被从“默认常驻连接”降级为“按需使用的流式手段”，把它的强项（流）留下，把它的硬伤（长期连接的运维成本）尽量移出默认路径。

## 4) 这次升级真正带来的收益（工程视角）

### 4.1 从“连接问题”回到“请求问题”

你不再需要围绕长连接做一堆运维设计（连接数、心跳、重连、优雅下线、LB 粘性……），而是回到熟悉的 HTTP 请求模型：超时、并发、重试、幂等。

### 4.2 一套入口更容易做安全与治理

统一入口意味着：

- 鉴权逻辑集中（少掉一半“到底在哪鉴权”的争论）
- 限流熔断更直接（按请求、按用户、按路由）
- 观测更连续（每次交互都有清晰的请求上下文）

### 4.3 更贴近 MCP 的长期形态

当 MCP 逐步从“本地玩具”走向“服务化能力”，你会越来越依赖：

- 标准化的基础设施（网关、WAF、IAM、审计）
- 可预测的扩展方式（水平扩容、灰度发布、自动伸缩）
- 更少“协议拼装”的状态管理

Streamable HTTP 的价值，本质是把这些能力都“免费”接进来。

## 5) 迁移建议：怎么从 SSE 平滑过渡

1) 先把业务逻辑与 transport 解耦：工具实现不要绑死在 SSE 的 session/endpoint 上。  
2) 明确取消与超时：流式响应要能处理中途取消、服务端回收资源。  
3) 把观测补齐：至少要有 request_id（或等价标识）、耗时、输出大小/Token 数、错误原因。  
4) 上网关前压测：重点看慢请求、并发、断线重试对后端的影响。

## 附：一键复现脚本

如果你不想手动开多个终端，本仓库提供了一个 PowerShell 脚本，自动完成：

1) 启动 `exercise/fastmcp_sse.py`  
2) `curl` 观察握手返回的 `endpoint + session_id`  
3) 批量拉起多个 SSE 客户端制造长连接  
4) 用 `netstat` 打印 `ESTABLISHED` 证据

运行方式：

```powershell
.\exercise\demo_fastmcp_sse_longconn.ps1 -Clients 3 -HoldSeconds 3
```

---

SSE 不是“不能用”，它只是更适合 demo 或小规模、强可控环境；而当你要把 MCP 服务当成长期维护的服务时，Streamable HTTP 会让你少背一整类“连接与网关”的技术债。

![MCP207提交](https://coze-hotel-1257853985.cos.ap-guangzhou.myqcloud.com/wx_articles/20260204/MCP207.png)
