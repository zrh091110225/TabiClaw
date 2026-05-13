# 路线规划工作流

用于重新规划完整路线，或从当前路线末尾继续追加目的地。

## 先读

- `data/route.md`：确认当前路线和末尾城市。
- `data/status.json`：确认当前城市和天数。
- `config/settings.yaml`：确认外部工具路径。

## 重新规划完整路线

```bash
bash scripts/replan_route.sh 起点 终点
```

如果用户明确要求重置状态：

```bash
bash scripts/replan_route.sh 起点 终点 --reset
```

## 从当前末尾继续追加

```bash
bash scripts/continue_route.sh 终点
```

## 会修改什么

重新规划可能修改：

- `data/route.md`
- 使用 `--reset` 时修改 `data/status.json`
- 使用 `--reset` 时同步 `data/journals/index.md` 顶部状态

追加路线会修改：

- `data/route.md`

## 验证

- `data/route.md` 路线起止点符合用户要求。
- 使用 `--reset` 时，`data/status.json` 回到起点状态。
- 未使用 `--reset` 时，不应重置当前旅行状态。

## 注意事项

- 不要在用户只想查看路线时重规划。
- 不要把外部工具失败后的空结果写成正式路线。

