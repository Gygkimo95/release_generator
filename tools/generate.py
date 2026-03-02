"""
文档生成脚本
用法：python tools/generate.py --type scale_release --version v2026.03

流程：
1. 读取模板、经验库、上期终版文档
2. 读取用户输入（input.md + screenshots/）
3. 组装 prompt 调用 Gemini
4. 保存生成结果为 initial.md
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent))
from gemini_client import load_config, generate, PROJECT_ROOT


def get_doc_type_dir(doc_type: str) -> Path:
    """获取文档类型目录"""
    return PROJECT_ROOT / "doc_types" / doc_type


def get_version_dir(doc_type: str, version: str) -> Path:
    """获取版本目录"""
    return get_doc_type_dir(doc_type) / "versions" / version


def load_template(doc_type: str) -> str:
    """加载文档模板"""
    template_path = get_doc_type_dir(doc_type) / "template.md"
    if not template_path.exists():
        raise FileNotFoundError(f"模板不存在: {template_path}")
    return template_path.read_text(encoding="utf-8")


def load_experience(doc_type: str, config: dict) -> str:
    """加载经验库，格式化为 prompt 可用的文本"""
    exp_path = get_doc_type_dir(doc_type) / "experience.json"
    if not exp_path.exists():
        return ""

    with open(exp_path, "r", encoding="utf-8") as f:
        exp = json.load(f)

    max_rules = config.get("generation", {}).get("max_experience_rules", 20)

    parts = []

    # 高置信度规则优先
    rules = sorted(exp.get("rules", []), key=lambda r: (
        0 if r.get("confidence") == "high" else 1,
        -r.get("times_applied", 0)
    ))[:max_rules]

    if rules:
        parts.append("## 历史经验规则（请严格遵循）")
        for r in rules:
            parts.append(f"- [{r['category']}] {r['rule']}")

    # 反模式
    anti = exp.get("anti_patterns", [])
    if anti:
        parts.append("\n## 需要避免的问题")
        for a in anti:
            parts.append(f"- ❌ {a['description']} → ✅ {a['solution']}")

    # Prompt 补丁
    patches = exp.get("prompt_patches", [])
    if patches:
        parts.append("\n## 额外撰写要求")
        for p in patches:
            parts.append(f"- {p['content']}")

    return "\n".join(parts)


def load_latest_final(doc_type: str) -> str:
    """加载最新终版文档"""
    latest_path = get_doc_type_dir(doc_type) / "latest_final.md"
    if latest_path.exists():
        return latest_path.read_text(encoding="utf-8")
    return ""


def load_user_input(version_dir: Path) -> str:
    """加载用户输入的功能描述"""
    input_path = version_dir / "input.md"
    if not input_path.exists():
        raise FileNotFoundError(
            f"请先创建用户输入文件: {input_path}\n"
            f"在其中描述本期新增功能和更新内容。"
        )
    return input_path.read_text(encoding="utf-8")


def find_screenshots(version_dir: Path) -> list[Path]:
    """查找截图文件"""
    screenshots_dir = version_dir / "screenshots"
    if not screenshots_dir.exists():
        return []

    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    images = []
    for f in sorted(screenshots_dir.iterdir()):
        if f.suffix.lower() in image_exts:
            images.append(f)
    return images


def assemble_prompt(template: str, experience: str, latest_final: str,
                    user_input: str, screenshots: list[Path]) -> str:
    """组装完整的生成 prompt"""
    parts = []

    # 1. 模板（角色 + 结构 + 规则）
    parts.append("=" * 60)
    parts.append("【文档生成模板与规则】")
    parts.append("=" * 60)
    parts.append(template)

    # 2. 经验
    if experience:
        parts.append("\n" + "=" * 60)
        parts.append("【历史经验（从过去的文档调整中积累）】")
        parts.append("=" * 60)
        parts.append(experience)

    # 3. 上期文档参考
    if latest_final:
        parts.append("\n" + "=" * 60)
        parts.append("【上一期终版文档（参考格式和风格）】")
        parts.append("=" * 60)
        parts.append(latest_final)

    # 4. 本期输入
    parts.append("\n" + "=" * 60)
    parts.append("【本期用户输入】")
    parts.append("=" * 60)
    parts.append(user_input)

    # 5. 截图说明
    if screenshots:
        parts.append(f"\n（附带了 {len(screenshots)} 张截图，请理解截图内容并在文档中合适位置引用）")

    # 6. 生成指令
    parts.append("\n" + "=" * 60)
    parts.append("【任务】")
    parts.append("=" * 60)
    parts.append(
        "请根据以上模板、经验规则、上期文档参考和本期用户输入，生成本期的 SCALE 发版文档。\n"
        "要求：\n"
        "1. 严格遵循模板中定义的章节结构\n"
        "2. 严格遵循历史经验中的所有规则\n"
        "3. 避免历史经验中列出的反模式\n"
        "4. 参考上期文档的格式和风格，但内容完全基于本期输入\n"
        "5. 如果附带了截图，在合适的位置以 markdown 图片语法引用\n"
        "6. 直接输出 markdown 文档内容，不要输出解释说明"
    )

    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="SCALE 文档生成工具")
    parser.add_argument("--type", required=True, help="文档类型，如 scale_release")
    parser.add_argument("--version", required=True, help="版本号，如 v2026.03")
    args = parser.parse_args()

    doc_type = args.type
    version = args.version

    print(f"📄 开始生成文档: {doc_type} / {version}")
    print(f"{'─' * 50}")

    # 加载配置
    config = load_config()

    # 确保版本目录存在
    version_dir = get_version_dir(doc_type, version)
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "screenshots").mkdir(exist_ok=True)

    # 1. 加载所有上下文
    print("📋 加载模板...")
    template = load_template(doc_type)

    print("🧠 加载经验库...")
    experience = load_experience(doc_type, config)
    if experience:
        rule_count = experience.count("- [")
        print(f"   已加载 {rule_count} 条经验规则")
    else:
        print("   （无经验记录）")

    print("📖 加载上期终版文档...")
    latest_final = load_latest_final(doc_type)
    if latest_final:
        print(f"   已加载（{len(latest_final)} 字符）")
    else:
        print("   （无历史文档）")

    print("📝 加载用户输入...")
    user_input = load_user_input(version_dir)
    print(f"   已加载 input.md（{len(user_input)} 字符）")

    print("🖼️  查找截图...")
    screenshots = find_screenshots(version_dir)
    if screenshots:
        print(f"   找到 {len(screenshots)} 张截图")
        for s in screenshots:
            print(f"   - {s.name}")
    else:
        print("   （无截图）")

    # 2. 组装 prompt
    print(f"\n{'─' * 50}")
    print("🔧 组装 prompt...")
    prompt = assemble_prompt(template, experience, latest_final, user_input, screenshots)
    print(f"   Prompt 总长度: {len(prompt)} 字符")

    # 3. 调用 Gemini 生成
    print("\n🤖 调用 Gemini 生成中...")
    image_paths = [str(s) for s in screenshots] if screenshots else None
    result = generate(prompt, image_paths, config)

    # 4. 清理结果（去掉可能的 markdown 代码块包裹）
    if result.startswith("```markdown"):
        result = result[len("```markdown"):].strip()
    if result.startswith("```"):
        result = result[3:].strip()
    if result.endswith("```"):
        result = result[:-3].strip()

    # 5. 保存结果
    initial_path = version_dir / "initial.md"
    initial_path.write_text(result, encoding="utf-8")

    print(f"\n{'─' * 50}")
    print(f"✅ 生成完成！")
    print(f"   📄 初版文档: {initial_path}")
    print(f"   📊 文档长度: {len(result)} 字符")
    print(f"\n💡 下一步操作：")
    print(f"   1. 在 Cursor 中打开 {initial_path} 审阅修改")
    print(f"   2. 修改完成后，将文件另存为（或复制为） final.md")
    print(f"   3. 运行 python tools/finalize.py --type {doc_type} --version {version}")


if __name__ == "__main__":
    main()


