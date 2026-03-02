"""
定稿 + 经验提炼脚本
用法：python tools/finalize.py --type scale_release --version v2026.03

流程：
1. 对比 initial.md 与 final.md 的差异
2. 调用 Gemini 分析差异，提炼经验规则
3. 更新经验库 experience.json
4. 更新 latest_final.md 软链接
"""

import argparse
import difflib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gemini_client import load_config, generate_text, PROJECT_ROOT


def get_doc_type_dir(doc_type: str) -> Path:
    return PROJECT_ROOT / "doc_types" / doc_type


def get_version_dir(doc_type: str, version: str) -> Path:
    return get_doc_type_dir(doc_type) / "versions" / version


def compute_diff(initial: str, final: str) -> str:
    """计算 initial 和 final 之间的 unified diff"""
    initial_lines = initial.splitlines(keepends=True)
    final_lines = final.splitlines(keepends=True)

    diff = difflib.unified_diff(
        initial_lines, final_lines,
        fromfile="initial.md", tofile="final.md",
        lineterm=""
    )
    return "\n".join(diff)


def build_experience_extraction_prompt(diff_text: str, initial: str, final: str,
                                       existing_experience: dict) -> str:
    """构建经验提炼 prompt"""
    # 现有规则摘要
    existing_rules = []
    for r in existing_experience.get("rules", []):
        existing_rules.append(f"- [{r['id']}] {r['rule']}")
    existing_rules_text = "\n".join(existing_rules) if existing_rules else "（暂无）"

    prompt = f"""你是一个文档生成经验分析专家。请分析以下文档初版和终版的差异，从中提炼可复用的经验规则。

## 差异内容（unified diff）

```diff
{diff_text}
```

## 初版文档（AI 生成）

```markdown
{initial[:3000]}
{"... (截断)" if len(initial) > 3000 else ""}
```

## 终版文档（人工调整后）

```markdown
{final[:3000]}
{"... (截断)" if len(final) > 3000 else ""}
```

## 现有经验规则

{existing_rules_text}

## 任务

请分析差异，输出 JSON 格式的分析结果。要求：

1. **new_rules**: 从本次差异中提炼的新规则（不要与现有规则重复）
   - 每条规则包含: id, category, rule, confidence
   - category 可选: structure, content, formatting, style, naming
   - confidence 可选: high, medium, low
   - id 格式: r + 三位数字（从现有最大编号之后递增）

2. **updated_rules**: 需要更新的现有规则
   - 包含: id, update（描述如何更新）

3. **new_anti_patterns**: 新发现的反模式
   - 包含: id, description, solution
   - id 格式: ap + 三位数字

4. **new_prompt_patches**: 新的 prompt 补丁
   - 包含: id, content
   - id 格式: pp + 三位数字

5. **summary**: 一句话总结本次调整的主要方向

只输出 JSON，不要输出其他内容。如果差异很小或没有可提炼的经验，对应数组留空。

```json
{{
  "new_rules": [],
  "updated_rules": [],
  "new_anti_patterns": [],
  "new_prompt_patches": [],
  "summary": ""
}}
```"""
    return prompt


def merge_experience(existing: dict, extraction: dict, version: str) -> dict:
    """将提取的经验合并到现有经验库"""
    # 更新元信息
    existing["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    existing["experience_version"] = existing.get("experience_version", 0) + 1

    # 添加新规则
    for rule in extraction.get("new_rules", []):
        rule["source_version"] = version
        rule["times_applied"] = 0
        existing.setdefault("rules", []).append(rule)

    # 更新现有规则
    for update in extraction.get("updated_rules", []):
        for rule in existing.get("rules", []):
            if rule["id"] == update["id"]:
                rule["rule"] = update.get("update", rule["rule"])
                rule["times_applied"] = rule.get("times_applied", 0) + 1
                break

    # 添加新反模式
    for ap in extraction.get("new_anti_patterns", []):
        existing.setdefault("anti_patterns", []).append(ap)

    # 添加新 prompt 补丁
    for pp in extraction.get("new_prompt_patches", []):
        pp["added_at"] = version
        existing.setdefault("prompt_patches", []).append(pp)

    return existing


def update_latest_symlink(doc_type: str, version: str):
    """更新 latest_final.md 软链接"""
    doc_type_dir = get_doc_type_dir(doc_type)
    latest_path = doc_type_dir / "latest_final.md"

    # 删除旧链接
    if latest_path.exists() or latest_path.is_symlink():
        latest_path.unlink()

    # 创建新链接
    target = Path("versions") / version / "final.md"
    latest_path.symlink_to(target)
    print(f"   🔗 latest_final.md → {target}")


def main():
    parser = argparse.ArgumentParser(description="SCALE 文档定稿 + 经验提炼")
    parser.add_argument("--type", required=True, help="文档类型，如 scale_release")
    parser.add_argument("--version", required=True, help="版本号，如 v2026.03")
    parser.add_argument("--skip-experience", action="store_true", help="跳过经验提炼（仅归档）")
    args = parser.parse_args()

    doc_type = args.type
    version = args.version

    print(f"📋 开始定稿: {doc_type} / {version}")
    print(f"{'─' * 50}")

    config = load_config()
    version_dir = get_version_dir(doc_type, version)

    # 检查文件存在
    initial_path = version_dir / "initial.md"
    final_path = version_dir / "final.md"

    if not initial_path.exists():
        print(f"❌ 初版文档不存在: {initial_path}")
        print(f"   请先运行 generate.py 生成初版")
        sys.exit(1)

    if not final_path.exists():
        print(f"❌ 终版文档不存在: {final_path}")
        print(f"   请在 Cursor 中编辑初版后，保存为 final.md")
        print(f"   提示：可以复制 initial.md 为 final.md，然后在 final.md 上修改")
        sys.exit(1)

    initial = initial_path.read_text(encoding="utf-8")
    final = final_path.read_text(encoding="utf-8")

    # 计算 diff
    print("🔍 计算差异...")
    diff_text = compute_diff(initial, final)

    if not diff_text.strip():
        print("   初版与终版完全一致，无需提炼经验")
    else:
        diff_lines = [l for l in diff_text.split("\n") if l.startswith("+") or l.startswith("-")]
        change_count = len([l for l in diff_lines if not l.startswith("+++") and not l.startswith("---")])
        print(f"   发现 {change_count} 处变更")

        # 保存 diff report
        diff_report_path = version_dir / "diff_report.md"
        diff_report_path.write_text(
            f"# Diff Report: {version}\n\n"
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"```diff\n{diff_text}\n```\n",
            encoding="utf-8"
        )
        print(f"   📄 差异报告: {diff_report_path}")

    # 经验提炼
    if diff_text.strip() and not args.skip_experience:
        auto_extract = config.get("experience", {}).get("auto_extract", True)
        if auto_extract:
            print(f"\n{'─' * 50}")
            print("🧠 经验提炼中...")

            # 加载现有经验
            exp_path = get_doc_type_dir(doc_type) / "experience.json"
            if exp_path.exists():
                with open(exp_path, "r", encoding="utf-8") as f:
                    existing_exp = json.load(f)
            else:
                existing_exp = {"doc_type": doc_type, "rules": [], "anti_patterns": [], "prompt_patches": []}

            # 调用 Gemini 分析差异
            prompt = build_experience_extraction_prompt(diff_text, initial, final, existing_exp)
            result = generate_text(prompt, config)

            # 解析 JSON 结果
            try:
                # 清理可能的 markdown 包裹
                result_clean = result.strip()
                if result_clean.startswith("```json"):
                    result_clean = result_clean[7:]
                if result_clean.startswith("```"):
                    result_clean = result_clean[3:]
                if result_clean.endswith("```"):
                    result_clean = result_clean[:-3]
                result_clean = result_clean.strip()

                extraction = json.loads(result_clean)

                # 输出分析结果
                new_rules = extraction.get("new_rules", [])
                updated_rules = extraction.get("updated_rules", [])
                new_ap = extraction.get("new_anti_patterns", [])
                new_pp = extraction.get("new_prompt_patches", [])
                summary = extraction.get("summary", "")

                print(f"   📊 分析结果:")
                print(f"      新规则: {len(new_rules)} 条")
                print(f"      更新规则: {len(updated_rules)} 条")
                print(f"      新反模式: {len(new_ap)} 条")
                print(f"      新 prompt 补丁: {len(new_pp)} 条")
                if summary:
                    print(f"      总结: {summary}")

                # 合并到经验库
                if new_rules or updated_rules or new_ap or new_pp:
                    merged = merge_experience(existing_exp, extraction, version)
                    with open(exp_path, "w", encoding="utf-8") as f:
                        json.dump(merged, f, ensure_ascii=False, indent=2)
                    print(f"   ✅ 经验库已更新: {exp_path}")
                else:
                    print(f"   ℹ️  本次无新经验需要记录")

                # 保存原始分析到 diff_report
                diff_report_path = version_dir / "diff_report.md"
                with open(diff_report_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## 经验提炼结果\n\n```json\n{json.dumps(extraction, ensure_ascii=False, indent=2)}\n```\n")

            except json.JSONDecodeError as e:
                print(f"   ⚠️  Gemini 返回的内容无法解析为 JSON: {e}")
                print(f"   原始返回内容已保存到 diff_report.md")
                diff_report_path = version_dir / "diff_report.md"
                with open(diff_report_path, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## Gemini 原始返回（解析失败）\n\n```\n{result}\n```\n")

    # 更新软链接
    print(f"\n{'─' * 50}")
    print("🔗 更新最新版本链接...")
    update_latest_symlink(doc_type, version)

    print(f"\n{'═' * 50}")
    print(f"✅ 定稿完成！")
    print(f"   📄 终版文档: {final_path}")
    print(f"   🔗 最新版本: {get_doc_type_dir(doc_type) / 'latest_final.md'}")
    if diff_text.strip():
        print(f"   📊 差异报告: {version_dir / 'diff_report.md'}")


if __name__ == "__main__":
    main()


