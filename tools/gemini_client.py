"""
Gemini API 客户端封装
支持纯文本和多模态（文本+图片）调用
"""

import os
import yaml
import google.generativeai as genai
from PIL import Image
from pathlib import Path


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def load_config() -> dict:
    """加载项目配置"""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_model(config: dict = None) -> genai.GenerativeModel:
    """获取配置好的 Gemini 模型实例"""
    if config is None:
        config = load_config()

    api_key = config["gemini"]["api_key"]
    model_name = config["gemini"]["model"]

    if not api_key:
        raise ValueError("请在 config.yaml 中配置 gemini.api_key")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    return model


def generate_text(prompt: str, config: dict = None) -> str:
    """纯文本生成"""
    model = get_model(config)
    response = model.generate_content(prompt)
    return response.text


def generate_with_images(prompt: str, image_paths: list[str | Path], config: dict = None) -> str:
    """多模态生成：文本 + 图片"""
    model = get_model(config)

    # 构建内容列表：prompt + 图片
    contents = [prompt]
    for img_path in image_paths:
        img_path = Path(img_path)
        if not img_path.exists():
            print(f"  ⚠️  图片不存在，跳过: {img_path}")
            continue
        img = Image.open(img_path)
        contents.append(img)
        print(f"  📎 已加载图片: {img_path.name}")

    response = model.generate_content(contents)
    return response.text


def generate(prompt: str, image_paths: list[str | Path] = None, config: dict = None) -> str:
    """统一生成接口：有图片走多模态，无图片走纯文本"""
    if image_paths and len(image_paths) > 0:
        return generate_with_images(prompt, image_paths, config)
    else:
        return generate_text(prompt, config)


