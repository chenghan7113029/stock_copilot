## 1. 配置与交易日

- [ ] 1.1 在 `config/app.example.yaml` 增加 `feishu:` 示例段（app_id/app_secret/chat_id/folder_token/narrate/sync_before_push/trading_days_only）
- [ ] 1.2 Modify `src/common/config_loader.py`：解析 `feishu:`，密钥支持环境变量 `FEISHU_APP_SECRET`（及必要时 `FEISHU_APP_ID`）
- [ ] 1.3 Create `src/common/trading_day.py`（或等价）：交易日判断 V1（工作日 + 可配置休市日列表）；Create `test/common/test_trading_day.py`

## 2. Composer（本地 Markdown）

- [ ] 2.1 Create `src/service/feishu/composer.py`：按固定五节组装 MD；综合叙事含非红蓝免责声明；单节失败写入错误块
- [ ] 2.2 Create 路径助手：`reports/feishu/{date}/{slot}/{code}.md`
- [ ] 2.3 Create `test/service/feishu/test_composer.py`：章节顺序、免责声明、单节失败降级、路径约定

## 3. Publisher（飞书 API）

- [ ] 3.1 Spike：确认飞书「Markdown → 新建云文档」API 路径；将结论记入 `docs/design/feishu-watchlist-push.md` 草案或 design 备注
- [ ] 3.2 Create `src/service/feishu/publisher.py`：tenant_access_token、新建文档、发送一票一消息；缺凭证明确失败
- [ ] 3.3 Create `test/service/feishu/test_publisher.py`：HTTP mock（新建成功、凭证缺失、dry-run 不写、失败通知）

## 4. Pipeline 与 CLI

- [ ] 4.1 Create `src/service/feishu/pipeline.py`：编排 sync（可选）→ composer → publisher；批次部分失败汇总
- [ ] 4.2 Modify `src/apps/cli.py`：新增 `feishu push`（单票/`--watchlist`、`--dry-run`、`--narrate`、sync 开关、slot）
- [ ] 4.3 Create `test/apps/test_cli_feishu_push.py`：dry-run、非交易日 skip、未配置飞书非 0 退出

## 5. 文档与运维说明

- [ ] 5.1 Modify `docs/user-guide.md`：飞书推送用法、配置、`--dry-run`、Windows 计划任务 09:00/13:00/17:00 示例、防休眠提示
- [ ] 5.2 Create 或更新 `docs/design/feishu-watchlist-push.md`（可从本 change design 精简落地）
- [ ] 5.3 Modify `docs/mrd/product-overview.md` / `docs/mrd/roadmap-todo.md`：登记「飞书常看推送」交付通道与状态
- [ ] 5.4 若新增 `src/service/feishu/`：Modify `docs/dev/engineering-conventions.md` 目录表

## 6. 验收

- [ ] 6.1 本地 `--dry-run --watchlist`：确认 MD 五节与路径
- [ ] 6.2 （可选，需真实飞书应用）非 dry-run 单票推送：确认新建文档 + 群消息链接
- [ ] 6.3 相关 pytest 全部通过

## 7. 归档

- [ ] 7.1 确认 `tasks.md` 全部完成
- [ ] 7.2 运行 `/opsx-archive add-feishu-watchlist-push`，同步 specs 到 `openspec/specs/`，并将 proposal/design 要点合并进 `docs/mrd/` 与 `docs/design/`
