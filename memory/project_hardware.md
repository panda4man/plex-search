---
name: project-hardware
description: Current GPU hardware and model configuration for plex-search deployment
metadata:
  type: project
---

Running on RTX 3060 (12GB VRAM). LLM model is qwen2.5:14b (~9GB), embed model is nomic-embed-text (~274MB). Total VRAM usage ~9.3GB — fits comfortably with 12GB.

**Why:** Upgraded from GTX 1660 Super (6GB). Extra headroom means OLLAMA_KEEP_ALIVE=-1 is safe — no VRAM pressure.

**How to apply:** Suggest qwen2.5:14b as default LLM model. KEEP_ALIVE=-1 is appropriate for this hardware.
