# ADOFAI Linux Native Fix & Toolkit (完全体全套解决方案)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux%20%7C%20SteamDeck-orange.svg)]()
[![Game: ADOFAI](https://img.shields.io/badge/Game-A%20Dance%20of%20Fire%20and%20Ice-red.svg)]()

> **从底层注入到全套修复的完全体解决方案**  
> 一键解决《冰与火之舞》（A Dance of Fire and Ice, ADOFAI）在 Linux / Steam Deck 原生运行环境下的所有顽疾：着色器崩溃、模组管理器方块字乱码、滑动条无法拖动、以及 Together 联机模组反作弊拦截。
> Linux 无法注入 dll 安装 mod ？无妨！我们这里可以直接让 Linux 也能跑 Windows 里面 UMM 的 mod 
 
[中文文档](#中文文档) | [English Documentation](#english-documentation)

---

<a name="中文文档"></a>
## 中文说明

### 痛点背景与修复原理

在 Linux 原生环境运行 ADOFAI 时，玩家与模组开发者通常会遭遇以下四大痛点：

| 问题现象 | 底层根因 | 本项目解决方案 |
| :--- | :--- | :--- |
| **启动/进关卡瞬间闪退崩溃** | Unity 引擎调用 `Shader.WarmupAllShaders()` 触发 Linux Mesa/RADV/NVIDIA 显卡驱动段错误。 | Harmony 动态拦截，跳过有缺陷的预热函数。 |
| **UMM 界面中文字体全为方块（豆腐块）** | Unity IMGUI 在 Linux 下默认英文字体缺少中日韩（CJK）字形表。 | 自动识别系统安装的 CJK 字体并写入 UMM 配置。 |
| **窗口大小/缩放滑动条无法拖拽** | Unity IMGUI 原生 `SliderHandler` 存在 `scrollTroughSide != 0` 缺陷：滑块追上光标瞬间即强制清空独占焦点（`hotControl = 0`），导致只能单次点击跳转，无法连续拖动。 | 自研独立 Control ID 双向事件分发体系，实现全行程平滑连续拖动，并提供 `[-]`/`[+]` 步进与常用分辨率/缩放预设。 |
| **Together 模组提示禁止使用并锁死联机** | Together 联机模组在内存解密后，扫描 UMM 模组列表并校验内置白名单，第三方模组会被标记为违规。 | 运行时动态拦截解密后的 `Together.dll`，注入白名单并屏蔽 `CaptureDisallowedMods` 拦截函数。 |

---

### 快速使用

#### 方式零：deb 包（Debian / Ubuntu 系）

```bash
sudo apt install ./adofai-linux-fix_1.1.0_all.deb
```

安装后即可从应用菜单启动 **ADOFAI Mod Manager**，或使用命令行 `adofai-fix` / `adofai-modmgr`。包内含预编译模组与注入器（`Architecture: all`），构建产物在只读系统目录下会自动落到 `~/.local/share/adofai-linux-fix/dist`。

> 其他发行版：Arch 系（含 SteamOS）与所有发行版均可**源码直跑**（见方式一，零编译依赖即可用 GUI 管理器）。RPM / AUR / Flatpak 等打包欢迎直接提 PR（放进 `packaging/` 目录即可）—— 社区的手最适合干这个。

#### 方式一：一键自动修复（推荐）

直接克隆本仓库并执行交互式配置工具：

```bash
git clone https://github.com/HoshiGT/adofai-linux-fix.git
cd adofai-linux-fix
./install.sh
```

或者使用完全静默安装模式（适用于脚本或自动化部署）：

```bash
./install.sh --auto
```

#### 方式二：手动安装已编译模组

1. 前往 `dist/` 目录获取 `LinuxCrashFix-v1.0.0.zip`（或从 GitHub Releases 下载）；
2. 打开 Unity Mod Manager（UMM）窗口（默认快捷键 `Ctrl + F10`）；
3. 将压缩包直接拖入 UMM 的 **Mods** 标签页即可完成安装。

---

### 工具箱功能 (`adofai_fix.py`)

本套件内置了零第三方依赖的 Python 控制台应用程序：
- **`[1] 一键全自动修复`**：自动完成游戏路径检测、核心备份、模组部署、字体修正与白名单绕过。
- **`[2] 安装/更新模组`**：单独部署 `LinuxCrashFix.dll`。
- **`[3] 修复中文字体`**：列出并选择本机字体库中的合适中文字体写入 `Params.xml`。
- **`[4] 源码一键编译`**：调用本地 Mono 编译器重新生成 DLL。
- **`[5] 环境诊断检测`**：检查 UMM 注入状态、核心文件备份与驱动信息。
- **`[6] 打开图形界面`**：启动下方拖拽式模组管理器。

### 图形界面模组管理器 (`adofai_modmgr.py`)

基于 GTK4（系统自带 PyGObject，零 pip 依赖）的 UMM 全功能管理前端，三个标签页对应 UMM Windows 安装器风格：

```bash
./adofai_modmgr.py          # 打开图形界面
```

- **多语言**：界面支持中文 / English / 한국어，跟随系统 locale 自动选择，标题栏下拉即时切换并持久化（CLI 输出同步跟随）；
- **模组页**：多列列表（启用 / 名称 / 版本 / 作者 / 文件夹），拖入 Mod 的 `.zip`（或含 `Info.json` 的文件夹）即安装，支持根目录/嵌套两种布局；升级时自动替换旧版本并清理残留 DLL；一键开关（写入 UMM `Params.xml`）、卸载移入回收站；
- **日志页**：环境诊断（UMM 注入状态、`Params.xml`、游戏进程、UMM Log.txt 末尾）与全部操作的时间戳日志；
- **安装器页**：UMM 注入管理 —— **游戏目录选择**（手动指定 / **全局搜索**：常见路径 + Steam `libraryfolders.vdf` 全部库 + HOME/挂载点限深扫描；结果标注构建类型（Linux 原生 / Windows 版 / 双版本）并按原生优先排序，多结果弹窗任选，选择结果持久化）、UMM 版本 / 注入状态 / 原始备份一览，一键 **注入 UMM**（往核心程序集嵌入启动桩，自动备份）、**卸载补丁**、**恢复原文件**，全新机器可从 UMM zip 安装运行时。注入由 `src/UMMInjector.cs`（与官方安装器相同的 dnlib 手法）经 `mono` 完成，缺失时自动编译；
- 纯命令行接口：`--list` / `--install <zip>` / `--toggle <Id> on|off` / `--remove <文件夹名>` / `--umm status|inject|unpatch|restore`。

---

<a name="english-documentation"></a>
## English Documentation

### Overview

Running *A Dance of Fire and Ice* (ADOFAI) natively on Linux or Steam Deck often encounters platform-specific issues caused by Unity's IMGUI loop, shader warmup driver incompatibilities, and strict third-party mod validation.

This toolkit provides an all-in-one fix and injection suite:
1. **Shader Warmup GPU Crash Bypass**: Skips `Shader.WarmupAllShaders()` to prevent crashes on Vulkan / Mesa / RADV / NVIDIA drivers.
2. **Continuous Drag Sliders & DPI Scaling**: Completely rewrites the IMGUI slider control flow using canonical Control ID capture. Smoothly drag sliders with mouse lock, direct text input, fine-tuning buttons, and 1080p/2K/4K presets.
3. **Together (TUF) Multiplayer Whitelist Bypass**: Dynamically intercepts the decrypted `Together.dll` in memory, adds `LinuxCrashFix` to `AllowedMods`, clears `CapturedMods`, and suppresses `CaptureDisallowedMods()`.
4. **CJK Font Fix**: Auto-configures native Chinese/Japanese/Korean fallback fonts (DejaVu Sans / Noto Sans CJK / WenQuanYi) to prevent tofu blocks (`□□□`).

### Installation

#### Method 0: deb package (Debian / Ubuntu based)

```bash
sudo apt install ./adofai-linux-fix_1.1.0_all.deb
```

Launch **ADOFAI Mod Manager** from the app menu, or use the `adofai-fix` / `adofai-modmgr` commands. Build outputs fall back to `~/.local/share/adofai-linux-fix/dist` when installed read-only.

> Other distros: run from source (Method 1) — the GUI manager needs no compilation. PRs adding RPM / AUR / Flatpak packaging (under `packaging/`) are always welcome.

#### Method 1: All-in-One CLI Tool
```bash
git clone https://github.com/HoshiGT/adofai-linux-fix.git
cd adofai-linux-fix
./install.sh --auto
```

#### Method 2: Manual Installation via UMM
- Grab `dist/LinuxCrashFix-v1.0.0.zip` and drop it into the **Mods** tab in Unity Mod Manager (`Ctrl+F10`).

### Building from Source

Requires Mono C# compiler (`mcs`):
```bash
./scripts/build.sh
```

### GUI Mod Manager

A GTK4 (PyGObject, zero pip dependencies) full-featured UMM front-end styled after the UMM Windows installer, localized in **中文 / English / 한국어** (follows the system locale, switchable live from the header bar, persisted). Three tabs: **Mods** (multi-column list with enable toggles, drag-and-drop zip/folder install, trash-safe uninstall), **Log** (diagnostics + timestamped operation log) and **Installer** (game directory picker with **global search** — common paths, every Steam library from `libraryfolders.vdf`, and bounded HOME/mount-point scans; results labeled Linux-native / Windows / dual build; multiple hits present a chooser, and the choice persists — plus inject / unpatch / restore UMM into the game's core assembly with automatic `.original_` backup; runtime files can be installed from a UMM zip).

```bash
./adofai_modmgr.py
```

CLI equivalents: `--list`, `--install <zip>`, `--toggle <Id> on|off`, `--remove <folder>`, `--umm status|inject|unpatch|restore`. The injector (`src/UMMInjector.cs`, same dnlib technique as the official installer) is compiled by `scripts/build_injector.sh` and invoked via `mono`; it is rebuilt automatically when missing.

---

### Project Structure

```
adofai-linux-fix/
├── src/
│   ├── LinuxCrashFix.cs         # C# Harmony patches & IMGUI controls
│   └── UMMInjector.cs           # UMM assembly injector (dnlib, same as official installer)
├── dist/
│   ├── LinuxCrashFix/           # Pre-built mod folder
│   ├── LinuxCrashFix-v1.0.0.zip # UMM drag-and-drop archive
│   └── UMMInjector.exe          # Compiled injector (run with mono)
├── scripts/
│   ├── build.sh                 # Mono compilation script (mod)
│   └── build_injector.sh        # Mono compilation script (injector)
├── adofai_fix.py                # Zero-dependency Python CLI / TUI toolkit
├── adofai_modmgr.py             # GTK4 UMM mod manager (GUI + CLI)
├── packaging/deb/build_deb.sh   # Debian package builder
├── install.sh                   # Fast launcher script
├── LICENSE                      # MIT License
└── README.md                    # Bilingual documentation
```

---

### License

This project is licensed under the [MIT License](LICENSE).
Created with ❤️ for the Linux & Steam Deck rhythm gaming community.
