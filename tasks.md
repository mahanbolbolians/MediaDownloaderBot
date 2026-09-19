# Execution Checklist: FFmpeg Activation, YouTube Resolution Fix & Spotify Audio Engine

- [x] **Phase 1: Self-Healing FFmpeg & Node.js Discovery Engine**
  - [x] Implement `ensure_ffmpeg()` with permissions repair (`chmod 0o755`), `/tmp/ffmpeg` linking, and Nix store scanning in `downloader/generic.py`.
  - [x] Add Node.js runtime discovery (`get_js_runtimes_config()`) to provide native EJS support to `yt-dlp`.
  - [x] Update `utils/media_tagger.py` to use active FFmpeg path.
  - [x] Configure `nixpacks.toml` with explicit PATH and package definitions.
- [x] **Phase 2: Multi-Tier Spotify Engine & Error Transparency**
  - [x] Implement multi-tier HTML parser (Twitter/OG tags, JSON-LD, title regex) with `oembed` fallback in `downloader/spotify.py`.
  - [x] Pass verified FFmpeg location and JS runtimes to Spotify `yt_dlp` instance.
  - [x] Add search fallback (with and without "audio") and defensive audio stream transcoding fallback.
- [x] **Phase 3: Bot Startup Verification & Status Diagnostics**
  - [x] Initialize `ensure_ffmpeg()` on bot startup in `bot.py`.
  - [x] Enrich `/status` command with FFmpeg binary path, Node.js status, and environment health.
- [x] **Phase 4: Unit Testing & Verification Gates**
  - [x] Write unit tests for Spotify HTML metadata extraction and FFmpeg initialization.
  - [x] Run full test suite with 100% pass rate (20/20 tests passed).
- [x] **Phase 5: Deployment & User Handoff**
  - [x] Push to GitHub `main` via proxy tunnel (`fd0e934`).
  - [x] Provide user verification instructions with `/status` command.
