# model-boundary-test

测试本地小模型的能力边界：不同大小的模型，在什么类型、什么难度的问题上还能答对。完整计划见 **TEST_PLAN.md**。

## 快速开始

```bash
# 在服务器 192.168.2.25 上（需要 OLLAMA_HOST=0.0.0.0:11434）
bash pull_models.sh            # Windows 服务器：.\pull_models.ps1

# 在自己的电脑上
pip install -r requirements.txt
python bench.py --models qwen3.5:4b --limit 5 --out results/smoke.jsonl     # 冒烟测试
python bench.py --models qwen3.5:2b qwen3.5:4b qwen3.5:9b gemma4:e4b gemma4:12b gemma4:26b qwen3.5:27b
python bench.py --models qwen3.5:4b qwen3.5:9b qwen3.5:27b --think on       # thinking 对比
python grade.py              # 自动判分；开放题写入 results/manual_review.csv，人工填 1/0 后再运行一次
python report.py             # 输出 results/report.md 和 results/boundary_heatmap.png
```

- 服务器地址可以用 `--host` 参数修改，或者设置环境变量 `OLLAMA_URL`。
- 程序中断后直接重新运行，已完成的题目会自动跳过。
- 开放题也可以用评委模型判分：`python grade.py --judge-model gpt-4o`（需要 `OPENAI_API_KEY`），或者用本地模型：`--judge-model qwen3.5:27b --base-url http://192.168.2.25:11434/v1`。

## 文件

| 文件 | 作用 |
|---|---|
| `data/boundary_set.jsonl` | 110 道测试题（5 个维度 × 4 个难度 × 5 题，另加 10 道中英对照题） |
| `data/boundary_set_review.csv` | 同一份题目的表格版，方便组员检查 |
| `bench.py` | 向 Ollama 提问，记录答案、延迟、tok/s 和 GPU 占用 |
| `grade.py` | 自动判分（选择题、数值题、简答题、格式规则）+ 开放题判分 |
| `report.py` | 生成边界表、热力图、中英对比和错题列表 |
| `pull_models.sh` / `.ps1` | 拉取模型；加参数 `all` 会同时拉取选测模型 |
