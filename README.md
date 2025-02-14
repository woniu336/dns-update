# 一个基于 Cloudflare API 的 DNS: 宕机自动切换ip脚本





一个基于 Cloudflare API 的智能 DNS 故障转移解决方案，当主服务器宕机时自动切换到备用 IP。

```
curl -sS -O https://raw.githubusercontent.com/woniu336/dns-update/main/dns_menu.sh && chmod +x dns_menu.sh && ./dns_menu.sh
```

预览：

```
┌─────────────────────────────────────────┐
│     Cloudflare 宕机切换IP脚本        │
│     博客:https://woniu336.github.io  │
├─────────────────────────────────────────┤
│ 1. 安装依赖                             │
│ 2. 设置 Cloudflare 配置                 │
│ 3. 设置钉钉机器人配置                   │
│ 4. 启动 DNS 更新脚本                    │
│ 5. 查看运行状态                         │
│ 6. 停止 DNS 更新脚本                    │
│ 7. 切换 CDN 状态                        │
│ 8. 设置服务器备注                       │
│ 9. 设置脚本启动快捷键                   │
│ 0. 退出                                 │
└─────────────────────────────────────────┘
请选择操作 (0-9):

```

要点：使用cf全局密钥，服务器不能禁ping，因为使用ping检测机制，



Zone ID:

![Image](https://img.meituan.net/video/b92146ad30fe87cfe55b05089f574fc75067.png)

钉钉通知：记得添加运行脚本的服务器ip

![Image](https://img.meituan.net/video/7a188fd043c3d843712a4eda5c0debda25838.png)



通知预览：

![Image](https://img.meituan.net/video/a489a5681aaec7fad979433962f242e748184.png)

### 检测逻辑说明

脚本使用 ping 命令检测服务器状态，具体逻辑如下：

1. 每分钟进行一次检测
2. 每次检测发送 5 个 ping 包
3. 根据丢包率判断服务器状态：
   - 丢包率 < 60%：认为服务器正常
   - 丢包率 ≥ 60%：认为服务器异常

### 故障转移机制

1. 连续失败计数：
   - 每次检测失败，连续失败计数 +1
   - 检测成功时重置为 0
   - 达到阈值（默认 3 次）时触发切换到备用 IP

2. 恢复机制：
   - 使用备用 IP 期间继续监控主 IP
   - 主 IP 恢复后开始累计连续成功次数
   - 连续成功达到阈值（默认 2 次）时切回主 IP

### DNS 更新流程

1. 触发切换条件后，通过 Cloudflare API 更新 DNS 记录
2. 可以为主备 IP 分别配置不同的 CDN 状态
3. 支持同时更新多个子域名
4. 所有 DNS 变更都会通过钉钉机器人通知（如已配置）

### 通知机制

通过钉钉机器人发送以下事件通知：
- 服务器宕机及切换到备用 IP
- 服务器恢复及切回主 IP
- 脚本运行异常

### 配置参数

关键参数说明：
- `FAILURE_THRESHOLD = 3`：触发切换的连续失败次数
- `SUCCESS_THRESHOLD = 2`：触发恢复的连续成功次数
- `ping_count = 5`：每次检测的 ping 包数量
- `timeout = 2`：ping 超时时间（秒）
- 检测间隔：60 秒

### 多域名监控

多个域名监控方法：复制一份脚本，重命名py脚本，然后后台运行：

```
nohup python3 /path/to/your/directory/dns_update.py >> /path/to/your/directory/nohup.out 2>&1 &
```

禁止运行

```
pkill -f dns_update.py
```

查看进程

```
ps -ef | grep '[p]ython3 dns_update.py'
```

或者

```
ps -ef | grep python3
```


### 使用建议

合理设置检测阈值：
- 失败阈值太低可能导致频繁切换
- 失败阈值太高会延长响应时间

