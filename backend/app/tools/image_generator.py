"""Image generator tool — create images via OpenAI DALL-E API."""

import logging
from pathlib import Path
from uuid import uuid4

from app.tools.base import BaseTool, ToolResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageGeneratorTool(BaseTool):
    name = "image_generator"
    description = (
        "Generate images from text descriptions using AI (DALL-E 3). "
        "The image is saved locally and the path is returned. "
        "Use for: creating logos, illustrations, diagrams, avatars, concept art."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Image description / generation prompt",
            },
            "size": {
                "type": "string",
                "enum": ["256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"],
                "description": "Image dimensions",
                "default": "1024x1024",
            },
            "style": {
                "type": "string",
                "enum": ["vivid", "natural"],
                "description": "DALL-E 3 style (vivid = dramatic, natural = realistic)",
                "default": "vivid",
            },
            "save_path": {
                "type": "string",
                "description": "Optional absolute path to save the image (defaults to uploads/generated/)",
                "default": None,
            },
        },
        "required": ["prompt"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        prompt = kwargs.get("prompt", "").strip()
        size = kwargs.get("size", "1024x1024")
        style = kwargs.get("style", "vivid")
        save_path = kwargs.get("save_path")

        if not prompt:
            return ToolResult(success=False, error="Prompt is required.")

        if not settings.openai_api_key:
            return ToolResult(
                success=False,
                error="OpenAI API key not configured. Set OPENAI_API_KEY in .env for image generation.",
            )

        # DALL-E 3 only supports 1024x1024, 1792x1024, 1024x1792
        dalle3_sizes = {"1024x1024", "1792x1024", "1024x1792"}
        model = "dall-e-3" if size in dalle3_sizes else "dall-e-2"

        try:
            import httpx  # noqa: PLC0415

            api_base = settings.openai_base_url or "https://api.openai.com/v1"

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{api_base}/images/generations",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "prompt": prompt,
                        "n": 1,
                        "size": size,
                        "style": style,
                        "response_format": "url",
                    },
                )

                if resp.status_code != 200:
                    detail = resp.json().get("error", {}).get("message", resp.text[:300])
                    return ToolResult(success=False, error=f"Image generation failed: {detail}")

                data = resp.json()
                image_url = data["data"][0]["url"]
                revised_prompt = data["data"][0].get("revised_prompt", prompt)

                # Download the image
                img_resp = await client.get(image_url)
                if img_resp.status_code != 200:
                    return ToolResult(success=False, error="Failed to download generated image.")
                image_bytes = img_resp.content

            # Save
            if save_path:
                dest = Path(save_path)
            else:
                gen_dir = Path(settings.upload_dir) / "generated"
                gen_dir.mkdir(parents=True, exist_ok=True)
                dest = gen_dir / f"{uuid4().hex}.png"

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(image_bytes)

            logger.info("Image generated: %s (%d bytes)", dest, len(image_bytes))

            return ToolResult(
                success=True,
                data={
                    "path": str(dest),
                    "filename": dest.name,
                    "size_bytes": len(image_bytes),
                    "prompt_used": revised_prompt,
                    "model": model,
                    "dimensions": size,
                },
            )

        except Exception as exc:
            logger.exception("Image generation failed: %s", exc)
            return ToolResult(success=False, error=f"Image generation failed: {exc}")
