"""
经验库管理工具
用法：
  python tools/experience_manager.py --type scale_release --action show
  python tools/experience_manager.py --type scale_release --action optimize
  python tools/experience_manager.py --type scale_release --action stats
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gemini_client import load_config, generate_text, PROJECT_ROOT


def get_experience_path(doc_type: str) -> Path:
    return PROJECT_ROOT / "doc_types" / doc_type / "experience.json"


def load_experience(doc_type: str) -> dict:
    """加载经验库"""
    exp_path = get_experience_path(doc_type)
    if not exp_path.exists():
        print(f"❌ 经验库不存在: {exp_path}")
        sys.exit(1)
    with open(exp_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_experience(doc_type: str, exp: dict):
    """保存经验库"""
    exp_path = get_experience_path(doc_type)
    with open(exp_path, "w", encoding="utf-8") as f:
        json.dump(exp, f, ensure_ascii=False, indent=2)


def action_show(doc_type: str):
    """展示经验库内容"""
    exp = load_experience(doc_type)

    print(f"📚 经验库: {doc_type}")
    print(f"   最后更新: {exp.get('last_updated', '未知')}")
    print(f"   版本: {exp.get('experience_version', '未知')}")
    print(f"   来源: {exp.get('source', '未知')}")
    print()

    # 规则
    rules = exp.get("rules", [])
    print(f"📏 经验规则 ({len(rules)} 条)")
    print(f"{'─' * 60}")
    for r in rules:
        confidence_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(r.get("confidence", ""), "⚪")
        print(f"  {confidence_icon} [{r['id']}] [{r['category']}] {r['rule']}")
        print(f"     来源: {r.get('source_version', '?')} | 应用次数: {r.get('times_applied', 0)}")
    print()

    # 反模式
    anti = exp.get("anti_patterns", [])
    print(f"🚫 反模式 ({len(anti)} 条)")
    print(f"{'─' * 60}")
    for a in anti:
        print(f"  [{a['id']}] ❌ {a['description']}")
        print(f"          ✅ {a['solution']}")
    print()

    # Prompt 补丁
    patches = exp.get("prompt_patches", [])
    print(f"🔧 Prompt 补丁 ({len(patches)} 条)")
    print(f"{'─' * 60}")
    for p in patches:
        print(f"  [{p['id']}] {p['content']}")
        print(f"     添加于: {p.get('added_at', '?')}")


def action_stats(doc_type: str):
    """经验库统计信息"""
    exp = load_experience(doc_type)

    rules = exp.get("rules", [])
    anti = exp.get("anti_patterns", [])
    patches = exp.get("prompt_patches", [])

    # 按类别统计
    categories = {}
    for r in rules:
        cat = r.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    # 按置信度统计
    confidences = {}
    for r in rules:
        conf = r.get("confidence", "unknown")
        confidences[conf] = confidences.get(conf, 0) + 1

    print(f"📊 经验库统计: {doc_type}")
    print(f"{'─' * 40}")
    print(f"  总规则数: {len(rules)}")
    print(f"  反模式数: {len(anti)}")
    print(f"  Prompt 补丁数: {len(patches)}")
    print()

    print(f"  按类别:")
    for cat, count in sorted(categories.items()):
        print(f"    {cat}: {count}")
    print()

    print(f"  按置信度:")
    for conf, count in sorted(confidences.items()):
        icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(conf, "⚪")
        print(f"    {icon} {conf}: {count}")


def action_optimize(doc_type: str):
    """AI 辅助优化经验库：合并重复、裁剪低质量、整理结构"""
    exp = load_experience(doc_type)
    config = load_config()

    rules = exp.get("rules", [])
    anti = exp.get("anti_patterns", [])
    patches = exp.get("prompt_patches", [])

    total = len(rules) + len(anti) + len(patches)
    print(f"🧹 开始优化经验库: {doc_type}")
    print(f"   当前: {len(rules)} 规则 + {len(anti)} 反模式 + {len(patches)} 补丁 = {total} 条")
    print()

    # 构建优化 prompt
    prompt = f"""你是一个经验库优化专家。请对以下文档生成经验库进行整理优化。

## 当前经验库

```json
{json.dumps(exp, ensure_ascii=False, indent=2)}
```

## 优化任务

请执行以下优化操作：

1. **合并重复**: 将含义相近或重叠的规则合并为一条更精确的规则
2. **裁剪低质量**: 删除过于笼统、缺乏操作性的规则
3. **提升清晰度**: 重写表述模糊的规则，使其更加具体可执行
4. **整理反模式**: 合并相似的反模式
5. **整理 prompt 补丁**: 合并可以合并的补丁，删除已被规则覆盖的补丁
6. **保持 id 不变**（对于保留的条目），新合并的条目使用新 id

## 输出要求

输出优化后的完整 experience.json 内容（JSON 格式）。
保持原有的 doc_type、last_updated 等元信息字段。
将 source 字段更新为 "optimized_by_ai"。

只输出 JSON，不要输出解释说明。"""

    print("🤖 调用 Gemini 优化中...")
    result = generate_text(prompt, config)

    # 解析结果
    try:
        result_clean = result.strip()
        if result_clean.startswith("```json"):
            result_clean = result_clean[7:]
        if result_clean.startswith("```"):
            result_clean = result_clean[3:]
        if result_clean.endswith("```"):
            result_clean = result_clean[:-3]
        result_clean = result_clean.strip()

        optimized = json.loads(result_clean)

        # 统计变化
        new_rules = optimized.get("rules", [])
        new_anti = optimized.get("anti_patterns", [])
        new_patches = optimized.get("prompt_patches", [])
        new_total = len(new_rules) + len(new_anti) + len(new_patches)

        print(f"\n📊 优化结果:")
        print(f"   规则: {len(rules)} → {len(new_rules)}")
        print(f"   反模式: {len(anti)} → {len(new_anti)}")
        print(f"   补丁: {len(patches)} → {len(new_patches)}")
        print(f"   总计: {total} → {new_total}")

        # 备份旧版本
        exp_path = get_experience_path(doc_type)
        backup_path = exp_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(exp, f, ensure_ascii=False, indent=2)
        print(f"\n   💾 旧版备份: {backup_path}")

        # 更新元信息
        optimized["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        optimized["experience_version"] = exp.get("experience_version", 0) + 1

        # 保存
        save_experience(doc_type, optimized)
        print(f"   ✅ 经验库已优化: {exp_path}")

    except json.JSONDecodeError as e:
        print(f"   ⚠️  Gemini 返回的内容无法解析为 JSON: {e}")
        print(f"   原始返回:")
        print(result[:500])


def main():
    parser = argparse.ArgumentParser(description="SCALE 经验库管理工具")
    parser.add_argument("--type", required=True, help="文档类型，如 scale_release")
    parser.add_argument("--action", required=True, choices=["show", "stats", "optimize"],
                        help="操作: show(查看), stats(统计), optimize(AI优化)")
    args = parser.parse_args()

    actions = {
        "show": action_show,
        "stats": action_stats,
        "optimize": action_optimize,
    }

    actions[args.action](args.type)


if __name__ == "__main__":
    main()


